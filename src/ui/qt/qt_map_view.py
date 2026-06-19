from __future__ import annotations
import math
import numpy as np
from PyQt5.QtCore import Qt, QTimer, QSize, QPointF
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen, QPolygonF

_SIZE = 170
_RENDER_RANGE_M = 4.0
_UPDATE_MS = 150
_RECOMPUTE_EVERY = 2            # recompute walls every N ticks (~300 ms)

# ── point filtering ───────────────────────────────────────────────────────────
_MIN_RANGE_M      = 0.4         # ignore robot body / self-returns
_MAX_RANGE_M      = 8.0         # cap at effective indoor lidar range
_MIN_HEIGHT_M     = 0.20        # keep points ≥ 20 cm above floor (max-raycasting means
                                 # close floor voxels no longer shadow far walls)
_MAX_HEIGHT_M     = 2.00        # drop ceiling returns

# ── raycasting ───────────────────────────────────────────────────────────────
# ULIDAR_ARRAY is the robot's dense voxel map (~47k points).  Raycasting finds
# the closest wall-height voxel in each 1° bin, producing a sparse scan profile
# (≤360 pts) of the currently visible surface — without grid saturation.
_N_RAYS    = 360                # angular bins  (1° each)
_SEG_GAP_M = 0.55               # gap between consecutive ray hits → segment boundary

# ── wall quality gates ────────────────────────────────────────────────────────
_MIN_SEG_PTS    = 4             # minimum consecutive ray hits (≈ 4° angular span)
_RDP_EPSILON_M  = 0.28          # RDP chord-residual tolerance — tolerates noisy/outplaced dots
_MIN_WALL_LEN_M = 0.30          # discard only very short isolated returns

# ── endpoint merging ──────────────────────────────────────────────────────────
_CONNECT_GAP_M     = 1.40       # bridge occlusion gaps (chair legs, posts) on the same wall
_CONNECT_ANGLE_TOL = 0.25       # ≈ 14° — must be nearly collinear to merge

# ── person marker ─────────────────────────────────────────────────────────────
_CAMERA_FOV_DEG = 120.0         # assumed camera horizontal FOV (matches lidar_distance.py)


# ── RDP wall-segment fitting ──────────────────────────────────────────────────

def _rdp_segments(pts: np.ndarray, epsilon: float, min_len: float) -> list:
    """Ramer-Douglas-Peucker simplification of an ordered surface contour.

    Splits at the point with maximum perpendicular distance from the chord
    connecting the current endpoints.  This is the correct split criterion for
    wall segmentation: corners have large chord-residuals; flat walls do not.

    Returns a list of (x1, y1, x2, y2) segments each with length >= min_len.
    """
    n = len(pts)
    if n < 2:
        return []

    keep = np.zeros(n, dtype=bool)
    keep[0] = keep[-1] = True

    stack: list[tuple[int, int]] = [(0, n - 1)]
    while stack:
        i0, i1 = stack.pop()
        if i1 - i0 < 2:
            continue

        p0, p1 = pts[i0], pts[i1]
        vec = p1 - p0
        d_sq = float(vec @ vec)

        if d_sq < 1e-12:
            # Degenerate chord (both endpoints coincide): find the farthest interior pt.
            diffs = pts[i0:i1 + 1] - p0
            dists = np.hypot(diffs[:, 0], diffs[:, 1])
            i_local = int(np.argmax(dists[1:-1])) + 1
            if dists[i_local] > epsilon:
                i_abs = i0 + i_local
                keep[i_abs] = True
                stack.append((i0, i_abs))
                stack.append((i_abs, i1))
            continue

        # Perpendicular distances from all interior points to the chord.
        diffs = pts[i0:i1 + 1] - p0
        t     = (diffs @ vec) / d_sq
        perp  = diffs - np.outer(t, vec)
        dists = np.hypot(perp[:, 0], perp[:, 1])

        # Only consider interior points (skip the two endpoints).
        i_local = int(np.argmax(dists[1:-1])) + 1
        if dists[i_local] > epsilon:
            i_abs = i0 + i_local
            keep[i_abs] = True
            stack.append((i0, i_abs))
            stack.append((i_abs, i1))

    key_idx = np.where(keep)[0]
    segs: list = []
    for k in range(len(key_idx) - 1):
        p0 = pts[key_idx[k]]
        p1 = pts[key_idx[k + 1]]
        d  = math.hypot(float(p1[0] - p0[0]), float(p1[1] - p0[1]))
        if d >= min_len:
            segs.append((float(p0[0]), float(p0[1]), float(p1[0]), float(p1[1])))

    return segs


def _connect_endpoints(segs: list, gap_tol: float, angle_tol: float) -> list:
    """Iteratively merge segment endpoint pairs that are close and collinear."""
    changed = True
    while changed and len(segs) > 1:
        changed = False
        used = [False] * len(segs)
        result = []

        for i in range(len(segs)):
            if used[i]:
                continue
            s = segs[i]

            for j in range(i + 1, len(segs)):
                if used[j]:
                    continue
                t = segs[j]

                a1 = math.atan2(s[3] - s[1], s[2] - s[0]) % math.pi
                a2 = math.atan2(t[3] - t[1], t[2] - t[0]) % math.pi
                da = min(abs(a1 - a2), math.pi - abs(a1 - a2))
                if da > angle_tol:
                    continue

                eps_s = [(s[0], s[1]), (s[2], s[3])]
                eps_t = [(t[0], t[1]), (t[2], t[3])]
                if not any(math.hypot(e2[0] - e1[0], e2[1] - e1[1]) < gap_tol
                           for e1 in eps_s for e2 in eps_t):
                    continue

                all_eps = eps_s + eps_t
                max_d, p1, p2 = 0.0, all_eps[0], all_eps[-1]
                for ei in all_eps:
                    for ej in all_eps:
                        d = math.hypot(ej[0] - ei[0], ej[1] - ei[1])
                        if d > max_d:
                            max_d, p1, p2 = d, ei, ej

                s = (p1[0], p1[1], p2[0], p2[1])
                used[j] = True
                changed = True

            result.append(s)
        segs = result

    return segs


# ── widget ────────────────────────────────────────────────────────────────────

class QtMapView(QWidget):
    """Top-down 2D map built directly from the current lidar scan.

    No occupancy grid or accumulation.  Each wall-recompute cycle:
      1. Take the raw lidar point cloud (same source as the lidar mini-map).
      2. Filter by range [0.4, 8] m and height ≥ 10 cm above the floor.
      3. Project (x, y) into a robot-centred 0.15 m grid and mark cells.
      4. Morphological close (bridges 1-cell gaps on the same wall).
      5. 8-connected component labelling.
      6. Per component: elongation gate → PCA line fit → recursive split.
      7. Discard short segments → merge close collinear endpoints.

    Because there is no accumulated state, the map is always consistent with
    what the lidar currently sees and cannot get stuck in a bad state.
    """

    def __init__(self, robot, parent=None):
        super().__init__(parent)
        self.robot = robot
        self._pose: tuple | None = None
        self._latest_points = None          # raw points from last tick
        self._timer: QTimer | None = None
        self._wall_segments: list = []
        self._surf_pts: np.ndarray | None = None  # raycasted surface pts (debug)
        self._wall_tick: int = 0
        self._camera_view = None
        self._last_person_world: tuple | None = None
        self.setFixedSize(_SIZE, _SIZE)
        self.setAttribute(Qt.WA_TranslucentBackground)

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def set_camera_view(self, camera_view) -> None:
        """Attach a QtCameraView so the map can show the tracked person's position."""
        self._camera_view = camera_view

    def setup(self) -> None:
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_data)
        self._timer.start(_UPDATE_MS)

    def cleanup(self) -> None:
        if self._timer:
            self._timer.stop()
            self._timer = None
        self._pose = None
        self._latest_points = None
        self._wall_segments = []
        self._last_person_world = None

    def sizeHint(self) -> QSize:
        return QSize(_SIZE, _SIZE)

    # ── data update ───────────────────────────────────────────────────────────

    def _update_data(self) -> None:
        if not getattr(self.robot, "is_connected", False):
            if self._pose is not None:
                self._pose = None
                self._latest_points = None
                self._wall_segments = []
                self._last_person_world = None
                self.update()
            return

        self._pose           = self.robot.get_lidar_pose()
        self._latest_points  = self.robot.get_lidar_points()
        self._update_person_pos()

        self._wall_tick += 1
        if self._wall_tick >= _RECOMPUTE_EVERY:
            self._wall_tick = 0
            self._wall_segments = self._compute_walls()

        self.update()

    # ── person position ───────────────────────────────────────────────────────

    def _update_person_pos(self) -> None:
        """Convert camera bounding-box + lidar distance → world (x, y)."""
        if self._camera_view is None or self._pose is None:
            return
        people    = self._camera_view.get_tracked_people()
        distances = self._camera_view.get_person_distances()
        if not people or not distances:
            return
        frame_w, _ = self._camera_view.get_frame_size()
        if frame_w <= 0:
            return

        rx, ry, yaw = self._pose
        half_fov = math.radians(_CAMERA_FOV_DEG / 2.0)

        for person in people:
            dist = distances.get(person.id)
            if dist is None or dist <= 0:
                continue
            x_c, _, w_c, _ = person.rect
            norm_x  = ((x_c + w_c / 2.0) / frame_w) * 2.0 - 1.0
            bearing = -norm_x * half_fov          # positive = left of forward
            lf = dist * math.cos(bearing)
            ll = dist * math.sin(bearing)
            self._last_person_world = (
                rx + lf * math.cos(yaw) - ll * math.sin(yaw),
                ry + lf * math.sin(yaw) + ll * math.cos(yaw),
            )
            return

    # ── wall extraction ───────────────────────────────────────────────────────

    def _compute_walls(self) -> list:
        try:
            segs, surf = self._compute_walls_inner()
            self._surf_pts = surf
            return segs
        except Exception as e:
            print(f"[MapView] _compute_walls exception: {e}")
            import traceback; traceback.print_exc()
            return []

    _EMPTY = ([], np.empty((0, 2)))

    def _compute_walls_inner(self):
        if self._pose is None or self._latest_points is None:
            return self._EMPTY

        pts = np.asarray(self._latest_points)
        if pts.ndim != 2 or pts.shape[0] == 0 or pts.shape[1] < 3:
            return self._EMPTY

        rx, ry, _ = self._pose

        # 1. Range filter.
        d = np.hypot(pts[:, 0] - rx, pts[:, 1] - ry)
        pts = pts[(d >= _MIN_RANGE_M) & (d <= _MAX_RANGE_M)]
        if len(pts) == 0:
            return self._EMPTY

        # 2. Height filter — keep torso-height returns only.
        #    Floor voxels sit at z ≈ floor_z.  With a global 5th-percentile
        #    estimate and _MIN_HEIGHT_M=0.10, floor voxels at h≈0.22 m slipped
        #    through and shadowed real walls in the raycasting step.
        #    Estimate the floor from close-range points (≤2 m) where floor
        #    returns are most reliable, then require h ≥ 45 cm.
        close_mask = d[d <= _MAX_RANGE_M] <= 2.0   # recompute on filtered pts
        d2 = np.hypot(pts[:, 0] - rx, pts[:, 1] - ry)
        cm = d2 <= 2.0
        if cm.sum() >= 20:
            floor_z = np.percentile(pts[cm, 2], 2.0)
        else:
            floor_z = np.percentile(pts[:, 2], 5.0)
        h = pts[:, 2] - floor_z
        pts = pts[(h >= _MIN_HEIGHT_M) & (h <= _MAX_HEIGHT_M)]
        if len(pts) == 0:
            return self._EMPTY

        # 3. Raycast: convert the dense accumulated voxel map into a sparse
        #    scan profile by finding the CLOSEST wall-height point in each
        #    angular bin.  This gives ≤ N_RAYS surface points that represent
        #    exactly what the lidar currently sees — without grid saturation.
        angles  = np.arctan2(pts[:, 1] - ry, pts[:, 0] - rx)   # (−π, π]
        dists   = np.hypot(pts[:, 0] - rx, pts[:, 1] - ry)

        bin_idx = ((angles + math.pi) / (2 * math.pi) * _N_RAYS).astype(int) % _N_RAYS

        # Use MAXIMUM distance per angular bin.
        # In a closed room, the farthest wall-height voxel in each direction IS
        # the room wall.  Close furniture/objects are between the robot and the
        # wall but do NOT shadow it with maximum raycasting.  Minimum raycasting
        # (the previous approach) stopped at the first piece of furniture,
        # producing a tight orange dot cluster that never reached the far walls.
        far_dist = np.zeros(_N_RAYS)
        np.maximum.at(far_dist, bin_idx, dists)

        valid = far_dist >= _MIN_RANGE_M
        if not valid.any():
            return self._EMPTY

        # Reconstruct surface points, ordered by angle (bin index).
        valid_bins  = np.where(valid)[0]
        bin_centres = -math.pi + (valid_bins + 0.5) * (2 * math.pi / _N_RAYS)
        surf_x = rx + far_dist[valid_bins] * np.cos(bin_centres)
        surf_y = ry + far_dist[valid_bins] * np.sin(bin_centres)
        surf   = np.column_stack([surf_x, surf_y])   # ≤ N_RAYS ordered pts

        # 4. Gap-segment: split into groups where consecutive ray hits are
        #    more than _SEG_GAP_M apart (object boundary or occlusion edge).
        if len(surf) < 2:
            return self._EMPTY

        between = np.hypot(np.diff(surf[:, 0]), np.diff(surf[:, 1]))
        splits  = np.where(between > _SEG_GAP_M)[0] + 1
        clusters = np.split(surf, splits)

        # Also try wrapping: if the first and last clusters are angularly
        # adjacent and close, merge them into one wall.
        if len(clusters) >= 2:
            gap_wrap = math.hypot(clusters[-1][-1, 0] - clusters[0][0, 0],
                                   clusters[-1][-1, 1] - clusters[0][0, 1])
            if gap_wrap <= _SEG_GAP_M:
                clusters[0] = np.vstack([clusters[-1], clusters[0]])
                clusters = clusters[:-1]

        # 5. RDP line fit per cluster → discard short segments.
        #    RDP splits at true corner points (max chord-residual), so the
        #    resulting segments follow the orange dot outline exactly.
        segs: list = []
        for cluster in clusters:
            if len(cluster) < _MIN_SEG_PTS:
                continue
            segs.extend(_rdp_segments(cluster, _RDP_EPSILON_M, _MIN_WALL_LEN_M))

        # 6. Join nearby collinear endpoint pairs.
        return _connect_endpoints(segs, _CONNECT_GAP_M, _CONNECT_ANGLE_TOL), surf

    # ── paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 120))
        painter.drawRoundedRect(rect, 8, 8)

        if self._pose is None:
            painter.setPen(QColor(220, 220, 220, 150))
            painter.drawText(rect, Qt.AlignCenter, "MAP")
            painter.end()
            return

        cx    = rect.width()  / 2.0
        cy    = rect.height() / 2.0
        scale = (min(rect.width(), rect.height()) / 2.0 - 6) / _RENDER_RANGE_M

        self._draw_range_rings(painter, cx, cy, scale)
        self._draw_surf_pts(painter, cx, cy, scale)   # debug: orange scan surface
        self._draw_walls(painter, cx, cy, scale)
        self._draw_person(painter, cx, cy, scale)
        self._draw_robot_marker(painter, cx, cy)
        painter.end()

    # ── drawing helpers ───────────────────────────────────────────────────────

    def _draw_surf_pts(self, painter: QPainter, cx, cy, scale) -> None:
        """Draw raycasted surface points as orange dots (diagnostic layer).

        These should align with the bright dots in the lidar mini-map.
        If they don't, there is a coordinate-frame mismatch to investigate.
        """
        if self._surf_pts is None or len(self._surf_pts) == 0 or self._pose is None:
            return
        rx, ry, yaw = self._pose
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 160, 0, 200))
        for wx, wy in self._surf_pts:
            dx, dy = wx - rx, wy - ry
            if math.hypot(dx, dy) > _RENDER_RANGE_M * 1.05:
                continue
            fwd  =  dx * cos_y + dy * sin_y
            left = -dx * sin_y + dy * cos_y
            painter.drawEllipse(QPointF(cx - left * scale, cy - fwd * scale), 1.5, 1.5)

    def _draw_range_rings(self, painter: QPainter, cx, cy, scale) -> None:
        pen = QPen(QColor(255, 255, 255, 40))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        step = max(1.0, math.floor(_RENDER_RANGE_M))
        r    = step
        while r <= _RENDER_RANGE_M:
            painter.drawEllipse(QPointF(cx, cy), r * scale, r * scale)
            r += step

    def _draw_walls(self, painter: QPainter, cx, cy, scale) -> None:
        if not self._wall_segments or self._pose is None:
            return

        rx, ry, yaw = self._pose
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)
        half_w = 0.14  # wall half-width in metres for rendering

        def to_screen(wx: float, wy: float):
            dx, dy = wx - rx, wy - ry
            fwd  =  dx * cos_y + dy * sin_y
            left = -dx * sin_y + dy * cos_y
            return cx - left * scale, cy - fwd * scale

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 220))

        for wx1, wy1, wx2, wy2 in self._wall_segments:
            dx, dy = wx2 - wx1, wy2 - wy1
            length = math.hypot(dx, dy)
            if length < 1e-6:
                continue
            ux, uy = dx / length, dy / length
            px, py = -uy, ux

            painter.drawPolygon(QPolygonF([
                QPointF(*to_screen(wx1 + px * half_w, wy1 + py * half_w)),
                QPointF(*to_screen(wx2 + px * half_w, wy2 + py * half_w)),
                QPointF(*to_screen(wx2 - px * half_w, wy2 - py * half_w)),
                QPointF(*to_screen(wx1 - px * half_w, wy1 - py * half_w)),
            ]))

    def _draw_person(self, painter: QPainter, cx, cy, scale) -> None:
        """Blue dot at the last known world position of the tracked person."""
        if self._last_person_world is None or self._pose is None:
            return

        rx, ry, yaw = self._pose
        wx, wy = self._last_person_world
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)

        dx, dy = wx - rx, wy - ry
        if math.hypot(dx, dy) > _RENDER_RANGE_M * 1.05:
            return

        fwd  =  dx * cos_y + dy * sin_y
        left = -dx * sin_y + dy * cos_y
        sx = cx - left * scale
        sy = cy - fwd * scale

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(80, 150, 255, 230))
        painter.drawEllipse(QPointF(sx, sy), 5.0, 5.0)

        pen = QPen(QColor(255, 255, 255, 200))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(sx, sy), 5.0, 5.0)

    def _draw_robot_marker(self, painter: QPainter, cx, cy) -> None:
        size = 6.0
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 230))
        painter.drawPolygon(QPolygonF([
            QPointF(cx,              cy - size),
            QPointF(cx - size * 0.7, cy + size * 0.7),
            QPointF(cx + size * 0.7, cy + size * 0.7),
        ]))

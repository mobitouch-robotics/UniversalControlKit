from __future__ import annotations
import math
import numpy as np
from PyQt5.QtCore import Qt, QTimer, QSize, QPointF
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen, QPolygonF, QBrush

_SIZE = 170
_RENDER_RANGE_M = 4.0
_UPDATE_MS = 150
_RECOMPUTE_EVERY = 2            # recompute walls every N ticks (~300 ms)

# ── point filtering ───────────────────────────────────────────────────────────
_MIN_RANGE_M      = 0.4         # ignore robot body / self-returns
_MAX_RANGE_M      = 8.0         # cap at effective indoor lidar range

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

# ── floor estimation / directional wall update ────────────────────────────────
_FLOOR_RADIUS_M      = 0.8              # only use points this close to robot for floor-Z estimate
_FRONT_ARC_RAD       = math.pi * 2.0 / 3.0   # ±120°: forward arc recomputed each tick

# ── point classification (wall vs obstacle) ───────────────────────────────────
_LIDAR_HEIGHT_M      = 0.45     # estimated Go2 lidar sensor height above floor
_WALL_ABOVE_LIDAR_M  = 0.20     # z >= lidar_z + this → wall class
_OBSTACLE_BAND_M     = 0.20     # |z - lidar_z| <= this → obstacle class
_OBSTACLE_GRID_M     = 0.25     # grid cell size for deduplicating obstacle positions
_OBS_WALL_MERGE_M    = 0.40     # obstacle point within this XY distance of a wall point → treat as wall

# ── debug / testing ───────────────────────────────────────────────────────────
_CLICK_TO_SET_PERSON = True     # clicking the map sets the person's world position


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
        self._nav_route: list = []              # world (x, y) waypoints from navigator
        self._obstacle_positions: list = []     # world (x, y) of low-obstacle points
        self._person_click_cb = None            # callback(wx, wy) for click-to-set-person
        self.setFixedSize(_SIZE, _SIZE)
        self.setAttribute(Qt.WA_TranslucentBackground)

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def set_camera_view(self, camera_view) -> None:
        """Attach a QtCameraView so the map can show the tracked person's position."""
        self._camera_view = camera_view

    def set_person_click_callback(self, cb) -> None:
        """Register a callback(wx, wy) called when the user clicks the map."""
        self._person_click_cb = cb

    def get_obstacle_positions(self) -> list:
        """Return world (x, y) positions of current low obstacles."""
        return list(self._obstacle_positions)

    def set_nav_route(self, route: list) -> None:
        """Update the navigation route drawn on the map.

        ``route`` is a list of world (x, y) waypoints as supplied by
        PersonTrackingController.  Pass an empty list to clear the route.
        """
        self._nav_route = list(route)

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
        self._nav_route = []
        self._obstacle_positions = []

    def sizeHint(self) -> QSize:
        return QSize(_SIZE, _SIZE)

    # ── input ─────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if not _CLICK_TO_SET_PERSON or self._person_click_cb is None or self._pose is None:
            super().mousePressEvent(event)
            return
        rect  = self.rect()
        cx    = rect.width()  / 2.0
        cy    = rect.height() / 2.0
        scale = (min(rect.width(), rect.height()) / 2.0 - 6) / _RENDER_RANGE_M
        # Screen → robot-relative (fwd up, left positive)
        sx, sy = float(event.x()), float(event.y())
        left   = (cx - sx) / scale
        fwd    = (cy - sy) / scale
        # Robot-relative → world
        rx, ry, yaw = self._pose
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)
        dx = fwd * cos_y - left * sin_y
        dy = fwd * sin_y + left * cos_y
        self._person_click_cb(rx + dx, ry + dy)

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
            segs, surf, obs = self._compute_walls_inner()
            self._surf_pts = surf
            self._obstacle_positions = obs
            return segs
        except Exception as e:
            print(f"[MapView] _compute_walls exception: {e}")
            import traceback; traceback.print_exc()
            return []

    _EMPTY = ([], np.empty((0, 2)), [])

    def _get_rear_segments(self, rx: float, ry: float, yaw: float) -> list:
        """Return segments from the previous frame that lie in the rear arc."""
        rear = []
        for seg in self._wall_segments:
            mx   = (seg[0] + seg[2]) / 2.0
            my   = (seg[1] + seg[3]) / 2.0
            b    = math.atan2(my - ry, mx - rx)
            diff = abs(math.atan2(math.sin(b - yaw), math.cos(b - yaw)))
            if diff > _FRONT_ARC_RAD:
                rear.append(seg)
        return rear

    def _compute_walls_inner(self):
        if self._pose is None or self._latest_points is None:
            return self._EMPTY

        pts = np.asarray(self._latest_points)
        if pts.ndim != 2 or pts.shape[0] == 0 or pts.shape[1] < 3:
            return self._EMPTY

        rx, ry, yaw = self._pose

        # 1. Range filter — keep d in sync for subsequent masks.
        d = np.hypot(pts[:, 0] - rx, pts[:, 1] - ry)
        mask = (d >= _MIN_RANGE_M) & (d <= _MAX_RANGE_M)
        pts  = pts[mask]
        d    = d[mask]
        if len(pts) == 0:
            return self._EMPTY

        # 2. Local floor Z from very close points only (adapts to floor changes).
        local_mask = d <= _FLOOR_RADIUS_M
        if local_mask.sum() >= 5:
            floor_z = np.percentile(pts[local_mask, 2], 5.0)
        else:
            floor_z = np.percentile(pts[:, 2], 5.0)

        lidar_z = floor_z + _LIDAR_HEIGHT_M

        # 3. Classify points by height relative to the lidar sensor:
        #    • wall pts    : z ≥ lidar_z + _WALL_ABOVE_LIDAR_M  (tall structures)
        #    • obstacle pts: |z − lidar_z| ≤ _OBSTACLE_BAND_M  (low clutter)
        #    • below: floor returns — discarded
        wall_mask = pts[:, 2] >= lidar_z + _WALL_ABOVE_LIDAR_M
        obs_mask  = (np.abs(pts[:, 2] - lidar_z) <= _OBSTACLE_BAND_M) & ~wall_mask

        wall_pts = pts[wall_mask]
        obs_pts  = pts[obs_mask]

        # 4. Restrict both classes to the forward arc.
        def _front(p: np.ndarray) -> np.ndarray:
            if len(p) == 0:
                return p
            b  = np.arctan2(p[:, 1] - ry, p[:, 0] - rx)
            rb = np.arctan2(np.sin(b - yaw), np.cos(b - yaw))
            return p[np.abs(rb) <= _FRONT_ARC_RAD]

        wall_pts_f = _front(wall_pts)
        obs_pts_f  = _front(obs_pts)

        # 5a. Drop obstacle points that have a wall-class point within
        #     _OBS_WALL_MERGE_M horizontally — they are just the lower portion
        #     of a wall, not a separate low obstacle.
        if len(obs_pts_f) > 0 and len(wall_pts_f) > 0:
            obs_xy  = obs_pts_f[:, :2]
            wall_xy = wall_pts_f[:, :2]
            diff    = obs_xy[:, np.newaxis, :] - wall_xy[np.newaxis, :, :]
            min_d   = np.hypot(diff[:, :, 0], diff[:, :, 1]).min(axis=1)
            obs_pts_f = obs_pts_f[min_d > _OBS_WALL_MERGE_M]

        # 5b. Obstacle positions: grid-deduplicate to _OBSTACLE_GRID_M cells.
        if len(obs_pts_f) > 0:
            gx = np.floor(obs_pts_f[:, 0] / _OBSTACLE_GRID_M).astype(int)
            gy = np.floor(obs_pts_f[:, 1] / _OBSTACLE_GRID_M).astype(int)
            _, idx = np.unique(np.stack([gx, gy], axis=1), axis=0, return_index=True)
            obs_positions = [
                (float((gx[i] + 0.5) * _OBSTACLE_GRID_M),
                 float((gy[i] + 0.5) * _OBSTACLE_GRID_M))
                for i in idx
            ]
        else:
            obs_positions = []

        rear_segs = self._get_rear_segments(rx, ry, yaw)

        if len(wall_pts_f) == 0:
            return rear_segs, np.empty((0, 2)), obs_positions

        # 6. Raycast: MAXIMUM distance per bin on wall-class front-arc points.
        angles   = np.arctan2(wall_pts_f[:, 1] - ry, wall_pts_f[:, 0] - rx)
        dists    = np.hypot(wall_pts_f[:, 0] - rx, wall_pts_f[:, 1] - ry)
        bin_idx  = ((angles + math.pi) / (2 * math.pi) * _N_RAYS).astype(int) % _N_RAYS
        far_dist = np.zeros(_N_RAYS)
        np.maximum.at(far_dist, bin_idx, dists)

        valid = far_dist >= _MIN_RANGE_M
        if not valid.any():
            return rear_segs, np.empty((0, 2)), obs_positions

        valid_bins  = np.where(valid)[0]
        bin_centres = -math.pi + (valid_bins + 0.5) * (2 * math.pi / _N_RAYS)
        surf_x = rx + far_dist[valid_bins] * np.cos(bin_centres)
        surf_y = ry + far_dist[valid_bins] * np.sin(bin_centres)
        surf   = np.column_stack([surf_x, surf_y])

        # 7. Gap-segment.
        if len(surf) < 2:
            return rear_segs, np.empty((0, 2)), obs_positions

        between  = np.hypot(np.diff(surf[:, 0]), np.diff(surf[:, 1]))
        splits   = np.where(between > _SEG_GAP_M)[0] + 1
        clusters = np.split(surf, splits)

        if len(clusters) >= 2:
            gap_wrap = math.hypot(clusters[-1][-1, 0] - clusters[0][0, 0],
                                   clusters[-1][-1, 1] - clusters[0][0, 1])
            if gap_wrap <= _SEG_GAP_M:
                clusters[0] = np.vstack([clusters[-1], clusters[0]])
                clusters = clusters[:-1]

        # 8. RDP fit per cluster.
        segs: list = []
        for cluster in clusters:
            if len(cluster) < _MIN_SEG_PTS:
                continue
            segs.extend(_rdp_segments(cluster, _RDP_EPSILON_M, _MIN_WALL_LEN_M))

        front_segs = _connect_endpoints(segs, _CONNECT_GAP_M, _CONNECT_ANGLE_TOL)

        # 9. Merge fresh front segments with preserved rear segments.
        return front_segs + rear_segs, surf, obs_positions

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
        self._draw_surf_pts(painter, cx, cy, scale)
        self._draw_obstacles(painter, cx, cy, scale)
        self._draw_walls(painter, cx, cy, scale)
        self._draw_nav_route(painter, cx, cy, scale)
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

    def _draw_obstacles(self, painter: QPainter, cx, cy, scale) -> None:
        if not self._obstacle_positions or self._pose is None:
            return
        rx, ry, yaw = self._pose
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 60, 60, 220))
        for wx, wy in self._obstacle_positions:
            dx, dy = wx - rx, wy - ry
            if math.hypot(dx, dy) > _RENDER_RANGE_M * 1.05:
                continue
            fwd  =  dx * cos_y + dy * sin_y
            left = -dx * sin_y + dy * cos_y
            painter.drawEllipse(QPointF(cx - left * scale, cy - fwd * scale), 2.5, 2.5)

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

    def _draw_nav_route(self, painter: QPainter, cx, cy, scale) -> None:
        """Draw the active navigation route as a cyan line with waypoint dots."""
        if not self._nav_route or self._pose is None:
            return

        rx, ry, yaw = self._pose
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)

        def to_screen(wx: float, wy: float) -> QPointF:
            dx, dy = wx - rx, wy - ry
            fwd  =  dx * cos_y + dy * sin_y
            left = -dx * sin_y + dy * cos_y
            return QPointF(cx - left * scale, cy - fwd * scale)

        # Line: robot → first waypoint → … → last waypoint.
        points = [QPointF(cx, cy)] + [to_screen(wx, wy) for wx, wy in self._nav_route]

        line_pen = QPen(QColor(0, 220, 200, 200))
        line_pen.setWidthF(1.8)
        line_pen.setCapStyle(Qt.RoundCap)
        line_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(line_pen)
        painter.setBrush(Qt.NoBrush)
        for i in range(len(points) - 1):
            painter.drawLine(points[i], points[i + 1])

        # Dots at each waypoint (skip the robot-centre pseudo-point).
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 255, 220, 230))
        for pt in points[1:]:
            painter.drawEllipse(pt, 3.0, 3.0)

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

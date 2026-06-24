from __future__ import annotations
import json
import math
import os
import time
import numpy as np
from collections import deque
from PyQt5.QtCore import Qt, QTimer, QSize, QPointF
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen, QPolygonF

_RECORD_DIR = os.path.expanduser("~/Downloads/UniversalControlKit")

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

# ── person marker ─────────────────────────────────────────────────────────────
_CAMERA_FOV_DEG = 120.0         # assumed camera horizontal FOV (matches lidar_distance.py)

# ── floor estimation / directional wall update ────────────────────────────────
_FLOOR_RADIUS_M      = 0.8              # only use points this close to robot for floor-Z estimate
_FRONT_ARC_RAD       = math.pi * 2.0 / 3.0   # ±120°: forward arc recomputed each tick

# ── point classification (wall vs obstacle) ───────────────────────────────────
_LIDAR_HEIGHT_M      = 0.45     # estimated Go2 lidar sensor height above floor
_WALL_ABOVE_LIDAR_M  = 0.55     # z >= lidar_z + this → wall class (~1 m above floor); keeps chairs out
_OBSTACLE_BAND_M     = 0.20     # |z - lidar_z| <= this → obstacle class
_OBSTACLE_GRID_M     = 0.25     # grid cell size for deduplicating obstacle positions
_OBS_WALL_MERGE_M    = 0.40     # obstacle point within this XY distance of a wall point → treat as wall

# ── noise filtering (raycast) ────────────────────────────────────────────────
_MIN_BIN_VOTES = 2              # raw wall points needed per 1° bin to trust the hit

# ── persistent wall memory ───────────────────────────────────────────────────
# A world-frame occupancy grid accumulates wall confidence over time.
# Cells increment on each hit; they only decay when the robot can actively see
# clear space in front of them (confirmed-empty raycast in the front arc).
# This keeps walls in memory even when the robot is too close to see their tops.
_WALL_CELL_M   = 0.20           # world-frame wall grid resolution (m)
_WALL_EXTENT_M = 15.0           # covers ±15 m from world origin
_WALL_N        = int(2 * _WALL_EXTENT_M / _WALL_CELL_M)   # 150
_WALL_HIT      = 2.0            # confidence added per observed hit
_WALL_MISS     = 0.35           # confidence removed per confirmed-clear cell on a ray
_WALL_MAX      = 12.0           # saturation (6 hits); needs ~34 clear ticks to erase ≈ 10 s
_WALL_THRESH   = 5.0            # minimum confidence to display / use for planning (3 hits)

# ── temporal scan buffer ──────────────────────────────────────────────────────
# A cell must appear in _SCAN_MIN_CONFIRM of the last _SCAN_BUFFER_SIZE scans
# before it stamps a hit into the confidence grid.  Transient returns (moving
# objects, single-frame reflections) appear in only 1-2 scans and are silently
# ignored, while stationary walls accumulate consistent hits and confirm quickly.
_SCAN_BUFFER_SIZE = 5           # rolling window length  (5 × 300 ms ≈ 1.5 s)
_SCAN_MIN_CONFIRM = 4           # minimum scans a cell must appear in to confirm

# ── floor-Z smoothing ─────────────────────────────────────────────────────────
# The per-frame 5th-percentile floor estimate can drift ±7 cm as the robot
# moves over slightly uneven terrain.  An EMA with α=0.25 smooths this to
# ±1–2 cm, stabilising all height-based classification thresholds.
_FLOOR_Z_ALPHA = 0.25           # EMA coefficient (higher = faster adaptation)

# ── obstacle temporal buffer ──────────────────────────────────────────────────
# Obstacle cells must appear in _OBS_MIN_CONFIRM of the last _OBS_BUFFER_SIZE
# scans to be passed to the route planner.  This filters single-scan reflections
# and transient hits (people walking through) while confirming real furniture
# within ≈ 0.6 s.
_OBS_BUFFER_SIZE = 3            # rolling window (3 × 300 ms ≈ 0.9 s)
_OBS_MIN_CONFIRM = 2            # min scans a cell must appear in

# ── exploration tracking ─────────────────────────────────────────────────────
_EXPLORE_EXTENT_M = 20.0
_EXPLORE_CELL_M   = 0.25
_EXPLORE_N        = int(2 * _EXPLORE_EXTENT_M / _EXPLORE_CELL_M)  # 160

# ── debug / testing ───────────────────────────────────────────────────────────
_CLICK_TO_SET_PERSON = True     # clicking the map sets the person's world position


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
        self._surf_pts: np.ndarray | None = None  # persistent wall surface points
        self._wall_grid: np.ndarray = np.zeros((_WALL_N, _WALL_N), dtype=np.float32)
        self._wall_tick: int = 0
        self._camera_view = None
        self._last_person_world: tuple | None = None
        self._nav_route: list = []              # world (x, y) waypoints from navigator
        self._obstacle_positions: list = []     # world (x, y) of low-obstacle points
        self._explored: np.ndarray = np.zeros((_EXPLORE_N, _EXPLORE_N), dtype=bool)
        self._scan_buffer: deque = deque(maxlen=_SCAN_BUFFER_SIZE)
        self._obs_buffer:  deque = deque(maxlen=_OBS_BUFFER_SIZE)
        self._floor_z_ema: float | None = None
        self._recording: bool = False
        self._record_file = None
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

    def get_wall_points(self) -> list:
        """Return world (x, y) of current raycasted wall surface points."""
        if self._surf_pts is None or len(self._surf_pts) == 0:
            return []
        return [(float(x), float(y)) for x, y in self._surf_pts]

    def get_explored_grid(self):
        """Return (explored_bool_grid, extent_m, cell_m) for route planning."""
        return self._explored, _EXPLORE_EXTENT_M, _EXPLORE_CELL_M

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
        self._last_person_world = None
        self._nav_route = []
        self._obstacle_positions = []
        self._surf_pts = None
        self._wall_grid = np.zeros((_WALL_N, _WALL_N), dtype=np.float32)
        self._explored = np.zeros((_EXPLORE_N, _EXPLORE_N), dtype=bool)
        self._scan_buffer.clear()
        self._obs_buffer.clear()
        self._floor_z_ema = None
        self.stop_recording()

    def sizeHint(self) -> QSize:
        return QSize(_SIZE, _SIZE)

    # ── recording ─────────────────────────────────────────────────────────────

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start_recording(self, path: str | None = None) -> str:
        """Open a JSONL recording file and start writing lidar frames.

        Each line is one frame:
            {"t": <unix_time>, "pose": [rx, ry, yaw], "pts": [[x,y,z], ...]}

        Returns the file path that was opened.
        """
        self.stop_recording()
        if path is None:
            ts   = time.strftime("%Y%m%d_%H%M%S")
            path = os.path.join(_RECORD_DIR, f"lidar_{ts}.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._record_file = open(path, "w")
        self._recording   = True
        print(f"[MapView] Recording → {path}")
        return path

    def stop_recording(self) -> None:
        """Flush and close the current recording file."""
        self._recording = False
        if self._record_file is not None:
            try:
                self._record_file.close()
            except Exception:
                pass
            self._record_file = None
            print("[MapView] Recording stopped")

    def _write_record_frame(self) -> None:
        if self._pose is None or self._latest_points is None:
            return
        try:
            pts = self._latest_points
            if hasattr(pts, "tolist"):
                pts = pts.tolist()
            ei, ej = np.where(self._explored)
            frame = {
                "t":        round(time.time(), 3),
                "pose":     [round(v, 4) for v in self._pose],
                "pts":      [[round(p[0], 3), round(p[1], 3), round(p[2], 3)] for p in pts],
                "explored": [ei.tolist(), ej.tolist()],
                "explore_meta": {
                    "extent_m": _EXPLORE_EXTENT_M,
                    "cell_m":   _EXPLORE_CELL_M,
                    "n":        _EXPLORE_N,
                },
            }
            self._record_file.write(json.dumps(frame, separators=(",", ":")) + "\n")
            self._record_file.flush()
        except Exception as e:
            print(f"[MapView] recording write error: {e}")

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
                self._last_person_world = None
                self.update()
            return

        self._pose           = self.robot.get_lidar_pose()
        self._latest_points  = self.robot.get_lidar_points()
        self._update_person_pos()

        self._wall_tick += 1
        if self._wall_tick >= _RECOMPUTE_EVERY:
            self._wall_tick = 0
            self._compute_walls()

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

    def _update_explored(self, rx: float, ry: float, surf: np.ndarray) -> None:
        """Mark cells along rays from robot to each surface point as explored."""
        n    = _EXPLORE_N
        ext  = _EXPLORE_EXTENT_M
        cell = _EXPLORE_CELL_M
        ri = int(np.clip((ry + ext) / cell, 0, n - 1))
        rj = int(np.clip((rx + ext) / cell, 0, n - 1))
        self._explored[ri, rj] = True
        if surf is None or len(surf) == 0:
            return
        n_steps = int(_MAX_RANGE_M / cell) + 2
        ts = np.linspace(0.0, 1.0, n_steps)
        xs = rx + ts[:, np.newaxis] * (surf[:, 0][np.newaxis, :] - rx)
        ys = ry + ts[:, np.newaxis] * (surf[:, 1][np.newaxis, :] - ry)
        eis = np.clip(((ys + ext) / cell).astype(int), 0, n - 1)
        ejs = np.clip(((xs + ext) / cell).astype(int), 0, n - 1)
        self._explored[eis.ravel(), ejs.ravel()] = True

    def _compute_walls(self) -> None:
        if self._recording and self._record_file is not None:
            self._write_record_frame()
        try:
            surf, obs = self._compute_walls_inner()
            self._surf_pts = surf
            self._obstacle_positions = obs
        except Exception as e:
            print(f"[MapView] _compute_walls exception: {e}")
            import traceback; traceback.print_exc()

    def _update_wall_grid(
        self,
        rx: float, ry: float,
        fresh_surf: np.ndarray,
        near_dist: np.ndarray,
        valid: np.ndarray,
    ) -> None:
        """Update the persistent wall confidence grid.

        Hits are applied at the raycasted surface positions (fresh_surf).
        Misses are applied only to cells that lie between the robot and a
        confirmed surface hit — cells that are definitely clear space.
        Cells NOT covered by any front-arc ray are never decayed, so walls
        stay in memory even when the robot can no longer see their tops.
        """
        ext  = _WALL_EXTENT_M
        cell = _WALL_CELL_M
        n    = _WALL_N

        # Hit: add confidence at each confirmed surface position.
        if len(fresh_surf) > 0:
            gi_h = np.clip(((fresh_surf[:, 1] + ext) / cell).astype(int), 0, n - 1)
            gj_h = np.clip(((fresh_surf[:, 0] + ext) / cell).astype(int), 0, n - 1)
            np.add.at(self._wall_grid, (gi_h, gj_h), _WALL_HIT)

        # Miss: for every valid front-arc bin, decay cells from the robot to
        # just in front of the detected surface (confirmed clear space).
        valid_bins = np.where(valid)[0]
        if len(valid_bins) > 0:
            n_steps  = int(_MAX_RANGE_M / cell) + 1
            ts       = (np.arange(n_steps) + 0.5) * cell        # (n_steps,)

            bin_angles = -math.pi + (valid_bins + 0.5) * (2 * math.pi / _N_RAYS)
            dists_f    = near_dist[valid_bins]                   # (n_valid,)

            cos_a = np.cos(bin_angles)[:, np.newaxis]            # (n_valid, 1)
            sin_a = np.sin(bin_angles)[:, np.newaxis]
            ts_2d = ts[np.newaxis, :]                            # (1, n_steps)

            wxs = rx + cos_a * ts_2d                             # (n_valid, n_steps)
            wys = ry + sin_a * ts_2d

            # Only decay cells clearly in front of the surface.
            miss_mask = ts_2d < (dists_f[:, np.newaxis] - cell)

            gis = np.clip(((wys + ext) / cell).astype(int), 0, n - 1)
            gjs = np.clip(((wxs + ext) / cell).astype(int), 0, n - 1)

            np.add.at(self._wall_grid, (gis[miss_mask], gjs[miss_mask]), -_WALL_MISS)

        np.clip(self._wall_grid, 0.0, _WALL_MAX, out=self._wall_grid)

    def _compute_walls_inner(self):
        _EMPTY = np.empty((0, 2)), []
        if self._pose is None or self._latest_points is None:
            return _EMPTY

        pts = np.asarray(self._latest_points)
        if pts.ndim != 2 or pts.shape[0] == 0 or pts.shape[1] < 3:
            return _EMPTY

        rx, ry, yaw = self._pose

        # 1. Range filter — keep d in sync for subsequent masks.
        d = np.hypot(pts[:, 0] - rx, pts[:, 1] - ry)
        mask = (d >= _MIN_RANGE_M) & (d <= _MAX_RANGE_M)
        pts  = pts[mask]
        d    = d[mask]
        if len(pts) == 0:
            return _EMPTY

        # 2. Local floor Z from very close points only (adapts to floor changes).
        local_mask = d <= _FLOOR_RADIUS_M
        if local_mask.sum() >= 5:
            raw_floor_z = float(np.percentile(pts[local_mask, 2], 5.0))
        else:
            raw_floor_z = float(np.percentile(pts[:, 2], 5.0))

        # Smooth with EMA to suppress per-frame drift in the height estimate.
        if self._floor_z_ema is None:
            self._floor_z_ema = raw_floor_z
        else:
            self._floor_z_ema = _FLOOR_Z_ALPHA * raw_floor_z + (1.0 - _FLOOR_Z_ALPHA) * self._floor_z_ema
        floor_z = self._floor_z_ema

        lidar_z = floor_z + _LIDAR_HEIGHT_M

        # 3. Classify points by height relative to the lidar sensor:
        #    • wall pts    : z ≥ lidar_z + _WALL_ABOVE_LIDAR_M  (tall structures)
        #    • obstacle pts: |z − lidar_z| ≤ _OBSTACLE_BAND_M  (low clutter)
        #    • floor returns: discarded
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
        #     _OBS_WALL_MERGE_M horizontally — lower portion of a wall, not
        #     a separate low obstacle.
        if len(obs_pts_f) > 0 and len(wall_pts_f) > 0:
            obs_xy  = obs_pts_f[:, :2]
            wall_xy = wall_pts_f[:, :2]
            diff    = obs_xy[:, np.newaxis, :] - wall_xy[np.newaxis, :, :]
            min_d   = np.hypot(diff[:, :, 0], diff[:, :, 1]).min(axis=1)
            obs_pts_f = obs_pts_f[min_d > _OBS_WALL_MERGE_M]

        # 5b. Obstacle positions: grid-deduplicate to _OBSTACLE_GRID_M cells,
        #     then apply temporal consistency (same cell in ≥ _OBS_MIN_CONFIRM
        #     recent scans) to filter transient reflections and moving objects.
        if len(obs_pts_f) > 0:
            gx = np.floor(obs_pts_f[:, 0] / _OBSTACLE_GRID_M).astype(int)
            gy = np.floor(obs_pts_f[:, 1] / _OBSTACLE_GRID_M).astype(int)
            cur_obs_cells: set = set(zip(gx.tolist(), gy.tolist()))
        else:
            cur_obs_cells = set()

        self._obs_buffer.append(cur_obs_cells)

        if cur_obs_cells and len(self._obs_buffer) >= _OBS_MIN_CONFIRM:
            confirmed_obs = {
                c for c in cur_obs_cells
                if sum(1 for s in self._obs_buffer if c in s) >= _OBS_MIN_CONFIRM
            }
            obs_positions = [
                (float((cx + 0.5) * _OBSTACLE_GRID_M), float((cy + 0.5) * _OBSTACLE_GRID_M))
                for cx, cy in confirmed_obs
            ]
        else:
            obs_positions = []

        # 6. Noise-filtered raycast: MINIMUM distance per 1° bin, require at
        #    least _MIN_BIN_VOTES raw wall points per bin, and discard isolated
        #    single-bin detections that have no valid neighbour within ±1°.
        if len(wall_pts_f) == 0:
            self._scan_buffer.append(set())
            return self._surf_from_grid(rx, ry), obs_positions

        angles    = np.arctan2(wall_pts_f[:, 1] - ry, wall_pts_f[:, 0] - rx)
        dists     = np.hypot(wall_pts_f[:, 0] - rx, wall_pts_f[:, 1] - ry)
        bin_idx   = ((angles + math.pi) / (2 * math.pi) * _N_RAYS).astype(int) % _N_RAYS
        near_dist = np.full(_N_RAYS, np.inf)
        bin_votes = np.zeros(_N_RAYS, dtype=np.int32)
        np.minimum.at(near_dist, bin_idx, dists)
        np.add.at(bin_votes, bin_idx, 1)

        valid = (
            (near_dist >= _MIN_RANGE_M) &
            (near_dist < _MAX_RANGE_M) &
            (bin_votes >= _MIN_BIN_VOTES)
        )
        # Remove detections that aren't part of a run of ≥ 3 consecutive valid bins.
        # A pair (2 bins) has only 2 valid in its ±2 window; a triple has 3.
        # This eliminates narrow spurious returns (single reflections, isolated chair-back edges)
        # while keeping actual wall surfaces which span many degrees.
        _vi = valid.astype(np.int32)
        _span5 = (np.roll(_vi, -2) + np.roll(_vi, -1) + _vi
                  + np.roll(_vi, 1) + np.roll(_vi, 2))
        valid &= (_span5 >= 3)

        # Fresh surface positions for this tick (used for hit stamping and exploration).
        if valid.any():
            vb  = np.where(valid)[0]
            bc  = -math.pi + (vb + 0.5) * (2 * math.pi / _N_RAYS)
            fresh_surf = np.column_stack([
                rx + near_dist[vb] * np.cos(bc),
                ry + near_dist[vb] * np.sin(bc),
            ])
        else:
            fresh_surf = np.empty((0, 2))

        # Update exploration tracking with the raw per-tick surface (before filtering).
        self._update_explored(rx, ry, fresh_surf)

        # ── temporal consistency filter ───────────────────────────────────────
        # Convert this scan's hits to wall-grid cell indices and push into the
        # rolling buffer.  A cell must appear in at least _SCAN_MIN_CONFIRM of
        # the last _SCAN_BUFFER_SIZE scans before it stamps a confidence hit.
        # This rejects single-frame reflections and moving-object returns while
        # confirming stationary walls within a few hundred milliseconds.
        if len(fresh_surf) > 0:
            gi_cur = np.clip(
                ((fresh_surf[:, 1] + _WALL_EXTENT_M) / _WALL_CELL_M).astype(int),
                0, _WALL_N - 1,
            )
            gj_cur = np.clip(
                ((fresh_surf[:, 0] + _WALL_EXTENT_M) / _WALL_CELL_M).astype(int),
                0, _WALL_N - 1,
            )
            cur_cells: set = set(zip(gi_cur.tolist(), gj_cur.tolist()))
        else:
            cur_cells = set()

        self._scan_buffer.append(cur_cells)

        # Build confirmed surface from cells seen in >= _SCAN_MIN_CONFIRM scans.
        if cur_cells and len(self._scan_buffer) >= _SCAN_MIN_CONFIRM:
            confirmed = {
                c for c in cur_cells
                if sum(1 for s in self._scan_buffer if c in s) >= _SCAN_MIN_CONFIRM
            }
            if confirmed:
                conf_gi = np.fromiter((c[0] for c in confirmed), dtype=np.int32)
                conf_gj = np.fromiter((c[1] for c in confirmed), dtype=np.int32)
                conf_surf = np.column_stack([
                    (conf_gj + 0.5) * _WALL_CELL_M - _WALL_EXTENT_M,
                    (conf_gi + 0.5) * _WALL_CELL_M - _WALL_EXTENT_M,
                ])
            else:
                conf_surf = np.empty((0, 2))
        else:
            conf_surf = np.empty((0, 2))

        # Update persistent wall confidence grid with confirmed hits only.
        # Miss raycast (decay of clear cells) runs unconditionally on raw scan data.
        self._update_wall_grid(rx, ry, conf_surf, near_dist, valid)

        # Derive display/navigation surface from the persistent grid.
        return self._surf_from_grid(rx, ry), obs_positions

    def _surf_from_grid(self, rx: float, ry: float) -> np.ndarray:
        """Return world (x, y) of all wall-grid cells above the confidence threshold."""
        ext  = _WALL_EXTENT_M
        cell = _WALL_CELL_M
        gi, gj = np.where(self._wall_grid >= _WALL_THRESH)
        if len(gi) == 0:
            return np.empty((0, 2))
        wx = (gj + 0.5) * cell - ext
        wy = (gi + 0.5) * cell - ext
        mask = np.hypot(wx - rx, wy - ry) <= _MAX_RANGE_M
        if not mask.any():
            return np.empty((0, 2))
        return np.column_stack([wx[mask], wy[mask]])

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
        self._draw_explored(painter, cx, cy, scale)
        self._draw_surf_pts(painter, cx, cy, scale)
        self._draw_obstacles(painter, cx, cy, scale)
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

    def _draw_explored(self, painter: QPainter, cx, cy, scale) -> None:
        if self._pose is None:
            return
        rx, ry, yaw = self._pose
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)
        n    = _EXPLORE_N
        ext  = _EXPLORE_EXTENT_M
        cell = _EXPLORE_CELL_M
        pix  = max(2, int(cell * scale))
        rng  = _RENDER_RANGE_M + cell
        i0 = max(0, int((ry - rng + ext) / cell))
        i1 = min(n, int((ry + rng + ext) / cell) + 2)
        j0 = max(0, int((rx - rng + ext) / cell))
        j1 = min(n, int((rx + rng + ext) / cell) + 2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(30, 110, 65, 50))
        for gi in range(i0, i1):
            for gj in range(j0, j1):
                if not self._explored[gi, gj]:
                    continue
                wx = (gj + 0.5) * cell - ext
                wy = (gi + 0.5) * cell - ext
                dx, dy = wx - rx, wy - ry
                if math.hypot(dx, dy) > rng:
                    continue
                fwd  =  dx * cos_y + dy * sin_y
                left = -dx * sin_y + dy * cos_y
                sx = cx - left * scale
                sy = cy - fwd  * scale
                painter.drawRect(int(sx - pix / 2), int(sy - pix / 2), pix, pix)

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

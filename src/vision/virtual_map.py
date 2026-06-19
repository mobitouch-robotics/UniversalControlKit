from __future__ import annotations
import threading
import numpy as np

# Map covers ±MAP_EXTENT_M from world origin in both X and Y.
MAP_EXTENT_M = 10.0
CELL_SIZE_M = 0.15
GRID_N = int(2 * MAP_EXTENT_M / CELL_SIZE_M)  # cells per axis (~133)

# Each lidar hit increments the cell; each update cycle decays all cells
# within DECAY_RANGE_M by MISS_DECAY.  Cells above WALL_THRESHOLD are
# considered occupied (walls / obstacles). MAX_CELL_VALUE caps accumulation
# so stale walls fade in ~3 s of no hits at 150 ms/update.
HIT_INCREMENT = 4
MISS_DECAY = 1
WALL_THRESHOLD = 5
MAX_CELL_VALUE = 20

# Only cells within this radius of the robot's current position are eligible
# for decay. Areas the robot cannot currently reach with its lidar (too far
# away, around a corner, in a different room) are left unchanged so the map
# stays persistent for previously explored space.
DECAY_RANGE_M = 8.0

# Point filtering — mirrors lidar_distance.py thresholds.
MIN_RANGE_M = 0.4           # ignore robot body returns
MAX_SCAN_RANGE_M = 8.0      # ignore points beyond effective lidar range.
                             # The Go2 sends its full onboard voxel map via
                             # ULIDAR_ARRAY (accumulated across sessions).
                             # Capping at scan range ensures only fresh
                             # observations build our map, not historical data.
FLOOR_PERCENTILE = 5.0
MIN_HEIGHT_ABOVE_FLOOR_M = 0.25
MAX_HEIGHT_ABOVE_FLOOR_M = 2.2


class VirtualMap:
    """World-frame occupancy grid built from lidar point clouds.

    Cells accumulate hit counts when lidar points land in them (360° lidar,
    full scan range) and slowly decay between updates — but only within the
    robot's forward-facing FOV cone.  This means:

    • Walls in front of the robot are actively verified and updated.
    • Walls behind or to the side persist unchanged until the robot turns
      toward them, giving a stable persistent map of explored space.

    Thread-safe: update() runs on a background poll timer; get_snapshot()
    is called from the Qt paint thread.
    """

    cell_size_m: float = CELL_SIZE_M
    map_extent_m: float = MAP_EXTENT_M
    grid_n: int = GRID_N
    wall_threshold: int = WALL_THRESHOLD
    max_cell_value: int = MAX_CELL_VALUE

    def __init__(self) -> None:
        self._grid = np.zeros((GRID_N, GRID_N), dtype=np.int16)
        self._lock = threading.Lock()
        self._pose: tuple | None = None

    # ------------------------------------------------------------------ #

    def update(self, lidar_points, lidar_pose) -> None:
        """Incorporate a new lidar scan into the map."""
        if lidar_points is None or lidar_pose is None:
            return
        pts = np.asarray(lidar_points)
        if pts.ndim != 2 or pts.shape[0] == 0 or pts.shape[1] < 3:
            return

        rx, ry, _ = lidar_pose

        # Strip floor and ceiling returns.
        floor_z = np.percentile(pts[:, 2], FLOOR_PERCENTILE)
        h = pts[:, 2] - floor_z
        pts = pts[(h >= MIN_HEIGHT_ABOVE_FLOOR_M) & (h <= MAX_HEIGHT_ABOVE_FLOOR_M)]
        if pts.shape[0] == 0:
            return

        # Strip robot body returns and points beyond effective scan range.
        dist = np.hypot(pts[:, 0] - rx, pts[:, 1] - ry)
        pts = pts[(dist >= MIN_RANGE_M) & (dist <= MAX_SCAN_RANGE_M)]
        if pts.shape[0] == 0:
            return

        # World XY → grid cell indices (full 360° hits).
        gx = ((pts[:, 0] + MAP_EXTENT_M) / CELL_SIZE_M).astype(int)
        gy = ((pts[:, 1] + MAP_EXTENT_M) / CELL_SIZE_M).astype(int)
        ok = (gx >= 0) & (gx < GRID_N) & (gy >= 0) & (gy < GRID_N)
        gx, gy = gx[ok], gy[ok]

        # Bounding box of cells within DECAY_RANGE_M of the robot.
        rgx = int((rx + MAP_EXTENT_M) / CELL_SIZE_M)
        rgy = int((ry + MAP_EXTENT_M) / CELL_SIZE_M)
        half = int(DECAY_RANGE_M / CELL_SIZE_M) + 1
        dx0 = max(0, rgx - half);  dx1 = min(GRID_N, rgx + half + 1)
        dy0 = max(0, rgy - half);  dy1 = min(GRID_N, rgy + half + 1)

        with self._lock:
            sub = self._grid[dy0:dy1, dx0:dx1]
            np.subtract(sub, MISS_DECAY, out=sub)
            np.clip(sub, 0, MAX_CELL_VALUE, out=sub)
            np.add.at(self._grid, (gy, gx), HIT_INCREMENT)
            np.clip(self._grid, 0, MAX_CELL_VALUE, out=self._grid)
            self._pose = lidar_pose

    def get_snapshot(self) -> tuple[np.ndarray, tuple | None]:
        """Return (grid_copy, pose) for rendering. Safe to call from any thread."""
        with self._lock:
            return self._grid.copy(), self._pose

from __future__ import annotations
import heapq
import logging
import math

import numpy as np
from PyQt5.QtCore import QTimer

from ..protocols import MovementControllerProtocol

logger = logging.getLogger(__name__)


def _angle_diff(a: float, b: float) -> float:
    """Signed difference a - b, normalized to [-pi, pi]."""
    return math.atan2(math.sin(a - b), math.cos(a - b))


# ── tracking (person visible and close) ───────────────────────────────────────
_POLL_MS            = 100
_ROTATE_SPEED_MIN   = 0.15
_ROTATE_SPEED_MAX   = 0.6
_ROTATE_DEADZONE    = 0.15      # fraction of half-frame; person is "centered"
_OFFSET_SMOOTHING   = 0.3
_MOVE_SPEED         = 0.3
_MIN_DISTANCE_M     = 1.0
_ALLOW_BACKING_UP   = False

# ── path navigation (person farther than trigger distance) ────────────────────
_NAV_TRIGGER_M      = 2.0       # start navigating when person is this far
_NAV_APPROACH_M     = 1.6       # stop navigating when this close to person
_NAV_GRID_CELL_M    = 0.25      # path-planning grid resolution in metres
_NAV_GRID_HALF_M    = 8.0       # grid covers ±8 m from robot
_NAV_ROBOT_RADIUS_M = 0.45      # robot radius for obstacle inflation
_NAV_FWD_SPEED      = 0.40      # forward speed while navigating
_NAV_ROT_SPEED_MAX  = 1.0       # max yaw speed while navigating
_NAV_ROT_DEADZONE   = 0.15      # rad — don't rotate if heading error is this small
_NAV_ROT_ALIGN      = 0.35      # rad — stop moving forward until heading is within this
_NAV_ARRIVE_M       = 0.50      # consider waypoint reached when within this distance
_NAV_PERSON_MOVE_M  = 0.60      # update goal endpoint if person moved this far
_NAV_PREFER_CLEAR_M = 1.00      # try to stay at least this far from walls
_NAV_WALL_PENALTY   = 6.0       # cost multiplier at zero clearance vs open space
_CAMERA_FOV_DEG     = 120.0


# ── path-planning helpers ─────────────────────────────────────────────────────

def _distance_transform(obstacle: np.ndarray, cell_m: float) -> np.ndarray:
    """Multi-source Dijkstra distance transform.

    Returns a float32 array where each cell holds the Euclidean distance (in
    metres) to the nearest obstacle cell.  Obstacle cells themselves are 0.
    """
    n = obstacle.shape[0]
    dist = np.full((n, n), np.inf, dtype=np.float32)

    _SQRT2 = math.sqrt(2)
    dirs = [
        (-1, -1, _SQRT2), (0, -1, 1.0), (1, -1, _SQRT2),
        (-1,  0, 1.0),                   (1,  0, 1.0),
        (-1,  1, _SQRT2), (0,  1, 1.0), (1,  1, _SQRT2),
    ]

    heap: list = []
    for i in range(n):
        for j in range(n):
            if obstacle[i, j]:
                dist[i, j] = 0.0
                heapq.heappush(heap, (0.0, i, j))

    while heap:
        d, ci, cj = heapq.heappop(heap)
        if d > dist[ci, cj]:
            continue
        for di, dj, step in dirs:
            ni, nj = ci + di, cj + dj
            if not (0 <= ni < n and 0 <= nj < n):
                continue
            nd = d + step * cell_m
            if nd < dist[ni, nj]:
                dist[ni, nj] = nd
                heapq.heappush(heap, (nd, ni, nj))

    return dist


def _plan_route(
    start: tuple[float, float],
    goal: tuple[float, float],
    walls: list,
    obstacles: list | None = None,
) -> list[tuple[float, float]]:
    """Return a list of world (x, y) waypoints from start to goal.

    Uses A* on a robot-centred cost grid where cells near walls are more
    expensive to traverse.  The robot is steered away from walls naturally:
    paths through open space cost less than paths hugging walls.  The
    returned list does not include ``start`` itself.
    """
    n_cells = int(2 * _NAV_GRID_HALF_M / _NAV_GRID_CELL_M)
    ox = start[0] - _NAV_GRID_HALF_M
    oy = start[1] - _NAV_GRID_HALF_M
    c  = _NAV_GRID_CELL_M

    # ── 1. Boolean obstacle grid (inflated by robot radius) ───────────────────
    grid = np.zeros((n_cells, n_cells), dtype=bool)
    infl = int(math.ceil(_NAV_ROBOT_RADIUS_M / c))

    def _stamp(wx: float, wy: float) -> None:
        gi = int((wy - oy) / c)
        gj = int((wx - ox) / c)
        for di in range(-infl, infl + 1):
            for dj in range(-infl, infl + 1):
                if math.hypot(di * c, dj * c) <= _NAV_ROBOT_RADIUS_M:
                    ni, nj = gi + di, gj + dj
                    if 0 <= ni < n_cells and 0 <= nj < n_cells:
                        grid[ni, nj] = True

    for x1, y1, x2, y2 in walls:
        seg_len = math.hypot(x2 - x1, y2 - y1)
        if seg_len < 1e-6:
            continue
        n_samp = max(2, int(seg_len / (c * 0.5)))
        for k in range(n_samp + 1):
            t = k / n_samp
            _stamp(x1 + t * (x2 - x1), y1 + t * (y2 - y1))

    for ox_pt, oy_pt in (obstacles or []):
        _stamp(ox_pt, oy_pt)

    def w2g(wx: float, wy: float) -> tuple[int, int]:
        gi = max(0, min(n_cells - 1, int((wy - oy) / c)))
        gj = max(0, min(n_cells - 1, int((wx - ox) / c)))
        return gi, gj

    def g2w(gi: int, gj: int) -> tuple[float, float]:
        return ox + gj * c + c * 0.5, oy + gi * c + c * 0.5

    sg = w2g(start[0], start[1])
    gg = w2g(goal[0],  goal[1])

    # Ensure start/goal cells are passable even if inside the inflated region.
    grid[sg[0], sg[1]] = False
    grid[gg[0], gg[1]] = False

    # ── 2. Distance transform → cost grid ────────────────────────────────────
    # Each free cell gets a travel-cost multiplier that increases as it
    # approaches a wall.  Cells ≥ _NAV_PREFER_CLEAR_M away cost 1.0 (no
    # penalty).  Cells closer cost up to _NAV_WALL_PENALTY× more.
    dist_field = _distance_transform(grid, c)

    t_field = np.clip(dist_field / _NAV_PREFER_CLEAR_M, 0.0, 1.0)
    cost_grid = np.where(
        grid,
        np.inf,
        1.0 + (_NAV_WALL_PENALTY - 1.0) * (1.0 - t_field),
    ).astype(np.float32)

    # ── 3. A* with weighted cost grid ─────────────────────────────────────────
    path_cells = _astar(cost_grid, sg, gg, n_cells)
    if path_cells is None:
        return [goal]

    waypoints = [g2w(gi, gj) for gi, gj in path_cells]
    return _simplify_path(waypoints, walls)


def _astar(
    cost_grid: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    n: int,
) -> list[tuple[int, int]] | None:
    """8-connected A* on a float cost grid (inf = obstacle).

    Move cost = Euclidean step distance × average cell cost of the two
    endpoints, so paths through open space (cost 1.0) are preferred over
    paths close to walls (cost up to _NAV_WALL_PENALTY).

    Returns a list of (row, col) cells from start (exclusive) to goal
    (inclusive), or None if no path exists.
    """
    if start == goal:
        return []

    def h(node: tuple[int, int]) -> float:
        return math.hypot(node[0] - goal[0], node[1] - goal[1])

    _SQRT2 = math.sqrt(2)
    dirs = [
        (-1, -1, _SQRT2), (0, -1, 1.0), (1, -1, _SQRT2),
        (-1,  0, 1.0),                   (1,  0, 1.0),
        (-1,  1, _SQRT2), (0,  1, 1.0), (1,  1, _SQRT2),
    ]

    g_score: dict[tuple, float] = {start: 0.0}
    came_from: dict[tuple, tuple | None] = {start: None}
    open_heap: list = [(h(start), 0.0, start)]
    closed: set = set()

    while open_heap:
        _, g, current = heapq.heappop(open_heap)
        if current in closed:
            continue
        closed.add(current)

        if current == goal:
            path = []
            node: tuple | None = goal
            while node is not None and node != start:
                path.append(node)
                node = came_from[node]
            path.reverse()
            return path

        ci, cj = current
        c_cost = float(cost_grid[ci, cj])
        for di, dj, step in dirs:
            ni, nj = ci + di, cj + dj
            if not (0 <= ni < n and 0 <= nj < n):
                continue
            n_cost = float(cost_grid[ni, nj])
            if math.isinf(n_cost):
                continue
            neighbour = (ni, nj)
            if neighbour in closed:
                continue
            # Weight the step by the average cell cost of from/to.
            ng = g + step * (c_cost + n_cost) * 0.5
            if ng < g_score.get(neighbour, float("inf")):
                g_score[neighbour] = ng
                came_from[neighbour] = current
                heapq.heappush(open_heap, (ng + h(neighbour), ng, neighbour))

    return None


def _pt_seg_dist(p: tuple, a: tuple, b: tuple) -> float:
    """Distance from point p to the nearest point on segment a–b."""
    abx, aby = b[0] - a[0], b[1] - a[1]
    d2 = abx * abx + aby * aby
    if d2 < 1e-12:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * abx + (p[1] - a[1]) * aby) / d2))
    return math.hypot(p[0] - a[0] - t * abx, p[1] - a[1] - t * aby)


def _seg_seg_min_dist(p1: tuple, p2: tuple, q1: tuple, q2: tuple) -> float:
    """Minimum distance between segments p1–p2 and q1–q2."""
    # Check proper intersection first (distance = 0).
    def _cross2(ax, ay, bx, by):
        return ax * by - ay * bx
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    ex, ey = q2[0] - q1[0], q2[1] - q1[1]
    denom = _cross2(dx, dy, ex, ey)
    if abs(denom) > 1e-10:
        fx, fy = q1[0] - p1[0], q1[1] - p1[1]
        t = _cross2(fx, fy, ex, ey) / denom
        u = _cross2(fx, fy, dx, dy) / denom
        if 0.0 < t < 1.0 and 0.0 < u < 1.0:
            return 0.0
    return min(
        _pt_seg_dist(p1, q1, q2),
        _pt_seg_dist(p2, q1, q2),
        _pt_seg_dist(q1, p1, p2),
        _pt_seg_dist(q2, p1, p2),
    )


def _simplify_path(
    waypoints: list[tuple[float, float]],
    walls: list,
) -> list[tuple[float, float]]:
    """Reduce waypoints in two passes.

    Pass 1 — skip waypoints when the shortcut maintains the preferred wall
    clearance (_NAV_PREFER_CLEAR_M).  This preserves the wall-avoidance
    character of the A* path in open space.

    Pass 2 — remove collinear intermediate points.  In a straight corridor
    the first pass cannot skip anything (every shortcut still passes within
    1 m of a wall), but all the intermediate points lie on the same line;
    pass 2 collapses those into a single segment.  The threshold of 0.25 m
    matches the grid cell size so genuine direction changes are kept.
    """
    if len(waypoints) <= 1:
        return waypoints

    # Pass 1: preferred-clearance line-of-sight shortcutting.
    result: list[tuple[float, float]] = []
    i = 0
    while i < len(waypoints):
        j = len(waypoints) - 1
        while j > i + 1:
            if _path_clear(waypoints[i], waypoints[j], walls):
                break
            j -= 1
        result.append(waypoints[j])
        i = j
        if i == len(waypoints) - 1:
            break

    if len(result) <= 2:
        return result

    # Pass 2: drop near-collinear interior points.
    collinear_tol = _NAV_GRID_CELL_M  # one cell width ≈ smallest meaningful turn
    out = [result[0]]
    for k in range(1, len(result) - 1):
        if _pt_seg_dist(result[k], out[-1], result[k + 1]) > collinear_tol:
            out.append(result[k])
    out.append(result[-1])
    return out


def _path_clear(
    p1: tuple[float, float],
    p2: tuple[float, float],
    walls: list,
) -> bool:
    """True if segment p1–p2 stays at least _NAV_PREFER_CLEAR_M from every wall.

    Using the preference clearance (not just robot radius) means simplification
    only merges waypoints when the shortcut keeps the same wall-avoidance
    character as the A* path.  In narrow corridors where preferred clearance is
    unachievable the simplification is simply more conservative (fewer merges).
    """
    for seg in walls:
        q1 = (seg[0], seg[1])
        q2 = (seg[2], seg[3])
        if _seg_seg_min_dist(p1, p2, q1, q2) < _NAV_PREFER_CLEAR_M:
            return False
    return True


# ── controller ────────────────────────────────────────────────────────────────

class PersonTrackingController(MovementControllerProtocol):
    """Autonomous controller that keeps a tracked person in view and at range.

    **Close-tracking mode** (person visible, distance ≤ _NAV_TRIGGER_M):
      The robot rotates proportionally to the person's horizontal offset from
      frame centre, and moves forward if they are farther than _MIN_DISTANCE_M.

    **Navigation mode** (person detected at distance > _NAV_TRIGGER_M):
      A wall-avoiding A* path is planned from the robot's current world position
      to the person's last known world position.  The robot follows the path
      waypoints while continuously re-observing the person and the room walls.
      The route is replanned live whenever the person moves significantly or the
      wall map changes.  Once the robot is within _NAV_APPROACH_M, it rotates
      to face the last known person position and returns to close-tracking mode.

    **Idle** (person not visible, not navigating):
      The robot stops and waits.  No look-around sweep is performed.
    """

    def __init__(self, robot, camera_view, map_view=None):
        super().__init__(robot)
        self._camera_view  = camera_view
        self._map_view     = map_view
        self._poll_timer   = None
        self._active_move  = (0.0, 0.0, 0.0)
        self._smoothed_offset: float | None = None

        # Navigation state
        self._is_navigating        = False
        self._route: list          = []
        self._route_person_pos     = None
        self._last_person_world    = None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def setup(self) -> None:
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._on_tick)
        self._poll_timer.start(_POLL_MS)
        if self._map_view is not None and hasattr(self._map_view, "set_person_click_callback"):
            self._map_view.set_person_click_callback(self._on_map_click)

    def cleanup(self) -> None:
        if self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer = None
        if self._map_view is not None and hasattr(self._map_view, "set_person_click_callback"):
            self._map_view.set_person_click_callback(None)
        self._smoothed_offset   = None
        self._is_navigating     = False
        self._route             = []
        self._push_route()
        self._last_person_world = None
        self._set_move(0.0, 0.0, 0.0)

    # ── main tick ─────────────────────────────────────────────────────────────

    def _on_tick(self) -> None:
        if not getattr(self.robot, "is_connected", False):
            return

        people = self._camera_view.get_tracked_people()
        pose   = self.robot.get_lidar_pose()

        # Update world position of the tracked person whenever they are visible.
        if people and pose is not None:
            self._update_person_world(people, pose)

        if self._is_navigating:
            # Navigation mode blocks normal tracking; run one navigation step.
            self._nav_step(pose)
            return

        if not people:
            # Person not visible, not navigating — stop and wait.
            self._smoothed_offset = None
            self._set_move(0.0, 0.0, 0.0)
            return

        # Person visible — decide between tracking and starting navigation.
        frame_width, _ = self._camera_view.get_frame_size()
        if frame_width <= 0:
            return

        distances = self._camera_view.get_person_distances()
        if len(people) == 1:
            dist = distances.get(people[0].id)
        else:
            dist = None

        if (dist is not None and dist > _NAV_TRIGGER_M
                and pose is not None and self._last_person_world is not None):
            # Person is too far — switch to navigation mode immediately.
            self._is_navigating = True
            self._route         = []
            self._nav_step(pose)
            return

        # Close enough: clear any stale route and track normally.
        if self._route:
            self._route = []
            self._push_route()
        centers = [p.rect[0] + p.rect[2] / 2.0 for p in people]
        target_center = centers[0] if len(people) == 1 else (min(centers) + max(centers)) / 2.0
        self._track_person(target_center, frame_width, dist)

    # ── close tracking ────────────────────────────────────────────────────────

    def _track_person(
        self,
        target_center: float,
        frame_width: float,
        distance: float | None,
    ) -> None:
        """Rotate to centre the person; move forward if too far away."""
        frame_center = frame_width / 2.0
        offset = (target_center - frame_center) / frame_center  # [-1, 1]

        if self._smoothed_offset is None:
            self._smoothed_offset = offset
        else:
            self._smoothed_offset += _OFFSET_SMOOTHING * (offset - self._smoothed_offset)

        z = self._rotation_for_offset(self._smoothed_offset)
        forward = 0.0
        if distance is not None:
            if distance > _NAV_TRIGGER_M:
                forward = _MOVE_SPEED
            elif distance < _MIN_DISTANCE_M and _ALLOW_BACKING_UP:
                forward = -_MOVE_SPEED
        self._set_move(forward, 0.0, z)

    def _rotation_for_offset(self, offset: float) -> float:
        abs_off = min(1.0, abs(offset))
        if abs_off <= _ROTATE_DEADZONE:
            return 0.0
        span = 1.0 - _ROTATE_DEADZONE
        t = (abs_off - _ROTATE_DEADZONE) / span
        mag = _ROTATE_SPEED_MIN + t * (_ROTATE_SPEED_MAX - _ROTATE_SPEED_MIN)
        return mag if offset < 0 else -mag

    # ── test helpers ──────────────────────────────────────────────────────────

    def _on_map_click(self, wx: float, wy: float) -> None:
        """Set the person's world position from a map click (testing only)."""
        self._last_person_world = (wx, wy)
        pose = self.robot.get_lidar_pose()
        if pose is not None:
            rx, ry, _ = pose
            dist = math.hypot(wx - rx, wy - ry)
            if dist > _NAV_TRIGGER_M:
                self._is_navigating = True
                self._route         = []

    # ── navigation ────────────────────────────────────────────────────────────

    def _find_first_blocked_segment(
        self,
        rx: float, ry: float,
        walls: list, obstacles: list,
    ) -> int | None:
        """Return index of the first blocked segment in [(rx,ry)]+route, or None."""
        if not self._route:
            return None
        pts = [(rx, ry)] + self._route
        for i in range(len(pts) - 1):
            p1, p2 = pts[i], pts[i + 1]
            for seg in walls:
                if _seg_seg_min_dist(p1, p2, (seg[0], seg[1]), (seg[2], seg[3])) < _NAV_ROBOT_RADIUS_M:
                    return i
            for ox, oy in obstacles:
                if _pt_seg_dist((ox, oy), p1, p2) < _NAV_ROBOT_RADIUS_M:
                    return i
        return None

    def _replan_suffix(
        self,
        rx: float, ry: float,
        px: float, py: float,
        walls: list, obstacles: list,
        blocked_idx: int,
    ) -> list:
        """Keep waypoints before the blocked segment; replan the rest."""
        pts          = [(rx, ry)] + self._route
        valid_prefix = self._route[:blocked_idx]
        new_suffix   = _plan_route(pts[blocked_idx], (px, py), walls, obstacles)
        return valid_prefix + new_suffix

    def _update_goal_endpoint(
        self,
        rx: float, ry: float,
        px: float, py: float,
        walls: list, obstacles: list,
    ) -> list:
        """Slide the final waypoint to the new person position."""
        if not self._route:
            return _plan_route((rx, ry), (px, py), walls, obstacles)
        anchor = self._route[-2] if len(self._route) >= 2 else (rx, ry)
        direct_clear = (
            all(_seg_seg_min_dist(anchor, (px, py), (s[0], s[1]), (s[2], s[3])) >= _NAV_PREFER_CLEAR_M
                for s in walls)
            and all(_pt_seg_dist((ox, oy), anchor, (px, py)) >= _NAV_ROBOT_RADIUS_M
                    for ox, oy in obstacles)
        )
        if direct_clear:
            return self._route[:-1] + [(px, py)]
        return self._route[:-1] + _plan_route(anchor, (px, py), walls, obstacles)

    def _nav_step(self, pose) -> None:
        """One tick of wall-avoiding path navigation."""
        if pose is None or self._last_person_world is None:
            self._set_move(0.0, 0.0, 0.0)
            return

        rx, ry, yaw = pose
        px, py = self._last_person_world
        dist_to_person = math.hypot(px - rx, py - ry)

        # Arrived within approach distance — done navigating.
        if dist_to_person <= _NAV_APPROACH_M:
            self._is_navigating = False
            self._route         = []
            self._push_route()
            self._rotate_toward(rx, ry, yaw, px, py)
            return

        walls     = self._get_walls()
        obstacles = self._get_obstacles()

        if not self._route:
            # No route yet — plan a fresh one.
            self._route            = _plan_route((rx, ry), (px, py), walls, obstacles)
            self._route_person_pos = (px, py)
            self._push_route()
        else:
            blocked_idx = self._find_first_blocked_segment(rx, ry, walls, obstacles)
            if blocked_idx is not None:
                # Route blocked — keep valid prefix, replan the suffix.
                self._route            = self._replan_suffix(rx, ry, px, py, walls, obstacles, blocked_idx)
                self._route_person_pos = (px, py)
                self._push_route()
            elif (self._route_person_pos is None or
                  math.hypot(px - self._route_person_pos[0],
                             py - self._route_person_pos[1]) > _NAV_PERSON_MOVE_M):
                # Goal moved — adjust the last waypoint only.
                self._route            = self._update_goal_endpoint(rx, ry, px, py, walls, obstacles)
                self._route_person_pos = (px, py)
                self._push_route()

        # Advance past already-reached waypoints.
        while self._route:
            wx, wy = self._route[0]
            if math.hypot(wx - rx, wy - ry) <= _NAV_ARRIVE_M:
                self._route.pop(0)
            else:
                break

        if not self._route:
            # End of route reached — face the person.
            self._push_route()
            self._rotate_toward(rx, ry, yaw, px, py)
            return

        self._move_toward_waypoint(rx, ry, yaw, self._route[0])

    def _move_toward_waypoint(
        self,
        rx: float, ry: float, yaw: float,
        waypoint: tuple[float, float],
    ) -> None:
        """Steer toward the next waypoint: rotate to align, then move forward."""
        wx, wy = waypoint
        target_angle = math.atan2(wy - ry, wx - rx)
        heading_err  = _angle_diff(target_angle, yaw)

        if abs(heading_err) > _NAV_ROT_ALIGN:
            # Heading too far off — rotate in place first.
            t   = min(1.0, abs(heading_err) / math.pi)
            rot = max(0.5, t) * _NAV_ROT_SPEED_MAX
            self._set_move(0.0, 0.0, rot if heading_err > 0 else -rot)
        else:
            # Aligned enough — move forward with a gentle yaw correction.
            rot = heading_err / _NAV_ROT_ALIGN * _NAV_ROT_SPEED_MAX * 0.4
            rot = max(-_NAV_ROT_SPEED_MAX, min(_NAV_ROT_SPEED_MAX, rot))
            self._set_move(_NAV_FWD_SPEED, 0.0, rot)

    def _rotate_toward(
        self,
        rx: float, ry: float, yaw: float,
        tx: float, ty: float,
    ) -> None:
        """Rotate in place toward (tx, ty)."""
        target_angle = math.atan2(ty - ry, tx - rx)
        err = _angle_diff(target_angle, yaw)
        if abs(err) < _NAV_ROT_DEADZONE:
            self._set_move(0.0, 0.0, 0.0)
        else:
            rot = _NAV_ROT_SPEED_MAX * (1.0 if err > 0 else -1.0)
            self._set_move(0.0, 0.0, rot)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _update_person_world(self, people, pose) -> None:
        """Compute world (x, y) of the closest tracked person from lidar distance."""
        distances = self._camera_view.get_person_distances()
        frame_w, _ = self._camera_view.get_frame_size()
        if frame_w <= 0:
            return
        rx, ry, yaw = pose
        half_fov = math.radians(_CAMERA_FOV_DEG / 2.0)
        for person in people:
            dist = distances.get(person.id)
            if dist is None or dist <= 0:
                continue
            x_c, _, w_c, _ = person.rect
            norm_x  = ((x_c + w_c / 2.0) / frame_w) * 2.0 - 1.0
            bearing = -norm_x * half_fov
            lf = dist * math.cos(bearing)
            ll = dist * math.sin(bearing)
            self._last_person_world = (
                rx + lf * math.cos(yaw) - ll * math.sin(yaw),
                ry + lf * math.sin(yaw) + ll * math.cos(yaw),
            )
            return

    def _get_walls(self) -> list:
        if self._map_view is None:
            return []
        return list(getattr(self._map_view, "_wall_segments", []))

    def _get_obstacles(self) -> list:
        if self._map_view is None:
            return []
        fn = getattr(self._map_view, "get_obstacle_positions", None)
        return fn() if fn is not None else []

    def _push_route(self) -> None:
        """Send the current route to the map view for rendering."""
        if self._map_view is not None and hasattr(self._map_view, "set_nav_route"):
            self._map_view.set_nav_route(self._route)

    def _set_move(self, x: float, y: float, z: float) -> None:
        cmd = (x, y, z)
        if cmd == self._active_move:
            return
        if hasattr(self.robot, "move"):
            self.robot.move(x, y, z)
        self._active_move = cmd

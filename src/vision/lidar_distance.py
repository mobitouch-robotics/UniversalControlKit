from __future__ import annotations
import math
from collections import defaultdict
import numpy

# Approximate horizontal field of view of the robot's front camera, in
# degrees. Used to map a detected person's horizontal position in the
# camera frame to an angular direction relative to the robot, so that lidar
# points in roughly the same direction can be used to estimate distance.
# This is a best-effort estimate and may need tuning against real hardware.
DEFAULT_CAMERA_FOV_DEGREES = 120.0

# Angular tolerance (in degrees) when matching lidar points to a person's
# direction. The lower bound handles narrow/far bounding boxes (where the
# angular width would otherwise be tiny); the upper bound prevents a wide,
# close bounding box from producing a huge cone that sweeps in unrelated
# objects - clustering below narrows it down further anyway.
MIN_ANGLE_TOLERANCE_DEGREES = 4.0
MAX_ANGLE_TOLERANCE_DEGREES = 15.0

# Lidar returns closer than this (meters) are assumed to be the robot's own
# body/legs rather than the environment, and are discarded.
MIN_FORWARD_DISTANCE_M = 0.3

# The lidar voxel map includes floor and ceiling returns, which would
# otherwise dominate the estimate (the floor right in front of the robot is
# much closer than any person). We estimate the floor height from the lower
# percentile of all nearby points, then only consider points within this
# band above it as candidates for a person.
FLOOR_PERCENTILE = 5.0
MIN_HEIGHT_ABOVE_FLOOR_M = 0.5
MAX_HEIGHT_ABOVE_FLOOR_M = 2.0

# Before clustering, points are grouped onto a coarse grid (vectorized with
# numpy) and reduced to one representative entry per occupied cell. The voxel
# map can contain tens of thousands of points - far more than needed to tell
# objects apart - and the clustering step below is a pure-Python loop, so
# without this reduction it becomes extremely slow.
DOWNSAMPLE_CELL_M = 0.1

# Points within this distance (meters, in the forward/left plane) of each
# other are grouped into the same "object" cluster.
CLUSTER_RADIUS_M = 0.25

# Clusters smaller than this (in downsampled cells) are treated as noise and
# ignored.
MIN_CLUSTER_POINTS = 2


def _cluster_points(forward: numpy.ndarray, left: numpy.ndarray, radius: float) -> list[list[int]]:
    """Group points into clusters using single-linkage grouping: any two
    points within `radius` of each other end up in the same cluster.

    Uses a simple spatial grid plus union-find, which is fast enough for the
    point counts involved here (after downsampling, angular/height filtering).
    """
    n = forward.size
    if n == 0:
        return []

    cell_x = numpy.floor(forward / radius).astype(int)
    cell_y = numpy.floor(left / radius).astype(int)

    cell_map: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i in range(n):
        cell_map[(int(cell_x[i]), int(cell_y[i]))].append(i)

    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    radius_sq = radius * radius
    for i in range(n):
        cx, cy = int(cell_x[i]), int(cell_y[i])
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in cell_map.get((cx + dx, cy + dy), ()):
                    if j <= i:
                        continue
                    df = forward[i] - forward[j]
                    dl = left[i] - left[j]
                    if df * df + dl * dl <= radius_sq:
                        union(i, j)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return list(groups.values())


def _filter_candidate_points(points: numpy.ndarray, lidar_pose):
    """Return (forward, left, height_above_floor) arrays for lidar points
    that pass the forward-distance and floor/ceiling height filters used for
    person distance estimation.

    `height_above_floor` is `None` if the input points have no z column.
    """
    if lidar_pose is not None:
        rx, ry, yaw = lidar_pose
    else:
        rx, ry, yaw = 0.0, 0.0, 0.0

    xs = points[:, 0] - rx
    ys = points[:, 1] - ry

    # Rotate into the robot's local frame (forward = local x, left = local y).
    forward = xs * math.cos(yaw) + ys * math.sin(yaw)
    left = -xs * math.sin(yaw) + ys * math.cos(yaw)

    # The camera only sees what's in front of the robot, and points very
    # close to the robot are likely returns off its own body/legs.
    mask = forward > MIN_FORWARD_DISTANCE_M
    forward = forward[mask]
    left = left[mask]
    if forward.size == 0:
        return forward, left, None

    # Exclude floor and ceiling returns so clusters aren't dominated by them.
    height_above_floor = None
    if points.shape[1] >= 3:
        heights = points[:, 2][mask]
        floor_z = numpy.percentile(heights, FLOOR_PERCENTILE)
        height_above_floor = heights - floor_z
        body_mask = (height_above_floor >= MIN_HEIGHT_ABOVE_FLOOR_M) & (
            height_above_floor <= MAX_HEIGHT_ABOVE_FLOOR_M
        )
        forward = forward[body_mask]
        left = left[body_mask]
        height_above_floor = height_above_floor[body_mask]

    return forward, left, height_above_floor


def _downsample(forward: numpy.ndarray, left: numpy.ndarray, point_ranges: numpy.ndarray, cell_size: float):
    """Reduce a large point set to one representative entry per occupied
    grid cell, using vectorized numpy operations.

    Each output entry's forward/left position is the mean of the points in
    that cell, and its range is the minimum range among them (so that the
    nearest-point distance of a cluster remains accurate after downsampling).
    """
    gx = numpy.floor(forward / cell_size).astype(numpy.int64)
    gy = numpy.floor(left / cell_size).astype(numpy.int64)
    cells = numpy.stack([gx, gy], axis=1)

    _unique_cells, inverse, counts = numpy.unique(cells, axis=0, return_inverse=True, return_counts=True)
    n_cells = counts.size

    cell_forward = numpy.bincount(inverse, weights=forward, minlength=n_cells) / counts
    cell_left = numpy.bincount(inverse, weights=left, minlength=n_cells) / counts

    cell_range = numpy.full(n_cells, numpy.inf)
    numpy.minimum.at(cell_range, inverse, point_ranges)

    return cell_forward, cell_left, cell_range


def estimate_person_distances(
    people,
    frame_width: int,
    lidar_points,
    lidar_pose,
    fov_degrees: float = DEFAULT_CAMERA_FOV_DEGREES,
) -> dict:
    """Estimate the distance (in meters) to each tracked person using lidar.

    Lidar points are filtered to plausible "person" candidates (in front of
    the robot, excluding robot self-returns, floor and ceiling), downsampled
    onto a coarse grid, then grouped into spatial clusters representing
    distinct objects. For each person, the cluster whose direction most
    closely matches the person's direction in the camera frame is used as the
    distance estimate (the cluster's nearest point). This avoids mixing
    points from unrelated background objects (e.g. walls) that happen to fall
    within a wide angular cone.

    Args:
        people: iterable of objects with `.id` and `.rect` (x, y, w, h) in
            camera frame pixel coordinates.
        frame_width: width of the camera frame in pixels.
        lidar_points: (N, 3) array of (x, y, z) lidar points in the robot's
            map frame, or None.
        lidar_pose: (x, y, yaw) tuple describing the robot's pose in the
            same map frame, or None (assumes origin/yaw=0).
        fov_degrees: assumed horizontal field of view of the camera.

    Returns:
        Dict mapping person id -> estimated distance in meters. People for
        whom no matching lidar cluster was found are omitted.
    """
    if not people or frame_width <= 0 or lidar_points is None:
        return {}

    points = numpy.asarray(lidar_points)
    if points.ndim != 2 or points.shape[0] == 0 or points.shape[1] < 2:
        return {}

    forward, left, _height_above_floor = _filter_candidate_points(points, lidar_pose)
    if forward.size == 0:
        return {}

    point_ranges = numpy.hypot(forward, left)

    # Reduce to one representative entry per occupied grid cell before
    # clustering, which is a pure-Python loop and would otherwise be far too
    # slow for the raw point counts involved.
    cell_forward, cell_left, cell_range = _downsample(forward, left, point_ranges, DOWNSAMPLE_CELL_M)

    # Group remaining points into distinct objects.
    clusters = _cluster_points(cell_forward, cell_left, CLUSTER_RADIUS_M)
    cluster_stats = []
    for indices in clusters:
        if len(indices) < MIN_CLUSTER_POINTS:
            continue
        idx = numpy.array(indices)
        centroid_angle = math.degrees(
            math.atan2(float(cell_left[idx].mean()), float(cell_forward[idx].mean()))
        )
        nearest_range = float(cell_range[idx].min())
        cluster_stats.append((centroid_angle, nearest_range))

    if not cluster_stats:
        return {}

    half_fov = fov_degrees / 2.0
    distances = {}
    for person in people:
        x, _y, w, _h = person.rect
        center_x = x + w / 2.0
        # -1 (left edge) .. +1 (right edge) of the camera frame.
        normalized_x = (center_x / frame_width) * 2.0 - 1.0
        # Right side of the image is the robot's right, i.e. negative "left".
        person_angle = -normalized_x * half_fov

        bbox_angle_width = (w / frame_width) * fov_degrees
        tolerance = min(
            MAX_ANGLE_TOLERANCE_DEGREES,
            max(MIN_ANGLE_TOLERANCE_DEGREES, bbox_angle_width / 2.0),
        )

        best_diff = None
        best_range = None
        for centroid_angle, nearest_range in cluster_stats:
            diff = abs(centroid_angle - person_angle)
            if diff <= tolerance and (best_diff is None or diff < best_diff):
                best_diff = diff
                best_range = nearest_range

        if best_range is not None:
            distances[person.id] = best_range

    return distances

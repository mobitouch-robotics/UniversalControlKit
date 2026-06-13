from __future__ import annotations
import math
import numpy

# Approximate horizontal field of view of the robot's front camera, in
# degrees. Used to map a detected person's horizontal position in the
# camera frame to an angular direction relative to the robot, so that lidar
# points in roughly the same direction can be used to estimate distance.
# This is a best-effort estimate and may need tuning against real hardware.
DEFAULT_CAMERA_FOV_DEGREES = 120.0

# Minimum angular tolerance (in degrees) when matching lidar points to a
# person's direction, in case the bounding box is very narrow.
MIN_ANGLE_TOLERANCE_DEGREES = 4.0


def estimate_person_distances(
    people,
    frame_width: int,
    lidar_points,
    lidar_pose,
    fov_degrees: float = DEFAULT_CAMERA_FOV_DEGREES,
) -> dict:
    """Estimate the distance (in meters) to each tracked person using lidar.

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
        whom no matching lidar points were found are omitted.
    """
    if not people or frame_width <= 0 or lidar_points is None:
        return {}

    points = numpy.asarray(lidar_points)
    if points.ndim != 2 or points.shape[0] == 0 or points.shape[1] < 2:
        return {}

    if lidar_pose is not None:
        rx, ry, yaw = lidar_pose
    else:
        rx, ry, yaw = 0.0, 0.0, 0.0

    xs = points[:, 0] - rx
    ys = points[:, 1] - ry

    # Rotate into the robot's local frame (forward = local x, left = local y).
    forward = xs * math.cos(yaw) + ys * math.sin(yaw)
    left = -xs * math.sin(yaw) + ys * math.cos(yaw)

    # The camera only sees what's in front of the robot.
    mask = forward > 0.05
    forward = forward[mask]
    left = left[mask]
    if forward.size == 0:
        return {}

    point_angles = numpy.degrees(numpy.arctan2(left, forward))
    point_ranges = numpy.hypot(forward, left)

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
        tolerance = max(MIN_ANGLE_TOLERANCE_DEGREES, bbox_angle_width / 2.0)

        diffs = numpy.abs(point_angles - person_angle)
        candidates = point_ranges[diffs <= tolerance]
        if candidates.size == 0:
            continue
        distances[person.id] = float(numpy.median(candidates))

    return distances

from __future__ import annotations

# Distance (in meters) at which a fully-visible person's bounding box height
# would equal the full camera frame height. Distance scales inversely with
# the bounding-box-height-to-frame-height ratio, so halving that ratio
# doubles the estimated distance. Calibrated from a real measurement (a
# person standing ~4m away produced a height ratio of ~0.625), but may still
# need further tuning against real hardware.
REFERENCE_DISTANCE_M = 2.5

# A person's bounding box must be inset from the top and bottom edges of the
# frame by at least this fraction of the frame height to be considered fully
# visible. Bounding boxes that are cut off at the top/bottom (e.g. the person
# is too close, or only partially in frame) produce unreliable height-based
# distance estimates and are skipped.
FRAME_EDGE_MARGIN_RATIO = 0.02


def estimate_person_distances(people, frame_height: int) -> dict:
    """Estimate the distance (in meters) to each tracked person using the
    height of their bounding box relative to the camera frame height.

    A person's silhouette grows smaller as they move farther away, so the
    bounding box height is inversely proportional to distance. Only people
    whose bounding box top and bottom are both inset from the frame edges by
    at least `FRAME_EDGE_MARGIN_RATIO` are included, since a bounding box
    that's cut off no longer reflects the person's full height.

    Args:
        people: iterable of objects with `.id` and `.rect` (x, y, w, h) in
            camera frame pixel coordinates.
        frame_height: height of the camera frame in pixels.

    Returns:
        Dict mapping person id -> estimated distance in meters. People who
        aren't fully in view are omitted.
    """
    if not people or frame_height <= 0:
        return {}

    margin = frame_height * FRAME_EDGE_MARGIN_RATIO
    distances = {}
    for person in people:
        _x, y, _w, h = person.rect
        if h <= 0:
            continue
        if y < margin or (y + h) > (frame_height - margin):
            continue
        height_ratio = h / frame_height
        distances[person.id] = REFERENCE_DISTANCE_M / height_ratio

    return distances

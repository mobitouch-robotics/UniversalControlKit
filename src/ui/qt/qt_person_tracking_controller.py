import logging
import math

from PyQt5.QtCore import QTimer

from ..protocols import MovementControllerProtocol

logger = logging.getLogger(__name__)


def _angle_diff(a: float, b: float) -> float:
    """Return the signed difference a - b, normalized to [-pi, pi]."""
    return math.atan2(math.sin(a - b), math.cos(a - b))


class PersonTrackingController(MovementControllerProtocol):
    """Autonomous controller that keeps tracked people roughly centered in
    the camera view and, for a single person, at a comfortable distance.

    The robot continuously rotates proportionally to how far the tracked
    people are from the horizontal center of the frame - small offsets
    produce small rotation speeds, larger offsets produce faster rotation
    (up to `_ROTATE_SPEED_MAX`), so the robot is constantly making small
    adjustments rather than only reacting once they cross into an outer
    zone.

    With a single tracked person, the target is that person's center. With
    multiple tracked people, the target is the midpoint between the
    leftmost and rightmost person, so the robot tries to keep the whole
    group in view. Forward/backward movement based on distance is only
    applied when exactly one person is tracked: the robot moves forward
    when they are farther than `_MAX_DISTANCE_M`. If `_ALLOW_BACKING_UP` is
    enabled, it will also move backward when closer than
    `_MIN_DISTANCE_M`; by default this is disabled, so the robot only
    approaches and never backs away.

    If all people disappear while the robot was actively rotating toward
    them, the robot keeps rotating at `_ROTATE_SPEED_MAX` in the same
    direction for up to `_SEARCH_MAX_ROTATION_DEGREES` additional degrees, in
    case they stepped out of frame, before giving up. Rotation stops
    immediately once the target is centered or someone is found again.
    """

    _POLL_MS = 100
    # Rotation speed scales with how far off-center the person is: from
    # _ROTATE_SPEED_MIN just outside the dead zone, up to _ROTATE_SPEED_MAX
    # when they're at the edge of the frame.
    _ROTATE_SPEED_MIN = 0.15
    _ROTATE_SPEED_MAX = 0.6
    # Fraction of the half-frame-width within which the person is considered
    # centered enough that no rotation is needed.
    _ROTATE_DEADZONE = 0.04
    _MOVE_SPEED = 0.3
    _MIN_DISTANCE_M = 0.5
    _MAX_DISTANCE_M = 1.0
    _SEARCH_MAX_ROTATION_DEGREES = 90.0
    # When False, the robot will move toward a person who is too far away
    # but will not back away from one who is too close.
    _ALLOW_BACKING_UP = False

    def __init__(self, robot, camera_view):
        super().__init__(robot)
        self._camera_view = camera_view
        self._poll_timer = None
        self._active_move = (0.0, 0.0, 0.0)
        self._search_z = 0.0
        self._search_start_yaw = None

    def setup(self):
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._on_tick)
        self._poll_timer.start(self._POLL_MS)

    def cleanup(self):
        if self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer = None
        self._search_z = 0.0
        self._search_start_yaw = None
        self._set_move(0.0, 0.0, 0.0)

    def _on_tick(self):
        if not getattr(self.robot, "is_connected", False):
            return

        people = self._camera_view.get_tracked_people()

        if len(people) == 0:
            self._search_for_person()
            return

        # At least one person tracked: stop any ongoing search and track normally.
        self._search_z = 0.0
        self._search_start_yaw = None

        frame_width, _ = self._camera_view.get_frame_size()
        if frame_width <= 0:
            return

        centers = [p.rect[0] + p.rect[2] / 2.0 for p in people]
        if len(people) == 1:
            target_center = centers[0]
            distance = self._camera_view.get_person_distances().get(people[0].id)
        else:
            # Aim for the midpoint between the leftmost and rightmost person,
            # so the whole group stays in view.
            target_center = (min(centers) + max(centers)) / 2.0
            distance = None

        frame_center = frame_width / 2.0

        # -1 (left edge) .. +1 (right edge) of the frame; negative means the
        # target is left of center.
        offset = (target_center - frame_center) / frame_center

        z = self._rotation_for_offset(offset)

        forward = 0.0
        if distance is not None:
            if distance > self._MAX_DISTANCE_M:
                forward = self._MOVE_SPEED
            elif distance < self._MIN_DISTANCE_M and self._ALLOW_BACKING_UP:
                forward = -self._MOVE_SPEED

        self._set_move(forward, 0.0, z)

    def _rotation_for_offset(self, offset: float) -> float:
        """Compute a proportional rotation speed to center a person.

        `offset` is in [-1, 1], negative meaning the person is left of
        center. Returns a positive z (rotate left) for negative offsets and
        vice versa, scaled between `_ROTATE_SPEED_MIN` and
        `_ROTATE_SPEED_MAX` outside of `_ROTATE_DEADZONE`, or 0 within it.
        """
        abs_offset = min(1.0, abs(offset))
        if abs_offset <= self._ROTATE_DEADZONE:
            return 0.0

        span = 1.0 - self._ROTATE_DEADZONE
        t = (abs_offset - self._ROTATE_DEADZONE) / span
        magnitude = self._ROTATE_SPEED_MIN + t * (self._ROTATE_SPEED_MAX - self._ROTATE_SPEED_MIN)
        return magnitude if offset < 0 else -magnitude

    def _search_for_person(self):
        """Handle the case where no person is currently tracked.

        If the robot was actively rotating toward a person right before they
        were lost, keep rotating in the same direction (without moving
        forward/backward) for up to `_SEARCH_MAX_ROTATION_DEGREES`, in the
        hope of finding them again. Otherwise, just stop.
        """
        if self._search_z == 0.0:
            last_z = self._active_move[2]
            if last_z == 0.0:
                self._set_move(0.0, 0.0, 0.0)
                return
            start_yaw = self._get_yaw()
            if start_yaw is None:
                # Can't measure rotation without pose data; give up.
                self._set_move(0.0, 0.0, 0.0)
                return
            # Search decisively in the last known direction, regardless of
            # how small the proportional rotation speed was at the moment
            # the person was lost.
            self._search_z = math.copysign(self._ROTATE_SPEED_MAX, last_z)
            self._search_start_yaw = start_yaw

        current_yaw = self._get_yaw()
        if current_yaw is not None and self._search_start_yaw is not None:
            traveled_degrees = abs(math.degrees(_angle_diff(current_yaw, self._search_start_yaw)))
            if traveled_degrees >= self._SEARCH_MAX_ROTATION_DEGREES:
                self._search_z = 0.0
                self._search_start_yaw = None
                self._set_move(0.0, 0.0, 0.0)
                return

        self._set_move(0.0, 0.0, self._search_z)

    def _get_yaw(self):
        """Return the robot's current yaw (radians) from lidar pose, or None."""
        get_pose = getattr(self.robot, "get_lidar_pose", None)
        if get_pose is None:
            return None
        try:
            pose = get_pose()
        except Exception:
            return None
        if pose is None:
            return None
        return pose[2]

    def _set_move(self, x: float, y: float, z: float):
        new_move = (x, y, z)
        if new_move == self._active_move:
            # The move worker keeps re-sending the active command, so
            # there's nothing more to do.
            return
        if hasattr(self.robot, "move"):
            self.robot.move(x, y, z)
        self._active_move = new_move

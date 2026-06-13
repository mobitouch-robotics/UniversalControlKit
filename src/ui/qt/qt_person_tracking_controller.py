import logging
import math

from PyQt5.QtCore import QTimer

from ..protocols import MovementControllerProtocol

logger = logging.getLogger(__name__)


def _angle_diff(a: float, b: float) -> float:
    """Return the signed difference a - b, normalized to [-pi, pi]."""
    return math.atan2(math.sin(a - b), math.cos(a - b))


class PersonTrackingController(MovementControllerProtocol):
    """Autonomous controller that keeps a single tracked person roughly
    centered in the camera view and at a comfortable distance.

    The horizontal field of view is split into three equal zones (left,
    center, right). While exactly one person is tracked and they remain in
    the left or right zone, the robot keeps rotating toward the center
    (continuously, like a held joystick direction). At the same time, if a
    lidar-based distance estimate is available, the robot moves forward when
    the person is farther than `_MAX_DISTANCE_M` and backward when closer
    than `_MIN_DISTANCE_M`, trying to keep them within that range.

    If the person disappears while the robot was actively rotating toward
    them, the robot keeps rotating in the same direction for up to
    `_SEARCH_MAX_ROTATION_DEGREES` additional degrees, in case they stepped
    out of frame, before giving up. Rotation stops immediately once the
    person reaches the center zone, is found again, or more than one person
    is detected.
    """

    _POLL_MS = 200
    _ROTATE_SPEED = 0.35
    _MOVE_SPEED = 0.3
    _MIN_DISTANCE_M = 1.0
    _MAX_DISTANCE_M = 2.0
    _SEARCH_MAX_ROTATION_DEGREES = 90.0

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

        if len(people) > 1:
            self._search_z = 0.0
            self._search_start_yaw = None
            self._set_move(0.0, 0.0, 0.0)
            return

        if len(people) == 0:
            self._search_for_person()
            return

        # Exactly one person tracked: stop any ongoing search and track normally.
        self._search_z = 0.0
        self._search_start_yaw = None

        frame_width, _ = self._camera_view.get_frame_size()
        if frame_width <= 0:
            return

        person = people[0]
        x, _y, w, _h = person.rect
        center_x = x + w / 2.0
        third = frame_width / 3.0

        if center_x < third:
            zone = "left"
        elif center_x > 2 * third:
            zone = "right"
        else:
            zone = "center"

        # Person on the left -> rotate left so they shift toward center, and
        # vice versa for the right side.
        if zone == "left":
            z = self._ROTATE_SPEED
        elif zone == "right":
            z = -self._ROTATE_SPEED
        else:
            z = 0.0

        forward = 0.0
        distance = self._camera_view.get_person_distances().get(person.id)
        if distance is not None:
            if distance > self._MAX_DISTANCE_M:
                forward = self._MOVE_SPEED
            elif distance < self._MIN_DISTANCE_M:
                forward = -self._MOVE_SPEED

        self._set_move(forward, 0.0, z)

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
            self._search_z = last_z
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

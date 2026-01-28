from ..protocols import KeyCode
from ..protocols import MovementControllerProtocol
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QWidget


class QtMovementController(MovementControllerProtocol):
    def __init__(self, robot, window: QWidget):
        super().__init__(robot)
        self.window = window
        self.active_keys = set()
        self.movement_speed = 1.0
        self._timer_ms = 100
        self._timer = None

    def setup(self):
        if QTimer:
            self._timer = QTimer()
            self._timer.timeout.connect(self._on_move_tick)
            self._timer.start(self._timer_ms)

    def cleanup(self):
        if self._timer:
            self._timer.stop()
            self._timer = None

    def handle_key_press(self, key: KeyCode):
        """Handle universal key code press."""
        self.active_keys.add(key)
        if key == KeyCode.SHIFT:
            if hasattr(self.robot, "rest"):
                self.robot.rest()
        elif key == KeyCode.TAB:
            if hasattr(self.robot, "standup"):
                self.robot.standup()
        elif key == KeyCode.ZERO:
            if hasattr(self.robot, "jump_forward"):
                self.robot.jump_forward()
        # Return True if handled
        return key in {
            KeyCode.UP,
            KeyCode.DOWN,
            KeyCode.LEFT,
            KeyCode.RIGHT,
            KeyCode.Z,
            KeyCode.X,
            KeyCode.SHIFT,
            KeyCode.TAB,
            KeyCode.ZERO,
        }

    def handle_key_release(self, key: KeyCode):
        """Handle universal key code release."""
        if key in self.active_keys:
            self.active_keys.remove(key)
        return key in {
            KeyCode.UP,
            KeyCode.DOWN,
            KeyCode.LEFT,
            KeyCode.RIGHT,
            KeyCode.Z,
            KeyCode.X,
            KeyCode.SHIFT,
            KeyCode.TAB,
            KeyCode.ZERO,
        }

    def _on_move_tick(self):
        x = 0.0
        y = 0.0
        z = 0.0
        if KeyCode.UP in self.active_keys:
            x += self.movement_speed
        if KeyCode.DOWN in self.active_keys:
            x -= self.movement_speed
        if KeyCode.Z in self.active_keys:
            y += self.movement_speed
        if KeyCode.X in self.active_keys:
            y -= self.movement_speed
        if KeyCode.LEFT in self.active_keys:
            z = 1.0
        if KeyCode.RIGHT in self.active_keys:
            z = -1.0
        if x < 0 and z != 0:
            z = -z
        # Only send move if robot is connected and move is available
        if (
            hasattr(self.robot, "is_connected")
            and self.robot.is_connected
            and hasattr(self.robot, "move")
        ):
            self.robot.move(x, y, z)


# Utility to map Qt key events to universal KeyCode
def qt_key_to_universal(event):
    qt_to_universal = {
        Qt.Key_Up: KeyCode.UP,
        Qt.Key_Down: KeyCode.DOWN,
        Qt.Key_Left: KeyCode.LEFT,
        Qt.Key_Right: KeyCode.RIGHT,
        Qt.Key_Z: KeyCode.Z,
        Qt.Key_X: KeyCode.X,
        Qt.Key_Shift: KeyCode.SHIFT,
        Qt.Key_Tab: KeyCode.TAB,
        Qt.Key_0: KeyCode.ZERO,
    }
    return qt_to_universal.get(event.key(), KeyCode.UNKNOWN)

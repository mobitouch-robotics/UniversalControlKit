from __future__ import annotations

try:
    from PyQt5.QtCore import Qt, QTimer
    from PyQt5.QtWidgets import QWidget
except Exception:
    Qt = None
    QTimer = None
    QWidget = None

from ..protocols import MovementControllerProtocol


class QtMovementController(MovementControllerProtocol):
    def __init__(self, robot, window: QWidget):
        self.robot = robot
        self.window = window
        self.active_keys = set()
        self.movement_speed = 0.5
        self._timer_ms = 100
        self._timer = None

    def setup(self) -> None:
        if QTimer:
            self._timer = QTimer()
            self._timer.timeout.connect(self._on_move_tick)
            self._timer.start(self._timer_ms)

    def cleanup(self) -> None:
        if self._timer:
            self._timer.stop()
            self._timer = None

    def handle_key_press(self, event):
        """Called by parent window on key press."""
        key = event.key()
        self.active_keys.add(key)
        
        # Shift keys - rest position
        if key in (Qt.Key_Shift,):
            self.robot.rest()
        # Tab - standup
        elif key == Qt.Key_Tab:
            self.robot.standup()
        # 0 - jump forward
        elif key == Qt.Key_0:
            self.robot.jump_forward()

    def handle_key_release(self, event):
        """Called by parent window on key release."""
        key = event.key()
        if key in self.active_keys:
            self.active_keys.remove(key)

    def _on_move_tick(self):
        x = 0.0
        y = 0.0
        z = 0.0
        if Qt.Key_Up in self.active_keys:
            x += self.movement_speed
        if Qt.Key_Down in self.active_keys:
            x -= self.movement_speed
        if Qt.Key_Z in self.active_keys:
            y += self.movement_speed
        if Qt.Key_X in self.active_keys:
            y -= self.movement_speed
        if Qt.Key_Left in self.active_keys:
            z = 1.0
        if Qt.Key_Right in self.active_keys:
            z = -1.0
        if x < 0 and z != 0:
            z = -z
        # Only send move if robot is connected
        if hasattr(self.robot, 'is_connected') and self.robot.is_connected():
            self.robot.move(x, y, z)

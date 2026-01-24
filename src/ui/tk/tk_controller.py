from __future__ import annotations

try:
    import tkinter as tk
except Exception:
    tk = None

from ..protocols import MovementControllerProtocol


class TkMovementController(MovementControllerProtocol):
    def __init__(self, robot, root: tk.Tk):
        self.robot = robot
        self.root = root
        self.active_keys = set()
        self.movement_speed = 0.5
        self._timer_ms = 100

    def setup(self) -> None:
        # Use bind_all to capture keys regardless of widget focus
        self.root.bind_all("<KeyPress>", self._on_key_press)
        self.root.bind_all("<KeyRelease>", self._on_key_release)
        self.root.after(self._timer_ms, self._on_move_tick)

    def cleanup(self) -> None:
        # Tk doesn't need explicit unbind here for simple apps
        pass

    def _on_key_press(self, event):
        key = event.keysym
        self.active_keys.add(key)
        if key in ("Shift_L", "Shift_R"):
            self.robot.rest()
        elif key == "Tab":
            self.robot.standup()
        elif key == "0":
            self.robot.jump_forward()

    def _on_key_release(self, event):
        key = event.keysym
        if key in self.active_keys:
            self.active_keys.remove(key)

    def _on_move_tick(self):
        x = 0.0
        y = 0.0
        z = 0.0
        if "Up" in self.active_keys:
            x += self.movement_speed
        if "Down" in self.active_keys:
            x -= self.movement_speed
        if "z" in self.active_keys:
            y += self.movement_speed
        if "x" in self.active_keys:
            y -= self.movement_speed
        if "Left" in self.active_keys:
            z = 1.0
        if "Right" in self.active_keys:
            z = -1.0
        if x < 0 and z != 0:
            z = -z
        self.robot.move(x, y, z)
        self.root.after(self._timer_ms, self._on_move_tick)

from __future__ import annotations

try:
    import tkinter as tk
    import threading
except Exception:
    tk = None
    threading = None

from .tk_controller import TkMovementController
from .tk_camera import TkCameraView


class TkApp:
    def __init__(self, robot_factory):
        self.robot_factory = robot_factory
        self.root = tk.Tk() if tk else None
        self.robot = None
        self.controller = None
        self.camera = None

    def setup(self):
        if not tk:
            raise RuntimeError("Tkinter not available")
        self.root.title("MobiTouchRobots")
        self.root.geometry("800x600")
        self.robot = self.robot_factory()
        self.controller = TkMovementController(self.robot, self.root)
        self.camera = TkCameraView(self.robot, self.root)
        self.controller.setup()
        self.camera.setup()
        # Ensure the root window has focus to receive key events
        try:
            self.root.focus_force()
        except Exception:
            pass
        # Connect robot in background to avoid blocking UI
        if threading:
            threading.Thread(target=self.robot.connect, daemon=True).start()

    def run(self):
        self.setup()
        self.root.mainloop()

    def cleanup(self):
        if self.controller:
            self.controller.cleanup()
        if self.camera:
            self.camera.cleanup()
        # Robot cleanup if needed
        try:
            if self.robot:
                self.robot.stop()
        except Exception:
            pass

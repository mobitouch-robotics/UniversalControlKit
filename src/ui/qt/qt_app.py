from __future__ import annotations

import sys
import threading

try:
    from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
    from PyQt5.QtCore import Qt
except Exception:
    QApplication = None
    QMainWindow = None
    QWidget = None
    QVBoxLayout = None
    Qt = None

from .qt_controller import QtMovementController
from .qt_camera import QtCameraView


class QtMainWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

    def keyPressEvent(self, event):
        """Override to handle key press events."""
        if self.controller:
            self.controller.handle_key_press(event)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Override to handle key release events."""
        if self.controller:
            self.controller.handle_key_release(event)
        super().keyReleaseEvent(event)


class QtApp:
    def __init__(self, robot_factory):
        self.robot_factory = robot_factory
        self.app = None
        self.window = None
        self.robot = None
        self.controller = None
        self.camera = None

    def setup(self):
        if not QApplication:
            raise RuntimeError("PyQt5 not available")
        
        # Create QApplication
        self.app = QApplication(sys.argv)
        
        # Create robot
        self.robot = self.robot_factory()
        
        # Create main window
        self.window = QtMainWindow(None)
        self.window.setWindowTitle("MobiTouchRobots")
        self.window.resize(800, 600)
        
        # Create central widget and layout
        central_widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        central_widget.setLayout(layout)
        self.window.setCentralWidget(central_widget)
        
        # Create camera view
        self.camera = QtCameraView(self.robot, self.window)
        self.camera.setup()
        if self.camera.get_widget():
            layout.addWidget(self.camera.get_widget())
        
        # Create controller
        self.controller = QtMovementController(self.robot, self.window)
        self.window.controller = self.controller
        self.controller.setup()
        
        # Connect robot in background to avoid blocking UI
        threading.Thread(target=self.robot.connect, daemon=True).start()
        
        # Show window
        self.window.show()

    def run(self):
        self.setup()
        return self.app.exec_()

    def cleanup(self):
        if self.controller:
            self.controller.cleanup()
        if self.camera:
            self.camera.cleanup()

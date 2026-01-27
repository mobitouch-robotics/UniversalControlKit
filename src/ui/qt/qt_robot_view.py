from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtCore import pyqtSignal, Qt
from .qt_camera import QtCameraView
from .qt_controller import QtMovementController
import threading


class RobotViewWidget(QWidget):
    back_to_selector = pyqtSignal()

    def __init__(self, robot, window, parent=None):
        super().__init__(parent)
        self.robot = robot
        self.window = window
        self.camera = None
        self.controller = None
        # Ensure RobotRepository singleton is initialized
        from src.robot.robot_repository import RobotRepository

        RobotRepository()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        # Top row: Back and Connect/Disconnect buttons with spacing
        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        # --- Create generic buttons ---
        back_btn = QPushButton("<- Back")
        back_btn.setFixedWidth(220)
        back_btn.clicked.connect(self._on_back)
        top_row.addWidget(back_btn)

        top_row.addSpacing(16)
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setFixedWidth(120)
        self.connect_btn.clicked.connect(self._on_connect)
        top_row.addWidget(self.connect_btn)

        top_row.addSpacing(8)
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setFixedWidth(120)
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        self.disconnect_btn.setEnabled(False)
        top_row.addWidget(self.disconnect_btn)

        top_row.addStretch(1)
        layout.addLayout(top_row)

        # Always use QtCameraView for all robots
        self.camera = QtCameraView(self.robot, self.window)
        self.camera.setup()
        if self.camera.get_widget():
            layout.addWidget(self.camera.get_widget())

        # Controller
        self.controller = QtMovementController(self.robot, self.window)
        self.window.controller = self.controller
        self.controller.setup()
        # Ensure this widget receives focus so key events go to the window/controller
        try:
            self.setFocusPolicy(Qt.StrongFocus)
            self.setFocus()
        except Exception:
            pass

    def _on_connect(self):
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)
        self.robot.connect()

    def _on_disconnect(self):
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.robot.disconnect()

    def _on_back(self):
        self.back_to_selector.emit()

    def cleanup(self):
        if self.controller:
            self.controller.cleanup()
            # Clear window.controller reference to allow deallocation
            if (
                hasattr(self.window, "controller")
                and self.window.controller is self.controller
            ):
                self.window.controller = None
            self.controller = None
        if self.camera:
            self.camera.cleanup()
            self.camera = None
        if self.robot:
            self.robot = None

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)

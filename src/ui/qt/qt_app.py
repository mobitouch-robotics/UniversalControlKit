from __future__ import annotations

import sys, os
from .qt_robot_selector import QtRobotSelector
from PyQt5.QtWidgets import QStackedWidget, QMenuBar, QAction, QWidget, QVBoxLayout, QPushButton, QHBoxLayout
from PyQt5.QtCore import pyqtSignal
from .qt_camera import QtCameraView
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from .qt_controller import QtMovementController
from src.robot.robot_go2 import Robot_Go2
from src.robot.robot_dummy import Robot_Dummy
import threading

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

class RobotViewWidget(QWidget):
    back_to_selector = pyqtSignal()

    def __init__(self, robot, window, parent=None):
        super().__init__(parent)
        self.robot = robot
        self.window = window
        self.camera = None
        self.controller = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        # Top row: Back and Connect/Disconnect buttons with spacing
        top_row = QHBoxLayout()
        top_row.setSpacing(16)
        back_btn = QPushButton("← Back to Robot Selection")
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

    def _on_connect(self):
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)
        # Connect robot in background to avoid blocking UI
        threading.Thread(target=self.robot.connect, daemon=True).start()

    def _on_disconnect(self):
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        try:
            self.robot.disconnect()
        except Exception as e:
            print(f"[DEBUG] Exception in disconnect: {e}")

    def _on_back(self):
        self.back_to_selector.emit()

    def cleanup(self):
        if self.controller:
            self.controller.cleanup()
            # Clear window.controller reference to allow deallocation
            if hasattr(self.window, 'controller') and self.window.controller is self.controller:
                self.window.controller = None
            self.controller = None
        if self.camera:
            self.camera.cleanup()
            self.camera = None
        if self.robot:
            try:
                self.robot.disconnect()
            except Exception as e:
                print(f"[DEBUG] Exception in cleanup disconnect: {e}")
            self.robot = None

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)

class QtApp:
    def __init__(self):
        self.app = None
        self.window = None
        self.stack = None
        self.robot = None
        self.controller = None
        self.camera = None
        self.selected_robot_type = None
        self.robot_view_widget = None

    def setup(self):
        self.app = QApplication(sys.argv)

        # Create main window and stacked widget
        self.window = QtMainWindow(None)
        self.window.setWindowTitle("MobiTouchRobots")
        self.window.resize(800, 600)
        self.stack = QStackedWidget()
        self.window.setCentralWidget(self.stack)

        # Add menu for returning to robot selection
        menubar = QMenuBar(self.window)
        robot_menu = menubar.addMenu("Robot")
        select_action = QAction("Select Robot...", self.window)
        robot_menu.addAction(select_action)
        self.window.setMenuBar(menubar)
        select_action.triggered.connect(self.show_selector)

        # Show selector at startup
        self.show_selector()
        self.window.show()

    def show_selector(self):
        # Clean up previous robot view if any
        if self.robot_view_widget:
            self.stack.removeWidget(self.robot_view_widget)
            self.robot_view_widget.cleanup()
            self.robot_view_widget.deleteLater()
            self.robot_view_widget = None

        selector = QtRobotSelector(self.window)
        self.stack.addWidget(selector)
        self.stack.setCurrentWidget(selector)
        def on_accept():
            self.selected_robot_type = selector.selected_robot
            if self.selected_robot_type:
                self.show_robot_view()
        selector.accepted.connect(on_accept)

    def show_robot_view(self):
        # Remove previous robot view if any
        if self.robot_view_widget:
            self.stack.removeWidget(self.robot_view_widget)
            self.robot_view_widget.cleanup()
            self.robot_view_widget.deleteLater()
            self.robot_view_widget = None
        # Create robot based on selection
        if self.selected_robot_type == "go2":
            robot = Robot_Go2(ip=os.environ.get("ROBOT_IP", "192.168.1.190"))
        elif self.selected_robot_type == "dummy":
            robot = Robot_Dummy()
        else:
            raise RuntimeError(f"Unknown robot type: {self.selected_robot_type}")

        # Create robot view widget (no auto-connect)
        robot_widget = RobotViewWidget(robot, self.window, parent=self.window)
        robot_widget.back_to_selector.connect(self.show_selector)

        self.robot_view_widget = robot_widget
        self.stack.addWidget(robot_widget)
        self.stack.setCurrentWidget(robot_widget)

    def run(self):
        self.setup()
        return self.app.exec_()

    def cleanup(self):
        if self.controller:
            self.controller.cleanup()
        if self.camera:
            self.camera.cleanup()

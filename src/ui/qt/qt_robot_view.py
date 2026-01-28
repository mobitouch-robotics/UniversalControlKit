from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor
from .qt_camera import QtCameraView
from .qt_top_panel import QtTopPanel


class RobotViewWidget(QWidget):
    def keyPressEvent(self, event):
        from .qt_controller import qt_key_to_universal

        key = qt_key_to_universal(event)
        handled = False
        for controller in self._movement_controllers:
            if hasattr(controller, "handle_key_press"):
                if controller.handle_key_press(key):
                    handled = True
        if not handled:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        from .qt_controller import qt_key_to_universal

        key = qt_key_to_universal(event)
        handled = False
        for controller in self._movement_controllers:
            if hasattr(controller, "handle_key_release"):
                if controller.handle_key_release(key):
                    handled = True
        if not handled:
            super().keyReleaseEvent(event)

    def cleanup(self):
        # Clean up camera view observer
        if hasattr(self, "camera_view") and hasattr(self.camera_view, "cleanup"):
            try:
                self.camera_view.cleanup()
            except Exception:
                pass
        # Clean up bottom panel observer
        if hasattr(self, "bottom_panel") and hasattr(self.bottom_panel, "cleanup"):
            try:
                self.bottom_panel.cleanup()
            except Exception:
                pass

    def __init__(self, robot, qt_app, parent=None, back_action=None):
        super().__init__(parent)
        self.robot = robot
        self.qt_app = qt_app
        self.back_action = back_action
        self._movement_controllers = []
        self.setFocusPolicy(Qt.StrongFocus)
        self._setup_colors()
        self._setup_main_layout()
        self._register_robot_observer()
        self.setup_movement()

    def setup_movement(self):
        """Initialize and connect movement controllers. Supports multiple controllers."""
        from .qt_controller import QtMovementController
        from .qt_gamepad_controller import GamepadMovementController

        qt_controller = QtMovementController(self.robot, self)
        qt_controller.setup()
        self._movement_controllers.append(qt_controller)

        gamepad_controller = GamepadMovementController(self.robot)
        gamepad_controller.setup()
        self._movement_controllers.append(gamepad_controller)

    def showEvent(self, event):
        super().showEvent(event)
        # Auto-connect to robot if not connected
        if not getattr(self.robot, "is_connected", False):
            if hasattr(self.robot, "connect") and callable(self.robot.connect):
                self.robot.connect()

    def _setup_colors(self):
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#303032"))
        self.setAutoFillBackground(True)
        self.setPalette(palette)

    def _register_robot_observer(self):
        """Register observer for robot updates (to be implemented)."""
        pass

    def _setup_main_layout(self):
        """Set up the main layout with true overlay using absolute positioning."""
        self._setup_camera()
        self._setup_overlay()
        self.camera_widget.setParent(self)
        self.overlay_widget.setParent(self)
        self.camera_widget.show()
        self.overlay_widget.show()
        self.overlay_widget.raise_()

    def _setup_camera(self):
        """Create and add the camera view as the bottom view (fills parent)."""
        self.camera_view = QtCameraView(self.robot, self)
        self.camera_view.setup()
        self.camera_widget = self.camera_view.get_widget()

    # Do not set WA_TransparentForMouseEvents so overlay is interactive
    # No need for manual geometry management with layout stacking

    def _setup_overlay(self):
        """Create a vertical stack overlay and add it on top of the camera view."""
        self.overlay_widget = QWidget(self)
        self.overlay_widget.setStyleSheet("background: transparent;")
        self.overlay_layout = QVBoxLayout()
        self.overlay_layout.setContentsMargins(0, 0, 0, 0)
        self.overlay_layout.setSpacing(0)
        self.overlay_widget.setLayout(self.overlay_layout)

        # Add TopPanel at the top of the overlay
        self.top_panel = QtTopPanel(
            self, title="Robot View", qt_app=self.qt_app, back_action=self._on_back
        )
        self.overlay_layout.addWidget(self.top_panel)
        # Add a vertical spacer to take up remaining space
        from PyQt5.QtWidgets import QSpacerItem, QSizePolicy

        self.overlay_layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )
        # Add RobotBottomPanel at the bottom
        from .robot_bottom_panel import RobotBottomPanel

        self.bottom_panel = RobotBottomPanel(self.robot, self)
        self.overlay_layout.addWidget(self.bottom_panel)

    def resizeEvent(self, event):
        # Ensure camera and overlay widgets always fill the parent
        if hasattr(self, "camera_widget"):
            self.camera_widget.setGeometry(0, 0, self.width(), self.height())
        if hasattr(self, "overlay_widget"):
            self.overlay_widget.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def _on_back(self, *args, **kwargs):
        """Handle back action from the top panel."""
        if self.back_action:
            self.back_action()
        else:
            print(
                "[DEBUG] Back action triggered in RobotViewWidget (no back_action set)"
            )

    def resizeEvent(self, event):
        # Ensure camera and overlay widgets always fill the parent
        if hasattr(self, "camera_widget"):
            self.camera_widget.setGeometry(0, 0, self.width(), self.height())
        if hasattr(self, "overlay_widget"):
            self.overlay_widget.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor
from .qt_camera import QtCameraView
from .qt_top_panel import QtTopPanel
from .qt_controller import QtMovementController
from .qt_gamepad_controller import GamepadMovementController
from .qt_controller import qt_key_to_universal
from PyQt5.QtWidgets import QSpacerItem, QSizePolicy
from .qt_controller import qt_key_to_universal


class RobotViewWidget(QWidget):

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
        # self.setup_movement()  # Only call when robot is connected

    def cleanup(self):
        # On view close: stop movement immediately and schedule a delayed stand_down
        try:
            # If a stand_down has already been scheduled (e.g. via explicit disconnect), skip
            scheduled = getattr(self.robot, "_stand_down_scheduled", False)
            if not scheduled:
                try:
                    if hasattr(self.robot, "move") and callable(self.robot.move):
                        try:
                            self.robot.move(0, 0, 0)
                        except Exception:
                            pass
                except Exception:
                    pass

                try:
                    # mark scheduled so bottom panel won't double-schedule
                    self.robot._stand_down_scheduled = True
                except Exception:
                    pass

                try:
                    from PyQt5.QtCore import QTimer

                    def _do_stand_down():
                        try:
                            if hasattr(self.robot, "stand_down") and callable(self.robot.stand_down):
                                self.robot.stand_down()
                        finally:
                            try:
                                self.robot._stand_down_scheduled = False
                            except Exception:
                                pass

                    QTimer.singleShot(1000, _do_stand_down)
                except Exception:
                    pass
        except Exception:
            pass

        self.camera_view.cleanup()
        self.bottom_panel.cleanup()
        self.cleanup_movement_controllers()

    def cleanup_movement_controllers(self):
        for controller in self._movement_controllers:
            controller.cleanup()
        self._movement_controllers = []

    def setup_movement(self):
        """Initialize and connect movement controllers. Supports multiple controllers."""
        qt_controller = QtMovementController(self.robot, self)
        qt_controller.setup()
        self._movement_controllers.append(qt_controller)

        # Create a GamepadMovementController for every configured joystick controller.
        # If none configured, fall back to a default controller that connects
        # to the first available joystick.
        try:
            from src.ui.controllers_repository import ControllersRepository

            repo = ControllersRepository()
            joystick_cfgs = []
            for c in repo.get_controllers():
                try:
                    if c.type.name == 'JOYSTICK':
                        joystick_cfgs.append(c)
                except Exception:
                    continue

            if joystick_cfgs:
                for cfg in joystick_cfgs:
                    try:
                        gamepad_controller = GamepadMovementController(self.robot, cfg)
                        gamepad_controller.setup()
                        self._movement_controllers.append(gamepad_controller)
                    except Exception:
                        # ignore failing controller setups and continue
                        continue
            else:
                # No configured joysticks: create a fallback controller that will
                # attempt to connect to the first available physical joystick.
                gamepad_controller = GamepadMovementController(self.robot, None)
                gamepad_controller.setup()
                self._movement_controllers.append(gamepad_controller)
        except Exception:
            # As a final fallback, try a default controller
            try:
                gamepad_controller = GamepadMovementController(self.robot, None)
                gamepad_controller.setup()
                self._movement_controllers.append(gamepad_controller)
            except Exception:
                pass

    def _setup_colors(self):
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#303032"))
        self.setAutoFillBackground(True)
        self.setPalette(palette)

    def _register_robot_observer(self):
        """Register observer for robot status changes (connection state)."""
        self.robot.add_status_observer(self._on_robot_status_change)

    def _unregister_robot_observer(self):
        """Unregister observer for robot status changes."""
        self.robot.remove_status_observer(self._on_robot_status_change)

    def _on_robot_status_change(self, robot):
        # Called when robot status changes; check connection state
        connected = getattr(robot, "is_connected", False)
        self._on_robot_connection_change(connected)

    def _on_robot_connection_change(self, connected):
        if connected:
            if not self._movement_controllers:
                self.setup_movement()
        else:
            self.cleanup_movement_controllers()

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

        self.overlay_layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        )
        # Add RobotBottomPanel at the bottom
        from .robot_bottom_panel import RobotBottomPanel
        from .qt_dualsense_overlay import QtDualSenseOverlay

        self.bottom_panel = RobotBottomPanel(
            self.robot, self,
            show_controller_callback=self._show_dualsense_overlay,
        )
        self.overlay_layout.addWidget(self.bottom_panel)

        # DualSense full-screen overlay (hidden by default, parented to self)
        self.dualsense_overlay = QtDualSenseOverlay(self)

    def _show_dualsense_overlay(self, controller_cfg=None):
        self.dualsense_overlay.set_controller(controller_cfg)
        self.dualsense_overlay.setGeometry(0, 0, self.width(), self.height())
        self.dualsense_overlay.show()

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
        self.camera_widget.setGeometry(0, 0, self.width(), self.height())
        self.overlay_widget.setGeometry(0, 0, self.width(), self.height())
        # Keep the DualSense overlay covering the full view when visible
        if hasattr(self, "dualsense_overlay"):
            self.dualsense_overlay.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return
        qt_key = event.key()
        key = qt_key_to_universal(event)
        handled = False
        for controller in self._movement_controllers:
            if hasattr(controller, "handle_key_press"):
                if controller.handle_key_press(qt_key):
                    handled = True
                elif controller.handle_key_press(key):
                    handled = True
        if not handled:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            return
        qt_key = event.key()
        key = qt_key_to_universal(event)
        handled = False
        for controller in self._movement_controllers:
            if hasattr(controller, "handle_key_release"):
                if controller.handle_key_release(qt_key):
                    handled = True
                elif controller.handle_key_release(key):
                    handled = True
        if not handled:
            super().keyReleaseEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        # Auto-connect to robot if not connected
        if not self.robot.is_connected and not self.robot.is_connecting:
            self.robot.connect()
            return
        else:
            self.setup_movement()

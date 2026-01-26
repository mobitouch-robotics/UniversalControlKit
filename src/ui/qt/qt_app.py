from __future__ import annotations

import sys, os
from .qt_robot_selector import QtRobotSelector
from PyQt5.QtWidgets import (
    QStackedWidget,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
)
from PyQt5.QtCore import pyqtSignal, Qt
from time import monotonic
from .qt_camera import QtCameraView
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from .qt_controller import QtMovementController
from src.robot.robot_go2 import Robot_Go2
from src.robot.robot_dummy import Robot_Dummy
import threading


def _apply_windows_dark_titlebar(win, enable: bool = True):
    """Best-effort: request Windows use an immersive dark title bar for a window.

    This uses DwmSetWindowAttribute where available. It's best-effort and
    intentionally swallows errors so it won't break non-Windows platforms.
    """
    try:
        import platform

        if platform.system() != "Windows":
            return
        import ctypes
        from ctypes import wintypes

        # Try the modern attribute value and fall back to the older one.
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20 = 19

        hwnd = int(win.winId())
        dwmapi = ctypes.windll.dwmapi
        val = ctypes.c_int(1 if enable else 0)
        res = dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            ctypes.c_int(DWMWA_USE_IMMERSIVE_DARK_MODE),
            ctypes.byref(val),
            ctypes.sizeof(val),
        )
        if res != 0:
            try:
                dwmapi.DwmSetWindowAttribute(
                    wintypes.HWND(hwnd),
                    ctypes.c_int(DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20),
                    ctypes.byref(val),
                    ctypes.sizeof(val),
                )
            except Exception:
                pass
    except Exception:
        # Nothing to do on failure ÔÇö keep application usable.
        pass


def _try_enable_windows_uxtheme_dark(hwnd: int | None = None):
    """Attempt to enable Windows 'dark mode' for the process/window using uxtheme.

    This is best-effort ÔÇö the functions used are present on newer Windows
    versions and may be absent on older ones. Failures are silently ignored.
    """
    try:
        import platform

        if platform.system() != "Windows":
            return
        import ctypes
        from ctypes import wintypes

        uxtheme = ctypes.WinDLL("uxtheme")

        # Try SetPreferredAppMode if available (newer Windows 10+)
        try:
            SetPreferredAppMode = uxtheme.SetPreferredAppMode
            SetPreferredAppMode.argtypes = [ctypes.c_int]
            SetPreferredAppMode.restype = ctypes.c_int
            # 1 is the value commonly used for 'AllowDark'
            try:
                SetPreferredAppMode(1)
            except Exception:
                pass
        except Exception:
            pass

        # Try AllowDarkModeForApp if present
        try:
            AllowDarkModeForApp = uxtheme.AllowDarkModeForApp
            AllowDarkModeForApp.argtypes = [wintypes.BOOL]
            AllowDarkModeForApp.restype = wintypes.BOOL
            try:
                AllowDarkModeForApp(True)
            except Exception:
                pass
        except Exception:
            pass

        # Try AllowDarkModeForWindow for the specific HWND if provided
        if hwnd is not None:
            try:
                AllowDarkModeForWindow = uxtheme.AllowDarkModeForWindow
                AllowDarkModeForWindow.argtypes = [wintypes.HWND, wintypes.BOOL]
                AllowDarkModeForWindow.restype = wintypes.BOOL
                try:
                    AllowDarkModeForWindow(wintypes.HWND(int(hwnd)), True)
                except Exception:
                    pass
            except Exception:
                pass
    except Exception:
        pass


class QtMainWindow(QMainWindow):
    def event(self, event):
        from PyQt5.QtCore import QEvent, Qt

        # Map maximize to full screen on Windows/Linux and handle leaving full screen
        if event.type() == QEvent.WindowStateChange:
            try:
                # Prefer using the event's oldState/newState when available to
                # detect a user-triggered maximize (transition to maximized).
                old_state = 0
                try:
                    old_state = event.oldState()
                except Exception:
                    old_state = 0
                new_state = self.windowState()

                # If user just maximized the window (and it wasn't maximized before),
                # treat that as a request for full screen unless we're in a debounce window
                # (i.e. we just exited fullscreen programmatically).
                if (new_state & Qt.WindowMaximized) and not (
                    old_state & Qt.WindowMaximized
                ):
                    try:
                        now = monotonic()
                    except Exception:
                        now = 0
                    if now < getattr(self, "_ignore_maximize_until", 0):
                        # Skip mapping to full screen because we recently exited it.
                        pass
                    else:
                        try:
                            self._enter_fullscreen()
                        except Exception:
                            try:
                                self.setWindowFlags(
                                    self.windowFlags()
                                    | Qt.FramelessWindowHint
                                    | Qt.WindowStaysOnTopHint
                                )
                                self.showFullScreen()
                            except Exception:
                                pass

                # If we were in full screen but now are not, restore flags and show normal.
                if (old_state & Qt.WindowFullScreen) and not (
                    new_state & Qt.WindowFullScreen
                ):
                    # Leaving fullscreen: force a normal (non-maximized) window state.
                    try:
                        self._exit_fullscreen()
                    except Exception:
                        # Fallback: clear flags and show normal
                        try:
                            self.setWindowFlags(
                                self.windowFlags()
                                & ~Qt.FramelessWindowHint
                                & ~Qt.WindowStaysOnTopHint
                            )
                        except Exception:
                            pass
                        try:
                            self.setWindowState(Qt.WindowNoState)
                        except Exception:
                            pass
                        try:
                            self.showNormal()
                        except Exception:
                            pass
            except Exception:
                pass
        return super().event(event)

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        # When we programmatically exit fullscreen, ignore immediate
        # maximize events for a short period to avoid re-entering fullscreen.
        self._ignore_maximize_until = 0.0
        # Remember normal (non-fullscreen) geometry so we can restore it
        # after leaving fullscreen. Initialize to None and set on first show/resize.
        self._saved_geometry = None
        self._saved_window_state = None

    def _enter_fullscreen(self):
        """Save current normal geometry and enter fullscreen (frameless).

        This records geometry/state so we can restore it when exiting fullscreen.
        """
        from PyQt5.QtCore import Qt as _Qt

        try:
            # Save geometry/state if not already saved and if we're not currently fullscreen
            if not self.isFullScreen():
                try:
                    self._saved_geometry = self.saveGeometry()
                except Exception:
                    self._saved_geometry = None
                try:
                    # QMainWindow.saveState may exist; wrap in try
                    self._saved_window_state = self.saveState()
                except Exception:
                    self._saved_window_state = None
        except Exception:
            pass

        try:
            self.setWindowFlags(
                self.windowFlags() | _Qt.FramelessWindowHint | _Qt.WindowStaysOnTopHint
            )
        except Exception:
            pass
        try:
            self.showFullScreen()
        except Exception:
            try:
                self.show()
            except Exception:
                pass

    def _exit_fullscreen(self):
        """Ensure the window leaves fullscreen and is not left maximized.

        This clears frameless/stay-on-top flags, forces WindowNoState and
        calls showNormal(). It also schedules a short single-shot to
        re-apply WindowNoState/showNormal after the event loop settles,
        which prevents some window managers from restoring a maximized
        state immediately.
        """
        from PyQt5.QtCore import QTimer, Qt as _Qt

        try:
            # Clear fullscreen-like flags so decorations come back
            self.setWindowFlags(
                self.windowFlags()
                & ~_Qt.FramelessWindowHint
                & ~_Qt.WindowStaysOnTopHint
            )
        except Exception:
            pass
        try:
            self.setWindowState(_Qt.WindowNoState)
        except Exception:
            pass
        # Restore to a centered 800x600 normal window (simpler, predictable behavior)
        try:
            width, height = 800, 600
            geom = None
            try:
                from PyQt5.QtWidgets import QApplication

                screen = QApplication.primaryScreen()
                if screen:
                    try:
                        geom = screen.availableGeometry()
                    except Exception:
                        geom = None
            except Exception:
                geom = None

            if geom:
                x = geom.x() + max(0, (geom.width() - width) // 2)
                y = geom.y() + max(0, (geom.height() - height) // 2)
                try:
                    self.setGeometry(x, y, width, height)
                except Exception:
                    try:
                        self.resize(width, height)
                        self.move(x, y)
                    except Exception:
                        pass
            else:
                try:
                    self.resize(width, height)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.showNormal()
        except Exception:
            try:
                self.show()
            except Exception:
                pass

        # Short debounce and guarantee normal state after the event loop.
        try:
            self._ignore_maximize_until = monotonic() + 0.7
        except Exception:
            pass
        try:
            QTimer.singleShot(
                60, lambda: (self.setWindowState(_Qt.WindowNoState), self.showNormal())
            )
        except Exception:
            pass

    def resizeEvent(self, event):
        # Track user resizing when not fullscreen so we remember the preferred normal size
        try:
            if not self.isFullScreen():
                try:
                    self._saved_geometry = self.saveGeometry()
                except Exception:
                    pass
                try:
                    self._saved_window_state = self.saveState()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            super().resizeEvent(event)
        except Exception:
            pass

    def moveEvent(self, event):
        # Track user moving when not fullscreen so we remember the preferred normal position
        try:
            if not self.isFullScreen():
                try:
                    self._saved_geometry = self.saveGeometry()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            super().moveEvent(event)
        except Exception:
            pass

    def keyPressEvent(self, event):
        """Override to handle key press events."""
        from PyQt5.QtCore import Qt as _Qt

        # Allow Esc/F11 to exit or toggle full screen regardless of controller
        try:
            k = event.key()
            if k == _Qt.Key_Escape and self.isFullScreen():
                try:
                    self._exit_fullscreen()
                except Exception:
                    try:
                        self.showNormal()
                    except Exception:
                        pass
                return
            if k == _Qt.Key_F11:
                try:
                    if self.isFullScreen():
                        self._exit_fullscreen()
                    else:
                        try:
                            self._enter_fullscreen()
                        except Exception:
                            try:
                                self.setWindowFlags(
                                    self.windowFlags()
                                    | _Qt.FramelessWindowHint
                                    | _Qt.WindowStaysOnTopHint
                                )
                            except Exception:
                                pass
                            try:
                                self.showFullScreen()
                            except Exception:
                                pass
                except Exception:
                    pass
                return
        except Exception:
            pass

        if self.controller:
            self.controller.handle_key_press(event)
        # If controller accepted the event, don't pass to default handlers
        try:
            if event.isAccepted():
                return
        except Exception:
            pass
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Override to handle key release events."""
        if self.controller:
            self.controller.handle_key_release(event)
        try:
            if event.isAccepted():
                return
        except Exception:
            pass
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

        # --- Button style logic (copied from Exit button in selector) ---
        is_dark = False
        try:
            from PyQt5.QtWidgets import QApplication
            from PyQt5.QtGui import QPalette
            app = QApplication.instance()
            if app is not None:
                try:
                    bg = app.palette().color(QPalette.Window)
                    is_dark = bg.lightness() < 128
                except Exception:
                    is_dark = False
        except Exception:
            is_dark = False
        # Fallback: on Windows query system preference via registry
        if not is_dark:
            try:
                import platform
                if platform.system() == "Windows":
                    import winreg
                    key = winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                    )
                    val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    is_dark = val == 0
            except Exception:
                pass

        # --- Create buttons ---
        back_btn = QPushButton("\u2190 Back to Robot Selection")
        back_btn.setFixedWidth(220)
        if is_dark:
            back_btn.setStyleSheet(
                "QPushButton { background-color: #424242; color: white; border-radius: 10px; padding: 10px; }"
                "QPushButton:hover { background-color: #3a3a3a; }"
                "QPushButton:pressed { background-color: #333333; }"
            )
        back_btn.clicked.connect(self._on_back)
        top_row.addWidget(back_btn)

        top_row.addSpacing(16)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setFixedWidth(120)
        if is_dark:
            self.connect_btn.setStyleSheet(
                "QPushButton { background-color: #424242; color: white; border-radius: 10px; padding: 10px; }"
                "QPushButton:hover { background-color: #3a3a3a; }"
                "QPushButton:pressed { background-color: #333333; }"
            )
        self.connect_btn.clicked.connect(self._on_connect)
        top_row.addWidget(self.connect_btn)

        top_row.addSpacing(8)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setFixedWidth(120)
        if is_dark:
            self.disconnect_btn.setStyleSheet(
                "QPushButton { background-color: #424242; color: white; border-radius: 10px; padding: 10px; }"
                "QPushButton:hover { background-color: #3a3a3a; }"
                "QPushButton:pressed { background-color: #333333; }"
            )
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
        from PyQt5.QtGui import QPalette, QColor

        # On Windows, detect system dark mode and apply a dark palette so
        # the application matches the user's preference. Keep `is_dark`
        # available so we can also request a dark title bar from DWM.
        is_dark = False
        try:
            import platform

            if platform.system() == "Windows":
                try:
                    import winreg

                    key = winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                    )
                    val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    is_dark = val == 0
                except Exception:
                    is_dark = False
            else:
                is_dark = False
        except Exception:
            is_dark = False

        if is_dark:
            try:
                palette = QPalette()
                # From Qt docs: a reasonable dark palette
                palette.setColor(QPalette.Window, QColor(53, 53, 53))
                palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
                palette.setColor(QPalette.Base, QColor(35, 35, 35))
                palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
                palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
                palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
                palette.setColor(QPalette.Text, QColor(255, 255, 255))
                palette.setColor(QPalette.Button, QColor(53, 53, 53))
                palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
                palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
                palette.setColor(QPalette.Link, QColor(42, 130, 218))
                palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
                palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
                self.app.setPalette(palette)
            except Exception:
                pass

        # Create main window and stacked widget
        # Before creating the window, try to enable app-level dark mode so
        # titlebar icons follow the dark theme when possible.
        try:
            if is_dark:
                _try_enable_windows_uxtheme_dark(None)
        except Exception:
            pass

        self.window = QtMainWindow(None)
        # If on Windows and the system uses dark mode, request a dark
        # title bar from DWM (best-effort; may not be supported on older
        # Windows versions). Also try to enable dark mode for the specific
        # window HWND so caption buttons render correctly.
        try:
            if is_dark:
                try:
                    _try_enable_windows_uxtheme_dark(self.window.winId())
                except Exception:
                    pass
                try:
                    _apply_windows_dark_titlebar(self.window, True)
                except Exception:
                    pass
        except Exception:
            pass
        self.window.setWindowTitle("MobiTouchRobots")
        self.window.resize(800, 600)
        self.stack = QStackedWidget()
        self.window.setCentralWidget(self.stack)

        # (Menu removed ÔÇö selector is shown by UI flow)

        # Show selector at startup
        self.show_selector()
        import platform

        if platform.system() == "Darwin":
            # Use native macOS animation and controls
            try:
                self.window._enter_fullscreen()
            except Exception:
                try:
                    self.window.showFullScreen()
                except Exception:
                    pass
        else:
            try:
                self.window._enter_fullscreen()
            except Exception:
                from PyQt5.QtCore import Qt

                try:
                    self.window.setWindowFlags(
                        self.window.windowFlags()
                        | Qt.FramelessWindowHint
                        | Qt.WindowStaysOnTopHint
                    )
                except Exception:
                    pass
                try:
                    self.window.showFullScreen()
                except Exception:
                    pass

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

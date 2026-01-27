import sys
from PyQt5.QtWidgets import QApplication
from .qt_main_window import QtMainWindow
from ..protocols import UIApp, _ExitCode

class QtApp(UIApp):
    def __init__(self):
        self.app = None
        self.window = None

    def setup(self):
        self.app = QApplication(sys.argv)
        # Create main window and stacked widget (no platform-specific theming)
        self.window = QtMainWindow(None)
        self.window.setWindowTitle("MobiTouchRobots")
        self.window.resize(800, 600)
        self.window.show()
        # Connect window-level exited signal to application quit
        self.window.exited.connect(lambda: self.app.quit())
        
    def run(self) -> _ExitCode:
        try:
            self.setup()
            return self.app.exec_()
        except Exception as e:
            try:
                print(f"qt_app: run failed: {e}", file=sys.stderr)
            except Exception:
                pass
            return 1
        finally:
            try:
                self.cleanup()
            except Exception:
                pass

    def cleanup(self):
        # If a robot view is active on the window, ask it to cleanup
        if self.window and getattr(self.window, "robot_view_widget", None):
            self.window.robot_view_widget.cleanup()

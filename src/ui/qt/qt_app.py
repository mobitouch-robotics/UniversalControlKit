from __future__ import annotations

import sys
from PyQt5.QtWidgets import QApplication
from .qt_main_window import QtMainWindow
from ..protocols import UIApp

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
        self.window.show_selector(on_exit=lambda: self.app.quit())
        
    def run(self):
        self.setup()
        try:
            return self.app.exec_()
        finally:
            self.cleanup()

    def cleanup(self):
        # If a robot view is active on the window, ask it to cleanup
        try:
            if self.window and getattr(self.window, "robot_view_widget", None):
                try:
                    self.window.robot_view_widget.cleanup()
                except Exception:
                    pass
        except Exception:
            pass

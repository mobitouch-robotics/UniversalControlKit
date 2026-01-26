from typing import Optional, Callable

from PyQt5.QtWidgets import QMainWindow, QStackedWidget, QApplication
from PyQt5.QtCore import Qt, QEvent

from .qt_robot_selector import QtRobotSelector
from .qt_robot_view import RobotViewWidget
from src.robot.robot_go2 import Robot_Go2
from src.robot.robot_dummy import Robot_Dummy


class QtMainWindow(QMainWindow):
    def event(self, event):
        # Use default event handling; fullscreen mapping removed.
        return super().event(event)

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        # Placeholder for future window-state handling
        self._ignore_maximize_until = 0.0
        # Create a stacked widget owned by the main window to manage views
        try:
            self.stack = QStackedWidget()
            self.setCentralWidget(self.stack)
        except Exception:
            self.stack = None
        self.selected_robot_type = None
        self.robot = None
        self.robot_view_widget = None
        self._on_exit_callback = None

    def resizeEvent(self, event):
        try:
            super().resizeEvent(event)
        except Exception:
            pass

    def moveEvent(self, event):
        try:
            super().moveEvent(event)
        except Exception:
            pass

    def keyPressEvent(self, event):
        if self.controller:
            try:
                self.controller.handle_key_press(event)
            except Exception:
                pass
        try:
            if event.isAccepted():
                return
        except Exception:
            pass
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if self.controller:
            try:
                self.controller.handle_key_release(event)
            except Exception:
                pass
        try:
            if event.isAccepted():
                return
        except Exception:
            pass
        super().keyReleaseEvent(event)

    # View management helpers
    def set_view(self, widget):
        try:
            if self.stack is None:
                return
            # clear existing widgets
            while self.stack.count() > 0:
                w = self.stack.widget(0)
                self.stack.removeWidget(w)
                try:
                    w.deleteLater()
                except Exception:
                    pass
            self.stack.addWidget(widget)
            self.stack.setCurrentWidget(widget)
        except Exception:
            pass

    def push_view(self, widget):
        try:
            if self.stack is None:
                return
            self.stack.addWidget(widget)
            self.stack.setCurrentWidget(widget)
        except Exception:
            pass

    # Window-centric navigation
    def show_selector(self, on_exit: Optional[Callable] = None):
        try:
            self._on_exit_callback = on_exit
            selector = QtRobotSelector(self)
            selector.selected.connect(lambda rt: self.show_robot_view(rt))
            selector.exited.connect(lambda: (on_exit() if on_exit else QApplication.quit()))
            self.set_view(selector)
        except Exception:
            pass

    def show_robot_view(self, robot_type: str):
        try:
            self.selected_robot_type = robot_type
            if robot_type == "go2":
                self.robot = Robot_Go2(ip=None)
            elif robot_type == "dummy":
                self.robot = Robot_Dummy()
            else:
                raise RuntimeError(f"Unknown robot type: {robot_type}")

            # create robot view and show it
            self.robot_view_widget = RobotViewWidget(self.robot, self)
            self.robot_view_widget.back_to_selector.connect(lambda: self.show_selector(self._on_exit_callback))
            self.set_view(self.robot_view_widget)
        except Exception:
            pass

from .qt_add_robot_view import QtAddRobotView
from PyQt5.QtCore import (
    pyqtSignal,
    QPropertyAnimation,
    QParallelAnimationGroup,
    QEasingCurve,
)
from PyQt5.QtWidgets import QMainWindow, QStackedWidget, QGraphicsOpacityEffect, QMessageBox
from .qt_robot_selector import QtRobotSelector
from .qt_robot_view import RobotViewWidget
from .qt_edit_robot_view import EditRobotView


class QtMainWindow(QMainWindow):

    exited = pyqtSignal()
    maximized = pyqtSignal()

    def __init__(self, qt_app, controller=None):
        super().__init__()
        self.controller = controller
        self.qt_app = qt_app
        # Create a stacked widget owned by the main window to manage views
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.robot_view_widget = None
        self._initial_view_shown = False

    def keyPressEvent(self, event):
        if self.controller is not None:
            self.controller.handle_key_press(event)
            if event.isAccepted():
                return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if self.controller is not None:
            self.controller.handle_key_release(event)
            if event.isAccepted():
                return
        super().keyReleaseEvent(event)

    # View management helpers
    def set_view(self, widget):
        # clear existing widgets
        while self.stack.count() > 0:
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)

    def push_view(self, widget):
        # Animate the transition sliding left-to-right for a forward push
        self.stack.addWidget(widget)
        self.animate_transition(widget, forward=True)

    def pop_view(self, pop_to_root=False):
        """
        Remove the current view and return to the previous one, calling cleanup on the popped view.
        If pop_to_root is True, remove all views except the first and animate transition directly to it.
        """
        if self.stack.count() <= 1:
            return
        if pop_to_root:
            root_widget = self.stack.widget(0)
            current_widget = self.stack.currentWidget()
            if current_widget is root_widget:
                return
            # Remove all widgets except root and current, so animation can run
            widgets_to_remove = [
                self.stack.widget(i)
                for i in range(1, self.stack.count())
                if self.stack.widget(i) is not current_widget
            ]
            for w in widgets_to_remove:
                self.stack.removeWidget(w)
                if hasattr(w, "cleanup"):
                    w.cleanup()
                w.deleteLater()
            # Animate transition to root_widget
            self.animate_transition(root_widget, forward=False)
        else:
            current_index = self.stack.currentIndex()
            prev_index = max(0, current_index - 1)
            prev_widget = self.stack.widget(prev_index)
            # Animate transition sliding right-to-left for a pop (reverse)
            self.animate_transition(prev_widget, forward=False)

    def animate_transition(self, new_widget, forward=True, duration=300):
        """Animate slide transition between current widget and new_widget.

        forward=True: new_widget slides in from right, current slides out left.
        forward=False: new_widget slides in from left, current slides out right.
        """
        current = self.stack.currentWidget()
        if current is None or new_widget is None or current is new_widget:
            self.stack.setCurrentWidget(new_widget)
            return

        stack_rect = self.stack.rect()
        w = stack_rect.width()
        h = stack_rect.height()
        if w == 0:
            w = self.stack.size().width()
            h = self.stack.size().height()

        # Position new_widget off-screen (right for push, left for pop)
        start_x = w if forward else -w
        end_x = 0
        current_end_x = -w if forward else w

        new_widget.setParent(self.stack)
        new_widget.setGeometry(start_x, 0, w, h)
        new_widget.show()

        # Animate geometry (slide) and opacity for both widgets
        anim_new_pos = QPropertyAnimation(new_widget, b"geometry")
        anim_new_pos.setDuration(duration)
        anim_new_pos.setStartValue(new_widget.geometry())
        anim_new_pos.setEndValue(self.stack.rect())
        anim_new_pos.setEasingCurve(QEasingCurve.OutCubic)

        anim_current_pos = QPropertyAnimation(current, b"geometry")
        anim_current_pos.setDuration(duration)
        anim_current_pos.setStartValue(current.geometry())
        anim_current_pos.setEndValue(current.geometry().translated(current_end_x, 0))
        anim_current_pos.setEasingCurve(QEasingCurve.OutCubic)

        # Opacity animations (optional, for smoothness)
        new_effect = new_widget.graphicsEffect()
        if not isinstance(new_effect, QGraphicsOpacityEffect):
            new_effect = QGraphicsOpacityEffect(new_widget)
            new_widget.setGraphicsEffect(new_effect)
        new_effect.setOpacity(1.0)

        current_effect = current.graphicsEffect()
        if not isinstance(current_effect, QGraphicsOpacityEffect):
            current_effect = QGraphicsOpacityEffect(current)
            current.setGraphicsEffect(current_effect)
        current_effect.setOpacity(1.0)

        group = QParallelAnimationGroup(self)
        group.addAnimation(anim_new_pos)
        group.addAnimation(anim_current_pos)

        # Keep reference so GC doesn't stop the animation
        self._current_animation = group

        def _on_finished():
            try:
                self.stack.setCurrentWidget(new_widget)
                # Reset geometry of widgets
                new_widget.setGeometry(0, 0, w, h)
                current.setGeometry(0, 0, w, h)
                if not forward:
                    self.stack.removeWidget(current)
                    if hasattr(current, "cleanup"):
                        current.cleanup()
                    current.deleteLater()
            finally:
                self._current_animation = None

        group.finished.connect(_on_finished)
        group.start()

    # Window-centric navigation
    def _show_disclaimer(self):
        from .qt_disclaimer_view import QtDisclaimerView

        disclaimer = QtDisclaimerView(
            on_accept=self.show_selector,
            on_discard=self.close,
            parent=self,
        )
        self.set_view(disclaimer)

    def show_selector(self):
        selector = QtRobotSelector(self, qt_app=self.qt_app)
        selector.selected.connect(lambda robot: self.show_robot_view(robot))
        def _on_edit_requested(obj):
            # Dispatch to appropriate editor based on object type
            from src.ui.controller_config import ControllerConfig

            if isinstance(obj, ControllerConfig):
                # Open controller editor
                from .qt_edit_controller_view import EditControllerView

                self.push_view(EditControllerView(obj, parent=self, back_action=self.pop_view, qt_app=self.qt_app))
            else:
                # Assume robot
                self.show_edit_robot_view(obj)

        selector.edit_requested.connect(_on_edit_requested)
        selector.exited.connect(lambda: self.exited.emit())
        selector.maximized.connect(lambda: self.maximized.emit())
        selector.add_robot_requested.connect(self.show_add_robot_view)
        selector.add_controller_requested.connect(self.show_add_controller_view)
        self.set_view(selector)

    def show_add_robot_view(self):
        add_view = QtAddRobotView(self, back_action=self.pop_view, qt_app=self.qt_app)
        add_view.robot_class_selected.connect(self.show_edit_robot_view)
        self.push_view(add_view)

    def show_add_controller_view(self):
        from .qt_add_controller_view import QtAddControllerView

        add_view = QtAddControllerView(self, back_action=self.pop_view, qt_app=self.qt_app)
        add_view.controller_added.connect(lambda cfg: None)
        self.push_view(add_view)

    def show_edit_robot_view(self, robot_cls):
        edit_view = EditRobotView(
            robot=robot_cls, parent=self, back_action=self.pop_view, qt_app=self.qt_app
        )
        self.push_view(edit_view)

    def showEvent(self, event):
        if not self._initial_view_shown:
            self._show_disclaimer()
            self._initial_view_shown = True
        super().showEvent(event)

    def show_robot_view(self, robot):
        from src.ui.controllers_repository import ControllersRepository

        try:
            has_controller = len(ControllersRepository().get_controllers()) > 0
        except Exception:
            has_controller = False

        if not has_controller:
            QMessageBox.warning(
                self,
                "No controller configured",
                "Please add at least one controller (keyboard or joystick) before opening robot view.",
            )
            return

        # robot is now an instance, not a type string
        self.robot_view_widget = RobotViewWidget(
            robot, self.qt_app, back_action=self.pop_view
        )
        self.push_view(self.robot_view_widget)
    

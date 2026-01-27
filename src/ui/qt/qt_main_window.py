from PyQt5.QtCore import (
    pyqtSignal,
    QPropertyAnimation,
    QParallelAnimationGroup,
    QEasingCurve,
)
from PyQt5.QtWidgets import QMainWindow, QStackedWidget, QGraphicsOpacityEffect
from .qt_robot_selector import QtRobotSelector
from .qt_robot_view import RobotViewWidget


class QtMainWindow(QMainWindow):

    exited = pyqtSignal()

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        # Create a stacked widget owned by the main window to manage views
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.robot_view_widget = None
        self._selector_shown = False

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

    def pop_view(self):
        """Remove the current view and return to the previous one, calling cleanup on the popped view."""
        if self.stack.count() <= 1:
            return
        current_index = self.stack.currentIndex()
        prev_index = max(0, current_index - 1)
        prev_widget = self.stack.widget(prev_index)
        # Animate transition sliding right-to-left for a pop (reverse)
        self.animate_transition(prev_widget, forward=False)

    def animate_transition(self, new_widget, forward=True, duration=300):
        """Animate slide transition between current widget and new_widget.

        forward=True means new_widget slides in from the right (push).
        forward=False means new_widget slides in from the left (pop/back).
        """
        current = self.stack.currentWidget()
        if current is None or new_widget is None or current is new_widget:
            # Fallback to direct switch
            self.stack.setCurrentWidget(new_widget)
            return

        stack_rect = self.stack.rect()
        w = stack_rect.width()
        h = stack_rect.height()
        if w == 0:
            # fallback to widget size
            w = self.stack.size().width()
            h = self.stack.size().height()

        # Ensure new_widget is parented to the stack and sized to fill it
        new_widget.setParent(self.stack)
        new_widget.setGeometry(0, 0, w, h)
        new_widget.show()

        # Ensure both widgets have an opacity effect we can animate
        new_effect = new_widget.graphicsEffect()
        if not isinstance(new_effect, QGraphicsOpacityEffect):
            new_effect = QGraphicsOpacityEffect(new_widget)
            new_widget.setGraphicsEffect(new_effect)
        new_effect.setOpacity(0.0)

        current_effect = current.graphicsEffect()
        if not isinstance(current_effect, QGraphicsOpacityEffect):
            current_effect = QGraphicsOpacityEffect(current)
            current.setGraphicsEffect(current_effect)
        current_effect.setOpacity(1.0)

        anim_new = QPropertyAnimation(new_effect, b"opacity")
        anim_new.setDuration(duration)
        anim_new.setStartValue(0.0)
        anim_new.setEndValue(1.0)
        anim_new.setEasingCurve(QEasingCurve.OutCubic)

        anim_current = QPropertyAnimation(current_effect, b"opacity")
        anim_current.setDuration(duration)
        anim_current.setStartValue(1.0)
        anim_current.setEndValue(0.0)
        anim_current.setEasingCurve(QEasingCurve.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(anim_new)
        group.addAnimation(anim_current)

        # Keep reference so GC doesn't stop the animation
        self._current_animation = group

        def _on_finished():
            try:
                # finalize the stack state
                self.stack.setCurrentWidget(new_widget)
                # If this was a forward push, keep the old widget in the stack
                # so that `pop_view()` can return to it. Only remove the old
                # widget on a backward/pop transition.
                if not forward:
                    self.stack.removeWidget(current)
                    if hasattr(current, "cleanup"):
                        current.cleanup()
                    current.deleteLater()
                else:
                    # restore opacity of kept widget to full in case reused later
                    current.graphicsEffect().setOpacity(1.0)
            finally:
                self._current_animation = None

        group.finished.connect(_on_finished)
        group.start()

    # Window-centric navigation
    def show_selector(self):
        selector = QtRobotSelector(self)
        selector.selected.connect(lambda robot: self.show_robot_view(robot))
        selector.exited.connect(lambda: self.exited.emit())
        self.set_view(selector)

    def showEvent(self, event):
        if not self._selector_shown:
            self.show_selector()
            self._selector_shown = True
        super().showEvent(event)

    def show_robot_view(self, robot):
        # robot is now an instance, not a type string
        self.robot_view_widget = RobotViewWidget(robot, self)
        self.robot_view_widget.back_to_selector.connect(lambda: self.pop_view())
        self.push_view(self.robot_view_widget)

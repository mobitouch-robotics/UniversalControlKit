from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtGui import QPalette, QColor
from .qt_top_panel import QtTopPanel
from .qt_section import QtSection
from src.robot.robot_repository import iter_robot_implementations
from PyQt5.QtWidgets import QPushButton, QHBoxLayout, QLabel


from PyQt5.QtCore import pyqtSignal, Qt


class QtAddRobotView(QWidget):
    robot_class_selected = pyqtSignal(object)

    def _make_bottom_badge_label(self, text: str, font_size: int = 15):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignLeft)
        label.setStyleSheet(
            f"font-size: {font_size}px; color: #fff; "
            "background: rgba(80, 80, 80, 200); "
            "border-radius: 0px; "
            "border-bottom-left-radius: 12px; border-bottom-right-radius: 12px; "
            "padding: 6px 8px; margin: 0px;"
        )
        return label

    def __init__(self, parent=None, back_action=None, qt_app=None):
        super().__init__(parent)
        self.setup_background()
        self.setStyleSheet(
            "QLabel { color: #fff; }"
            "QPushButton { color: #fff; }"
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.top_panel = QtTopPanel(
            self, back_action=back_action, title="Add new robot", qt_app=qt_app
        )
        layout.addWidget(self.top_panel)

        # Use a grid of robot class panels
        from .qt_grid_section import QtGridSection
        from .qt_panel import QtPanel

        self.robots_grid = QtGridSection(self)
        self._update_robots_grid()
        robot_type_section = QtSection("Robot kind", self.robots_grid)
        robot_type_section.setContentsMargins(16, 0, 16, 0)
        layout.addWidget(robot_type_section)
        layout.addStretch(1)
        self.setLayout(layout)

    def _update_robots_grid(self):
        from PyQt5.QtWidgets import QLabel, QWidget, QVBoxLayout
        from PyQt5.QtCore import Qt
        from .qt_panel import QtPanel
        from src.robot.robot_repository import iter_robot_implementations

        panels = []
        for robot_cls in iter_robot_implementations():
            try:
                name = robot_cls.display_name() if hasattr(robot_cls, "display_name") else robot_cls.__name__
            except Exception:
                name = robot_cls.__name__
            label = self._make_bottom_badge_label(name)
            panel_content = QVBoxLayout()
            panel_content.setContentsMargins(0, 0, 0, 0)
            panel_content.setSpacing(0)
            panel_content.addStretch(1)
            panel_content.addWidget(label)
            panel_widget = QWidget()
            panel_widget.setStyleSheet("background: transparent;")
            panel_widget.setLayout(panel_content)
            background_image = None
            if hasattr(robot_cls, "image") and callable(robot_cls.image):
                img_path = robot_cls.image()
                if img_path:
                    background_image = img_path
            panel = QtPanel(panel_widget, background_image=background_image)
            if panel.layout() is not None:
                panel.layout().setContentsMargins(0, 0, 0, 0)
            panel.setFixedSize(200, 150)
            panel.setCursor(Qt.PointingHandCursor)
            panel.mousePressEvent = (
                lambda event, cls=robot_cls: self.robot_class_selected.emit(cls)
            )
            panels.append(panel)
        self.robots_grid.set_children(panels)

    def setup_background(self):
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#303032"))
        self.setAutoFillBackground(True)
        self.setPalette(palette)

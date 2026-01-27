from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtGui import QPalette, QColor
from .qt_top_panel import QtTopPanel
from .qt_section import QtSection
from src.robot.robot_repository import iter_robot_implementations
from PyQt5.QtWidgets import QPushButton, QHBoxLayout, QLabel


class QtAddRobotView(QWidget):
    def __init__(self, parent=None, back_action=None):
        super().__init__(parent)
        self.setup_background()

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.top_panel = QtTopPanel(self, back_action=back_action)
        layout.addWidget(self.top_panel)

        # Use a grid of robot class panels
        from .qt_grid_section import QtGridSection
        from .qt_panel import QtPanel

        self.robots_grid = QtGridSection(self)
        self._update_robots_grid()
        robot_type_section = QtSection("ROBOT TYPE", self.robots_grid)
        robot_type_section.setContentsMargins(16, 0, 16, 0)
        layout.addWidget(robot_type_section)
        layout.addStretch(1)
        self.setLayout(layout)

    def _update_robots_grid(self):
        from PyQt5.QtWidgets import QLabel
        from PyQt5.QtCore import Qt
        from .qt_panel import QtPanel
        from src.robot.robot_repository import iter_robot_implementations

        panels = []
        for robot_cls in iter_robot_implementations():
            label = QLabel(robot_cls.__name__)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(
                "font-size: 15px; color: #fff; background: transparent;"
            )
            panel = QtPanel(label)
            panel.setFixedSize(140, 100)
            panels.append(panel)
        self.robots_grid.set_children(panels)

    def setup_background(self):
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#303032"))
        self.setAutoFillBackground(True)
        self.setPalette(palette)

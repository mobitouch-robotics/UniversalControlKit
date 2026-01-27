from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
    QGridLayout,
)
from PyQt5.QtCore import Qt, pyqtSignal
from src.robot.robot_repository import RobotRepository
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QSizePolicy,
    QSpacerItem,
)
from PyQt5.QtGui import QPixmap, QPalette, QColor
from .qt_battery_bar import QTBatteryBar
from .qt_panel import QtPanel
from .qt_top_panel import QtTopPanel
from .qt_section import QtSection
from .qt_grid_section import QtGridSection


class QtRobotSelector(QWidget):
    def create_add_robot_panel(self):
        from PyQt5.QtGui import QColor

        add_label = QLabel("+   Add robot")
        add_label.setAlignment(Qt.AlignCenter)
        add_label.setStyleSheet(
            "font-size: 15px; color: #fff; background: transparent;"
        )
        darker_color = QColor(10, 10, 10, 80)
        add_panel = QtPanel(background_color=darker_color)
        add_panel.setFixedSize(140, 100)
        add_panel.setCursor(Qt.PointingHandCursor)
        add_panel.addWidget(add_label)
        add_panel.mousePressEvent = lambda event: self._on_add_robot()
        return add_panel

    add_robot_requested = pyqtSignal()
    selected = pyqtSignal(object)
    exited = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._robot_status_callbacks = []
        self.setup_colors()
        self.setup_layout()
        self._register_robot_observers()

    def _register_robot_observers(self):
        repo = RobotRepository()
        for robot in repo.get_robots():
            cb = self._make_status_callback(robot)
            robot.add_status_observer(cb)
            self._robot_status_callbacks.append((robot, cb))

    def _make_status_callback(self, robot):
        def callback(_):
            self._update_robots_grid()

        return callback

    def _update_robots_grid(self):
        """
        Build and replace children inside self.robots_grid only.
        """
        if not hasattr(self, "robots_grid") or self.robots_grid is None:
            return
        children = self._build_robot_panels()
        children.append(self.create_add_robot_panel())
        self.robots_grid.set_children(children)

    def _update_robot_status(self, robot):
        # Update only the status widgets for this robot
        for battery_bar, battery_label, r in getattr(self, "_status_widgets", []):
            if r is robot:
                connected = getattr(robot, "is_connected", False)
                battery = getattr(robot, "battery_status", 0)
                battery_bar.set_battery(battery, connected)
                if connected:
                    if battery_label is not None:
                        battery_label.setText(f"{battery}%")
                        battery_label.show()
                else:
                    if battery_label is not None:
                        battery_label.hide()

    def cleanup(self):
        # Remove all observers when widget is destroyed
        for robot, cb in getattr(self, "_robot_status_callbacks", []):
            robot.remove_status_observer(cb)
        self._robot_status_callbacks = []

    def _refresh_status(self):
        pass  # No longer needed

    def setup_colors(self):
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#303032"))
        self.setAutoFillBackground(True)
        self.setPalette(palette)

    def robots_view(self):
        # This method sets up and returns a QtSection containing the robots grid and add button
        self.robots_grid = QtGridSection(self)
        self._update_robots_grid()
        section = QtSection("Robots", self.robots_grid)
        section.setContentsMargins(16, 0, 16, 0)
        return section

    def _build_robot_panels(self):
        def build_robot_panel(robot):
            name_label = QLabel(robot.name)
            name_label.setWordWrap(True)
            name_label.setAlignment(Qt.AlignLeft)
            name_label.setStyleSheet(
                "font-size: 12px; color: #fff; background: transparent;"
            )
            panel_content = QVBoxLayout()
            panel_content.setContentsMargins(0, 0, 0, 0)
            panel_content.addWidget(name_label)

            # Always create the battery label, but show only if connected
            battery_label = QLabel()
            battery_label.setAlignment(Qt.AlignLeft)
            battery_label.setStyleSheet(
                "font-size: 11px; color: #bbb; background: transparent;"
            )
            if hasattr(robot, "is_connected") and robot.is_connected:
                battery_label.setText(f"{robot.battery_status}%")
                battery_label.show()
            else:
                battery_label.hide()
            panel_content.addWidget(battery_label)

            panel_content.addStretch(1)
            battery_bar = QTBatteryBar(height=5)
            battery_bar.set_battery(
                getattr(robot, "battery_status", 0),
                getattr(robot, "is_connected", False),
            )
            panel_content.addWidget(battery_bar)
            panel_widget = QWidget()
            panel_widget.setStyleSheet("background: transparent;")
            panel_widget.setLayout(panel_content)
            panel = QtPanel(panel_widget)
            panel.setFixedSize(140, 100)
            panel.setCursor(Qt.PointingHandCursor)
            panel.mousePressEvent = lambda event, r=robot: self.selected.emit(r)
            return panel

        repo = RobotRepository()
        robots = repo.get_robots()
        return [build_robot_panel(robot) for robot in robots]

    def _on_add_robot(self):
        # Emit a signal to request showing the add robot view
        self.add_robot_requested.emit()

    def setup_layout(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.top_panel = QtTopPanel(self)
        self.top_panel.exited.connect(self.exited.emit)
        layout.addWidget(self.top_panel)
        layout.addWidget(self.robots_view())

        layout.addStretch(1)
        self.setLayout(layout)

    def _top_panel(self):
        panel = QWidget()
        # panel.setFixedHeight(48)
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        panel.setStyleSheet("background-color: rgba(0, 0, 0, 64);")
        layout = QHBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)

        # Logo on the left
        logo_label = QLabel()
        logo_label.setStyleSheet("background: transparent;")
        logo_pixmap = QPixmap("logo.png")
        if not logo_pixmap.isNull():
            scaled = logo_pixmap.scaledToHeight(24, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled)
        layout.addWidget(logo_label, alignment=Qt.AlignVCenter)

        # Spacer in the middle
        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Minimize and close buttons on the right
        btn_minimize = QPushButton("–")
        btn_minimize.setStyleSheet(
            "background: transparent; color: white; font-size: 20px;"
        )
        btn_minimize.setToolTip("Minimize")
        btn_close = QPushButton("✕")
        btn_close.setStyleSheet(
            "background: transparent; color: white; font-size: 20px;"
        )
        btn_close.setToolTip("Close")
        btn_close.clicked.connect(lambda: self.exited.emit())
        layout.addWidget(btn_minimize, alignment=Qt.AlignVCenter)
        layout.addWidget(btn_close, alignment=Qt.AlignVCenter)

        panel.setLayout(layout)
        return panel

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "_update_robots_grid"):
            self._update_robots_grid()

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_update_robots_grid"):
            self._update_robots_grid()

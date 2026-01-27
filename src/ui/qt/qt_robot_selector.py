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


class QtRobotSelector(QWidget):

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
            self._update_robot_status(robot)

        return callback

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
        # This method sets up and returns a layout containing the label and the robots grid
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(16, 0, 16, 0)
        # Add small gray label above robots grid
        robots_label = QLabel("Robots")
        robots_label.setStyleSheet(
            "color: #888; font-size: 10px; font-weight: bold; background: transparent;"
        )
        robots_label.setAlignment(Qt.AlignLeft)
        container_layout.addWidget(robots_label)

        self.robots_grid = QGridLayout()
        self.robots_grid.setContentsMargins(0, 0, 0, 0)
        self.robots_grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._current_cols = None
        self._robot_panels = []
        self._status_widgets = []

        def update_grid(force_status_refresh=False):
            repo = RobotRepository()
            robots = repo.get_robots()
            panel_width = 140
            panel_spacing = 16
            available_width = self.width() if self.width() > 0 else 800
            cols = max(1, (available_width - 32) // (panel_width + panel_spacing))
            prev_cols = getattr(self, "_current_cols", None)
            # Only redraw grid if layout changes, unless forced for status refresh
            if not force_status_refresh:
                if prev_cols is not None and cols == prev_cols:
                    return
                if (
                    prev_cols is not None
                    and len(robots) <= cols
                    and len(robots) <= prev_cols
                ):
                    return
            # Always clear grid for full redraw or status refresh
            while self.robots_grid.count():
                item = self.robots_grid.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()
            self._robot_panels = []
            self._status_widgets = []
            for i, robot in enumerate(robots):
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
                # Battery progress bar
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
                panel.setFixedSize(panel_width, 100)
                panel.setCursor(Qt.PointingHandCursor)
                panel.mousePressEvent = lambda event, r=robot: self.selected.emit(r)
                row = i // cols
                col = i % cols
                self.robots_grid.addWidget(panel, row, col)
                self._robot_panels.append(panel)
                self._status_widgets.append((battery_bar, battery_label, robot))
            self._current_cols = cols

        self._update_robots_grid = update_grid
        self._update_robots_grid()
        container_layout.addLayout(self.robots_grid)
        return container_layout

    def setup_layout(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._top_panel())
        layout.addLayout(self.robots_view())
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

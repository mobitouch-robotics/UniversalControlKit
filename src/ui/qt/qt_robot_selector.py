# --- Complex robots ---

# --- Controllers ---

# --- Programs ---

import os

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
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
from src.ui.controller_config import ControllerType
from .qt_battery_bar import QTBatteryBar
from .qt_panel import QtPanel
from .qt_top_panel import QtTopPanel
from .qt_section import QtSection
from .qt_grid_section import QtGridSection


class QtRobotSelector(QWidget):
    def _controller_background_image(self, cfg):
        ui_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        type_name = ""
        try:
            type_name = cfg.type.value
        except Exception:
            type_name = ""

        if type_name:
            type_path = os.path.join(ui_dir, f"{type_name}.png")
            if os.path.exists(type_path):
                return type_path

        # Fallback for joystick/controller naming mismatch
        fallback_path = os.path.join(ui_dir, "controller.png")
        if os.path.exists(fallback_path):
            return fallback_path
        return None

    def _create_add_panel(self, text, click_handler=None):
        from PyQt5.QtGui import QColor

        add_label = QLabel(text)
        add_label.setAlignment(Qt.AlignCenter)
        add_label.setStyleSheet(
            "font-size: 15px; color: #fff; background: transparent;"
        )
        darker_color = QColor(10, 10, 10, 80)
        add_panel = QtPanel(background_color=darker_color)
        add_panel.setFixedSize(140, 100)
        add_panel.setCursor(Qt.PointingHandCursor)
        add_panel.addWidget(add_label)
        if click_handler:
            add_panel.mousePressEvent = click_handler
        return add_panel

    def controllers_view(self):
        self.controllers_grid = QtGridSection(self)
        # Build panels for existing controllers and include Add panel
        from src.ui.controllers_repository import ControllersRepository

        repo = ControllersRepository()
        controllers = repo.get_controllers()
        panels = []
        # Build a mapping of joystick guid -> detected name using pygame so we
        # prefer live device names when available.
        try:
            import pygame

            pygame.joystick.init()
            detected = {}
            for i in range(pygame.joystick.get_count()):
                try:
                    j = pygame.joystick.Joystick(i)
                    try:
                        j.init()
                    except Exception:
                        pass
                    name = ""
                    try:
                        name = j.get_name() or ""
                    except Exception:
                        name = ""
                    guid = ""
                    try:
                        guid_raw = j.get_guid() if hasattr(j, "get_guid") else ""
                        guid = str(guid_raw) if guid_raw is not None else ""
                    except Exception:
                        guid = ""
                    if guid:
                        detected[guid] = name or f"Joystick {i}"
                except Exception:
                    continue
        except Exception:
            detected = {}

        for cfg in controllers:
            if cfg.type == ControllerType.JOYSTICK:
                display_name = detected.get(cfg.guid) or (cfg.name.capitalize() if getattr(cfg, 'name', None) else f"joystick{(' - ' + (cfg.guid or '')) if cfg.guid else ''}")
            else:
                display_name = cfg.name if getattr(cfg, 'name', None) else cfg.type.value.capitalize()

            label = QLabel(display_name)
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignLeft)
            label.setStyleSheet("font-size: 12px; color: #fff; background: transparent;")

            # Build panel with Edit/Delete actions similar to robots
            # Put only the label inside the panel (like robots view)
            panel = QtPanel(label, background_image=self._controller_background_image(cfg))
            panel.setFixedSize(140, 100)
            panel.setCursor(Qt.PointingHandCursor)
            panel.mousePressEvent = lambda event, c=cfg: self.edit_requested.emit(c)

            # Create action row (Edit/Delete) that will sit below the panel, like robots
            action_layout = QHBoxLayout()
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(8)
            action_layout.setAlignment(Qt.AlignHCenter)

            edit_label = QLabel("Edit")
            edit_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            edit_label.setFixedHeight(22)
            edit_label.setStyleSheet("font-size: 11px; color: #bbb; background: transparent;")
            edit_label.setCursor(Qt.PointingHandCursor)
            def on_edit(event, c=cfg):
                self.edit_requested.emit(c)
            edit_label.mousePressEvent = on_edit
            action_layout.addWidget(edit_label)

            delete_label = QLabel("Delete")
            delete_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            delete_label.setFixedHeight(22)
            delete_label.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")
            delete_label.setCursor(Qt.PointingHandCursor)
            def on_delete(event, c=cfg):
                from src.ui.controllers_repository import ControllersRepository

                repo = ControllersRepository()
                try:
                    repo.delete_controller(c)
                except Exception:
                    pass
                try:
                    self.delete_requested.emit(c)
                except Exception:
                    pass
                try:
                    self._update_controllers_grid()
                except Exception:
                    pass
            delete_label.mousePressEvent = on_delete
            action_layout.addWidget(delete_label)

            # Build the outer stack matching robot panels
            stack_layout = QVBoxLayout()
            stack_layout.setContentsMargins(0, 0, 0, 0)
            stack_layout.setSpacing(4)
            stack_layout.addWidget(panel)
            stack_layout.addLayout(action_layout)

            stack_widget = QWidget()
            stack_widget.setLayout(stack_layout)
            panels.append(stack_widget)

        add_panel = self._create_add_panel("+ New")
        add_panel.mousePressEvent = lambda event: self.add_controller_requested.emit()
        panels.append(add_panel)

        self.controllers_grid.set_children(panels)
        section = QtSection("Controllers", self.controllers_grid)
        section.setContentsMargins(16, 0, 16, 0)
        return section

    def create_add_robot_panel(self):
        from PyQt5.QtGui import QColor

        add_label = QLabel("+ New")
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
    add_controller_requested = pyqtSignal()
    selected = pyqtSignal(object)
    edit_requested = pyqtSignal(object)
    exited = pyqtSignal()
    maximized = pyqtSignal()

    delete_requested = pyqtSignal(object)

    def __init__(self, parent=None, qt_app=None):
        super().__init__(parent)
        self._robot_status_callbacks = []
        self.qt_app = qt_app
        self.setup_colors()
        self.setup_layout()
        self._register_robot_observers()
        self._register_controller_observers()

    def _register_robot_observers(self):
        repo = RobotRepository()
        for robot in repo.get_robots():
            cb = self._make_status_callback(robot)
            robot.add_status_observer(cb)
            self._robot_status_callbacks.append((robot, cb))

    def _register_controller_observers(self):
        from src.ui.controllers_repository import ControllersRepository

        repo = ControllersRepository()

        def _on_controllers_changed():
            # Refresh controllers grid if present
            try:
                if hasattr(self, "controllers_grid") and self.controllers_grid is not None:
                    self._update_controllers_grid()
            except Exception:
                pass

        repo.add_observer(_on_controllers_changed)
        self._controller_observer = _on_controllers_changed

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

    def _update_controllers_grid(self):
        """Build and replace children inside self.controllers_grid only."""
        if not hasattr(self, "controllers_grid") or self.controllers_grid is None:
            return
        from src.ui.controllers_repository import ControllersRepository

        repo = ControllersRepository()
        controllers = repo.get_controllers()
        panels = []
        for cfg in controllers:
            display_name = cfg.name if getattr(cfg, 'name', None) else f"{cfg.type.value}{(' - ' + (cfg.guid or '')) if cfg.guid else ''}"
            label = QLabel(display_name)
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignLeft)
            label.setStyleSheet("font-size: 12px; color: #fff; background: transparent;")

            # Build panel with Edit/Delete actions similar to robots
            panel = QtPanel()
            panel.setFixedSize(140, 100)
            panel.setCursor(Qt.PointingHandCursor)

            # Build simple panel with the label as the panel content (previous appearance)
            action_layout = QHBoxLayout()
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(8)
            action_layout.setAlignment(Qt.AlignHCenter)

            edit_label = QLabel("Edit")
            edit_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            edit_label.setFixedHeight(22)
            edit_label.setStyleSheet("font-size: 11px; color: #bbb; background: transparent;")
            edit_label.setCursor(Qt.PointingHandCursor)
            def on_edit(event, c=cfg):
                self.edit_requested.emit(c)
            edit_label.mousePressEvent = on_edit
            action_layout.addWidget(edit_label)

            delete_label = QLabel("Delete")
            delete_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            delete_label.setFixedHeight(22)
            delete_label.setStyleSheet("font-size: 11px; color: #e74c3c; background: transparent;")
            delete_label.setCursor(Qt.PointingHandCursor)
            def on_delete(event, c=cfg):
                from src.ui.controllers_repository import ControllersRepository

                repo = ControllersRepository()
                try:
                    repo.delete_controller(c)
                except Exception:
                    pass
                try:
                    self.delete_requested.emit(c)
                except Exception:
                    pass
                try:
                    self._update_controllers_grid()
                except Exception:
                    pass
            delete_label.mousePressEvent = on_delete
            action_layout.addWidget(delete_label)

            # Build the panel and the outer stack matching robot panels
            panel = QtPanel(label, background_image=self._controller_background_image(cfg))
            panel.setFixedSize(140, 100)
            panel.setCursor(Qt.PointingHandCursor)
            panel.mousePressEvent = lambda event, c=cfg: self.edit_requested.emit(c)

            stack_layout = QVBoxLayout()
            stack_layout.setContentsMargins(0, 0, 0, 0)
            stack_layout.setSpacing(4)
            stack_layout.addWidget(panel)
            stack_layout.addLayout(action_layout)

            stack_widget = QWidget()
            stack_widget.setLayout(stack_layout)
            panels.append(stack_widget)

        add_panel = self._create_add_panel("+ New")
        add_panel.mousePressEvent = lambda event: self.add_controller_requested.emit()
        panels.append(add_panel)

        # (tester removed)

        self.controllers_grid.set_children(panels)

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
        # Remove controller observer
        try:
            from src.ui.controllers_repository import ControllersRepository

            repo = ControllersRepository()
            if hasattr(self, "_controller_observer"):
                repo.remove_observer(self._controller_observer)
                self._controller_observer = None
        except Exception:
            pass

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

            # Try to get image for background
            background_image = None
            if hasattr(type(robot), "image") and callable(type(robot).image):
                img_path = type(robot).image()
                if img_path:
                    background_image = img_path

            panel = QtPanel(panel_widget, background_image=background_image)
            panel.setFixedSize(140, 100)
            panel.setCursor(Qt.PointingHandCursor)
            panel.mousePressEvent = lambda event, r=robot: self.selected.emit(r)

            # Create vertical stack: robot panel + horizontal Edit/Delete labels
            stack_layout = QVBoxLayout()
            stack_layout.setContentsMargins(0, 0, 0, 0)
            stack_layout.setSpacing(4)
            stack_layout.addWidget(panel)

            action_layout = QHBoxLayout()
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(8)
            action_layout.setAlignment(Qt.AlignHCenter)

            edit_label = QLabel("Edit")
            edit_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            edit_label.setFixedHeight(22)
            edit_label.setStyleSheet(
                "font-size: 11px; color: #bbb; background: transparent;"
            )
            edit_label.setCursor(Qt.PointingHandCursor)

            def on_edit(event):
                self.edit_requested.emit(robot)

            edit_label.mousePressEvent = on_edit
            action_layout.addWidget(edit_label)

            delete_label = QLabel("Delete")
            delete_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            delete_label.setFixedHeight(22)
            delete_label.setStyleSheet(
                "font-size: 11px; color: #e74c3c; background: transparent;"
            )
            delete_label.setCursor(Qt.PointingHandCursor)

            def on_delete(event):
                from src.robot.robot_repository import RobotRepository

                repo = RobotRepository()
                repo.delete_robot(robot)
                self.delete_requested.emit(robot)
                self._update_robots_grid()

            delete_label.mousePressEvent = on_delete
            action_layout.addWidget(delete_label)

            stack_layout.addLayout(action_layout)

            stack_widget = QWidget()
            stack_widget.setLayout(stack_layout)
            return stack_widget

        repo = RobotRepository()
        robots = repo.get_robots()
        return [build_robot_panel(robot) for robot in robots]

    def _on_add_robot(self):
        # Emit a signal to request showing the add robot view
        self.add_robot_requested.emit()

    def setup_layout(self):
        from PyQt5.QtWidgets import QScrollArea

        self.top_panel = QtTopPanel(self, title="Select robot", qt_app=self.qt_app)

        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(16)
        layout.addWidget(self.robots_view())
        layout.addWidget(self.controllers_view())
        layout.addStretch(1)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(content_widget)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.top_panel)
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    def _top_panel(self):
        panel = QWidget()
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # Remove background and frame
        panel.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
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
            "background: transparent; color: white; font-size: 20px; border: none;"
        )
        btn_minimize.setToolTip("Minimize")
        btn_close = QPushButton("✕")
        btn_close.setStyleSheet(
            "background: transparent; color: white; font-size: 20px; border: none;"
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

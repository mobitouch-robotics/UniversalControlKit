import os

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QLineEdit
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QPalette, QColor
from .qt_top_panel import QtTopPanel
from .qt_section import QtSection
from .qt_grid_section import QtGridSection
from .qt_panel import QtPanel
from PyQt5.QtCore import Qt

from src.ui.controller_config import ControllerConfig, ControllerType
from src.ui.controllers_repository import ControllersRepository


class QtAddControllerView(QWidget):
    controller_added = pyqtSignal(object)

    def _controller_background_image(self, controller_type: ControllerType):
        ui_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        type_path = os.path.join(ui_dir, f"{controller_type.value}.png")
        if os.path.exists(type_path):
            return type_path
        fallback_path = os.path.join(ui_dir, "controller.png")
        if os.path.exists(fallback_path):
            return fallback_path
        return None

    def __init__(self, parent=None, back_action=None, qt_app=None):
        super().__init__(parent)
        self.qt_app = qt_app
        self.setup_background()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.top_panel = QtTopPanel(self, back_action=back_action, title="Add controller", qt_app=qt_app)
        layout.addWidget(self.top_panel)

        # selection grid: keyboard / joystick
        self.grid = QtGridSection(self)
        repo = ControllersRepository()
        has_keyboard = any(c.type == ControllerType.KEYBOARD for c in repo.get_controllers())

        panels = []

        # keyboard panel (only when not already added)
        if not has_keyboard:
            kb_label = QLabel("Keyboard")
            kb_label.setAlignment(Qt.AlignCenter)
            kb_label.setStyleSheet("font-size: 15px; color: #fff; background: transparent;")
            kb_panel = QtPanel(background_image=self._controller_background_image(ControllerType.KEYBOARD))
            kb_panel.addWidget(kb_label)
            kb_panel.setFixedSize(140, 100)
            kb_panel.setCursor(Qt.PointingHandCursor)
            kb_panel.mousePressEvent = lambda e: self._show_keyboard_view(back_action)
            panels.append(kb_panel)

        # joystick panel
        js_label = QLabel("Joystick")
        js_label.setAlignment(Qt.AlignCenter)
        js_label.setStyleSheet("font-size: 15px; color: #fff; background: transparent;")
        js_panel = QtPanel(background_image=self._controller_background_image(ControllerType.JOYSTICK))
        js_panel.addWidget(js_label)
        js_panel.setFixedSize(140, 100)
        js_panel.setCursor(Qt.PointingHandCursor)
        js_panel.mousePressEvent = lambda e: self._show_joystick_view(back_action)
        panels.append(js_panel)

        self.grid.set_children(panels)

        section = QtSection("Controller type", self.grid)
        section.setContentsMargins(16, 0, 16, 0)
        layout.addWidget(section)
        layout.addStretch(1)
        self.setLayout(layout)

    def _show_keyboard_view(self, back_action):
        # Create a new ControllerConfig instance prefilled for keyboard and open EditControllerView
        from .qt_edit_controller_view import EditControllerView
        cfg = ControllerConfig(type=ControllerType.KEYBOARD, guid=None)
        top = self.window()
        if top is not None and hasattr(top, "push_view"):
            top.push_view(EditControllerView(cfg, parent=top, back_action=top.pop_view, qt_app=self.qt_app))

    def _show_joystick_view(self, back_action):
        # Create a new ControllerConfig instance prefilled for joystick and open EditControllerView
        from .qt_edit_controller_view import EditControllerView
        cfg = ControllerConfig(type=ControllerType.JOYSTICK, guid=None)
        top = self.window()
        if top is not None and hasattr(top, "push_view"):
            top.push_view(EditControllerView(cfg, parent=top, back_action=top.pop_view, qt_app=self.qt_app))

    def _add_keyboard(self, back_action):
        cfg = ControllerConfig(type=ControllerType.KEYBOARD, guid=None)
        repo = ControllersRepository()
        repo.add_controller(cfg)
        self.controller_added.emit(cfg)
        if back_action:
            back_action()

    def _add_joystick(self, back_action):
        guid = ""
        if hasattr(self, 'guid_input'):
            guid = self.guid_input.text().strip()
        cfg = ControllerConfig(type=ControllerType.JOYSTICK, guid=guid or None)
        repo = ControllersRepository()
        repo.add_controller(cfg)
        self.controller_added.emit(cfg)
        if back_action:
            back_action()

    def setup_background(self):
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#303032"))
        self.setAutoFillBackground(True)
        self.setPalette(palette)

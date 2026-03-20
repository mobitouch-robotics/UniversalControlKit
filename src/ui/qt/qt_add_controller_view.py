import os
import pathlib
import sys

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QLineEdit
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QPalette, QColor
from .qt_top_panel import QtTopPanel
from .qt_section import QtSection
from .qt_grid_section import QtGridSection
from .qt_panel import QtPanel
from PyQt5.QtCore import Qt

from src.ui.controller_config import ControllerConfig, ControllerType
from src.ui.controller_mapping_defaults import get_keyboard_default_mappings
from src.ui.controllers_repository import ControllersRepository


class QtAddControllerView(QWidget):
    controller_added = pyqtSignal(object)

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

    def _controller_background_image(self, controller_type: ControllerType):
        candidates = []

        current_ui_dir = pathlib.Path(__file__).resolve().parent.parent
        candidates.append(current_ui_dir / f"{controller_type.value}.png")

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            meipass_ui_dir = pathlib.Path(meipass) / "src" / "ui"
            candidates.append(meipass_ui_dir / f"{controller_type.value}.png")

        exe_path = pathlib.Path(sys.executable).resolve()
        resources_ui_dir = exe_path.parent.parent / "Resources" / "src" / "ui"
        candidates.append(resources_ui_dir / f"{controller_type.value}.png")

        for candidate in candidates:
            if candidate.exists():
                return str(candidate)

        fallback_candidates = [
            current_ui_dir / "controller.png",
        ]
        if meipass:
            fallback_candidates.append(pathlib.Path(meipass) / "src" / "ui" / "controller.png")
        fallback_candidates.append(resources_ui_dir / "controller.png")

        for candidate in fallback_candidates:
            if candidate.exists():
                return str(candidate)

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
            kb_label = self._make_bottom_badge_label("Keyboard")
            kb_content = QVBoxLayout()
            kb_content.setContentsMargins(0, 0, 0, 0)
            kb_content.setSpacing(0)
            kb_content.addStretch(1)
            kb_content.addWidget(kb_label)
            kb_widget = QWidget()
            kb_widget.setStyleSheet("background: transparent;")
            kb_widget.setLayout(kb_content)
            kb_panel = QtPanel(background_image=self._controller_background_image(ControllerType.KEYBOARD))
            kb_panel.addWidget(kb_widget)
            if kb_panel.layout() is not None:
                kb_panel.layout().setContentsMargins(0, 0, 0, 0)
            kb_panel.setFixedSize(200, 150)
            kb_panel.setCursor(Qt.PointingHandCursor)
            kb_panel.mousePressEvent = lambda e: self._show_keyboard_view(back_action)
            panels.append(kb_panel)

        # joystick panel
        js_label = self._make_bottom_badge_label("Joystick")
        js_content = QVBoxLayout()
        js_content.setContentsMargins(0, 0, 0, 0)
        js_content.setSpacing(0)
        js_content.addStretch(1)
        js_content.addWidget(js_label)
        js_widget = QWidget()
        js_widget.setStyleSheet("background: transparent;")
        js_widget.setLayout(js_content)
        js_panel = QtPanel(background_image=self._controller_background_image(ControllerType.JOYSTICK))
        js_panel.addWidget(js_widget)
        if js_panel.layout() is not None:
            js_panel.layout().setContentsMargins(0, 0, 0, 0)
        js_panel.setFixedSize(200, 150)
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
        cfg = ControllerConfig(type=ControllerType.KEYBOARD, guid=None, mappings=get_keyboard_default_mappings())
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

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox, QPushButton,
)
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt

from .qt_top_panel import QtTopPanel
from .qt_section import QtSection
from src.ui.controller_config import ControllerConfig, ControllerType
from src.ui.controllers_repository import ControllersRepository
from src.ui.voice.voice_settings import (
    SUPPORTED_LANGUAGES, MODEL_SIZES,
    load_voice_settings, save_voice_settings,
)


class VoiceSettingsView(QWidget):
    """Settings view for configuring and adding a voice controller."""

    def __init__(self, parent=None, back_action=None, qt_app=None):
        super().__init__(parent)
        self.qt_app = qt_app
        self._back_action = back_action
        self._setup_background()

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.top_panel = QtTopPanel(
            self, back_action=back_action, title="Voice Controller", qt_app=qt_app
        )
        layout.addWidget(self.top_panel)

        # Load current settings
        settings = load_voice_settings()

        # Language selector
        lang_widget = QWidget()
        lang_layout = QVBoxLayout()
        lang_layout.setContentsMargins(0, 0, 0, 0)
        lang_layout.setSpacing(4)

        lang_label = QLabel("Language")
        lang_label.setStyleSheet("color: #aaa; font-size: 12px; background: transparent;")
        lang_layout.addWidget(lang_label)

        self._lang_combo = QComboBox()
        self._lang_combo.setStyleSheet(
            "QComboBox { background: #444; color: #fff; padding: 6px; border-radius: 6px; font-size: 13px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background: #444; color: #fff; selection-background-color: #666; }"
        )
        current_lang = settings.get("language", "en")
        for code, name in SUPPORTED_LANGUAGES:
            self._lang_combo.addItem(name, code)
            if code == current_lang:
                self._lang_combo.setCurrentIndex(self._lang_combo.count() - 1)
        lang_layout.addWidget(self._lang_combo)
        lang_widget.setLayout(lang_layout)

        lang_section = QtSection("Language", lang_widget)
        lang_section.setContentsMargins(16, 8, 16, 0)
        layout.addWidget(lang_section)

        # Model size selector
        model_widget = QWidget()
        model_layout = QVBoxLayout()
        model_layout.setContentsMargins(0, 0, 0, 0)
        model_layout.setSpacing(4)

        model_label = QLabel("Whisper model (downloaded on first use)")
        model_label.setStyleSheet("color: #aaa; font-size: 12px; background: transparent;")
        model_layout.addWidget(model_label)

        self._model_combo = QComboBox()
        self._model_combo.setStyleSheet(
            "QComboBox { background: #444; color: #fff; padding: 6px; border-radius: 6px; font-size: 13px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background: #444; color: #fff; selection-background-color: #666; }"
        )
        current_model = settings.get("model_size", "base")
        for size_id, label in MODEL_SIZES:
            self._model_combo.addItem(label, size_id)
            if size_id == current_model:
                self._model_combo.setCurrentIndex(self._model_combo.count() - 1)
        model_layout.addWidget(self._model_combo)
        model_widget.setLayout(model_layout)

        model_section = QtSection("Model", model_widget)
        model_section.setContentsMargins(16, 8, 16, 0)
        layout.addWidget(model_section)

        # Info label
        info = QLabel("Push-to-talk: hold V key or use the microphone button.\n"
                       "Commands: sit, stand, dance, jump, hello, stop,\n"
                       "move forward 3 seconds, turn left 2 seconds, etc.")
        info.setWordWrap(True)
        info.setStyleSheet("color: #888; font-size: 12px; background: transparent; padding: 16px;")
        layout.addWidget(info)

        # Save button
        self._save_btn = QPushButton("Save")
        self._save_btn.setFixedHeight(36)
        self._save_btn.setStyleSheet(
            "font-size: 14px; padding: 4px 16px; border-radius: 8px; "
            "background: #223366; color: #fff;"
        )
        self._save_btn.setCursor(Qt.PointingHandCursor)
        self._save_btn.clicked.connect(self._on_save)
        save_container = QWidget()
        save_layout = QVBoxLayout()
        save_layout.setContentsMargins(16, 16, 16, 0)
        save_layout.addWidget(self._save_btn)
        save_container.setLayout(save_layout)
        layout.addWidget(save_container)

        layout.addStretch(1)
        self.setLayout(layout)

    def _on_save(self):
        lang = self._lang_combo.currentData()
        model = self._model_combo.currentData()
        save_voice_settings({"language": lang, "model_size": model})

        # Create voice controller config in repository
        cfg = ControllerConfig(type=ControllerType.VOICE, guid=None, name="Voice")
        repo = ControllersRepository()
        repo.add_controller(cfg)

        # Go back
        if self._back_action:
            self._back_action()

    def _setup_background(self):
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#303032"))
        self.setAutoFillBackground(True)
        self.setPalette(palette)

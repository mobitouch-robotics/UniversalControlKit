from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor


class QtPanel(QWidget):
    def __init__(
        self, widget=None, parent=None, background_color=None, background_image=None
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(16, 16, 16, 16)
        self.setLayout(self._layout)
        # Default: 0.25 alpha white background, rounded corners
        if background_color is None:
            background_color = QColor(255, 255, 255, 20)
        if isinstance(background_color, QColor):
            rgba = f"rgba({background_color.red()}, {background_color.green()}, {background_color.blue()}, {background_color.alpha()})"
        else:
            # fallback for string or other types
            rgba = str(background_color)
        style = f"background-color: {rgba};\nborder-radius: 12px;"
        if background_image:
            style += f"\nbackground-image: url('{background_image}');\nbackground-position: center;\nbackground-repeat: no-repeat;\nbackground-size: cover;"
        self.setStyleSheet(style)
        if widget is not None:
            self._layout.addWidget(widget)

    def addWidget(self, widget):
        self._layout.addWidget(widget)

    def addLayout(self, layout):
        self._layout.addLayout(layout)

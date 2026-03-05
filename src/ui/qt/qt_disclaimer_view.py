from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QPushButton


class QtDisclaimerView(QWidget):
    def __init__(self, on_accept=None, on_discard=None, parent=None):
        super().__init__(parent)
        self._on_accept = on_accept
        self._on_discard = on_discard
        self._setup_background()
        self._setup_layout()

    def _setup_background(self):
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor("#303032"))
        self.setAutoFillBackground(True)
        self.setPalette(palette)

    def _setup_layout(self):
        root = QVBoxLayout()
        root.setContentsMargins(48, 48, 48, 36)
        root.setSpacing(20)

        title = QLabel("Warning")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 34px; font-weight: 600; color: #fff; background: transparent;")

        message = QLabel(
            "This application is unofficial testing software.\n\n"
            "It may contain errors, unstable behavior, or other issues.\n"
            "By continuing, you acknowledge that the authors are not responsible for any damage,\n"
            "data loss, hardware problems, injuries, or other consequences caused by using this software."
        )
        message.setAlignment(Qt.AlignCenter)
        message.setWordWrap(True)
        message.setStyleSheet("font-size: 18px; color: #ddd; background: transparent;")

        root.addStretch(1)
        root.addWidget(title)
        root.addWidget(message)
        root.addStretch(1)

        buttons = QHBoxLayout()
        buttons.setSpacing(14)
        buttons.addStretch(1)

        discard = QPushButton("Discard")
        discard.setCursor(Qt.PointingHandCursor)
        discard.setStyleSheet(
            "font-size: 15px; padding: 10px 28px; background: #444; color: white; border-radius: 8px;"
        )
        discard.clicked.connect(self._discard)

        accept = QPushButton("Accept")
        accept.setCursor(Qt.PointingHandCursor)
        accept.setStyleSheet(
            "font-size: 15px; padding: 10px 28px; background: #222; color: white; border-radius: 8px;"
        )
        accept.clicked.connect(self._accept)

        buttons.addWidget(discard)
        buttons.addWidget(accept)
        buttons.addStretch(1)

        root.addLayout(buttons)
        self.setLayout(root)

    def _accept(self):
        if callable(self._on_accept):
            self._on_accept()

    def _discard(self):
        if callable(self._on_discard):
            self._on_discard()

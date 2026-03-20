import pathlib
import sys

from PyQt5.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, pyqtSignal


class QtTopPanel(QWidget):

    def _resolve_logo_path(self) -> str | None:
        candidates = [
            pathlib.Path.cwd() / "logo.png",
        ]

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(pathlib.Path(meipass) / "logo.png")

        exe_path = pathlib.Path(sys.executable).resolve()
        candidates.append(exe_path.parent.parent / "Resources" / "logo.png")

        for candidate in candidates:
            if candidate.exists():
                return str(candidate)

        return None

    def __init__(self, parent=None, back_action=None, title=None, qt_app=None):
        super().__init__(parent)
        self.back_action = back_action
        self.qt_app = qt_app
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout()
        layout.setContentsMargins(16, 8, 16, 4)
        layout.setSpacing(8)

        # Back arrow (if back_action is set)
        if self.back_action:
            btn_back = QPushButton()
            btn_back.setStyleSheet(
                "background: transparent; color: white; font-size: 20px;"
            )
            btn_back.setFixedSize(32, 32)
            btn_back.setText("←")
            btn_back.clicked.connect(self.back_action)
            layout.addWidget(btn_back, alignment=Qt.AlignVCenter)

        # Logo on the left
        logo_label = QLabel()
        logo_label.setStyleSheet("background: transparent;")
        logo_path = self._resolve_logo_path()
        logo_pixmap = QPixmap(logo_path) if logo_path else QPixmap()
        if not logo_pixmap.isNull():
            scaled = logo_pixmap.scaledToHeight(32, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled)
        layout.addWidget(logo_label, alignment=Qt.AlignVCenter)

        # Title in the center (if set)
        if title is not None:
            left_spacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
            right_spacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
            layout.addItem(left_spacer)
            title_label = QLabel(title)
            title_label.setStyleSheet(
                "color: white; font-weight: bold; font-size: 18px; margin-left: 16px; margin-right: 16px; background: transparent;"
            )
            title_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(title_label, alignment=Qt.AlignVCenter)
            layout.addItem(right_spacer)
        else:
            # Spacer in the middle
            layout.addItem(
                QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
            )

        # Minimize and close buttons on the right
        btn_maximize = QPushButton("◻")
        btn_maximize.setStyleSheet(
            "background: transparent; color: white; font-size: 20px; margin: 0px; padding-left: 16px; padding-right: 16px;"
        )
        btn_maximize.setCursor(Qt.PointingHandCursor)
        if self.qt_app:
            btn_maximize.clicked.connect(self.qt_app.toggle_fullscreen)
        btn_close = QPushButton("✕")
        btn_close.setStyleSheet(
            "background: transparent; color: white; font-size: 20px; margin: 0px; padding-left: 16px; padding-right: 16px;"
        )
        btn_close.setCursor(Qt.PointingHandCursor)
        if self.qt_app:
            btn_close.clicked.connect(self.qt_app.app.quit)
        layout.addWidget(btn_maximize, alignment=Qt.AlignVCenter)
        layout.addWidget(btn_close, alignment=Qt.AlignVCenter)

        self.setLayout(layout)

    def paintEvent(self, event):
        from PyQt5.QtGui import QPainter, QColor

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))  # 160/255 ≈ 0.6 alpha
        super().paintEvent(event)

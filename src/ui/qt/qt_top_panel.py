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
    exited = pyqtSignal()
    minimized = pyqtSignal()

    def __init__(self, parent=None, back_action=None):
        super().__init__(parent)
        self.back_action = back_action
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # Set background color using QPalette for reliability
        from PyQt5.QtGui import QPalette, QColor

        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(0, 0, 0, 64))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        layout = QHBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Back arrow (if back_action is set)
        if self.back_action:
            btn_back = QPushButton()
            btn_back.setStyleSheet(
                "background: transparent; color: white; font-size: 20px;"
            )
            btn_back.setFixedSize(32, 32)
            btn_back.setToolTip("Back")
            # Use a unicode left arrow or load an icon if available
            btn_back.setText("←")
            btn_back.clicked.connect(self.back_action)
            layout.addWidget(btn_back, alignment=Qt.AlignVCenter)

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
        btn_minimize.clicked.connect(self.minimized.emit)
        btn_close = QPushButton("✕")
        btn_close.setStyleSheet(
            "background: transparent; color: white; font-size: 20px;"
        )
        btn_close.setToolTip("Close")
        btn_close.clicked.connect(self.exited.emit)
        layout.addWidget(btn_minimize, alignment=Qt.AlignVCenter)
        layout.addWidget(btn_close, alignment=Qt.AlignVCenter)

        self.setLayout(layout)

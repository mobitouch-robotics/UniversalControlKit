from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QHBoxLayout,
)
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt, pyqtSignal
import os


class QtRobotSelector(QWidget):

    selected = pyqtSignal(str)
    exited = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Load background image once
        bg_path = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            ),
            "background.jpg",
        )
        self._background_pixmap = QPixmap(bg_path)

        # Main layout with vertical centering
        main_layout = QVBoxLayout()

        # Title label
        title = QLabel("Select which robot to use:")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 20, QFont.Bold))
        main_layout.addWidget(title)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(40)

        self.go2_btn = QPushButton("Go2 Robot")
        self.go2_btn.setFont(QFont("Arial", 16))
        self.go2_btn.setMinimumHeight(60)
        self.go2_btn.setMinimumWidth(180)
        self.go2_btn.setStyleSheet(
            "QPushButton { background-color: #1976D2; color: white; border-radius: 12px; } QPushButton:hover { background-color: #1565C0; }"
        )
        self.go2_btn.clicked.connect(lambda: self._select("go2"))
        btn_row.addWidget(self.go2_btn)

        self.dummy_btn = QPushButton("Dummy Robot")
        self.dummy_btn.setFont(QFont("Arial", 16))
        self.dummy_btn.setMinimumHeight(60)
        self.dummy_btn.setMinimumWidth(180)
        self.dummy_btn.setStyleSheet(
            "QPushButton { background-color: #388E3C; color: white; border-radius: 12px; } QPushButton:hover { background-color: #2E7D32; }"
        )
        self.dummy_btn.clicked.connect(lambda: self._select("dummy"))
        btn_row.addWidget(self.dummy_btn)

        main_layout.addLayout(btn_row)

        # Exit button to close the application
        exit_btn = QPushButton("Exit")
        exit_btn.setFixedWidth(140)
        exit_btn.clicked.connect(self._on_exit)
        main_layout.addWidget(exit_btn, alignment=Qt.AlignCenter)

        self.setLayout(main_layout)

    def paintEvent(self, event):
        super().paintEvent(event)
        if hasattr(self, "_background_pixmap") and not self._background_pixmap.isNull():
            from PyQt5.QtGui import QPainter

            painter = QPainter(self)
            # Aspect Fill logic
            widget_rect = self.rect()
            pixmap = self._background_pixmap
            if not pixmap.isNull():
                # Calculate scale for aspect fill
                w, h = widget_rect.width(), widget_rect.height()
                pw, ph = pixmap.width(), pixmap.height()
                scale = max(w / pw, h / ph)
                new_w, new_h = int(pw * scale), int(ph * scale)
                x = (w - new_w) // 2
                y = (h - new_h) // 2
                painter.drawPixmap(x, y, new_w, new_h, pixmap)
            painter.end()

    def _select(self, robot_type):
        self.selected.emit(robot_type)

    def _on_exit(self):
        self.exited.emit()

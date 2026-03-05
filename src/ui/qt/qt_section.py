from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt


class QtSection(QWidget):
    def __init__(self, title: str, content: QWidget, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        # Title label
        title_label = QLabel(title)
        title_label.setStyleSheet(
            "color: #fff; font-size: 10px; font-weight: bold; background: transparent;"
        )
        title_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(title_label)
        # Content widget
        layout.addWidget(content)
        self.setLayout(layout)

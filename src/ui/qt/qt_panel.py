from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import Qt


class QtPanel(QWidget):
    def __init__(self, widget=None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(16, 16, 16, 16)
        self.setLayout(self._layout)
        # 0.25 alpha black background, rounded corners
        self.setStyleSheet(
            """
            background-color: rgba(255, 255, 255, 20);
            border-radius: 12px;
            """
        )
        if widget is not None:
            self._layout.addWidget(widget)

    def addWidget(self, widget):
        self._layout.addWidget(widget)

    def addLayout(self, layout):
        self._layout.addLayout(layout)

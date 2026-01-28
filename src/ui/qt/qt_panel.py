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
        self._background_color = background_color
        self._background_image_path = background_image
        self._background_pixmap = None
        self.setStyleSheet(f"background-color: {rgba};\nborder-radius: 12px;")
        if background_image:
            from PyQt5.QtGui import QPixmap

            self._background_pixmap = QPixmap(background_image)
        if widget is not None:
            self._layout.addWidget(widget)

    def paintEvent(self, event):
        from PyQt5.QtGui import QPainter, QPainterPath

        super().paintEvent(event)
        if self._background_pixmap is not None and not self._background_pixmap.isNull():
            painter = QPainter(self)
            w, h = self.width(), self.height()
            radius = 12
            pm = self._background_pixmap.scaled(
                w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            x = (w - pm.width()) // 2
            y = (h - pm.height()) // 2
            path = QPainterPath()
            path.addRoundedRect(0, 0, w, h, radius, radius)
            painter.setClipPath(path)
            painter.drawPixmap(x, y, pm)
            # Draw semi-transparent black mask
            painter.setBrush(QColor(0, 0, 0, 127))
            painter.setPen(Qt.NoPen)
            painter.drawPath(path)
            painter.end()

    def addWidget(self, widget):
        self._layout.addWidget(widget)

    def addLayout(self, layout):
        self._layout.addLayout(layout)

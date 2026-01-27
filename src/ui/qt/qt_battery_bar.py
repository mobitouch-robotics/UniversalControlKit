from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QPixmap, QPainter, QColor
from PyQt5.QtCore import Qt


class QTBatteryBar(QLabel):
    def __init__(self, height=5, parent=None):
        super().__init__(parent)
        self._height = height
        self.setFixedHeight(self._height)
        self.setSizePolicy(self.sizePolicy().Expanding, self.sizePolicy().Fixed)
        self.setStyleSheet("background: transparent; border-radius: 2px;")
        self._battery = 0
        self._connected = False
        self.update_bar()

    def set_battery(self, battery, connected=True):
        self._battery = max(0, min(100, int(battery)))
        self._connected = connected
        self.update_bar()

    def update_bar(self):
        width = max(1, self.width())
        radius = self._height / 2
        pixmap = QPixmap(width, self._height)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Always draw rounded gray background
        painter.setBrush(QColor("#888"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, width, self._height, radius, radius)

        # Draw green progress only if connected
        if self._connected and self._battery > 0:
            green_width = max(10, int(width * self._battery / 100))
            green_width = min(green_width, width)
            painter.setBrush(QColor("#4caf50"))
            painter.setPen(Qt.NoPen)
            # Draw green bar with rounded ends
            painter.drawRoundedRect(0, 0, green_width, self._height, radius, radius)

        painter.end()
        self.setPixmap(pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_bar()

    def _rounded_left_rect(self, x, y, w, h, r):
        from PyQt5.QtGui import QPainterPath

        path = QPainterPath()
        path.moveTo(x + r, y)
        path.lineTo(x + w, y)
        path.lineTo(x + w, y + h)
        path.lineTo(x + r, y + h)
        path.arcTo(x, y, 2 * r, h, 180, -180)
        path.closeSubpath()
        return path

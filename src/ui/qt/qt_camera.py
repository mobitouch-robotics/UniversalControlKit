from __future__ import annotations
from ..protocols import CameraViewProtocol
import numpy as np
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QImage, QPixmap, QPainter

class QtCameraView(CameraViewProtocol):
    def __init__(self, robot, parent):
        self.robot = robot
        self.label = FrameWidget(parent)
        self._timer_ms = 50
        self._frames = 0
        self._latest_frame = None
        self._timer = None
        self._logged_frame_info = False
        self._color_swapped = None

    def setup(self):
        self._timer = QTimer()
        self._timer.timeout.connect(self._update)
        self._timer.start(self._timer_ms)
        try:
            print("qt_camera: timer started", self._timer_ms)
        except Exception:
            pass

    def cleanup(self) -> None:
        self._timer.stop()
        self._timer = None
        self._latest_frame = None

    def update_frame(self, frame) -> None:
        if frame is None:
            return
        # Avoid unnecessary copying; keep reference to frame so QImage
        # uses the underlying buffer while we hold a reference.
        # Ensure contiguous layout for QImage
        try:
            display_frame = np.ascontiguousarray(frame)
        except Exception:
            display_frame = frame
        self._latest_frame = display_frame
        # Log first frame for diagnostics
        try:
            if not self._logged_frame_info:
                print("qt_camera: frame", getattr(display_frame, 'shape', None), getattr(display_frame, 'dtype', None))
                self._logged_frame_info = True
        except Exception:
            pass
        self._render_frame()

    def _render_frame(self):
        """Render the latest frame scaled to window size with AspectFill."""
        if self._latest_frame is None:
            return

        try:
            frame = self._latest_frame
            # Expect (height, width, channels)
            if frame is None:
                return
            if frame.ndim != 3:
                return
            height, width, channels = frame.shape
            bytes_per_line = channels * width

            if channels == 3:
                q_image = QImage(
                    frame.data,
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format_RGB888,
                )
            else:
                return

            pixmap = QPixmap.fromImage(q_image)
            try:
                self.label.setPixmap(pixmap)
            except Exception:
                return
            self._frames += 1
        except Exception:
            pass

    def _update(self):
        """Poll for new frames from the robot."""
        frame = self.robot.get_camera_frame()
        self.update_frame(frame)
        if self._latest_frame is not None:
            self._render_frame()

    def get_widget(self):
        """Return the frame widget to be added to the layout."""
        return self.label

class FrameWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = None

    def setPixmap(self, pixmap: QPixmap | None):
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._pixmap is None:
            painter.fillRect(self.rect(), Qt.black)
            return
        w, h = self.width(), self.height()
        pm = self._pixmap.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x = (w - pm.width()) // 2
        y = (h - pm.height()) // 2
        painter.drawPixmap(x, y, pm)
        try:
            painter.end()
        except Exception:
            pass

    def sizeHint(self):
        return QSize(640, 480)
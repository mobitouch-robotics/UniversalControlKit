from __future__ import annotations
from ..protocols import CameraViewProtocol
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QImage, QPixmap

class QtCameraView(CameraViewProtocol):
    def __init__(self, robot, parent):
        self.robot = robot
        self.label = QLabel("Connecting camera...") if QLabel else None
        if self.label:
            self.label.setAlignment(Qt.AlignCenter)
            self.label.setScaledContents(False)
            self.label.setMinimumSize(640, 480)
        self._timer_ms = 50
        self._frames = 0
        self._latest_frame = None
        self._timer = None

    def setup(self):
        if QTimer and self.label:
            self._timer = QTimer()
            self._timer.timeout.connect(self._update)
            self._timer.start(self._timer_ms)

    def cleanup(self) -> None:
        if hasattr(self, '_timer') and self._timer:
            self._timer.stop()
            self._timer = None

    def update_frame(self, frame) -> None:
        if frame is None:
            try:
                self.label.setText("No camera frames yet...")
            except Exception:
                pass
            return

        # Just display the frame, skip detection
        display_frame = frame.copy()
        self._latest_frame = display_frame
        self._render_frame()

    def _render_frame(self):
        """Render the latest frame scaled to window size with AspectFill."""
        if self._latest_frame is None:
            return
       
        try:
            # Get current label dimensions
            label_width = self.label.width()
            label_height = self.label.height()

            # Skip if window not yet sized
            if label_width <= 1 or label_height <= 1:
                return

            # Get frame dimensions
            frame = self._latest_frame
            height, width, channels = frame.shape
            bytes_per_line = channels * width

            # Create QImage from numpy array
            # Assuming RGB format (most common)
            if channels == 3:
                q_image = QImage(
                    frame.data,
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format_RGB888
                )
            else:
                # Fallback for other formats
                return

            # Create pixmap from image
            pixmap = QPixmap.fromImage(q_image)

            # Scale to fit label while maintaining aspect ratio (AspectKeep)
            # For AspectFill behavior, we use scaled with KeepAspectRatioByExpanding
            scaled_pixmap = pixmap.scaled(
                label_width,
                label_height,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )

            # Crop to exact label size (center crop)
            if scaled_pixmap.width() > label_width or scaled_pixmap.height() > label_height:
                x_offset = (scaled_pixmap.width() - label_width) // 2
                y_offset = (scaled_pixmap.height() - label_height) // 2
                scaled_pixmap = scaled_pixmap.copy(
                    x_offset, y_offset, label_width, label_height
                )

            self.label.setPixmap(scaled_pixmap)
            self._frames += 1
        except Exception:
            # If conversion fails, ignore to keep UI responsive
            pass

    def _update(self):
        """Poll for new frames from the robot."""
        frame = None
        try:
            frame = self.robot.get_camera_frame()
        except Exception:
            frame = None
        self.update_frame(frame)
        # Re-render on window resize
        if self._latest_frame is not None:
            self._render_frame()

    def get_widget(self):
        """Return the QLabel widget to be added to the layout."""
        return self.label

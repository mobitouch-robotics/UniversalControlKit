from __future__ import annotations
import time
from ..protocols import CameraViewProtocol
from ...vision.person_tracker import PersonTracker
from ...vision.lidar_distance import estimate_person_distances
import numpy as np
from PyQt5.QtCore import Qt, QTimer, QSize, QRect
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor


class QtCameraView(CameraViewProtocol):
    def __init__(self, robot, parent):
        self.robot = robot
        self.label = FrameWidget(parent, robot=robot)
        self._timer_ms = 50
        self._frames = 0
        self._latest_frame = None
        self._timer = None
        self._logged_frame_info = False
        self._color_swapped = None
        self._person_tracker = PersonTracker()
        self._latest_distances = {}
        self._last_distance_estimate_time = 0.0
        self._distance_estimate_interval = 0.5  # 2 Hz

    def setup(self):
        self._timer = QTimer()
        self._timer.timeout.connect(self._update)
        self._timer.start(self._timer_ms)
        # Observe robot status changes
        if hasattr(self.robot, "status_changed"):
            self.robot.status_changed.connect(self._on_robot_status_changed)
        try:
            print("qt_camera: timer started", self._timer_ms)
        except Exception:
            pass

    def _on_robot_status_changed(self):
        # If robot is disconnected, clear the frame so robot image is shown
        if not getattr(self.robot, "is_connected", False):
            self._latest_frame = None
            self._latest_distances = {}
            try:
                self.label.set_overlay([], 0, 0)
                self.label.setPixmap(None)
                self.label.update()
            except Exception:
                pass

    def cleanup(self) -> None:
        self._timer.stop()
        self._timer = None
        self._latest_frame = None
        self._person_tracker.cleanup()
        # Disconnect robot status observation if possible
        if hasattr(self.robot, "status_changed"):
            try:
                self.robot.status_changed.disconnect(self._on_robot_status_changed)
            except Exception:
                pass

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
        self._person_tracker.process_frame(display_frame)
        # Log first frame for diagnostics
        try:
            if not self._logged_frame_info:
                print(
                    "qt_camera: frame",
                    getattr(display_frame, "shape", None),
                    getattr(display_frame, "dtype", None),
                )
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
                tracked_people = self.get_tracked_people()
                now = time.monotonic()
                if now - self._last_distance_estimate_time >= self._distance_estimate_interval:
                    self._latest_distances = self._estimate_person_distances(tracked_people, width)
                    self._last_distance_estimate_time = now
                self.label.set_overlay(tracked_people, width, height, self._latest_distances)
                self.label.setPixmap(pixmap)
            except Exception:
                return
            self._frames += 1
        except Exception:
            pass

    def get_tracked_people(self):
        """Return the rectangles of currently tracked people in frame pixel coordinates."""
        return self._person_tracker.get_people()

    def _estimate_person_distances(self, tracked_people, frame_width):
        """Estimate distance to each tracked person using lidar data, if available."""
        if not tracked_people:
            return {}
        try:
            lidar_points = self.robot.get_lidar_points()
        except Exception:
            lidar_points = None
        if lidar_points is None:
            return {}
        try:
            lidar_pose = self.robot.get_lidar_pose()
        except Exception:
            lidar_pose = None
        return estimate_person_distances(tracked_people, frame_width, lidar_points, lidar_pose)

    def get_person_distances(self):
        """Return the latest dict mapping tracked person id -> estimated distance in meters."""
        return self._latest_distances

    def get_frame_size(self):
        """Return the (width, height) of the most recent camera frame, or (0, 0)."""
        frame = self._latest_frame
        if frame is None or frame.ndim != 3:
            return (0, 0)
        height, width, _ = frame.shape
        return (width, height)

    def _update(self):
        """Poll for new frames from the robot."""
        if not getattr(self.robot, "is_connected", False):
            # Only clear and update if there was a previous frame
            if self._latest_frame is not None:
                self._latest_frame = None
                self._latest_distances = {}
                self.label.set_overlay([], 0, 0)
                self.label.setPixmap(None)
                self.label.update()
            return
        frame = self.robot.get_camera_frame()
        self.update_frame(frame)
        if self._latest_frame is not None:
            self._render_frame()

    def get_widget(self):
        """Return the frame widget to be added to the layout."""
        return self.label


class FrameWidget(QWidget):
    def __init__(self, parent=None, robot=None):
        super().__init__(parent)
        self._pixmap = None
        self._tracked_people = []
        self._frame_size = (0, 0)
        self._distances = {}
        self.robot = robot
        self._robot_image = None
        # Try to load robot image if available
        if (
            robot is not None
            and hasattr(type(robot), "image")
            and callable(type(robot).image)
        ):
            img_path = type(robot).image()
            if img_path:
                try:
                    from PyQt5.QtGui import QPixmap

                    self._robot_image = QPixmap(img_path)
                except Exception:
                    self._robot_image = None

    def setPixmap(self, pixmap: QPixmap | None):
        self._pixmap = pixmap
        self.update()

    def set_overlay(self, tracked_people, frame_width: int, frame_height: int, distances=None):
        """Set the tracked-people rectangles (in frame pixel coordinates) to draw,
        and optionally a dict mapping person id -> estimated distance in meters."""
        self._tracked_people = tracked_people
        self._frame_size = (frame_width, frame_height)
        self._distances = distances or {}

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._pixmap is None:
            # Show robot image if available, else fallback to background color
            if self._robot_image is not None and not self._robot_image.isNull():
                w, h = self.width(), self.height()
                pm = self._robot_image.scaled(
                    w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                )
                x = (w - pm.width()) // 2
                y = (h - pm.height()) // 2
                painter.drawPixmap(x, y, pm)
            else:
                painter.fillRect(self.rect(), QColor("#303032"))
            try:
                painter.end()
            except Exception:
                pass
            return
        w, h = self.width(), self.height()
        pm = self._pixmap.scaled(
            w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
        )
        x = (w - pm.width()) // 2
        y = (h - pm.height()) // 2
        painter.drawPixmap(x, y, pm)
        self._draw_person_overlays(painter, pm, x, y)
        try:
            painter.end()
        except Exception:
            pass

    def _draw_person_overlays(self, painter, pm, offset_x, offset_y):
        """Draw white rectangles around currently tracked people."""
        if not self._tracked_people:
            return
        frame_w, frame_h = self._frame_size
        if frame_w <= 0 or frame_h <= 0:
            return
        scale_x = pm.width() / frame_w
        scale_y = pm.height() / frame_h
        pen = QPen(QColor("white"))
        pen.setWidth(2)
        painter.setPen(pen)
        for person in self._tracked_people:
            x, y, w, h = person.rect
            rect_x = int(offset_x + x * scale_x)
            rect_y = int(offset_y + y * scale_y)
            rect_w = int(w * scale_x)
            rect_h = int(h * scale_y)
            painter.setPen(pen)
            painter.drawRect(rect_x, rect_y, rect_w, rect_h)
            self._draw_distance_label(painter, person, QRect(rect_x, rect_y, rect_w, rect_h))

    def _draw_distance_label(self, painter, person, rect):
        """Draw the estimated distance to a person, centered in their rectangle."""
        distance = self._distances.get(person.id)
        if distance is None:
            return
        label = f"{distance:.1f} m"

        font = painter.font()
        font.setBold(True)
        font.setPointSize(12)
        painter.setFont(font)

        metrics = painter.fontMetrics()
        text_size = metrics.size(Qt.TextSingleLine, label)
        bg_rect = QRect(0, 0, text_size.width() + 10, text_size.height() + 6)
        bg_rect.moveCenter(rect.center())

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 140))
        painter.drawRoundedRect(bg_rect, 4, 4)

        painter.setPen(QColor("white"))
        painter.drawText(rect, Qt.AlignCenter, label)

    def sizeHint(self):
        return QSize(640, 480)

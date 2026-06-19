from __future__ import annotations
import math
import numpy
from PyQt5.QtCore import Qt, QTimer, QSize, QPointF
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen, QPolygonF


# Only points within this radius of the robot's current position are drawn.
# This matches the effective indoor lidar range and ensures we display the
# current scan footprint rather than the robot's full historical voxel map.
_CURRENT_SCAN_RADIUS_M = 8.0


class QtLidarView(QWidget):
    """Live top-down overlay showing only the robot's current lidar readings.

    Points are fetched from the robot each refresh cycle and filtered to those
    within the active scan radius so that historical points from previous robot
    positions are excluded. The view rotates with the robot so its forward
    direction always points up.
    """

    _SIZE = 170
    _RANGE_M = 3.0      # metres from centre to edge of the display
    _MAX_POINTS = 2000  # stride-downsampled cap (no random flicker)
    _UPDATE_MS = 100    # refresh interval in ms

    def __init__(self, robot, parent=None):
        super().__init__(parent)
        self.robot = robot
        self._points = None
        self._pose = None
        self._timer = None
        self.setFixedSize(self._SIZE, self._SIZE)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def setup(self):
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_data)
        self._timer.start(self._UPDATE_MS)

    def cleanup(self):
        if self._timer:
            self._timer.stop()
            self._timer = None
        self._points = None
        self._pose = None

    def sizeHint(self):
        return QSize(self._SIZE, self._SIZE)

    def _update_data(self):
        if not getattr(self.robot, "is_connected", False):
            if self._points is not None or self._pose is not None:
                self._points = None
                self._pose = None
                self.update()
            return
        raw    = self.robot.get_lidar_points()
        pose   = self.robot.get_lidar_pose()
        self._points = self._filter_current(raw, pose)
        self._pose   = pose
        self.update()

    @staticmethod
    def _filter_current(points, pose):
        """Return only points within the active scan radius of the robot."""
        if points is None:
            return None
        pts = numpy.asarray(points)
        if pts.ndim != 2 or pts.shape[0] == 0 or pts.shape[1] < 2:
            return None
        if pose is not None:
            rx, ry, _ = pose
        else:
            rx, ry = 0.0, 0.0
        dist = numpy.hypot(pts[:, 0] - rx, pts[:, 1] - ry)
        return pts[dist <= _CURRENT_SCAN_RADIUS_M]

    # ── paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 120))
        painter.drawRoundedRect(rect, 8, 8)

        if self._points is None or len(self._points) == 0:
            painter.setPen(QColor(220, 220, 220, 150))
            painter.drawText(rect, Qt.AlignCenter, "LIDAR")
            painter.end()
            return

        cx, cy = rect.width() / 2.0, rect.height() / 2.0
        scale  = (min(rect.width(), rect.height()) / 2.0 - 6) / self._RANGE_M

        self._draw_range_rings(painter, cx, cy, scale)
        self._draw_points(painter, cx, cy, scale)
        self._draw_robot_marker(painter, cx, cy)
        painter.end()

    def _draw_range_rings(self, painter, cx, cy, scale):
        pen = QPen(QColor(255, 255, 255, 40))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        step = max(1.0, math.floor(self._RANGE_M))
        r = step
        while r <= self._RANGE_M:
            painter.drawEllipse(QPointF(cx, cy), r * scale, r * scale)
            r += step

    def _draw_points(self, painter, cx, cy, scale):
        pts = self._points
        if pts is None or len(pts) == 0:
            return

        rx, ry, yaw = self._pose if self._pose is not None else (0.0, 0.0, 0.0)
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)

        xs = pts[:, 0] - rx
        ys = pts[:, 1] - ry

        # Keep only what fits in the displayed range.
        r = self._RANGE_M * 1.05
        mask = numpy.hypot(xs, ys) <= r
        xs, ys = xs[mask], ys[mask]

        # Height above estimated floor (z column, if present).
        if pts.shape[1] >= 3:
            zs = pts[:, 2][mask]
            floor_z = numpy.percentile(zs, 5.0)
            height = numpy.clip(zs - floor_z, 0.0, 2.0)  # 0 = floor, 2 m = top
        else:
            height = numpy.ones(xs.size)

        if xs.size == 0:
            return

        # Stride downsample — deterministic, no per-frame flicker.
        if xs.size > self._MAX_POINTS:
            step = xs.size // self._MAX_POINTS + 1
            xs, ys, height = xs[::step], ys[::step], height[::step]

        # Rotate into robot frame (forward → up).
        fwd  =  xs * cos_y + ys * sin_y
        left = -xs * sin_y + ys * cos_y
        sx_all = cx - left * scale
        sy_all = cy - fwd * scale

        # Alpha scales linearly with height: floor → 20, 2 m → 210.
        # Quantise into 6 buckets to minimise brush changes per frame.
        raw_alpha = (20 + 190 * (height / 2.0)).astype(int)
        bucket_size = 32
        bucket_alpha = numpy.clip(
            (raw_alpha // bucket_size) * bucket_size, 20, 224
        )

        painter.setPen(Qt.NoPen)
        for alpha in numpy.unique(bucket_alpha):
            painter.setBrush(QColor(120, 220, 255, int(alpha)))
            for sx, sy in zip(sx_all[bucket_alpha == alpha], sy_all[bucket_alpha == alpha]):
                painter.drawEllipse(QPointF(sx, sy), 1.2, 1.2)

    def _draw_robot_marker(self, painter, cx, cy):
        size = 6.0
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 230))
        painter.drawPolygon(QPolygonF([
            QPointF(cx,              cy - size),
            QPointF(cx - size * 0.7, cy + size * 0.7),
            QPointF(cx + size * 0.7, cy + size * 0.7),
        ]))

from __future__ import annotations
import math
import numpy
from PyQt5.QtCore import Qt, QTimer, QSize, QPointF
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QColor, QPen, QPolygonF


class QtLidarView(QWidget):
    """Small overlay widget showing a top-down map of nearby lidar points.

    Points are drawn relative to the robot's current pose, rotated so the
    robot's forward direction always points up, with the robot itself shown
    as a triangle marker at the center.
    """

    _SIZE = 170
    _RANGE_M = 3.0  # meters from center to edge of the view
    _MAX_POINTS = 1500
    _UPDATE_MS = 150

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
        self._points = self.robot.get_lidar_points()
        self._pose = self.robot.get_lidar_pose()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 120))
        painter.drawRoundedRect(rect, 8, 8)

        if self._points is None:
            painter.setPen(QColor(220, 220, 220, 150))
            painter.drawText(rect, Qt.AlignCenter, "LIDAR")
            painter.end()
            return

        cx, cy = rect.width() / 2.0, rect.height() / 2.0
        scale = (min(rect.width(), rect.height()) / 2.0 - 6) / self._RANGE_M

        self._draw_range_rings(painter, cx, cy, scale)
        self._draw_points(painter, cx, cy, scale)
        self._draw_robot_marker(painter, cx, cy)

        painter.end()

    def _draw_range_rings(self, painter, cx, cy, scale):
        ring_pen = QPen(QColor(255, 255, 255, 40))
        ring_pen.setWidth(1)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.NoBrush)
        step = max(1.0, math.floor(self._RANGE_M))
        radius = step
        while radius <= self._RANGE_M:
            painter.drawEllipse(QPointF(cx, cy), radius * scale, radius * scale)
            radius += step

    def _draw_points(self, painter, cx, cy, scale):
        points = self._points
        if points is None:
            return
        points = numpy.asarray(points)
        if points.ndim != 2 or points.shape[0] == 0 or points.shape[1] < 2:
            return

        pose = self._pose
        if pose is not None:
            rx, ry, yaw = pose
        else:
            rx, ry, yaw = 0.0, 0.0, 0.0

        xs = points[:, 0] - rx
        ys = points[:, 1] - ry

        # Keep only points within the displayed range (with a small margin).
        max_r = self._RANGE_M * 1.05
        mask = (numpy.abs(xs) <= max_r) & (numpy.abs(ys) <= max_r)
        xs = xs[mask]
        ys = ys[mask]
        if xs.size == 0:
            return

        if xs.size > self._MAX_POINTS:
            idx = numpy.random.choice(xs.size, self._MAX_POINTS, replace=False)
            xs = xs[idx]
            ys = ys[idx]

        # Rotate world-relative coordinates into the robot's local frame so
        # the robot's forward direction always points up on screen.
        forward = xs * math.cos(yaw) + ys * math.sin(yaw)
        left = -xs * math.sin(yaw) + ys * math.cos(yaw)

        screen_x = cx - left * scale
        screen_y = cy - forward * scale

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(120, 220, 255, 200))
        for sx, sy in zip(screen_x, screen_y):
            painter.drawEllipse(QPointF(sx, sy), 1.2, 1.2)

    def _draw_robot_marker(self, painter, cx, cy):
        size = 6.0
        triangle = QPolygonF([
            QPointF(cx, cy - size),
            QPointF(cx - size * 0.7, cy + size * 0.7),
            QPointF(cx + size * 0.7, cy + size * 0.7),
        ])
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 255, 255, 230))
        painter.drawPolygon(triangle)

import asyncio
import threading
import os
import cv2
import numpy as np
import math
import tempfile
from typing import Optional
from pathlib import Path

# Optional GTK imports for resource loading
try:
    import gi
    gi.require_version('Gio', '2.0')
    from gi.repository import Gio, GLib
    HAS_GTK = True
except Exception:
    HAS_GTK = False


from .robot import Robot

class Robot_Dummy(Robot):
    def __init__(self, *args, **kwargs):
        self.position = [0.0, 0.0, 0.0]  # x, y, z (y is up)
        self.angle = 0.0  # Yaw angle in degrees
        self.running = False
        self._vel_forward = 0.0
        self._vel_strafe = 0.0
        self._vel_yaw = 0.0
        self._timer = None

    def is_connected(self) -> bool:
        return self.running

    def connect(self):
        if self.running:
            return
        self.running = True
        # Start update timer for smooth movement
        import threading
        def update_loop():
            import time
            last = time.time()
            while self.running:
                now = time.time()
                dt = min(now - last, 0.05)
                last = now
                self._update_position(dt)
                time.sleep(0.016)
        self._timer = threading.Thread(target=update_loop, daemon=True)
        self._timer.start()

    def disconnect(self):
        print("[DEBUG] Robot_Dummy.disconnect called")
        self.running = False
        self._vel_forward = 0.0
        self._vel_strafe = 0.0
        self._vel_yaw = 0.0

    def move(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        """
        Set the robot's velocity for smooth movement.
        x = forward/back, y = strafe, z = rotate (yaw)
        """
        if not self.running:
            return
        self._vel_forward = x * 2.0  # units per second
        self._vel_strafe = y * 2.0
        self._vel_yaw = z * 90.0  # degrees per second

    def _update_position(self, dt):
        # Smoothly update position and angle based on velocity
        self.angle = (self.angle + self._vel_yaw * dt) % 360
        rad = math.radians(self.angle)
        forward = self._vel_forward * dt
        strafe = self._vel_strafe * dt
        self.position[0] += forward * math.sin(rad) + strafe * math.cos(rad)
        self.position[2] += forward * math.cos(rad) - strafe * math.sin(rad)

    def stop(self):
        pass

    def rest(self):
        pass

    def standup(self):
        pass

    def jump_forward(self):
        pass

    def get_camera_frame(self):
        return None

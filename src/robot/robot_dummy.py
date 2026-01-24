import asyncio
import threading
import gi
import os
import cv2
import numpy as np
import math
from typing import Optional
from gi.repository import Gio, GLib


class Robot_Dummy:
    def __init__(self, resource_path_video: str, resource_path_robot: str):
        self.position = [0, 0]
        self.angle = 0.0  # Angle in degrees (0 is pointing "Up" or "North")
        self.video_path = self._extract_resource_to_temp(
            resource_path_video, "dummy_stream.mp4"
        )
        self.robot_path = self._extract_resource_to_temp(
            resource_path_robot, "robot_dummy.png"
        )

        self.latest_frame = None
        self.running = False
        self._loop = None
        self._thread = None

    def _extract_resource_to_temp(self, resource_path, filename):
        try:
            bytes_data = Gio.resources_lookup_data(
                resource_path, Gio.ResourceLookupFlags.NONE
            )
            temp_path = os.path.join(GLib.get_tmp_dir(), filename)
            with open(temp_path, "wb") as f:
                f.write(bytes_data.get_data())
            return temp_path
        except Exception as e:
            print(f"Failed to load {resource_path}: {e}")
            return None

    def connect(self):
        if not self.video_path or self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self._thread.start()

    def _run_event_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.create_task(self._video_producer())
            self._loop.run_forever()
        finally:
            self._loop.close()

    async def _video_producer(self):
        cap = cv2.VideoCapture(self.video_path)
        raw_robot = cv2.imread(self.robot_path, cv2.IMREAD_UNCHANGED)

        if raw_robot is None:
            return

        # Resize once to fit 100x100
        h_orig, w_orig = raw_robot.shape[:2]
        scale = min(100 / w_orig, 100 / h_orig)
        new_dim = (int(w_orig * scale), int(h_orig * scale))
        base_robot = cv2.resize(raw_robot, new_dim, interpolation=cv2.INTER_AREA)

        while self.running:
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            # --- ROTATION LOGIC ---
            # Create rotation matrix around the center of the robot image
            hr, wr = base_robot.shape[:2]
            center = (wr // 2, hr // 2)
            # We use negative angle because OpenCV rotates counter-clockwise
            M = cv2.getRotationMatrix2D(center, -self.angle, 1.0)
            robot_img = cv2.warpAffine(
                base_robot,
                M,
                (wr, hr),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(0, 0, 0, 0),
            )
            # ----------------------

            h_v, w_v = frame.shape[:2]
            h_r, w_r = robot_img.shape[:2]

            center_y = (h_v - h_r) // 2 + int(self.position[1])
            center_x = (w_v - w_r) // 2 + int(self.position[0])

            y1, y2 = max(0, center_y), min(h_v, center_y + h_r)
            x1, x2 = max(0, center_x), min(w_v, center_x + w_r)
            ry1, ry2 = max(0, -center_y), min(h_r, h_v - center_y)
            rx1, rx2 = max(0, -center_x), min(w_r, w_v - center_x)

            if x1 < x2 and y1 < y2:
                overlay_part = robot_img[ry1:ry2, rx1:rx2]
                if overlay_part.shape[2] == 4:
                    alpha_m = overlay_part[:, :, 3] / 255.0
                    for c in range(3):
                        frame[y1:y2, x1:x2, c] = (1.0 - alpha_m) * frame[
                            y1:y2, x1:x2, c
                        ] + alpha_m * overlay_part[:, :, c]
                else:
                    frame[y1:y2, x1:x2] = overlay_part[:, :, :3]

            self.latest_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            await asyncio.sleep(0.033)
        cap.release()

    def move(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        """
        Move the robot with specified velocities.

        Args:
            x: Forward/backward velocity (-1.0 to 1.0, positive = forward)
            y: Left/right strafe velocity (-1.0 to 1.0, positive = right)
            z: Rotational velocity (-1.0 to 1.0, positive = counterclockwise)
        """
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_move(x, y, z), self._loop)

    async def _async_move(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        """Internal async implementation of move."""
        # Speed factor to scale velocity to pixel/degree movement
        speed_factor = 3.0

        # Apply rotation (z is rotational velocity)
        if z != 0:
            delta_angle = z * speed_factor
            self.angle = (self.angle + delta_angle) % 360

        # Apply movement (x is forward/back, y is strafe)
        if x != 0 or y != 0:
            rad = math.radians(self.angle)
            # x is forward (negative y on screen), y is strafe (x on screen)
            dx = y * speed_factor
            dy = -x * speed_factor

            # Rotate movement vector by current angle
            self.position[0] += dx * math.cos(rad) - dy * math.sin(rad)
            self.position[1] += dx * math.sin(rad) + dy * math.cos(rad)

    def stop(self):
        """Stop all robot movement (no-op for dummy robot)."""
        pass

    def rest(self):
        """Put the robot into rest position (no-op for dummy robot)."""
        pass

    def standup(self):
        """Make the robot stand up (no-op for dummy robot)."""
        pass

    def get_camera_frame(self) -> Optional[np.ndarray]:
        return self.latest_frame

    def disconnect(self):
        self.running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        for path in [self.video_path, self.robot_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

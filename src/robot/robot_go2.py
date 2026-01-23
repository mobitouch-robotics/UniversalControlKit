import asyncio
import cv2
from .robot import Robot
from unitree_webrtc_connect.webrtc_driver import UnitreeWebRTCConnection, WebRTCConnectionMethod
from aiortc import MediaStreamTrack
from queue import Queue
import cv2, numpy, asyncio, threading, time

class Robot_Go2(Robot):
    def __init__(self, ip: str, connection_method: WebRTCConnectionMethod = WebRTCConnectionMethod.LocalSTA):
        self.ip = ip
        self.connection_method = connection_method
        self.conn = None
        self.latest_frame = None
        self.running = False
        self._loop = None

    def connect(self):
        """Main entry point: Spawns the background thread and loop."""
        self.running = True
        thread = threading.Thread(target=self._run_event_loop, daemon=True)
        thread.start()

    def _run_event_loop(self):
        """The internal background worker."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._async_connect())
        self._loop.run_forever()

    async def _async_connect(self):
        """Internal async setup logic."""
        try:
            self.conn = UnitreeWebRTCConnection(self.connection_method, ip=self.ip)
            await self.conn.connect()
            self.conn.video.switchVideoChannel(True)
            self.conn.video.add_track_callback(self._recv_camera_stream)
            print(f"Robot {self.ip} connected.")
        except Exception as e:
            print(f"Async Connection Error: {e}")

    async def _recv_camera_stream(self, track: MediaStreamTrack):
        while self.running:
            try:
                frame = await track.recv()
                # Direct to RGB for high-performance GTK rendering
                self.latest_frame = frame.to_ndarray(format="rgb24")
            except Exception:
                break

    def get_camera_frame(self):
        """Thread-safe access to the latest frame for the UI."""
        return self.latest_frame

    def disconnect(self):
        self.running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

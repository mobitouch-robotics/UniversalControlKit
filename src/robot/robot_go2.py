import asyncio
import threading
import logging
import numpy as np
from aiortc import MediaStreamTrack
from unitree_webrtc_connect.webrtc_driver import UnitreeWebRTCConnection, WebRTCConnectionMethod

# 1. Silence the H264 decoder warnings at the start
logging.getLogger("aiortc.codecs.h264").setLevel(logging.ERROR)

class Robot_Go2:
    def __init__(self, ip: str, connection_method: WebRTCConnectionMethod = WebRTCConnectionMethod.LocalSTA):
        self.ip = ip
        self.connection_method = connection_method
        self.conn = None
        self.latest_frame = None
        self.running = False
        self._loop = None
        self._thread = None

    def connect(self):
        """Starts the background thread and event loop."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self._thread.start()

    def _run_event_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_connect())
            self._loop.run_forever()
        finally:
            self._loop.close()

    async def _async_connect(self):
        try:
            self.conn = UnitreeWebRTCConnection(self.connection_method, ip=self.ip)
            await self.conn.connect()

            # Enable video and set channel
            self.conn.video.switchVideoChannel(True)
            self.conn.video.add_track_callback(self._recv_camera_stream)

            print(f"Robot {self.ip} connected via WebRTC.")
        except Exception as e:
            print(f"Async Connection Error: {e}")

    async def _recv_camera_stream(self, track: MediaStreamTrack):
        """Handles incoming video packets."""
        while self.running:
            try:
                frame = await track.recv()
                # Convert to RGB (GTK-native) immediately
                # Format "rgb24" is preferred for Gdk.MemoryTexture
                self.latest_frame = frame.to_ndarray(format="rgb24")

            except Exception as e:
                print(f"Track reception stopped: {e}")
                break

    def get_camera_frame(self):
        """Thread-safe access to the latest frame."""
        return self.latest_frame

    def disconnect(self):
        """Gracefully shuts down the connection and the thread."""
        self.running = False
        if self._loop:
            # Schedule the cleanup inside the async loop
            self._loop.call_soon_threadsafe(self._cleanup_sync)

    def _cleanup_sync(self):
        """Task to be run inside the loop for cleaning up resources."""
        asyncio.ensure_future(self._async_disconnect())

    async def _async_disconnect(self):
        if self.conn:
            # Close the WebRTC PeerConnection
            await self.conn.pc.close()
        if self._loop:
            self._loop.stop()
        print("Robot disconnected safely.")


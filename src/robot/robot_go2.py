import asyncio
import threading
import logging
from datetime import datetime
import numpy as np
from typing import Optional
from aiortc import MediaStreamTrack
from unitree_webrtc_connect.webrtc_driver import (
    UnitreeWebRTCConnection,
    WebRTCConnectionMethod,
)
from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD


class Robot_Go2:

    def __init__(
        self,
        ip: str,
        connection_method: WebRTCConnectionMethod = WebRTCConnectionMethod.LocalSTA,
    ):
        self.ip = ip
        self.connection_method = connection_method
        self.conn = None
        self.latest_frame = None
        self.running = False
        self._loop = None
        self._thread = None
        self._move_lock = None
        self._move_event = None
        self._move_task = None
        self._latest_move = (0.0, 0.0, 0.0)

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
            self._move_lock = asyncio.Lock()
            self._move_event = asyncio.Event()
            self._move_task = self._loop.create_task(self._move_worker())
            self._loop.run_until_complete(self._async_connect())
            self._loop.run_forever()
        finally:
            self._loop.close()

    async def _async_connect(self):
        try:
            self.conn = UnitreeWebRTCConnection(self.connection_method, ip=self.ip)
            await self.conn.connect()

            # Switch to AI mode for assisted movement
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["MOTION_SWITCHER"],
                {"api_id": 1002, "parameter": {"name": "ai"}},
            )

            # Enable video and set channel
            self.conn.video.switchVideoChannel(True)
            self.conn.video.add_track_callback(self._recv_camera_stream)

            print(f"Robot {self.ip} connected via WebRTC (AI mode enabled).")
        except SystemExit as e:
            print(f"Connection failed: Robot may be unavailable or already connected to another client.")
            print(f"SystemExit code: {e.code}")
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

    def get_camera_frame(self) -> Optional[np.ndarray]:
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
        self.running = False
        if self._move_task:
            self._move_task.cancel()
            self._move_task = None
        if self.conn:
            # Close the WebRTC PeerConnection
            await self.conn.pc.close()
        if self._loop:
            self._loop.stop()
        print("Robot disconnected safely.")

    def move(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        """
        Move the robot with specified velocities.

        Args:
            x: Forward/backward velocity (positive = forward)
            y: Left/right strafe velocity (positive = right)
            z: Rotational velocity (positive = counterclockwise)
        """
        if not self._loop or not self._move_event or self._loop.is_closed():
            return

        # Keep only the latest command; worker will send in order, one at a time
        self._latest_move = (x, y, z)
        self._loop.call_soon_threadsafe(self._move_event.set)

    async def _move_worker(self):
        """Send only the most recent move command, serialized via a lock."""
        last_send = 0.0
        while True:
            await self._move_event.wait()
            self._move_event.clear()

            if not self.conn:
                continue

            # Enforce a minimum 100ms gap between sends while still coalescing to latest
            while True:
                now = asyncio.get_event_loop().time()
                elapsed = now - last_send
                if elapsed < 0.1:
                    # Wait remaining time, but restart if a newer command arrives
                    try:
                        await asyncio.wait_for(
                            self._move_event.wait(), timeout=0.1 - elapsed
                        )
                        self._move_event.clear()
                        # Newer command available; loop to recompute timing with freshest values
                        continue
                    except asyncio.TimeoutError:
                        pass
                break

            x, y, z = self._latest_move

            # Clamp values to [-1.0, 1.0]
            x = max(-1.0, min(1.0, x))
            y = max(-1.0, min(1.0, y))
            z = max(-1.0, min(1.0, z))

            try:
                async with self._move_lock:
                    await self.conn.datachannel.pub_sub.publish_request_new(
                        RTC_TOPIC["SPORT_MOD"],
                        {
                            "api_id": SPORT_CMD["Move"],
                            "parameter": {"x": x, "y": y, "z": z},
                        },
                    )
                    logging.info(
                        ">>> %s move sent x=%.3f y=%.3f z=%.3f",
                        datetime.now().isoformat(timespec="milliseconds"),
                        x,
                        y,
                        z,
                    )
                    last_send = asyncio.get_event_loop().time()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"Move command error: {e}")

    def stop(self):
        """Stop all robot movement."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_stop(), self._loop)

    async def _async_stop(self):
        """Internal async implementation of stop."""
        if not self.conn:
            print("Robot not connected. Cannot stop.")
            return

        try:
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], {"api_id": SPORT_CMD["StopMove"]}
            )
        except Exception as e:
            print(f"Stop command error: {e}")

    def rest(self):
        """Put the robot into rest position (lay down slowly)."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_rest(), self._loop)

    async def _async_rest(self):
        """Internal async implementation of rest."""
        if not self.conn:
            print("Robot not connected. Cannot rest.")
            return

        try:
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], {"api_id": SPORT_CMD["StandDown"]}
            )
        except Exception as e:
            print(f"Rest command error: {e}")

    def standup(self):
        """Make the robot stand up from rest position."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_standup(), self._loop)

    async def _async_standup(self):
        """Internal async implementation of standup."""
        if not self.conn:
            print("Robot not connected. Cannot stand up.")
            return

        try:
            # Use RecoveryStand to recover from laying down position
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], {"api_id": SPORT_CMD["RecoveryStand"]}
            )
            print("Robot recovery command sent.")
        except Exception as e:
            print(f"Stand up command error: {e}")

    def jump_forward(self):
        """Make the robot jump forward."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_jump_forward(), self._loop)

    async def _async_jump_forward(self):
        """Internal async implementation of jump forward."""
        if not self.conn:
            print("Robot not connected. Cannot jump.")
            return

        try:
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], {"api_id": SPORT_CMD["FrontJump"]}
            )
            print("Front jump command sent.")
        except Exception as e:
            print(f"Jump command error: {e}")

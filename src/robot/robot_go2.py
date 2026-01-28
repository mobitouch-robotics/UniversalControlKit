from enum import Enum
from dataclasses import dataclass
import asyncio
import threading
import numpy as np
from typing import Optional
from enum import Enum
from dataclasses import dataclass
from aiortc import MediaStreamTrack
from unitree_webrtc_connect.webrtc_driver import (
    UnitreeWebRTCConnection,
)
from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD
from .robot import Robot
import os


class Go2Topic(Enum):
    MOTION_SWITCHER = "MOTION_SWITCHER"
    SPORT_MOD = "SPORT_MOD"
    LOW_STATE = "LOW_STATE"


class Go2Command(Enum):
    MOTION_SWITCHER = "MOTION_SWITCHER"
    MOVE = "Move"
    STOP_MOVE = "StopMove"
    STAND_DOWN = "StandDown"
    RECOVERY_STAND = "RecoveryStand"
    FRONT_JUMP = "FrontJump"


@dataclass
class MoveParams:
    x: float
    y: float
    z: float


class CommandParams:
    @staticmethod
    def for_move(x, y, z):
        return {"api_id": SPORT_CMD["Move"], "parameter": {"x": x, "y": y, "z": z}}

    @staticmethod
    def for_stop():
        return {"api_id": SPORT_CMD["StopMove"]}

    @staticmethod
    def for_stand_down():
        return {"api_id": SPORT_CMD["StandDown"]}

    @staticmethod
    def for_recovery_stand():
        return {"api_id": SPORT_CMD["RecoveryStand"]}

    @staticmethod
    def for_front_jump():
        return {"api_id": SPORT_CMD["FrontJump"]}

    @staticmethod
    def for_motion_switcher(name):
        return {"api_id": 1002, "parameter": {"name": name}}

    # Add more as needed

    @staticmethod
    def for_command(cmd: Go2Command, **kwargs):
        if cmd == Go2Command.MOVE:
            return CommandParams.for_move(
                kwargs.get("x", 0.0), kwargs.get("y", 0.0), kwargs.get("z", 0.0)
            )
        elif cmd == Go2Command.STOP_MOVE:
            return CommandParams.for_stop()
        elif cmd == Go2Command.STAND_DOWN:
            return CommandParams.for_stand_down()
        elif cmd == Go2Command.RECOVERY_STAND:
            return CommandParams.for_recovery_stand()
        elif cmd == Go2Command.FRONT_JUMP:
            return CommandParams.for_front_jump()
        elif cmd == Go2Command.MOTION_SWITCHER:
            if "name" not in kwargs:
                raise ValueError(
                    "'name' parameter required for MOTION_SWITCHER command"
                )
            return CommandParams.for_motion_switcher(kwargs["name"])
        else:
            raise ValueError(f"Unknown command: {cmd}")


class Robot_Go2(Robot):

    @classmethod
    def image(cls) -> str | None:
        return os.path.join(os.path.dirname(__file__), "robot_go2.png")

    def send_command(self, topic: Go2Topic, cmd: Go2Command, **kwargs):
        if not self.conn:
            return
        params = CommandParams.for_command(cmd, **kwargs)
        return asyncio.run_coroutine_threadsafe(
            self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC[topic.value], params
            ),
            self._loop,
        )

    def property_requirement(self, name):
        if name == "name":
            return True
        if name == "connection_type":
            return True
        elif name == "ip_address":
            conn_type = getattr(self, "connection_type", None)
            return conn_type in ("Remote", "LocalSTA") or None
        elif name == "serial_nr":
            conn_type = getattr(self, "connection_type", None)
            if conn_type is None:
                return None
            if conn_type == "LocalAP":
                return None
            elif conn_type == "LocalSTA":
                return False
            elif conn_type == "Remote":
                return True
            else:
                return None
        elif name == "username":
            # Example: only required for Remote connection
            conn_type = getattr(self, "connection_type", None)
            if conn_type is None:
                return None
            return conn_type in ("Remote",) or None
        elif name == "password":
            # Example: only required for Remote connection
            conn_type = getattr(self, "connection_type", None)
            if conn_type is None:
                return None
            return conn_type in ("Remote",) or None
        else:
            return None

    @classmethod
    def properties(cls) -> dict:
        return {
            "name": "str",
            "connection_type": "enum:LocalAP|LocalSTA|Remote",
            "ip_address": "str",
            "serial_nr": "str",
            "username": "str",
            "password": "str",
        }

    # Shared method for subscribing to topics
    def subscribe_topic(self, topic: Go2Topic, callback):
        if not self.conn:
            return
        self.conn.datachannel.pub_sub.subscribe(RTC_TOPIC[topic.value], callback)

    def unsubscribe_topic(self, topic: Go2Topic):
        if not self.conn:
            return
        self.conn.datachannel.pub_sub.unsubscribe(RTC_TOPIC[topic.value])

    def get_connection_type_enum(self):
        """
        Convert self.connection_type (str) to WebRTCConnectionMethod enum.
        """
        from unitree_webrtc_connect.constants import WebRTCConnectionMethod

        ct = self.connection_type
        if isinstance(ct, str):
            if ct == "LocalAP":
                return WebRTCConnectionMethod.LocalAP
            elif ct == "LocalSTA":
                return WebRTCConnectionMethod.LocalSTA
            elif ct == "Remote":
                return WebRTCConnectionMethod.Remote
        return WebRTCConnectionMethod.LocalAP

    # Restore instance variable initialization to __init__
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = kwargs.pop("name", None)
        self.ip_address = kwargs.pop("ip_address", None)
        self.connection_type = kwargs.pop("connection_type", None)
        self.conn = None
        self.latest_frame = None
        self.running = False
        self._loop = None
        self._thread = None
        self._move_lock = None
        self._move_event = None
        self._move_task = None
        self._latest_move = (0.0, 0.0, 0.0)
        self._battery_level = 0

    @property
    def battery_status(self) -> int:
        return getattr(self, "_battery_level", 0)

    @property
    def is_connected(self) -> bool:
        return bool(self.running)

    def connect(self):
        if self.running:
            return
        self._connect_future = None
        self._thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self._thread.start()

    def _run_event_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._move_lock = asyncio.Lock()
            self._move_event = asyncio.Event()
            try:
                self._connect_future = asyncio.ensure_future(
                    asyncio.wait_for(self._async_connect(), timeout=5)
                )
                self._loop.run_until_complete(self._connect_future)
            except asyncio.TimeoutError:
                self.running = False
                return
            except asyncio.CancelledError:
                self.running = False
                return
            except Exception:
                self.running = False
                return
            self._loop.run_forever()
        finally:
            if self._loop.is_running() or not self._loop.is_closed():
                tasks = asyncio.all_tasks(self._loop)
                for task in tasks:
                    task.cancel()
                self._loop.run_until_complete(
                    asyncio.gather(*tasks, return_exceptions=True)
                )
            self._loop.close()

    async def _async_connect(self):
        try:

            def none_if_empty(val):
                return (
                    None
                    if val is None or (isinstance(val, str) and val.strip() == "")
                    else val
                )

            self.conn = UnitreeWebRTCConnection(
                self.get_connection_type_enum(),
                serialNumber=none_if_empty(getattr(self, "serial_nr", None)),
                ip=none_if_empty(getattr(self, "ip_address", None)),
                username=none_if_empty(getattr(self, "username", None)),
                password=none_if_empty(getattr(self, "password", None)),
            )
            await self.conn.connect()

            # Switch to AI mode for assisted movement
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["MOTION_SWITCHER"],
                {"api_id": 1002, "parameter": {"name": "ai"}},
            )

            # Enable video and set channel
            self.conn.video.switchVideoChannel(True)
            self.conn.video.add_track_callback(self._recv_camera_stream)
            # Start move worker now that connection is established
            try:
                self._move_task = asyncio.create_task(self._move_worker())
            except Exception:
                pass
            # Only now mark as running and notify observers
            self.running = True
            self.notify_status_observers()
            try:
                self.subscribe_low_state()
            except Exception:
                pass
        except SystemExit as e:
            print(
                f"Connection failed: Robot may be unavailable or already connected to another client."
            )
            print(f"SystemExit code: {e.code}")
            self.running = False
            self.notify_status_observers()
        except Exception as e:
            print(f"Async Connection Error: {e}")
            self.running = False
            self.notify_status_observers()

    def subscribe_low_state(self):
        if not self.conn or not self._loop:
            return

        def lowstate_callback(message):
            print("HEARTBEAT DATA:", message)
            self._handle_low_state(message)

        self._lowstate_callback = lowstate_callback
        self.subscribe_topic(Go2Topic.LOW_STATE, self._lowstate_callback)

    def unsubscribe_low_state(self):
        if hasattr(self, "_lowstate_callback") and self.conn:
            self.unsubscribe_topic(Go2Topic.LOW_STATE)
            del self._lowstate_callback

    def _handle_low_state(self, message):
        resp = message.get("data", {})
        bms_state = resp.get("bms_state", {})
        battery_val = bms_state.get("soc") if isinstance(bms_state, dict) else None
        if battery_val is not None:
            try:
                new_battery_level = int(battery_val)
            except Exception:
                new_battery_level = 0
        else:
            new_battery_level = 0
        if new_battery_level != self._battery_level:
            self._battery_level = new_battery_level
            self.notify_status_observers()

    def _cleanup_sync(self):
        asyncio.ensure_future(self._async_disconnect())

    async def _async_disconnect(self):
        self.running = False
        if self._move_task:
            self._move_task.cancel()
            self._move_task = None
        if self.conn:
            try:
                self.conn.video.switchVideoChannel(False)
            except Exception:
                pass
            await self.conn.pc.close()
        if self._loop:
            self._loop.stop()

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
        self.running = False
        self.notify_status_observers()
        self.unsubscribe_low_state()
        if self._loop:
            if self.conn:
                try:
                    self.conn.video.switchVideoChannel(False)
                except Exception:
                    pass
                try:
                    coro = self.conn.pc.close()
                    if asyncio.iscoroutine(coro):
                        asyncio.run_coroutine_threadsafe(coro, self._loop)
                except Exception:
                    pass
            self._loop.call_soon_threadsafe(self._cleanup_sync)
            if hasattr(self, "_connect_future") and self._connect_future is not None:

                def cancel_connect():
                    if not self._connect_future.done():
                        self._connect_future.cancel()

                self._loop.call_soon_threadsafe(cancel_connect)
            self._loop.call_soon_threadsafe(self._loop.stop)

        def _cleanup():
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5)
            self._thread = None

        import threading as _threading

        _threading.Thread(target=_cleanup, daemon=True).start()

    def _cleanup_sync(self):
        """Task to be run inside the loop for cleaning up resources."""
        asyncio.ensure_future(self._async_disconnect())

    async def _async_disconnect(self):
        self.running = False
        if self._move_task:
            self._move_task.cancel()
            self._move_task = None
        if self.conn:
            # Disable video channel before closing PeerConnection
            try:
                self.conn.video.switchVideoChannel(False)
            except Exception:
                pass
            # Close the WebRTC PeerConnection
            await self.conn.pc.close()
        if self._loop:
            self._loop.stop()

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
        last_move = None
        while True:
            await self._move_event.wait()
            self._move_event.clear()

            if not self.conn:
                continue

            x, y, z = self._latest_move
            # Clamp values to [-1.0, 1.0]
            x = max(-1.0, min(1.0, x))
            y = max(-1.0, min(1.0, y))
            z = max(-1.0, min(1.0, z))

            # If move is zero, send only once
            if (x, y, z) == (0.0, 0.0, 0.0):
                if last_move == (0.0, 0.0, 0.0):
                    continue
                last_move = (0.0, 0.0, 0.0)
                try:
                    async with self._move_lock:
                        print("robot_go2: publishing move", x, y, z)
                        await self.conn.datachannel.pub_sub.publish_request_new(
                            RTC_TOPIC["SPORT_MOD"],
                            {
                                "api_id": SPORT_CMD["Move"],
                                "parameter": {"x": x, "y": y, "z": z},
                            },
                        )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    print(f"Move command error: {e}")
                continue

            # For nonzero moves, send continuously at 100ms intervals until move changes
            import time

            last_send_time = 0.0
            while (x, y, z) != (0.0, 0.0, 0.0):
                now = time.time()
                # Only send if 100ms have passed since last send
                if now - last_send_time >= 0.1:
                    try:
                        async with self._move_lock:
                            print("robot_go2: publishing move", x, y, z)
                            await self.conn.datachannel.pub_sub.publish_request_new(
                                RTC_TOPIC["SPORT_MOD"],
                                {
                                    "api_id": SPORT_CMD["Move"],
                                    "parameter": {"x": x, "y": y, "z": z},
                                },
                            )
                        last_send_time = now
                        last_move = (x, y, z)
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        print(f"Move command error: {e}")
                # Wait for either 100ms or a new move event
                try:
                    await asyncio.wait_for(self._move_event.wait(), timeout=0.1)
                    self._move_event.clear()
                    x, y, z = self._latest_move
                    x = max(-1.0, min(1.0, x))
                    y = max(-1.0, min(1.0, y))
                    z = max(-1.0, min(1.0, z))
                except asyncio.TimeoutError:
                    pass
                # If move changed, break and handle new move
                if (x, y, z) != last_move:
                    break

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

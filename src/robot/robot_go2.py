import os, asyncio, threading, numpy, time
from typing import Optional
from aiortc import MediaStreamTrack
from unitree_webrtc_connect.webrtc_driver import (
    UnitreeWebRTCConnection,
    WebRTCConnectionMethod,
)
from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD, VUI_COLOR
from .robot import Robot


def robot_command(action_name: str):
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            if not self.conn:
                print(f"Robot not connected. Cannot {action_name}.")
                return None
            try:
                return await func(self, *args, **kwargs)
            except Exception as e:
                print(f"{action_name} error: {e}")
                return None

        return wrapper

    return decorator


class Robot_Go2(Robot):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = kwargs.pop("name", None)
        self.ip_address = kwargs.pop("ip_address", None)
        self.connection_type = kwargs.pop("connection_type", None)
        self._connected = False
        self._connecting = False
        self._conn = None
        self._loop = None
        self._thread = None
        self._latest_frame = None
        self._battery_level = 0
        self._move_lock = None
        self._move_event = None
        self._move_task = None
        self._latest_move = (0.0, 0.0, 0.0)
        self._lowstate_callback = None

    @classmethod
    def image(cls) -> str | None:
        return os.path.join(os.path.dirname(__file__), "robot_go2.png")

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

    def property_requirement(self, name):
        match name:
            case "name" | "connection_type":
                return True
            case "ip_address":
                return self.connection_type in ("Remote", "LocalSTA") or None
            case "serial_nr":
                match self.connection_type:
                    case "LocalAP":
                        return None
                    case "LocalSTA":
                        return False
                    case "Remote":
                        return True
                    case _:
                        return None
            case "username" | "password":
                return self.connection_type in ("Remote",) or None
            case _:
                return None

    @property
    def is_connected(self) -> bool:
        return bool(self._connected)

    @is_connected.setter
    def is_connected(self, value: bool):
        if self._connected != value:
            self._connected = value
            self.notify_status_observers()

    @property
    def is_connecting(self) -> bool:
        return self._connecting

    @is_connecting.setter
    def is_connecting(self, value: bool):
        if self._connecting != value:
            self._connecting = value
            self.notify_status_observers()

    @property
    def battery_status(self) -> int:
        return self._battery_level

    @battery_status.setter
    def battery_status(self, value: int):
        if self._battery_level != value:
            self._battery_level = value
            self.notify_status_observers()

    def get_camera_frame(self) -> Optional[numpy.ndarray]:
        return self._latest_frame

    def move(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        if not self._loop or not self._move_event or self._loop.is_closed():
            return
        self._latest_move = (x, y, z)
        self._loop.call_soon_threadsafe(self._move_event.set)

    def connect(self):
        if self.is_connected or self.is_connecting:
            return
        self.is_connecting = True
        self._connect_future = None
        self._thread = threading.Thread(
            target=self._connected_run_event_loop, daemon=True
        )
        self._thread.start()

    async def _async_connect(self):
        try:

            def none_if_empty(val):
                return (
                    None
                    if val is None or (isinstance(val, str) and val.strip() == "")
                    else val
                )

            def _get_connection_type_enum(robot):
                ct = robot.connection_type
                if isinstance(ct, str):
                    if ct == "LocalAP":
                        return WebRTCConnectionMethod.LocalAP
                    elif ct == "LocalSTA":
                        return WebRTCConnectionMethod.LocalSTA
                    elif ct == "Remote":
                        return WebRTCConnectionMethod.Remote
                return WebRTCConnectionMethod.LocalAP

            self._conn = UnitreeWebRTCConnection(
                _get_connection_type_enum(self),
                serialNumber=none_if_empty(getattr(self, "serial_nr", None)),
                ip=none_if_empty(getattr(self, "ip_address", None)),
                username=none_if_empty(getattr(self, "username", None)),
                password=none_if_empty(getattr(self, "password", None)),
            )
            await self._conn.connect()

            # TODO: Should remove?
            # Switch to AI mode for assisted movement (robust, non-fatal)
            try:
                params = {
                    "api_id": SPORT_CMD["MotionSwitcher"],
                    "parameter": {"name": "ai"},
                }
                await self._conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["MOTION_SWITCHER"], params
                )
                print("Switched to AI mode after connect.")
            except Exception as e:
                print(f"Warning: Failed to switch to AI mode after connect: {e}")

            # Enable video and set channel
            self._conn.video.switchVideoChannel(True)
            self._conn.video.add_track_callback(self._recv_camera_stream)
            # Start move worker now that connection is established
            self._move_task = asyncio.create_task(self._move_worker())
            # Only now mark as running and notify observers
            self.is_connected = True
            self.is_connecting = False
            self._subscribe_low_state()
        except SystemExit as e:
            print(f"Connection failed: Exit code: {e.code}")
            self.is_connected = False
            self.is_connecting = False
        except Exception as e:
            print(f"Async Connection Error: {e}")
            self.is_connected = False
            self.is_connecting = False

    def disconnect(self):
        self.is_connected = False
        self._unsubscribe_low_state()
        if self._loop:
            if self._conn:
                try:
                    self._conn.video.switchVideoChannel(False)
                except Exception:
                    pass
                try:
                    coro = self._conn.pc.close()
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

    async def _async_disconnect(self):
        self.is_connected = False
        if self._move_task:
            self._move_task.cancel()
            self._move_task = None
        if self._conn:
            # Disable video channel before closing PeerConnection
            try:
                self._conn.video.switchVideoChannel(False)
            except Exception:
                pass
            # Close the WebRTC PeerConnection
            await self._conn.pc.close()
        if self._loop:
            self._loop.stop()

    def _cleanup_sync(self):
        asyncio.ensure_future(self._async_disconnect())

    def _subscribe_topic(self, topic: str, callback):
        self._conn and self._conn.datachannel.pub_sub.subscribe(
            RTC_TOPIC[topic], callback
        )

    def _unsubscribe_topic(self, topic: str):
        self._conn and self._conn.datachannel.pub_sub.unsubscribe(RTC_TOPIC[topic])

    def _subscribe_low_state(self):
        def lowstate_callback(message):
            # print("HEARTBEAT DATA:", message)
            self._handle_low_state(message)

        self._lowstate_callback = lowstate_callback
        self._subscribe_topic("LOW_STATE", self._lowstate_callback)

    def _unsubscribe_low_state(self):
        if self._lowstate_callback and self._conn:
            self._unsubscribe_topic("LOW_STATE")
            self._lowstate_callback = None

    def _handle_low_state(self, message):
        resp = message.get("data", {})
        bms_state = resp.get("bms_state", {})
        battery_val = bms_state.get("soc") if isinstance(bms_state, dict) else None
        self.battery_status = int(battery_val) if battery_val is not None else 0

    def _connected_run_event_loop(self):
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
                self.is_connected = False
                self.is_connecting = False
                return
            except asyncio.CancelledError:
                self.is_connected = False
                self.is_connecting = False
                return
            except Exception:
                self.is_connected = False
                self.is_connecting = False
                return
            self._loop.run_forever()
        finally:
            self.is_connecting = False
            if self._loop.is_running() or not self._loop.is_closed():
                tasks = asyncio.all_tasks(self._loop)
                for task in tasks:
                    task.cancel()
                self._loop.run_until_complete(
                    asyncio.gather(*tasks, return_exceptions=True)
                )
            self._loop.close()

    async def _move_worker(self):
        last_move = (0.0, 0.0, 0.0)
        while True:
            await self._move_event.wait()
            self._move_event.clear()

            if not self._conn:
                continue

            x, y, z = self._latest_move
            x = max(-1.0, min(1.0, x))
            y = max(-1.0, min(1.0, y))
            z = max(-1.0, min(1.0, z))

            # If move is zero, send only once
            if (x, y, z) == (0.0, 0.0, 0.0):
                if last_move != (0.0, 0.0, 0.0):
                    try:
                        async with self._move_lock:
                            params = {
                                "api_id": SPORT_CMD["Move"],
                                "parameter": {"x": x, "y": y, "z": z},
                            }
                            await self._conn.datachannel.pub_sub.publish_request_new(
                                RTC_TOPIC["SPORT_MOD"], params
                            )
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        print(f"Move command error: {e}")
                last_move = (0.0, 0.0, 0.0)
                continue

            # For nonzero moves, send continuously at 100ms intervals until move changes
            last_send_time = 0.0
            while (x, y, z) != (0.0, 0.0, 0.0):
                now = time.time()
                # Only send if 100ms have passed since last send
                if now - last_send_time >= 0.1:
                    try:
                        async with self._move_lock:
                            params = {
                                "api_id": SPORT_CMD["Move"],
                                "parameter": {"x": x, "y": y, "z": z},
                            }
                            await self._conn.datachannel.pub_sub.publish_request_new(
                                RTC_TOPIC["SPORT_MOD"], params
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
                    new_x, new_y, new_z = self._latest_move
                    new_x = max(-1.0, min(1.0, new_x))
                    new_y = max(-1.0, min(1.0, new_y))
                    new_z = max(-1.0, min(1.0, new_z))
                except asyncio.TimeoutError:
                    new_x, new_y, new_z = x, y, z
                # If move changed, break and handle new move
                if (new_x, new_y, new_z) != (x, y, z):
                    # If the new move is zero, send a stop command before breaking
                    if (new_x, new_y, new_z) == (0.0, 0.0, 0.0):
                        try:
                            async with self._move_lock:
                                params = {
                                    "api_id": SPORT_CMD["Move"],
                                    "parameter": {"x": 0.0, "y": 0.0, "z": 0.0},
                                }
                                await self._conn.datachannel.pub_sub.publish_request_new(
                                    RTC_TOPIC["SPORT_MOD"], params
                                )
                        except asyncio.CancelledError:
                            raise
                        except Exception as e:
                            print(f"Move command error: {e}")
                        last_move = (0.0, 0.0, 0.0)
                    break
                # Otherwise, continue sending current move

    async def _recv_camera_stream(self, track: MediaStreamTrack):
        """Handles incoming video packets."""
        while self.is_connected:
            try:
                frame = await track.recv()
                # Convert to RGB (GTK-native) immediately
                # Format "rgb24" is preferred for Gdk.MemoryTexture
                self._latest_frame = frame.to_ndarray(format="rgb24")

            except Exception as e:
                print(f"Track reception stopped: {e}")
                break

    async def _with_connection(self, action_name: str, coro_func, *args, **kwargs):
        if not self._conn:
            print(f"Robot not connected. Cannot {action_name}.")
            return None
        try:
            return await coro_func(*args, **kwargs)
        except Exception as e:
            print(f"{action_name} error: {e}")
            return None

    # ----------------------------------------------------------------------------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------------------
    # ----------------------------------------------------------------------------------------------------------------------

    def jump_forward(self):
        """Make the robot jump forward."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_jump_forward(), self._loop)

    async def _async_jump_forward(self):
        """Internal async implementation of jump forward."""
        if not self._conn:
            print("Robot not connected. Cannot jump.")
            return
        try:
            params = {"api_id": SPORT_CMD["FrontJump"]}
            await self._conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], params
            )
            print("Front jump command sent.")
        except Exception as e:
            print(f"Jump command error: {e}")

    def finger_heart(self):
        """Trigger FingerHeart action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("FingerHeart"), self._loop
            )

    def enable_obstacle_avoidance(self):
        """Enable obstacle avoidance function."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_obstacle_avoidance(True), self._loop
            )

    def disable_obstacle_avoidance(self):
        """Disable obstacle avoidance function."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_obstacle_avoidance(False), self._loop
            )

    async def _async_obstacle_avoidance(self, enable: bool):
        async def do_obstacle():
            from unitree_webrtc_connect.constants import RTC_TOPIC

            api_id = (
                SPORT_CMD["ObstaclesAvoidEnable"]
                if enable
                else SPORT_CMD["ObstaclesAvoidDisable"]
            )
            params = {"api_id": api_id, "parameter": {}}
            await self._conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["OBSTACLES_AVOID"], params
            )
            print(f"Obstacle avoidance {'enabled' if enable else 'disabled'}.")

        await self._with_connection("change obstacle avoidance state", do_obstacle)

    def stand_up(self):
        """Trigger StandUp action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("StandUp"), self._loop
            )

    # --- Async implementations ---
    @robot_command("SimpleSportCmd")
    async def _async_simple_sport_cmd(self, cmd_name):
        # Map cmd_name to parameter dict directly
        simple_param_cmds = {
            "GetBodyHeight": {"api_id": SPORT_CMD["GetBodyHeight"]},
            "GetFootRaiseHeight": {"api_id": SPORT_CMD["GetFootRaiseHeight"]},
            "GetSpeedLevel": {"api_id": SPORT_CMD["GetSpeedLevel"]},
            "Sit": {"api_id": SPORT_CMD["Sit"]},
            "StandUp": {"api_id": SPORT_CMD["StandUp"]},
            "RiseSit": {"api_id": SPORT_CMD["RiseSit"]},
            "Trigger": {"api_id": SPORT_CMD["Trigger"]},
            "Hello": {"api_id": SPORT_CMD["Hello"]},
            "Stretch": {"api_id": SPORT_CMD["Stretch"]},
            "Wallow": {"api_id": SPORT_CMD["Wallow"]},
            "Dance1": {"api_id": SPORT_CMD["Dance1"]},
            "Dance2": {"api_id": SPORT_CMD["Dance2"]},
            "Scrape": {"api_id": SPORT_CMD["Scrape"]},
            "FrontFlip": {"api_id": SPORT_CMD["FrontFlip"]},
            "LeftFlip": {"api_id": SPORT_CMD["LeftFlip"]},
            "RightFlip": {"api_id": SPORT_CMD["RightFlip"]},
            "BackFlip": {"api_id": SPORT_CMD["BackFlip"]},
            "FrontPounce": {"api_id": SPORT_CMD["FrontPounce"]},
            "WiggleHips": {"api_id": SPORT_CMD["WiggleHips"]},
            "GetState": {"api_id": SPORT_CMD["GetState"]},
            "EconomicGait": {"api_id": SPORT_CMD["EconomicGait"]},
            "LeadFollow": {"api_id": SPORT_CMD["LeadFollow"]},
            "FingerHeart": {"api_id": SPORT_CMD["FingerHeart"]},
            "Bound": {"api_id": SPORT_CMD["Bound"]},
            "MoonWalk": {"api_id": SPORT_CMD["MoonWalk"]},
            "OnesidedStep": {"api_id": SPORT_CMD["OnesidedStep"]},
            "CrossStep": {"api_id": SPORT_CMD["CrossStep"]},
            "Handstand": {"api_id": SPORT_CMD["Handstand"]},
            "FreeWalk": {"api_id": SPORT_CMD["FreeWalk"]},
            "Standup": {"api_id": SPORT_CMD["Standup"]},
            "CrossWalk": {"api_id": SPORT_CMD["CrossWalk"]},
            "Damp": {"api_id": SPORT_CMD["Damp"]},
            "BalanceStand": {"api_id": SPORT_CMD["BalanceStand"]},
        }
        params = simple_param_cmds.get(cmd_name)
        if params is None:
            params = {"api_id": SPORT_CMD[cmd_name]}
        await self._conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], params
        )
        print(f"{cmd_name} command sent.")

    def enable_lidar(self):
        """Enable the lidar scanner."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_set_lidar(True), self._loop)

    def disable_lidar(self):
        """Disable the lidar scanner."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_set_lidar(False), self._loop)

    async def _async_set_lidar(self, enable: bool):
        if not self._conn:
            print("Robot not connected. Cannot set lidar state.")
            return
        try:
            state = "ON" if enable else "OFF"
            self._conn.datachannel.pub_sub.publish_without_callback(
                RTC_TOPIC["ULIDAR_SWITCH"], state
            )
            print(f"Lidar {state} command sent.")
        except Exception as e:
            print(f"Error setting lidar state: {e}")

    def set_led_color(self, color: VUI_COLOR, time: int = 5, flash_cycle: int = 0):
        """Set the LED color. Accepts VUI_COLOR value or string name. time: seconds. flash_cycle: ms (0=solid)."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_set_led_color(color, time, flash_cycle), self._loop
            )

    async def _async_set_led_color(
        self, color: VUI_COLOR, time: int = 5, flash_cycle: int = 0
    ):
        if not self._conn:
            print("Robot not connected. Cannot set LED color.")
            return
        try:
            param = {"color": color, "time": time}
            if flash_cycle > 0:
                param["flash_cycle"] = flash_cycle
            params = {"api_id": SPORT_CMD["SetLEDColor"], "parameter": param}
            await self._conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["VUI"], params
            )
        except Exception as e:
            print(f"Error setting LED color: {e}")

    def set_flashlight_brightness(self, brightness: int):
        """Set the flashlight brightness (0-10, 0=off)."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_set_flashlight_brightness(brightness), self._loop
            )

    async def _async_set_flashlight_brightness(self, brightness: int):
        if not self._conn:
            print("Robot not connected. Cannot set flashlight brightness.")
            return
        try:
            params = {
                "api_id": SPORT_CMD["FlashlightBrightness"],
                "parameter": {"brightness": int(brightness)},
            }
            await self._conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["VUI"], params
            )
            print(f"Set flashlight brightness to {brightness}.")
        except Exception as e:
            print(f"Error setting flashlight brightness: {e}")

    def flashlight_on(self):
        """Turn flashlight on (max brightness)."""
        self.set_flashlight_brightness(10)

    def flashlight_off(self):
        """Turn flashlight off (brightness 0)."""
        self.set_flashlight_brightness(0)

    def sit(self):
        """Make the robot sit down."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_sit(), self._loop)

    async def _async_sit(self):
        if not self._conn:
            print("Robot not connected. Cannot sit.")
            return
        try:
            params = {"api_id": SPORT_CMD["Sit"]}
            await self._conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], params
            )
            print("Sit command sent.")
        except Exception as e:
            print(f"Sit command error: {e}")

    def stretch(self):
        """Make the robot stretch."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_stretch(), self._loop)

    async def _async_stretch(self):
        if not self._conn:
            print("Robot not connected. Cannot stretch.")
            return
        try:
            params = {"api_id": SPORT_CMD["Stretch"]}
            await self._conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], params
            )
            print("Stretch command sent.")
        except Exception as e:
            print(f"Stretch command error: {e}")

    def hello(self):
        """Make the robot wave hello."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_hello(), self._loop)

    async def _async_hello(self):
        if not self._conn:
            print("Robot not connected. Cannot say hello.")
            return
        try:
            params = {"api_id": SPORT_CMD["Hello"]}
            await self._conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], params
            )
            print("Hello command sent.")
        except Exception as e:
            print(f"Hello command error: {e}")

    def dance1(self):
        """Make the robot perform Dance1."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_dance1(), self._loop)

    async def _async_dance1(self):
        if not self._conn:
            print("Robot not connected. Cannot dance1.")
            return
        try:
            params = {"api_id": SPORT_CMD["Dance1"]}
            await self._conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], params
            )
            print("Dance1 command sent.")
        except Exception as e:
            print(f"Dance1 command error: {e}")

    def dance2(self):
        """Make the robot perform Dance2."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_dance2(), self._loop)

    async def _async_dance2(self):
        if not self._conn:
            print("Robot not connected. Cannot dance2.")
            return
        try:
            params = {"api_id": SPORT_CMD["Dance2"]}
            await self._conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], params
            )
            print("Dance2 command sent.")
        except Exception as e:
            print(f"Dance2 command error: {e}")

    def rest(self):
        """Put the robot into rest position (lay down slowly)."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_rest(), self._loop)

    async def _async_rest(self):
        """Internal async implementation of rest."""
        if not self._conn:
            print("Robot not connected. Cannot rest.")
            return

        try:
            params = {"api_id": SPORT_CMD["StandDown"]}
            await self._conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], params
            )
        except Exception as e:
            print(f"Rest command error: {e}")

    def standup(self):
        """Make the robot stand up from rest position."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_standup(), self._loop)

    async def _async_standup(self):
        """Internal async implementation of standup."""
        if not self._conn:
            print("Robot not connected. Cannot stand up.")
            return

        try:
            # Use RecoveryStand to recover from laying down position
            params = {"api_id": SPORT_CMD["RecoveryStand"]}
            await self._conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], params
            )
            print("Robot recovery command sent.")
        except Exception as e:
            print(f"Stand up command error: {e}")

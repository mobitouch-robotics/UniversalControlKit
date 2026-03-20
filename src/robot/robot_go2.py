import os, asyncio, threading, numpy, time, sys, pathlib
from typing import Optional
from aiortc import MediaStreamTrack
from unitree_webrtc_connect.webrtc_driver import (
    UnitreeWebRTCConnection,
    WebRTCConnectionMethod,
)
from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD, VUI_COLOR
from .robot import Robot


class Robot_Go2(Robot):

    @classmethod
    def display_name(cls) -> str:
        return "Unitree Go2"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = kwargs.pop("name", None)
        self.ip_address = kwargs.pop("ip_address", None)
        self.connection_type = kwargs.pop("connection_type", None)
        self.serial_nr = kwargs.pop("serial_nr", None)
        self.username = kwargs.pop("username", None)
        self.password = kwargs.pop("password", None)
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
        candidates = [
            pathlib.Path(__file__).with_name("robot_go2.png"),
            pathlib.Path.cwd() / "src" / "robot" / "robot_go2.png",
        ]

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            meipass_path = pathlib.Path(meipass)
            candidates.append(meipass_path / "src" / "robot" / "robot_go2.png")

        exe_path = pathlib.Path(sys.executable).resolve()
        candidates.append(exe_path.parent.parent / "Resources" / "src" / "robot" / "robot_go2.png")

        for candidate in candidates:
            if candidate.exists():
                return str(candidate)

        return None

    @classmethod
    def properties(cls) -> dict:
        return {
            "name": "str",
            "connection_type": "enum:LocalAP|LocalSTA",
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

    def move_obstacle_avoid(self, x: float, y: float, z: float):
        self._send_command(
            "OBSTACLES_AVOID",
            1003,
            None,
            {"x": x, "y": y, "yaw": z, "mode": 0},
        )

    def connect(self):
        if self.is_connected or self.is_connecting:
            return
        # Reset last-known temperature when initiating a new connection
        try:
            self.temperature = None
        except Exception:
            pass
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
                serialNumber=none_if_empty(self.serial_nr),
                ip=none_if_empty(self.ip_address),
                username=none_if_empty(self.username),
                password=none_if_empty(self.password),
            )
            await self._conn.connect()
            # Enable video and set channel
            # TODO: Consider moving somewhere else, allowing enabling/disabling camera stream.
            self._conn.video.switchVideoChannel(True)
            self._conn.video.add_track_callback(self._recv_camera_stream)
            # Enable lidar and obstacle avoidance by default on connect.
            self.set_lidar(True)
            self.set_obstacle_avoid(True)
            # Without this command, the robot does not accept move_obstacle_avoid commands from API.
            self.setup_obstacle_avoid_from_api(is_from_api=True)
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
        # Clear temperature on disconnect
        try:
            self.temperature = None
        except Exception:
            pass
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

        threading.Thread(target=_cleanup, daemon=True).start()

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
            print("HEARTBEAT DATA:", message)
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
        # Extract maximum temperature from available fields in lowstate
        try:
            temps = []
            # motor_state: list of dicts with 'temperature'
            ms = resp.get('motor_state')
            if isinstance(ms, (list, tuple)):
                for m in ms:
                    try:
                        t = m.get('temperature') if isinstance(m, dict) else None
                        if t is not None:
                            temps.append(float(t))
                    except Exception:
                        continue

            # top-level temperature fields
            try:
                t1 = resp.get('temperature_ntc1')
                if t1 is not None:
                    temps.append(float(t1))
            except Exception:
                pass

            # bms nested temps: bq_ntc and mcu_ntc
            try:
                if isinstance(bms_state, dict):
                    bq = bms_state.get('bq_ntc')
                    if isinstance(bq, (list, tuple)):
                        for v in bq:
                            try:
                                temps.append(float(v))
                            except Exception:
                                continue
                    mcu = bms_state.get('mcu_ntc')
                    if isinstance(mcu, (list, tuple)):
                        for v in mcu:
                            try:
                                temps.append(float(v))
                            except Exception:
                                continue
            except Exception:
                pass

            if temps:
                try:
                    max_temp = max(temps)
                    # store as integer °C
                    self.temperature = int(round(max_temp))
                except Exception:
                    self.temperature = None
            else:
                self.temperature = None
        except Exception:
            try:
                self.temperature = None
            except Exception:
                pass

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
                    # TODO: Try here is probably not needed.
                    try:
                        async with self._move_lock:
                            self.move_obstacle_avoid(x, y, z)
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
                            self.move_obstacle_avoid(
                                x * 1.5, y * 1, z * 1.57
                            )  # TODO: Better scalling for speed
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
                # If move changed
                if (new_x, new_y, new_z) != (x, y, z):
                    # TODO: If the new move is zero, send a stop command before breaking?
                    if (new_x, new_y, new_z) == (0.0, 0.0, 0.0):
                        try:
                            async with self._move_lock:
                                self.move_obstacle_avoid(0.0, 0.0, 0.0)
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

    def _send_command(
        self,
        topic: str,
        api: dict | int,
        command: str | None,
        params: dict | None = None,
        simple_params=None,
        callback: bool = True,
    ):
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_send_command(
                    topic, api, command, params, simple_params, callback
                ),
                self._loop,
            )

    async def _async_send_command(
        self,
        topic: str,
        api: dict | int,
        command: str | None,
        params: dict | None,
        simple_params,
        callback: bool,
    ):
        if not self._conn:
            print("Robot not connected. Cannot send command.")
            return
        try:
            param = {
                "api_id": (
                    api[command]
                    if isinstance(api, dict) and command is not None
                    else api
                )
            }
            if params is not None:
                param["parameter"] = params
            elif simple_params is not None:
                param = simple_params
            # print(">> ", topic, param);
            if callback:
                result = await self._conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC[topic], param
                )
                # print("<< ", result)
            else:
                self._conn.datachannel.pub_sub.publish_without_callback(
                    RTC_TOPIC[topic], param
                )
        except Exception as e:
            print(f"Send command error: {e}")

    def get_motion_switcher(self):
        self._send_command("MOTION_SWITCHER", 1001, None, None, callback=True)

    def motion_switcher(self, name: str):
        self._send_command("MOTION_SWITCHER", 1002, None, {"name": name})

    def move_send(self, x: float, y: float, z: float):
        self._send_command("SPORT_MOD", SPORT_CMD, "Move", {"x": x, "y": y, "z": z})

    def jump_forward(self):
        self._send_command("SPORT_MOD", SPORT_CMD, "FrontJump")

    def finger_heart(self):
        self._send_command("SPORT_MOD", SPORT_CMD, "FingerHeart")

    def stand_up(self):
        self._send_command("SPORT_MOD", SPORT_CMD, "StandUp")

    def sit(self):
        self._send_command("SPORT_MOD", SPORT_CMD, "Sit")

    def stretch(self):
        self._send_command("SPORT_MOD", SPORT_CMD, "Stretch")

    def hello(self):
        self._send_command("SPORT_MOD", SPORT_CMD, "Hello")

    def dance1(self):
        self._send_command("SPORT_MOD", SPORT_CMD, "Dance1")

    def dance2(self):
        self._send_command("SPORT_MOD", SPORT_CMD, "Dance2")

    def stand_down(self):
        self._send_command("SPORT_MOD", SPORT_CMD, "StandDown")

    def stand_up(self):
        self._send_command("SPORT_MOD", SPORT_CMD, "StandUp")

    def recovery_stand(self):
        self._send_command("SPORT_MOD", SPORT_CMD, "RecoveryStand")

    def stop_move(self):
        self._send_command("SPORT_MOD", SPORT_CMD, "Stop")

    def set_flashlight_brightness(self, brightness: int):
        self._send_command("VUI", 1005, None, {"brightness": brightness})

    def set_lidar(self, enable: bool):
        self._send_command(
            "ULIDAR_SWITCH",
            1005,
            None,
            simple_params="ON" if enable else "OFF",
            callback=False,
        )

    def set_led_color(self, color: VUI_COLOR, time: int = 5):
        self._send_command("VUI", 1007, None, {"color": color, "time": time})

    def set_obstacle_avoid(self, enable: bool):
        self._send_command(
            "OBSTACLES_AVOID",
            1001,
            None,
            {"enable": enable},
        )

    def get_obstacle_avoid(self):
        self._send_command(
            "OBSTACLES_AVOID",
            1002,
            None,
            None,
        )

    def setup_obstacle_avoid_from_api(self, is_from_api):
        self._send_command(
            "OBSTACLES_AVOID",
            1004,
            None,
            {"is_remote_commands_from_api": is_from_api},
        )

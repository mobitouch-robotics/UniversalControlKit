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
from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD, VUI_COLOR
from .robot import Robot
import os


def robot_command(action_name):
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
    STAND_OUT = "StandOut"


@dataclass
class MoveParams:
    x: float
    y: float
    z: float


class Robot_Go2(Robot):
    async def _with_connection(self, action_name: str, coro_func, *args, **kwargs):
        if not self.conn:
            print(f"Robot not connected. Cannot {action_name}.")
            return None
        try:
            return await coro_func(*args, **kwargs)
        except Exception as e:
            print(f"{action_name} error: {e}")
            return None

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
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["OBSTACLES_AVOID"], params
            )
            print(f"Obstacle avoidance {'enabled' if enable else 'disabled'}.")

        await self._with_connection("change obstacle avoidance state", do_obstacle)

    # --- Additional SPORT_CMD actions ---
    def damp(self):
        """Trigger Damp action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("Damp"), self._loop
            )

    def balance_stand(self):
        """Trigger BalanceStand action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("BalanceStand"), self._loop
            )

    def stand_up(self):
        """Trigger StandUp action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("StandUp"), self._loop
            )

    def rise_sit(self):
        """Trigger RiseSit action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("RiseSit"), self._loop
            )

    def switch_gait(self, gait: int):
        """Switch gait. gait: int (gait type)."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_switch_gait(gait), self._loop)

    def trigger(self):
        """Trigger action (generic)."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("Trigger"), self._loop
            )

    def body_height(self, height: float):
        """Set body height."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_body_height(height), self._loop
            )

    def foot_raise_height(self, height: float):
        """Set foot raise height."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_foot_raise_height(height), self._loop
            )

    def speed_level(self, level: int):
        """Set speed level."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_speed_level(level), self._loop)

    def trajectory_follow(self, trajectory):
        """Follow a trajectory (parameter format TBD)."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_trajectory_follow(trajectory), self._loop
            )

    def continuous_gait(self, enable: bool):
        """Enable/disable continuous gait."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_continuous_gait(enable), self._loop
            )

    def content(self, content):
        """Send content (parameter format TBD)."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_content(content), self._loop)

    def wallow(self):
        """Trigger Wallow action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("Wallow"), self._loop
            )

    def get_body_height(self):
        """Get body height."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("GetBodyHeight"), self._loop
            )

    def get_foot_raise_height(self):
        """Get foot raise height."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("GetFootRaiseHeight"), self._loop
            )

    def get_speed_level(self):
        """Get speed level."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("GetSpeedLevel"), self._loop
            )

    def switch_joystick(self, enable: bool):
        """Switch joystick control."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_switch_joystick(enable), self._loop
            )

    def pose(self, pose):
        """Set pose (parameter format TBD)."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_pose(pose), self._loop)

    def scrape(self):
        """Trigger Scrape action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("Scrape"), self._loop
            )

    def front_flip(self):
        """Trigger FrontFlip action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("FrontFlip"), self._loop
            )

    def front_pounce(self):
        """Trigger FrontPounce action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("FrontPounce"), self._loop
            )

    def wiggle_hips(self):
        """Trigger WiggleHips action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("WiggleHips"), self._loop
            )

    def get_state(self):
        """Get robot state."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("GetState"), self._loop
            )

    def economic_gait(self):
        """Trigger EconomicGait action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("EconomicGait"), self._loop
            )

    def finger_heart(self):
        """Trigger FingerHeart action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("FingerHeart"), self._loop
            )

    def bound(self):
        """Trigger Bound action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("Bound"), self._loop
            )

    def onesided_step(self):
        """Trigger OnesidedStep action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("OnesidedStep"), self._loop
            )

    def cross_step(self):
        """Trigger CrossStep action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("CrossStep"), self._loop
            )

    def free_walk(self):
        """Trigger FreeWalk action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("FreeWalk"), self._loop
            )

    def standup_alt(self):
        """Trigger Standup (alternate) action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("Standup"), self._loop
            )

    def cross_walk(self):
        """Trigger CrossWalk action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("CrossWalk"), self._loop
            )

    def lead_follow(self):
        """Trigger LeadFollow action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("LeadFollow"), self._loop
            )

    def left_flip(self):
        """Trigger LeftFlip action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("LeftFlip"), self._loop
            )

    def right_flip(self):
        """Trigger RightFlip action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("RightFlip"), self._loop
            )

    def back_flip(self):
        """Trigger BackFlip action."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_simple_sport_cmd("BackFlip"), self._loop
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
        await self.conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], params
        )
        print(f"{cmd_name} command sent.")

    @robot_command("SwitchGait")
    async def _async_switch_gait(self, gait: int):
        params = {"api_id": SPORT_CMD["SwitchGait"], "parameter": {"gait": gait}}
        await self.conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], params
        )

    @robot_command("BodyHeight")
    async def _async_body_height(self, height: float):
        params = {"api_id": SPORT_CMD["BodyHeight"], "parameter": {"height": height}}
        await self.conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], params
        )

    @robot_command("FootRaiseHeight")
    async def _async_foot_raise_height(self, height: float):
        params = {
            "api_id": SPORT_CMD["FootRaiseHeight"],
            "parameter": {"height": height},
        }
        await self.conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], params
        )

    @robot_command("SpeedLevel")
    async def _async_speed_level(self, level: int):
        params = {"api_id": SPORT_CMD["SpeedLevel"], "parameter": {"level": level}}
        await self.conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], params
        )

    @robot_command("TrajectoryFollow")
    async def _async_trajectory_follow(self, trajectory):
        params = {
            "api_id": SPORT_CMD["TrajectoryFollow"],
            "parameter": {"trajectory": trajectory},
        }
        await self.conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], params
        )

    @robot_command("ContinuousGait")
    async def _async_continuous_gait(self, enable: bool):
        params = {
            "api_id": SPORT_CMD["ContinuousGait"],
            "parameter": {"enable": enable},
        }
        await self.conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], params
        )

    @robot_command("Content")
    async def _async_content(self, content: str):
        params = {"api_id": SPORT_CMD["Content"], "parameter": {"content": content}}
        await self.conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], params
        )
        print(f"Content command sent. content={content}")

    @robot_command("SwitchJoystick")
    async def _async_switch_joystick(self, enable: bool):
        params = {
            "api_id": SPORT_CMD["SwitchJoystick"],
            "parameter": {"enable": enable},
        }
        await self.conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], params
        )
        print(f"SwitchJoystick command sent. enable={enable}")

    @robot_command("Pose")
    async def _async_pose(self, pose: str):
        params = {"api_id": SPORT_CMD["Pose"], "parameter": {"pose": pose}}
        await self.conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["SPORT_MOD"], params
        )
        print(f"Pose command sent. pose={pose}")

    def stand_out(self, enable: bool = True):
        """Trigger StandOut (handstand/stand out) action. enable=True to stand out, False to return."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_stand_out(enable), self._loop)

    async def _async_stand_out(self, enable: bool):
        if not self.conn:
            print("Robot not connected. Cannot StandOut.")
            return
        try:
            params = {"api_id": SPORT_CMD["StandOut"], "parameter": {"data": enable}}
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], params
            )
            print(f"StandOut command sent. enable={enable}")
        except Exception as e:
            print(f"StandOut command error: {e}")

    def enable_lidar(self):
        """Enable the lidar scanner."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_set_lidar(True), self._loop)

    def disable_lidar(self):
        """Disable the lidar scanner."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_set_lidar(False), self._loop)

    async def _async_set_lidar(self, enable: bool):
        if not self.conn:
            print("Robot not connected. Cannot set lidar state.")
            return
        try:
            state = "ON" if enable else "OFF"
            self.conn.datachannel.pub_sub.publish_without_callback(
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
        if not self.conn:
            print("Robot not connected. Cannot set LED color.")
            return
        try:
            param = {"color": color, "time": time}
            if flash_cycle > 0:
                param["flash_cycle"] = flash_cycle
            params = {"api_id": SPORT_CMD["SetLEDColor"], "parameter": param}
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["VUI"], params
            )
        except Exception as e:
            print(f"Error setting LED color: {e}")

    def get_flashlight_brightness(self):
        """Fetch the current flashlight brightness (0-10)."""
        if self._loop:
            return asyncio.run_coroutine_threadsafe(
                self._async_get_flashlight_brightness(), self._loop
            )

    async def _async_get_flashlight_brightness(self):
        if not self.conn:
            print("Robot not connected. Cannot get flashlight brightness.")
            return None
        try:
            response = await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["VUI"], {"api_id": 1006}
            )
            if response["data"]["header"]["status"]["code"] == 0:
                import json

                data = json.loads(response["data"]["data"])
                brightness = data.get("brightness", None)
                print(f"Current flashlight brightness: {brightness}")
                return brightness
            else:
                print("Failed to get flashlight brightness.")
                return None
        except Exception as e:
            print(f"Error getting flashlight brightness: {e}")
            return None

    def set_flashlight_brightness(self, brightness: int):
        """Set the flashlight brightness (0-10, 0=off)."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._async_set_flashlight_brightness(brightness), self._loop
            )

    async def _async_set_flashlight_brightness(self, brightness: int):
        if not self.conn:
            print("Robot not connected. Cannot set flashlight brightness.")
            return
        try:
            params = {
                "api_id": SPORT_CMD["FlashlightBrightness"],
                "parameter": {"brightness": int(brightness)},
            }
            await self.conn.datachannel.pub_sub.publish_request_new(
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
        if not self.conn:
            print("Robot not connected. Cannot sit.")
            return
        try:
            params = {"api_id": SPORT_CMD["Sit"]}
            await self.conn.datachannel.pub_sub.publish_request_new(
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
        if not self.conn:
            print("Robot not connected. Cannot stretch.")
            return
        try:
            params = {"api_id": SPORT_CMD["Stretch"]}
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], params
            )
            print("Stretch command sent.")
        except Exception as e:
            print(f"Stretch command error: {e}")

    def shake(self):
        """Make the robot shake."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_shake(), self._loop)

    async def _async_shake(self):
        if not self.conn:
            print("Robot not connected. Cannot shake.")
            return
        try:
            params = {"api_id": SPORT_CMD["Shake"]}
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], params
            )
            print("Shake command sent.")
        except Exception as e:
            print(f"Shake command error: {e}")

    def hello(self):
        """Make the robot wave hello."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_hello(), self._loop)

    async def _async_hello(self):
        if not self.conn:
            print("Robot not connected. Cannot say hello.")
            return
        try:
            params = {"api_id": SPORT_CMD["Hello"]}
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], params
            )
            print("Hello command sent.")
        except Exception as e:
            print(f"Hello command error: {e}")

    def handstand(self):
        """Make the robot do a handstand."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_handstand(), self._loop)

    async def _async_handstand(self):
        if not self.conn:
            print("Robot not connected. Cannot handstand.")
            return
        try:
            params = {"api_id": SPORT_CMD["Handstand"]}
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], params
            )
            print("Handstand command sent.")
        except Exception as e:
            print(f"Handstand command error: {e}")

    def dance1(self):
        """Make the robot perform Dance1."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_dance1(), self._loop)

    async def _async_dance1(self):
        if not self.conn:
            print("Robot not connected. Cannot dance1.")
            return
        try:
            params = {"api_id": SPORT_CMD["Dance1"]}
            await self.conn.datachannel.pub_sub.publish_request_new(
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
        if not self.conn:
            print("Robot not connected. Cannot dance2.")
            return
        try:
            params = {"api_id": SPORT_CMD["Dance2"]}
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], params
            )
            print("Dance2 command sent.")
        except Exception as e:
            print(f"Dance2 command error: {e}")

    def moonwalk(self):
        """Make the robot perform MoonWalk."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_moonwalk(), self._loop)

    async def _async_moonwalk(self):
        if not self.conn:
            print("Robot not connected. Cannot moonwalk.")
            return
        try:
            params = {"api_id": SPORT_CMD["MoonWalk"]}
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], params
            )
            print("MoonWalk command sent.")
        except Exception as e:
            print(f"MoonWalk command error: {e}")

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
        self._is_connecting = False

    @property
    def is_connecting(self) -> bool:
        return getattr(self, "_is_connecting", False)

    @is_connecting.setter
    def is_connecting(self, value: bool):
        if getattr(self, "_is_connecting", False) != value:
            self._is_connecting = value
            self.notify_status_observers()

    @property
    def battery_status(self) -> int:
        return getattr(self, "_battery_level", 0)

    @property
    def is_connected(self) -> bool:
        return bool(self.running)

    def connect(self):
        if self.running or self.is_connecting:
            return
        self.is_connecting = True
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
                self.is_connecting = False
                return
            except asyncio.CancelledError:
                self.running = False
                self.is_connecting = False
                return
            except Exception:
                self.running = False
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

            # Switch to AI mode for assisted movement (robust, non-fatal)
            try:
                params = {
                    "api_id": SPORT_CMD["MotionSwitcher"],
                    "parameter": {"name": "ai"},
                }
                await self.conn.datachannel.pub_sub.publish_request_new(
                    RTC_TOPIC["MOTION_SWITCHER"], params
                )
                print("Switched to AI mode after connect.")
            except Exception as e:
                print(f"Warning: Failed to switch to AI mode after connect: {e}")

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
            self.is_connecting = False
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
            self.is_connecting = False
            self.notify_status_observers()
        except Exception as e:
            print(f"Async Connection Error: {e}")
            self.running = False
            self.is_connecting = False
            self.notify_status_observers()

    def subscribe_low_state(self):
        if not self.conn or not self._loop:
            return

        def lowstate_callback(message):
            # print("HEARTBEAT DATA:", message)
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
        """Send only the most recent move command, serialized via a lock. Always send a stop (0,0,0) if movement ends."""
        last_move = (0.0, 0.0, 0.0)
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
                if last_move != (0.0, 0.0, 0.0):
                    try:
                        async with self._move_lock:
                            params = {
                                "api_id": SPORT_CMD["Move"],
                                "parameter": {"x": x, "y": y, "z": z},
                            }
                            await self.conn.datachannel.pub_sub.publish_request_new(
                                RTC_TOPIC["SPORT_MOD"], params
                            )
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        print(f"Move command error: {e}")
                last_move = (0.0, 0.0, 0.0)
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
                            params = {
                                "api_id": SPORT_CMD["Move"],
                                "parameter": {"x": x, "y": y, "z": z},
                            }
                            await self.conn.datachannel.pub_sub.publish_request_new(
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
                                await self.conn.datachannel.pub_sub.publish_request_new(
                                    RTC_TOPIC["SPORT_MOD"], params
                                )
                        except asyncio.CancelledError:
                            raise
                        except Exception as e:
                            print(f"Move command error: {e}")
                        last_move = (0.0, 0.0, 0.0)
                    break
                # Otherwise, continue sending current move

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
            params = {"api_id": SPORT_CMD["StopMove"]}
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], params
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
            params = {"api_id": SPORT_CMD["StandDown"]}
            await self.conn.datachannel.pub_sub.publish_request_new(
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
        if not self.conn:
            print("Robot not connected. Cannot stand up.")
            return

        try:
            # Use RecoveryStand to recover from laying down position
            params = {"api_id": SPORT_CMD["RecoveryStand"]}
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], params
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
            params = {"api_id": SPORT_CMD["FrontJump"]}
            await self.conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], params
            )
            print("Front jump command sent.")
        except Exception as e:
            print(f"Jump command error: {e}")

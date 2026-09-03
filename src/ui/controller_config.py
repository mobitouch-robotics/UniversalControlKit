from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class ControllerType(Enum):
    KEYBOARD = "keyboard"
    JOYSTICK = "joystick"
    VOICE = "voice"


class ControllerAction(Enum):
    # Movement group
    MOVEMENT = "movement_axes"
    RUN = "run"
    SLOW = "slow"
    ROTATION = "rotation_axis"

    # Pose group
    STAND_UP = "stand_up"
    STAND_DOWN = "stand_down"
    STRETCH = "stretch"
    SIT = "sit"

    # Actions group
    HELLO = "hello"
    JUMP = "jump_forward"
    FINGER_HEART = "finger_heart"
    DANCE1 = "dance1"

    # Other toggles
    TOGGLE_FLASH = "toggle_flash_brightness"
    TOGGLE_LED = "toggle_led_color"
    TOGGLE_LIDAR = "toggle_lidar"

    # Voice
    PUSH_TO_TALK = "push_to_talk"



@dataclass
class ControllerConfig:
    """Configuration for an input controller (keyboard or gamepad).

    Fields:
    - type: ControllerType
    - guid: Optional[str] -- identifier for joystick controllers (GUID or name substring)
    """

    type: ControllerType
    guid: Optional[str] = None
    name: Optional[str] = None
    # mappings: list of {"action": str, "input": Optional[str]}
    mappings: list[dict] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {"type": self.type.value, "guid": self.guid, "name": self.name}
        data["mappings"] = self.mappings if self.mappings is not None else []
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ControllerConfig":
        t = data.get("type")
        try:
            ctype = ControllerType(t) if t is not None else ControllerType.KEYBOARD
        except Exception:
            # unknown -> treat as keyboard fallback
            ctype = ControllerType.KEYBOARD
        guid = data.get("guid")
        name = data.get("name")
        mappings = data.get("mappings") or []
        return cls(type=ctype, guid=guid, name=name, mappings=mappings)

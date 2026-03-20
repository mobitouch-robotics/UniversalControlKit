import copy
import json
import os


def _defaults_file_path() -> str:
    return os.path.join(os.path.dirname(__file__), "controller_mapping_defaults.json")


def _load_defaults() -> dict:
    try:
        with open(_defaults_file_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def get_keyboard_default_mappings() -> list[dict]:
    defaults = _load_defaults()
    mappings = defaults.get("keyboard") or []
    return copy.deepcopy(mappings)


def get_joystick_default_mappings(joystick_name: str | None, joystick_guid: str | None = None) -> list[dict]:
    defaults = _load_defaults()
    joystick_defaults = defaults.get("joystick") or {}

    name = (joystick_name or "").lower()

    if "asustek computer inc." in name or "rog ally" in name:
        return copy.deepcopy(joystick_defaults.get("asus_rog_ally") or [])

    if "dualsense" in name:
        return copy.deepcopy(joystick_defaults.get("dualsense") or [])

    return []

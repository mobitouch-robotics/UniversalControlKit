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


def get_joystick_default_mappings(joystick_name: str | None) -> list[dict]:
    if not joystick_name:
        return []
    name = joystick_name.lower()
    defaults = _load_defaults()
    joystick_defaults = defaults.get("joystick") or {}

    if "dualsense" in name:
        return copy.deepcopy(joystick_defaults.get("dualsense") or [])

    return []

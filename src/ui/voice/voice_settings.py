import json
import logging

from src.app_paths import get_app_data_file

logger = logging.getLogger(__name__)

_SETTINGS_FILE = "voice_settings.json"

# Supported languages (subset of Whisper's 50+ languages, most common ones)
SUPPORTED_LANGUAGES = [
    ("en", "English"),
    ("pl", "Polish"),
    ("de", "German"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("it", "Italian"),
    ("pt", "Portuguese"),
    ("ja", "Japanese"),
    ("zh", "Chinese"),
    ("ko", "Korean"),
    ("ru", "Russian"),
    ("uk", "Ukrainian"),
    ("nl", "Dutch"),
    ("sv", "Swedish"),
    ("cs", "Czech"),
    ("tr", "Turkish"),
]

MODEL_SIZES = [
    ("tiny", "Tiny (~75MB, fastest)"),
    ("base", "Base (~150MB, recommended)"),
    ("small", "Small (~500MB, most accurate)"),
]


def load_voice_settings() -> dict:
    """Load voice settings from disk. Returns defaults if file doesn't exist."""
    defaults = {"language": "en", "model_size": "base"}
    try:
        path = get_app_data_file(_SETTINGS_FILE)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Merge with defaults
        for k, v in defaults.items():
            if k not in data:
                data[k] = v
        return data
    except FileNotFoundError:
        return defaults
    except Exception:
        logger.exception("Failed to load voice settings")
        return defaults


def save_voice_settings(settings: dict):
    """Save voice settings to disk."""
    try:
        path = get_app_data_file(_SETTINGS_FILE)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        logger.exception("Failed to save voice settings")

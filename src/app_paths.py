import os
import platform


APP_DIR_NAME = "UniversalControlKit"


def get_app_data_dir() -> str:
    system = platform.system()

    if system == "Darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif system == "Windows":
        base = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")

    app_dir = os.path.join(base, APP_DIR_NAME)
    os.makedirs(app_dir, exist_ok=True)
    return app_dir


def get_app_data_file(filename: str) -> str:
    return os.path.join(get_app_data_dir(), filename)

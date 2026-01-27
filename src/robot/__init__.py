import importlib
import pathlib
import sys


# Dynamically import all Python modules for robot implementations.
# TODO: Refactor
robot_dir = pathlib.Path(__file__).parent
for pyfile in robot_dir.glob("*.py"):
    name = pyfile.stem
    if name.startswith("_") or name == "robot_repository" or name == "robot":
        continue
    module_name = f"{__package__}.{name}" if __package__ else name
    if module_name not in sys.modules:
        importlib.import_module(module_name)

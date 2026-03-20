import importlib
import pathlib
import pkgutil
import sys


def _iter_robot_module_names() -> list[str]:
    excluded = {"robot", "robot_repository", "__init__"}
    module_names: list[str] = []

    package_name = __package__ or __name__
    try:
        package_module = importlib.import_module(package_name)
        package_path = getattr(package_module, "__path__", None)
        if package_path is not None:
            for module_info in pkgutil.iter_modules(package_path):
                name = module_info.name
                if name.startswith("_") or name in excluded:
                    continue
                module_names.append(f"{package_name}.{name}")
    except Exception:
        pass

    if module_names:
        return module_names

    robot_dir = pathlib.Path(__file__).parent
    for pyfile in robot_dir.glob("*.py"):
        name = pyfile.stem
        if name.startswith("_") or name in excluded:
            continue
        module_names.append(f"{package_name}.{name}" if package_name else name)

    return module_names


for module_name in _iter_robot_module_names():
    if module_name in sys.modules:
        continue
    try:
        importlib.import_module(module_name)
    except Exception:
        continue

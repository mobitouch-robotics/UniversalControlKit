from typing import List, Optional
from .robot import Robot


class RobotRepository:
    def save_to_file(self, filepath: str):
        import json

        robots_data = []
        for robot in self.robots:
            props = robot.__class__.properties()
            data = {"type": robot.get_type()}
            for key in props:
                data[key] = getattr(robot, key, None)
            data["id"] = getattr(robot, "id", None)
            data["name"] = getattr(robot, "name", None)
            robots_data.append(data)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(robots_data, f, indent=2)

    def load_from_file(self, filepath: str):
        import json
        from .robot import Robot
        import importlib

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                robots_data = json.load(f)
        except Exception:
            return
        self.robots.clear()
        for data in robots_data:
            robot_type = data.get("type")
            robot_cls = next(
                (
                    cls
                    for cls in iter_robot_implementations()
                    if cls.__name__ == robot_type
                ),
                None,
            )
            if robot_cls:
                # Only pass properties defined in robot_cls.properties()
                props = robot_cls(id=data.get("id"), name=data.get("name"))
                for key in robot_cls.properties():
                    if key in data:
                        setattr(props, key, data[key])
                self.robots.append(props)

    _instance = None

    _storage_file = "robots.json"

    def add_robot(self, robot_instance: Robot):
        """Add a new robot instance to the repository and save."""
        if robot_instance not in self.robots:
            self.robots.append(robot_instance)
            self.save_to_file(self._storage_file)
            return True
        return False

    def delete_robot(self, robot_instance: Robot):
        """Delete a robot instance from the repository and save."""
        if robot_instance in self.robots:
            self.robots.remove(robot_instance)
            self.save_to_file(self._storage_file)
            return True
        return False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.robots = []
        # Try to load from file first
        try:
            self.load_from_file(self._storage_file)
        except Exception as e:
            print(f"Failed to load robots from file. Exception: {e}")
            self.robots = []
        self._initialized = True

    def get_robots(self) -> List:
        return self.robots

    def get_robot_by_id(self, robot_id: str) -> Optional[Robot]:
        for robot in self.robots:
            if getattr(robot, "id", None) == robot_id:
                return robot
        return None


def iter_robot_implementations():
    """Yield all non-abstract Robot subclasses recursively."""

    def all_subclasses(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from all_subclasses(sub)

    for sub in all_subclasses(Robot):
        # Optionally skip abstract classes
        if not hasattr(sub, "__abstractmethods__") or not sub.__abstractmethods__:
            yield sub

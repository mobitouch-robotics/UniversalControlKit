from typing import List, Optional
from .robot import Robot


class RobotRepository:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.robots: List = []
        # Dynamically instantiate all Robot implementations with default args
        for robot_cls in iter_robot_implementations():
            try:
                # You may want to customize instantiation logic here
                if robot_cls.__name__ == "Robot_Go2":
                    self.robots.append(
                        robot_cls(id="go2", name="Go2 Robot", ip="192.168.1.192")
                    )
                elif robot_cls.__name__ == "Robot_Dummy":
                    self.robots.append(robot_cls(id="dummy", name="Dummy Robot"))
                    self.robots.append(robot_cls(id="dummy2", name="Dummy Robot"))
                else:
                    self.robots.append(
                        robot_cls(
                            id=robot_cls.__name__.lower(), name=robot_cls.__name__
                        )
                    )
            except Exception:
                pass
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

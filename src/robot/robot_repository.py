from typing import List, Optional
from .robot_go2 import Robot_Go2
from .robot_dummy import Robot_Dummy


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
        self.robots.append(Robot_Go2(id="go2", name="Go2 Robot", ip="192.168.1.192"))
        self.robots.append(Robot_Dummy(id="dummy", name="Dummy Robot"))
        self.robots.append(Robot_Dummy(id="dummy2", name="Dummy Robot 2"))
        self.robots.append(Robot_Dummy(id="dummy3", name="Dummy Robot 3"))
        self.robots.append(
            Robot_Dummy(
                id="dummy4", name="Dummy Robot 4 with long name asakskasjkajsas"
            )
        )
        self._initialized = True

    def get_robots(self) -> List:
        return self.robots

    def get_robot_by_id(self, robot_id: str) -> Optional:
        for robot in self.robots:
            if getattr(robot, "id", None) == robot_id:
                return robot
        return None

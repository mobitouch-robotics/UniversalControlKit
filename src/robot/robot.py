from abc import ABC, abstractmethod
from typing import Optional
import numpy


class Robot(ABC):
    @abstractmethod
    def property_requirement(self, name):
        """
        Returns:
            None: if property should not be displayed at all
            True: if property is required
            False: if property is optional
        """
        pass

    @classmethod
    @abstractmethod
    def properties(cls) -> dict:
        """
        Return a dictionary of configuration keys and their types for the robot implementation.
        Example:
            return {
                "ip_address": "str",
                "connection_method": "enum:option1|option2|option3"
            }
        """
        pass

    def __init__(self, id: str, name: str, *args, **kwargs):
        self.id = id
        self.name = name
        self._status_observers = []

    def add_status_observer(self, callback):
        if callback not in self._status_observers:
            self._status_observers.append(callback)

    def remove_status_observer(self, callback):
        if callback in self._status_observers:
            self._status_observers.remove(callback)

    def notify_status_observers(self):
        for cb in self._status_observers:
            try:
                cb(self)
            except Exception:
                pass

    def get_type(self) -> str:
        """Return the robot type as the class name by default."""
        return self.__class__.__name__

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        pass

    @property
    @abstractmethod
    def battery_status(self) -> int:
        pass

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def get_camera_frame(self) -> Optional[numpy.ndarray]:
        pass

    @abstractmethod
    def move(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def rest(self):
        pass

    @abstractmethod
    def standup(self):
        pass

    @abstractmethod
    def jump_forward(self):
        pass

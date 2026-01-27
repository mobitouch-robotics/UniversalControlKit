from abc import ABC, abstractmethod
from typing import Optional, List
import numpy as np


class Robot(ABC):
    @property
    def battery_status(self) -> int:
        """Return battery percentage (0-100). Override in subclasses."""
        raise NotImplementedError()

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

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def get_camera_frame(self) -> Optional[np.ndarray]:
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

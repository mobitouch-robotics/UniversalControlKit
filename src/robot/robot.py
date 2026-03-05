from abc import ABC, abstractmethod
from typing import Optional
import numpy
from PyQt5.QtCore import QObject, pyqtSignal
from abc import ABCMeta


class MetaQObjectABC(type(QObject), ABCMeta):
    pass


class Robot(QObject, metaclass=MetaQObjectABC):
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

    @classmethod
    @abstractmethod
    def image(cls) -> str | None:
        pass

    @classmethod
    @abstractmethod
    def display_name(cls) -> str:
        pass

    status_changed = pyqtSignal(object)

    def __init__(self, *args, **kwargs):
        super().__init__()
        # Latest reported maximum temperature (°C) or None
        self._temperature = None

    def add_status_observer(self, callback):
        self.status_changed.connect(callback)

    def remove_status_observer(self, callback):
        self.status_changed.disconnect(callback)

    def notify_status_observers(self):
        self.status_changed.emit(self)

    def get_type(self) -> str:
        """Return the robot type as the class name by default."""
        return self.__class__.__name__

    @property
    def temperature(self) -> int | None:
        """Maximum reported temperature in °C or None if unknown."""
        return self._temperature

    @temperature.setter
    def temperature(self, value: int | None):
        if value is None:
            if self._temperature is None:
                return
            self._temperature = None
            self.notify_status_observers()
            return
        try:
            v = int(value)
        except Exception:
            return
        if v != self._temperature:
            self._temperature = v
            self.notify_status_observers()

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        pass

    @property
    @abstractmethod
    def is_connecting(self) -> bool:
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

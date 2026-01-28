from enum import Enum, auto


# Universal key code enum
class KeyCode(Enum):
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()
    Z = auto()
    X = auto()
    SHIFT = auto()
    TAB = auto()
    ZERO = auto()
    UNKNOWN = auto()


from abc import ABC, abstractmethod
from typing import Optional
import numpy

_ExitCode = int


class UIApp(ABC):
    @abstractmethod
    def run(self) -> _ExitCode:
        """Run the UI application and return an exit code."""
        raise NotImplementedError()


class MovementControllerProtocol(ABC):

    def __init__(self, robot):
        self.robot = robot

    @abstractmethod
    def setup(self):
        pass

    @abstractmethod
    def cleanup(self):
        pass

    def handle_key_press(self, key: "KeyCode"):
        pass

    def handle_key_release(self, key: "KeyCode"):
        pass


class CameraViewProtocol(ABC):
    @abstractmethod
    def update_frame(self, frame: Optional[numpy.ndarray]):
        pass

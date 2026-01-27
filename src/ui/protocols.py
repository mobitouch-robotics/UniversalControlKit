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
    @abstractmethod
    def setup(self):
        pass

    @abstractmethod
    def cleanup(self):
        pass

class CameraViewProtocol(ABC):
    @abstractmethod
    def update_frame(self, frame: Optional[numpy.ndarray]):
        pass
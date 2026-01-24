from abc import ABC, abstractmethod
from typing import Optional
import numpy as np


class MovementControllerProtocol(ABC):
    @abstractmethod
    def setup(self) -> None:
        pass

    @abstractmethod
    def cleanup(self) -> None:
        pass


class CameraViewProtocol(ABC):
    @abstractmethod
    def update_frame(self, frame: Optional[np.ndarray]) -> None:
        pass


class UIApp(ABC):
    @abstractmethod
    def run(self) -> None:
        pass

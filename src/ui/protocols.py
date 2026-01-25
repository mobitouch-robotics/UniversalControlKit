from abc import ABC, abstractmethod
from typing import Optional
import numpy as np

class UIApp(ABC):
    @abstractmethod
    def run(self):
        pass

class MovementControllerProtocol(ABC):
    @abstractmethod
    def setup(self):
        pass

    @abstractmethod
    def cleanup(self):
        pass

class CameraViewProtocol(ABC):
    @abstractmethod
    def update_frame(self, frame: Optional[np.ndarray]):
        pass
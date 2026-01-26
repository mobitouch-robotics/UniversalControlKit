from abc import ABC, abstractmethod
from typing import Optional
import numpy as np

class Robot(ABC):

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

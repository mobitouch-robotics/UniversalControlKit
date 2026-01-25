from abc import ABC, abstractmethod
from typing import Optional
import numpy as np

class Robot(ABC):

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if the robot is connected and can accept commands."""
        pass

    @abstractmethod
    def connect(self):
        """Connect to the robot."""
        pass

    @abstractmethod
    def disconnect(self):
        """
        Disconnect from the robot. This method must be non-blocking and should not block the main/UI thread.
        If the disconnect operation is slow, it should internally run in a background thread or use async mechanisms as appropriate.
        """
        pass

    @abstractmethod
    def move(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        """Move the robot with specified velocities."""
        pass

    @abstractmethod
    def stop(self):
        """Stop all robot movement."""
        pass

    @abstractmethod
    def rest(self):
        """Put the robot into rest position (lay down)."""
        pass

    @abstractmethod
    def standup(self):
        """Make the robot stand up from rest position."""
        pass

    @abstractmethod
    def jump_forward(self):
        """Make the robot jump forward."""
        pass

    @abstractmethod
    def get_camera_frame(self) -> Optional[np.ndarray]:
        """Get the latest camera frame from the robot."""
        pass

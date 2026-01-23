from abc import ABC

class Robot(ABC):

    async def connect(self) -> bool:
        pass

    async def disconnect(self) -> bool:
        pass


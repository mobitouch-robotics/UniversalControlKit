from abc import ABC, abstractmethod
from typing import Optional


class STTProvider(ABC):
    """Abstract base class for speech-to-text providers."""

    @abstractmethod
    def transcribe(self, audio_data: bytes, sample_rate: int) -> Optional[str]:
        """Transcribe raw PCM audio bytes to text.

        Args:
            audio_data: Raw 16-bit mono PCM audio bytes.
            sample_rate: Sample rate in Hz (e.g. 16000).

        Returns:
            Transcribed text, or None if nothing was recognized.
        """
        raise NotImplementedError()

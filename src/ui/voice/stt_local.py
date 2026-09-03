import logging
import numpy as np
from typing import Optional

from .stt_provider import STTProvider

logger = logging.getLogger(__name__)


class LocalWhisperProvider(STTProvider):
    """Local speech-to-text using faster-whisper (CTranslate2 backend).

    Loads the model lazily on first transcription call to avoid blocking startup.
    """

    def __init__(self, model_size: str = "base", language: str = "en"):
        self._model_size = model_size
        self._language = language
        self._model = None

    @property
    def language(self) -> str:
        return self._language

    @language.setter
    def language(self, value: str):
        self._language = value

    @property
    def model_size(self) -> str:
        return self._model_size

    def _ensure_model(self):
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel
            logger.info("Loading faster-whisper model '%s'...", self._model_size)
            self._model = WhisperModel(self._model_size, compute_type="int8")
            logger.info("faster-whisper model loaded successfully.")
        except Exception:
            logger.exception("Failed to load faster-whisper model")
            raise

    def transcribe(self, audio_data: bytes, sample_rate: int) -> Optional[str]:
        self._ensure_model()

        # Convert raw 16-bit PCM bytes to float32 numpy array
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        if len(audio_np) == 0:
            return None

        # Resample to 16000 Hz if needed (faster-whisper expects 16kHz)
        if sample_rate != 16000:
            try:
                ratio = 16000 / sample_rate
                indices = np.arange(0, len(audio_np), 1 / ratio).astype(int)
                indices = indices[indices < len(audio_np)]
                audio_np = audio_np[indices]
            except Exception:
                logger.warning("Failed to resample audio from %d to 16000 Hz", sample_rate)

        try:
            segments, info = self._model.transcribe(
                audio_np,
                language=self._language,
                beam_size=3,
                vad_filter=True,
            )
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())
            result = " ".join(text_parts).strip()
            return result if result else None
        except Exception:
            logger.exception("Transcription failed")
            return None

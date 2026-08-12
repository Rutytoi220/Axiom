"""AudioManager — unified façade for AXIOM's audio subsystem.

Wraps the existing TextToSpeechEngine and AudioRecorder/WhisperTranscriber
into a single, import-friendly surface. Does NOT rewrite the underlying
engines — just provides a unified access point and the TTS-enabled toggle
that the UI checks before speaking.
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


class AudioManager:
    """Thin façade over TextToSpeechEngine, AudioRecorder and WhisperTranscriber."""

    _instance: AudioManager | None = None

    @classmethod
    def instance(cls) -> "AudioManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self.tts_enabled: bool = True   # toggled by the speaker button
        self._tts = None
        self._stt = None
        self._recorder = None

        try:
            from axiom.audio.tts import TextToSpeechEngine
            self._tts = TextToSpeechEngine.instance()
            logger.info("AudioManager: TTS ready")
        except Exception as e:
            logger.warning(f"AudioManager: TTS unavailable — {e}")

        try:
            from axiom.audio.stt import WhisperTranscriber, AudioRecorder
            self._stt = WhisperTranscriber.instance()
            self._recorder = AudioRecorder()
            logger.info("AudioManager: STT ready")
        except Exception as e:
            logger.warning(f"AudioManager: STT unavailable — {e}")

    # ── TTS ───────────────────────────────────────────────────────────── #

    async def speak(self, text: str) -> None:
        """Speak text asynchronously if TTS is enabled and available."""
        if not self.tts_enabled or not self._tts:
            return
        await self._tts.speak(text)

    # ── STT push-to-talk ──────────────────────────────────────────────── #

    @property
    def has_stt(self) -> bool:
        return self._stt is not None and self._recorder is not None

    def start_listening(self) -> None:
        """Start audio capture (push-to-talk)."""
        if self._recorder:
            self._recorder.start_recording()

    def stop_listening(self):
        """Stop audio capture and return raw numpy array."""
        if self._recorder:
            return self._recorder.stop_recording()
        import numpy as np
        return np.array([], dtype="float32")

    async def transcribe(self, audio_data) -> str:
        """Transcribe captured audio via faster-whisper."""
        if not self._stt:
            return ""
        return await self._stt.transcribe(audio_data)

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
        self._tts_loaded = False
        self._stt_loaded = False

    def _load_tts_sync(self):
        if self._tts_loaded: return
        self._tts_loaded = True
        try:
            from axiom.audio.tts import TextToSpeechEngine
            self._tts = TextToSpeechEngine.instance()
            logger.info("AudioManager: TTS dynamically loaded")
        except Exception as e:
            logger.warning(f"AudioManager: TTS loading failed: {e}")

    async def prepare_tts(self) -> None:
        if not self._tts_loaded:
            import asyncio
            await asyncio.to_thread(self._load_tts_sync)

    def _load_stt_sync(self):
        if self._stt_loaded: return
        self._stt_loaded = True
        try:
            from axiom.audio.stt import WhisperTranscriber, AudioRecorder
            self._stt = WhisperTranscriber.instance()
            self._recorder = AudioRecorder()
            logger.info("AudioManager: STT dynamically loaded")
        except Exception as e:
            logger.warning(f"AudioManager: STT loading failed: {e}")

    async def prepare_stt(self) -> None:
        if not self._stt_loaded:
            import asyncio
            await asyncio.to_thread(self._load_stt_sync)

    # ── TTS ───────────────────────────────────────────────────────────── #

    async def speak(self, text: str) -> None:
        """Speak text asynchronously if TTS is enabled and available."""
        if not self.tts_enabled:
            return
        await self.prepare_tts()
        if not self._tts:
            return
        await self._tts.speak(text)

    # ── STT push-to-talk ──────────────────────────────────────────────── #

    @property
    def has_stt(self) -> bool:
        """Optimistically return True if it hasn't failed to load yet."""
        if not self._stt_loaded:
            return True
        return self._stt is not None and self._recorder is not None

    def start_listening_sync(self) -> None:
        """Start audio capture (must call await prepare_stt() first)."""
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
        await self.prepare_stt()
        if not self._stt:
            return ""
        return await self._stt.transcribe(audio_data)

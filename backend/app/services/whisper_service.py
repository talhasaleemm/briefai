"""
WhisperService stub — full implementation in Stage 2.
"""


class WhisperService:
    """Wraps faster-whisper for audio transcription (stub)."""

    def __init__(self) -> None:
        self._model = None

    def transcribe(self, audio_path: str) -> dict:
        raise NotImplementedError("WhisperService will be implemented in Stage 2.")

"""
WhisperService — wraps faster-whisper for audio transcription.

Supports:
  - File-based transcription (path to any audio file)
  - NumPy array transcription  (for WebSocket streaming)

The model is loaded lazily on first call and cached as a module-level singleton
so it is not reloaded between requests.
"""
from __future__ import annotations

import logging
import time
from math import gcd
from pathlib import Path
from typing import Optional

import numpy as np

from briefai.config import settings
from briefai.schemas import TranscriptionResult, TranscriptSegment

logger = logging.getLogger(__name__)


class WhisperService:
    """
    Thread-safe wrapper around faster_whisper.WhisperModel.

    Model loading is deferred to the first call of transcribe_file() or
    transcribe_array() so startup time is zero even if whisper is unused.
    """

    def __init__(self) -> None:
        self._model = None
        self._model_size: str = settings.WHISPER_MODEL_SIZE
        self._device: str = settings.WHISPER_DEVICE
        self._compute_type: str = settings.WHISPER_COMPUTE_TYPE

    # ── Internal ──────────────────────────────────────────────────────────────

    def _load_model(self) -> None:
        """Load the faster-whisper model. Safe to call multiple times — is a no-op after first load."""
        if self._model is not None:
            return

        from faster_whisper import WhisperModel  # lazy import — avoids startup cost

        logger.info(
            "Loading faster-whisper model '%s' on device='%s' compute='%s'",
            self._model_size,
            self._device,
            self._compute_type,
        )
        t0 = time.perf_counter()

        try:
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
            )
        except (ValueError, RuntimeError) as exc:
            # Graceful CUDA → CPU fallback
            if any(kw in str(exc).lower() for kw in ("cuda", "gpu", "cublas")):
                logger.warning("CUDA unavailable — falling back to CPU int8. Reason: %s", exc)
                self._device = "cpu"
                self._compute_type = "int8"
                self._model = WhisperModel(
                    self._model_size,
                    device="cpu",
                    compute_type="int8",
                )
            else:
                raise

        elapsed = time.perf_counter() - t0
        logger.info("Model loaded in %.2f s", elapsed)

    @staticmethod
    def _resample_to_16k(audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Resample audio to 16 kHz using polyphase filtering (scipy)."""
        if sample_rate == 16000:
            return audio
        from scipy.signal import resample_poly

        factor = gcd(16000, sample_rate)
        up, down = 16000 // factor, sample_rate // factor
        return resample_poly(audio, up, down).astype(np.float32)

    # ── Public API ────────────────────────────────────────────────────────────

    def transcribe_file(
        self,
        audio_path: str | Path,
        language: Optional[str] = None,
        beam_size: int = 5,
    ) -> TranscriptionResult:
        """
        Transcribe an audio file (WAV, MP3, FLAC, OGG, …).

        Args:
            audio_path:  Path to the audio file.
            language:    ISO 639-1 language code, or None for auto-detect.
            beam_size:   Beam width for decoding (higher → more accurate, slower).

        Returns:
            TranscriptionResult with full concatenated transcript + per-segment detail.
        """
        self._load_model()

        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(
            "Transcribing file '%s' (language=%s, beam=%d)",
            audio_path.name,
            language or "auto",
            beam_size,
        )
        t0 = time.perf_counter()

        segments_gen, info = self._model.transcribe(
            str(audio_path),
            language=language or None,
            beam_size=beam_size,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )

        segments: list[TranscriptSegment] = []
        text_parts: list[str] = []

        for seg in segments_gen:  # consume generator eagerly
            cleaned = seg.text.strip()
            if cleaned:
                segments.append(
                    TranscriptSegment(
                        start=round(seg.start, 3),
                        end=round(seg.end, 3),
                        text=cleaned,
                        confidence=round(seg.avg_logprob, 4),
                    )
                )
                text_parts.append(cleaned)

        elapsed = time.perf_counter() - t0
        logger.info(
            "File transcription done in %.2f s — %d segment(s), detected language='%s'",
            elapsed,
            len(segments),
            info.language,
        )

        return TranscriptionResult(
            transcript=" ".join(text_parts),
            segments=segments,
            language=info.language,
            duration_seconds=round(info.duration, 3),
        )

    def transcribe_array(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        language: Optional[str] = None,
        beam_size: int = 5,
    ) -> TranscriptionResult:
        """
        Transcribe a NumPy float32 audio array (used by the WebSocket endpoint).

        Args:
            audio:        Float32 mono audio samples.
            sample_rate:  Source sample rate (will be resampled to 16 kHz if needed).
            language:     ISO 639-1 code, or None for auto-detect.
            beam_size:    Beam width for decoding.

        Returns:
            TranscriptionResult.
        """
        self._load_model()

        # Normalise dtype
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Stereo → mono
        if audio.ndim == 2:
            audio = audio.mean(axis=1).astype(np.float32)
        elif audio.ndim != 1:
            raise ValueError(f"Expected 1-D or 2-D audio array, got shape {audio.shape}")

        # Resample if necessary
        audio = self._resample_to_16k(audio, sample_rate)

        duration = len(audio) / 16000
        logger.info(
            "Transcribing audio array: %.2f s at %d Hz (language=%s)",
            duration,
            sample_rate,
            language or "auto",
        )
        t0 = time.perf_counter()

        segments_gen, info = self._model.transcribe(
            audio,
            language=language or None,
            beam_size=beam_size,
            # VAD filter is intentionally DISABLED for streaming chunks.
            # The Silero VAD model needs long-form context and aggressively
            # discards entire short 3-second streaming chunks as "silence",
            # producing empty transcripts even when speech is present.
            # The VAD chunking is handled upstream by the WebSocket endpoint.
            vad_filter=False,
        )

        segments: list[TranscriptSegment] = []
        text_parts: list[str] = []

        for seg in segments_gen:
            cleaned = seg.text.strip()
            if cleaned:
                segments.append(
                    TranscriptSegment(
                        start=round(seg.start, 3),
                        end=round(seg.end, 3),
                        text=cleaned,
                        confidence=round(seg.avg_logprob, 4),
                    )
                )
                text_parts.append(cleaned)

        elapsed = time.perf_counter() - t0
        logger.info("Array transcription done in %.2f s", elapsed)

        return TranscriptionResult(
            transcript=" ".join(text_parts),
            segments=segments,
            language=info.language,
            duration_seconds=round(info.duration, 3),
        )

    @property
    def is_loaded(self) -> bool:
        """True if the underlying model has been loaded into memory."""
        return self._model is not None


# ── Module-level singleton ────────────────────────────────────────────────────
_singleton: Optional[WhisperService] = None


def get_whisper_service() -> WhisperService:
    """
    FastAPI dependency — returns the shared WhisperService singleton.
    The model is NOT loaded here; it loads lazily on the first transcription call.
    """
    global _singleton
    if _singleton is None:
        _singleton = WhisperService()
    return _singleton

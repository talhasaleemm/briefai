"""
DiarizationService — uses SpeechBrain ECAPA-TDNN embeddings and Scikit-Learn clustering 
to assign speaker labels to Whisper transcription segments.
"""
import logging
import time
from typing import Optional, List, Dict, Any
from pathlib import Path

import torch
import torchaudio
import numpy as np
from sklearn.cluster import AgglomerativeClustering

from app.core.config import settings

logger = logging.getLogger(__name__)


class NullDiarizationService:
    """A no-op service returned when diarization is disabled in config."""
    def diarize_segments(self, audio_path: str | Path, whisper_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Return segments unmodified except for a default speaker label
        return [
            {**seg, "speaker": "Speaker 1"} for seg in whisper_segments
        ]

    @property
    def is_loaded(self) -> bool:
        return False


class DiarizationService:
    """
    Token-free speaker diarization pipeline using SpeechBrain embeddings.
    Lazy loads the ECAPA-TDNN model on first request.
    """
    def __init__(self) -> None:
        self._classifier = None
        self._model_source = "speechbrain/spkrec-ecapa-voxceleb"
        self._savedir = Path("models") / "speechbrain"

    def _load_model(self) -> None:
        """Lazy load the SpeechBrain ECAPA-TDNN encoder."""
        if self._classifier is not None:
            return

        logger.info("Loading SpeechBrain ECAPA-TDNN speaker embedding model...")
        t0 = time.perf_counter()

        # Monkey-patch torchaudio.list_audio_backends for SpeechBrain compatibility
        import torchaudio
        original_list_audio_backends = getattr(torchaudio, 'list_audio_backends', None)
            
        # Monkey-patch huggingface_hub for SpeechBrain compatibility (use_auth_token -> token)
        import huggingface_hub
        original_hf_hub_download = huggingface_hub.hf_hub_download
        
        # Monkey-patch os.symlink for Windows (SpeechBrain uses symlink_to which calls os.symlink)
        import os, shutil
        original_symlink = getattr(os, 'symlink', None)
        
        def patched_hf_hub_download(*args, **kwargs):
            if 'use_auth_token' in kwargs:
                kwargs['token'] = kwargs.pop('use_auth_token')
            try:
                return original_hf_hub_download(*args, **kwargs)
            except Exception as e:
                # SpeechBrain expects requests.exceptions.HTTPError(404) for missing custom.py,
                # but newer huggingface_hub uses httpx and throws HTTPStatusError.
                filename = kwargs.get('filename')
                if not filename and len(args) > 1:
                    filename = args[1]
                if filename == 'custom.py':
                    # specifically catch only HTTPStatusError with 404 for custom.py
                    import httpx
                    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                        raise ValueError("File not found on HF hub")
                raise

        def patched_symlink(src, dst, target_is_directory=False, **kwargs):
            try:
                original_symlink(src, dst, target_is_directory, **kwargs)
            except OSError as e:
                if getattr(e, 'winerror', None) == 1314:
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)
                else:
                    raise

        from speechbrain.inference.speaker import EncoderClassifier
        
        run_opts = {"device": "cpu"}
        if settings.WHISPER_DEVICE != "cpu" and torch.cuda.is_available():
             run_opts["device"] = "cuda"

        try:
            torchaudio.list_audio_backends = lambda: ["soundfile"]
            huggingface_hub.hf_hub_download = patched_hf_hub_download
            if original_symlink:
                os.symlink = patched_symlink

            self._classifier = EncoderClassifier.from_hparams(
                source=self._model_source,
                savedir=str(self._savedir),
                run_opts=run_opts
            )
        finally:
            if original_list_audio_backends:
                torchaudio.list_audio_backends = original_list_audio_backends
            else:
                delattr(torchaudio, 'list_audio_backends')
            huggingface_hub.hf_hub_download = original_hf_hub_download
            if original_symlink:
                os.symlink = original_symlink
        
        elapsed = time.perf_counter() - t0
        logger.info("Embedding model loaded in %.2f s", elapsed)

    def diarize_segments(
        self, 
        audio_path: str | Path, 
        whisper_segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract speaker embeddings for each Whisper segment and cluster them to assign speaker labels.
        
        Args:
            audio_path: Path to the original audio file.
            whisper_segments: List of segment dicts containing 'start' and 'end' in seconds.
            
        Returns:
            List of LabeledSegment dicts with 'speaker' field appended.
        """
        if not whisper_segments:
            return []

        self._load_model()
        
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info("Starting diarization for %d segments using SpeechBrain...", len(whisper_segments))
        t0 = time.perf_counter()

        # 1. Load audio using soundfile directly to avoid torchaudio's torchcodec dependency
        import soundfile as sf
        wav_data, sr = sf.read(str(audio_path), dtype='float32')
        if wav_data.ndim == 1:
            waveform = torch.from_numpy(wav_data).unsqueeze(0)
        else:
            waveform = torch.from_numpy(wav_data).transpose(0, 1)

        # Resample if necessary
        if sr != 16000:
            resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16000)
            waveform = resampler(waveform)
            sr = 16000

        # 2. Extract embeddings for each segment
        embeddings = []
        valid_indices = []
        
        for i, seg in enumerate(whisper_segments):
            start_sec = seg["start"]
            end_sec = seg["end"]
            
            # Convert to sample indices
            start_idx = int(start_sec * sr)
            end_idx = int(end_sec * sr)
            
            # Slice the audio waveform
            chunk = waveform[:, start_idx:end_idx]
            
            # ECAPA-TDNN expects at least ~0.5s of audio to produce a valid embedding. 
            # Very short segments are risky. We will still extract them, but pad if too short.
            if chunk.shape[1] < 1600: # less than 0.1s
                pad_amount = 1600 - chunk.shape[1]
                chunk = torch.nn.functional.pad(chunk, (0, pad_amount))

            with torch.no_grad():
                emb = self._classifier.encode_batch(chunk)
                # emb shape is [batch, 1, 192]
                emb = emb.squeeze().cpu().numpy()
                embeddings.append(emb)
                valid_indices.append(i)

        if not embeddings:
            # Fallback if no embeddings could be extracted
            return [{**seg, "speaker": "Speaker 1"} for seg in whisper_segments]

        X = np.stack(embeddings) # shape: [num_segments, 192]
        
        # If there's only one segment, we can't cluster
        if len(X) == 1:
            return [{**whisper_segments[0], "speaker": "Speaker 1"}]

        # 3. Cluster the embeddings
        # Cosine distance is the standard metric for angular margin embeddings like ECAPA-TDNN.
        # We use a fixed distance_threshold to let the algorithm decide the number of speakers.
        clustering = AgglomerativeClustering(
            n_clusters=None,
            metric="cosine",
            linkage="average",
            distance_threshold=settings.DIARIZATION_COSINE_THRESHOLD,
        )
        
        cluster_labels = clustering.fit_predict(X)
        
        # 4. Map cluster IDs to human-readable speaker names
        unique_clusters = np.unique(cluster_labels)
        # Create a mapping like {0: "Speaker 1", 2: "Speaker 2"}
        speaker_map = {cid: f"Speaker {i+1}" for i, cid in enumerate(unique_clusters)}

        # 5. Assign back to segments
        labeled_segments = []
        for i, seg in enumerate(whisper_segments):
            labeled_seg = dict(seg)
            if i in valid_indices:
                idx = valid_indices.index(i)
                cid = cluster_labels[idx]
                labeled_seg["speaker"] = speaker_map[cid]
            else:
                labeled_seg["speaker"] = "Unknown"
            labeled_segments.append(labeled_seg)

        elapsed = time.perf_counter() - t0
        logger.info("Diarization complete in %.2f s. Detected %d speaker(s).", elapsed, len(unique_clusters))

        return labeled_segments

    @property
    def is_loaded(self) -> bool:
        return self._classifier is not None


# ── Module-level singleton ────────────────────────────────────────────────────
_singleton: Optional[DiarizationService] = None


def get_diarization_service() -> DiarizationService | NullDiarizationService:
    """
    FastAPI dependency — returns the shared DiarizationService singleton,
    or a Null service if the feature is disabled.
    """
    if not settings.DIARIZATION_ENABLED:
        return NullDiarizationService()
        
    global _singleton
    if _singleton is None:
        _singleton = DiarizationService()
    return _singleton

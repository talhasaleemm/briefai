import asyncio
import gc
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import numpy as np

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.diarization_service import DiarizationService, NullDiarizationService
from app.api.transcription import _background_diarization_tasks, _run_diarization
from app.core.security import create_access_token
from app.models.database import Transcript, User
from app.api.deps import get_current_user

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def clean_dependency_overrides():
    """Temporarily clears get_current_user auth override to test actual auth logic."""
    old_override = app.dependency_overrides.pop(get_current_user, None)
    yield
    if old_override is not None:
        app.dependency_overrides[get_current_user] = old_override


@pytest.fixture
def mock_diarization_service():
    """Returns a mock diarization service that generates predictable clusters."""
    svc = MagicMock(spec=DiarizationService)
    svc.is_loaded = True
    
    # Mock diarize_segments to just return predefined labeled segments
    def fake_diarize(audio_path, whisper_segments):
        labeled = []
        for i, seg in enumerate(whisper_segments):
            # Alternating speakers
            labeled.append({**seg, "speaker": f"Speaker {(i % 2) + 1}"})
        return labeled
        
    svc.diarize_segments.side_effect = fake_diarize
    return svc


def test_upload_triggers_diarization_when_enabled(sample_wav: Path, mock_diarization_service):
    token = create_access_token({"sub": "testuser_1"})
    
    from app.services.diarization_service import get_diarization_service
    app.dependency_overrides[get_diarization_service] = lambda: mock_diarization_service
    
    try:
        with patch("app.api.transcription.settings.DIARIZATION_ENABLED", True):
            # We need to mock _launch_diarization_task so the async background task doesn't 
            # hang the sync TestClient event loop unpredictably.
            with patch("app.api.transcription._launch_diarization_task") as mock_launch:
                mock_launch.side_effect = lambda coro: coro.close() # Prevent unawaited coroutine warning
                # 1. Upload
                with open(sample_wav, "rb") as f:
                    resp = client.post(
                        "/api/v1/transcription/upload",
                        files={"file": ("test.wav", f, "audio/wav")},
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    
                assert resp.status_code == 200
                data = resp.json()
                assert data["diarization_status"] == "pending"
                
                # Verify the background task was launched
                mock_launch.assert_called_once()
    finally:
        app.dependency_overrides.pop(get_diarization_service, None)


def test_diarization_endpoint_isolation(db, clean_dependency_overrides):
    # Create User A
    user_a = User(username="usera", email="a@example.com", hashed_password="pw")
    db.add(user_a)
    db.commit()
    db.refresh(user_a)

    # Create User B
    user_b = User(username="userb", email="b@example.com", hashed_password="pw")
    db.add(user_b)
    db.commit()
    db.refresh(user_b)

    user_a_token = create_access_token(str(user_a.id))
    user_b_token = create_access_token(str(user_b.id))

    # Create a transcript for User A
    transcript_a = Transcript(
        user_id=user_a.id,  # user A
        title="Test Transcript",
        content="Hello",
        diarization_status="complete",
        diarized_segments=[{"start": 0.0, "end": 1.0, "text": "Hello", "speaker": "Speaker 1"}]
    )
    db.add(transcript_a)
    db.commit()
    db.refresh(transcript_a)
    tid = transcript_a.id

    # User A can access
    resp = client.get(f"/api/v1/transcription/{tid}/diarization", headers={"Authorization": f"Bearer {user_a_token}"})
    assert resp.status_code == 200
    assert resp.json()["diarization_status"] == "complete"
    
    # User B cannot access - returns 404
    resp = client.get(f"/api/v1/transcription/{tid}/diarization", headers={"Authorization": f"Bearer {user_b_token}"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Transcript not found."


@pytest.mark.asyncio
async def test_background_task_anchored_not_silently_killed():
    """Verify task anchoring prevents garbage collection of pending tasks."""
    from app.api.transcription import _launch_diarization_task
    
    task_started = asyncio.Event()
    task_completed = asyncio.Event()
    
    async def slow_coro():
        task_started.set()
        await asyncio.sleep(0.1)
        task_completed.set()
        return "done"
        
    # Launch task - reference is intentionally NOT stored locally
    _launch_diarization_task(slow_coro())
    
    # Wait for it to start
    await task_started.wait()
    
    # Force garbage collection
    gc.collect()
    
    # The task should complete successfully because it's anchored in _background_diarization_tasks
    try:
        await asyncio.wait_for(task_completed.wait(), timeout=1.0)
    except asyncio.TimeoutError:
        pytest.fail("Task was silently killed by garbage collection")

def test_diarize_segments_clustering():
    """Verify that DiarizationService correctly clusters distinct embeddings."""
    from app.services.diarization_service import DiarizationService
    import numpy as np
    
    svc = DiarizationService()
    
    # We can mock the classifier and _load_model
    svc._load_model = lambda: None
    svc._classifier = MagicMock()
    
    # We'll mock the `encode_batch` to return distinct orthogonal embeddings for different speakers
    # Speaker A: [1, 0, 0], Speaker B: [0, 1, 0]
    
    # Let's say we have 4 segments: A, B, A, B
    segments = [
        {"start": 0.0, "end": 1.0, "text": "A1"},
        {"start": 1.0, "end": 2.0, "text": "B1"},
        {"start": 2.0, "end": 3.0, "text": "A2"},
        {"start": 3.0, "end": 4.0, "text": "B2"}
    ]
    
    import torch
    def fake_encode_batch(chunk):
        # We just use a stateful counter or size to determine which embedding to return
        # But `encode_batch` is called in a loop for each segment
        # In the DiarizationService, the chunk size is padded if less than 1600.
        # We can just mock the whole embedding loop if needed, but it's easier to mock `encode_batch` side_effect.
        pass
    
    svc._classifier.encode_batch.side_effect = [
        torch.tensor([[[1.0, 0.0, 0.0]]]), # A1
        torch.tensor([[[0.0, 1.0, 0.0]]]), # B1
        torch.tensor([[[1.0, 0.0, 0.0]]]), # A2
        torch.tensor([[[0.0, 1.0, 0.0]]])  # B2
    ]
    
    # We need a dummy audio file. We can just use a real wav file from tests
    # But `soundfile.read` will be called. We can mock that too.
    with patch("soundfile.read") as mock_read, patch("pathlib.Path.exists", return_value=True):
        # return dummy wav data (4 seconds of zeros)
        mock_read.return_value = (np.zeros(16000 * 4, dtype=np.float32), 16000)
        
        labeled = svc.diarize_segments("dummy.wav", segments)
        
    assert len(labeled) == 4
    # Check that A1 and A2 have the same speaker, B1 and B2 have the same speaker, and A != B
    assert labeled[0]["speaker"] == labeled[2]["speaker"]
    assert labeled[1]["speaker"] == labeled[3]["speaker"]
    assert labeled[0]["speaker"] != labeled[1]["speaker"]


@pytest.mark.asyncio
async def test_diarization_failed_state_on_exception(db, clean_dependency_overrides):
    """Verify that if diarize_segments throws an exception, the status is set to 'failed'."""
    from app.api.transcription import _run_diarization
    from app.services.diarization_service import DiarizationService
    
    user = User(username="erruser", email="err@example.com", hashed_password="pw")
    db.add(user)
    db.commit()
    
    transcript = Transcript(
        user_id=user.id,
        title="Err Transcript",
        content="Hello",
        diarization_status="pending",
        diarized_segments=[]
    )
    db.add(transcript)
    db.commit()
    db.refresh(transcript)
    tid = transcript.id
    
    svc = MagicMock(spec=DiarizationService)
    svc.diarize_segments.side_effect = Exception("Simulated crash")
    
    # We need to run the background task logic directly
    import pathlib
    with patch("app.api.transcription.get_db") as mock_get_db:
        def dummy_gen():
            yield db
        mock_get_db.side_effect = dummy_gen
        await _run_diarization(tid, pathlib.Path("dummy.wav"), [], svc)
    
    # Check DB state
    db.refresh(transcript)
    assert transcript.diarization_status == "failed"

def test_monkey_patch_restored_on_exception():
    """Verify that monkey patches in _load_model are strictly restored even if from_hparams crashes."""
    from app.services.diarization_service import DiarizationService
    import os
    import torchaudio
    
    # Pre-patch torchaudio so we can safely mock speechbrain without crashing its __init__
    if not hasattr(torchaudio, 'list_audio_backends'):
        torchaudio.list_audio_backends = lambda: ["soundfile"]
    
    svc = DiarizationService()
    
    original_symlink = getattr(os, 'symlink', None)
    
    import huggingface_hub
    original_hf = huggingface_hub.hf_hub_download
    
    # Mock from_hparams to throw an exception
    with patch("speechbrain.inference.speaker.EncoderClassifier.from_hparams") as mock_from_hparams:
        mock_from_hparams.side_effect = Exception("Simulated OOM crash during load")
        
        import pytest
        with pytest.raises(Exception, match="Simulated OOM crash during load"):
            svc._load_model()
            
    # Assert originals are fully restored
    assert getattr(os, 'symlink', None) is original_symlink
    assert huggingface_hub.hf_hub_download is original_hf

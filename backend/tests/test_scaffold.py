"""
Stage 1 scaffold smoke-test.
Verifies that:
  - All expected directories exist
  - All expected files exist
  - The FastAPI app can be imported without errors
  - Config loads with defaults (no .env required)
"""
import importlib
import sys
from pathlib import Path

# Make backend/ importable
BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

EXPECTED_DIRS = [
    "briefai",
    "briefai/routers",
    "briefai/utils",
    "briefai/internal",
    "briefai/retrieval",
    "briefai/models",
    "briefai/schemas",
    "briefai/services",
    "briefai/prompts",
    "tests",
]

EXPECTED_FILES = [
    "briefai/main.py",
    "briefai/config.py",
    "briefai/services/whisper_service.py",
    "briefai/services/ollama_service.py",
    "briefai/prompts/templates.py",
    "requirements.txt",
    ".env.example",
]


def test_directories_exist():
    for d in EXPECTED_DIRS:
        assert (BACKEND / d).is_dir(), f"Missing directory: {d}"


def test_files_exist():
    for f in EXPECTED_FILES:
        assert (BACKEND / f).is_file(), f"Missing file: {f}"


def test_app_imports():
    mod = importlib.import_module("briefai.main")
    assert hasattr(mod, "app"), "FastAPI 'app' object not found in main.py"


def test_config_loads():
    from briefai.config import settings
    assert settings.APP_NAME == "BriefAI"
    assert settings.PORT == 8000
    assert isinstance(settings.CORS_ORIGINS, list)


def test_schemas_importable():
    from briefai.schemas import (
        TranscriptionResult, SummarizationRequest
    )
    from briefai.constants import TaskType, ModelName
    assert TaskType.SUMMARIZE == "summarize"
    assert ModelName.QWEN3 == "qwen3:1.7b"

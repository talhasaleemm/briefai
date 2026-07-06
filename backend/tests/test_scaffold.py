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
    "app",
    "app/api",
    "app/core",
    "app/models",
    "app/services",
    "app/prompts",
    "tests",
]

EXPECTED_FILES = [
    "app/main.py",
    "app/core/config.py",
    "app/models/schemas.py",
    "app/services/whisper_service.py",
    "app/services/ollama_service.py",
    "app/prompts/templates.py",
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
    mod = importlib.import_module("app.main")
    assert hasattr(mod, "app"), "FastAPI 'app' object not found in main.py"


def test_config_loads():
    from app.core.config import settings
    assert settings.APP_NAME == "BriefAI"
    assert settings.PORT == 8000
    assert isinstance(settings.CORS_ORIGINS, list)


def test_schemas_importable():
    from app.models.schemas import (
        TaskType, ModelName, TranscriptionResult, SummarizationRequest
    )
    assert TaskType.SUMMARIZE == "summarize"
    assert ModelName.QWEN3 == "qwen3:1.7b"

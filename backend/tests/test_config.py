import os
import subprocess
import sys
from pathlib import Path

from backend.app.config import load_environment
from backend.app.services.ai_service import DEFAULT_GEMINI_MODEL, get_gemini_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_env_file_values_loaded_when_absent_from_os(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_API_KEY=dummy-test-key\n"
        "GEMINI_MODEL=gemini-custom-test\n"
        "DATABASE_URL=sqlite:///./data/custom_test.db\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    loaded = load_environment(dotenv_path=env_file)
    assert loaded is True

    api_key, model = get_gemini_config()
    assert api_key == "dummy-test-key"
    assert model == "gemini-custom-test"
    assert os.getenv("DATABASE_URL") == "sqlite:///./data/custom_test.db"


def test_os_environment_takes_precedence_over_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GEMINI_API_KEY=from-dotenv\n"
        "GEMINI_MODEL=from-dotenv-model\n"
        "CHROMA_PERSIST_DIR=/tmp/from_dotenv\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("GEMINI_API_KEY", "from-os-env")
    monkeypatch.setenv("GEMINI_MODEL", "from-os-model")
    monkeypatch.setenv("CHROMA_PERSIST_DIR", "/tmp/from_os")

    load_environment(dotenv_path=env_file)

    api_key, model = get_gemini_config()
    assert api_key == "from-os-env"
    assert model == "from-os-model"
    assert os.getenv("CHROMA_PERSIST_DIR") == "/tmp/from_os"


def test_defaults_when_optional_variables_absent(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-test-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CHROMA_PERSIST_DIR", raising=False)

    _, model = get_gemini_config()
    assert model == DEFAULT_GEMINI_MODEL


def test_module_imports_succeed_without_circular_errors():
    import_script = (
        "import importlib\n"
        "for mod in (\n"
        "    'backend.app.config',\n"
        "    'backend.app.database',\n"
        "    'backend.app.services.ai_service',\n"
        "    'backend.app.rag.ingest',\n"
        "    'backend.app.main',\n"
        "    'frontend.app',\n"
        "):\n"
        "    assert importlib.import_module(mod) is not None\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", import_script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"Fresh module import failed (exit {result.returncode}).\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

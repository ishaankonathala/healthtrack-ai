from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def load_environment(dotenv_path: Path | None = None) -> bool:
    """Load variables from .env without overriding existing OS environment variables."""
    target = dotenv_path if dotenv_path is not None else ENV_FILE
    return load_dotenv(dotenv_path=target, override=False)


load_environment()

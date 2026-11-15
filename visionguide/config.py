from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


# Resolve the project root independently of the current working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"


def load_environment() -> None:
    """
    Load project environment variables.

    The project's .env takes priority over existing OS environment variables.
    If .env does not exist, existing OS environment variables remain usable.
    """
    load_dotenv(dotenv_path=ENV_FILE, override=True)


@dataclass(frozen=True)
class AppConfig:
    model_path: str
    camera_index: int | str = 0
    confidence_threshold: float = 0.35
    target_fps: int = 8
    frame_width: int = 1280
    frame_height: int = 720
    speech_rate: int = 165
    safety_alert_cooldown_seconds: float = 5.0
    data_dir: Path = Path("data")

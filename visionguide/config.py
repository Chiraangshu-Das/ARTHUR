from dataclasses import dataclass
from pathlib import Path


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

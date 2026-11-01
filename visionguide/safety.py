from __future__ import annotations

import time
from visionguide.perception import Detection

# Only a small class set is considered. This is a visual heuristic, not a validated collision predictor.
APPROACH_CANDIDATES = {"person", "bicycle", "car", "motorcycle", "bus", "truck", "train", "dog"}


class SafetyEngine:
    """Alert filter; disabled by the UI at startup.

    An alert requires a tracked candidate in the central image area whose apparent
    bounding-box area has grown over time. This is not a validated collision predictor.
    """
    def __init__(self, cooldown_seconds: float = 5.0):
        self.cooldown_seconds = cooldown_seconds
        self.last_alert: dict[str, float] = {}

    def update(self, detections: list[Detection], frame_width: int, now: float | None = None) -> list[str]:
        if now is None:
            now = time.monotonic()
        alerts: list[str] = []
        for item in sorted(detections, key=lambda d: abs(d.center_x - frame_width / 2)):
            if item.label not in APPROACH_CANDIDATES or item.track_id is None:
                continue
            if item.area_growth < 1.28:
                continue
            if not (frame_width * 0.22 <= item.center_x <= frame_width * 0.78):
                continue
            key = f"{item.label}:{item.track_id}"
            if now - self.last_alert.get(key, -1e9) < self.cooldown_seconds:
                continue
            alerts.append(
                f"Possible approach pattern: {item.label} is near the centre of the camera view. "
                "This visual alert is not a validated mobility aid; verify your surroundings independently."
            )
            self.last_alert[key] = now
            if len(alerts) >= 1:
                break
        return alerts

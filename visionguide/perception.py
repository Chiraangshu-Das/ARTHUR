from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any
import time

import cv2


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int
    center_x: float
    center_y: float
    direction: str
    track_id: int | None = None
    motion_direction: str = ""
    area_growth: float = 1.0
    area_fraction: float = 0.0
    distance_m: float | None = None
    distance_spread: float | None = None
    closing_speed_mps: float | None = None
    time_to_contact_s: float | None = None


def direction_for(center_x: float, frame_width: int) -> str:
    """Image-relative direction, not a calibrated direction in world coordinates."""
    if center_x < frame_width / 3:
        return "left"
    if center_x > frame_width * 2 / 3:
        return "right"
    return "centre"


class MotionHistory:
    """Tracks apparent image motion. This is not a depth or collision sensor."""
    def __init__(self, max_age_seconds: float = 2.0):
        self.max_age_seconds = max_age_seconds
        self._samples: dict[int, deque[tuple[float, float, float, float]]] = defaultdict(lambda: deque(maxlen=16))

    def update(self, track_id: int | None, center_x: float, center_y: float, area: float, now: float) -> tuple[str, float]:
        if track_id is None:
            return "", 1.0
        samples = self._samples[track_id]
        while samples and now - samples[0][0] > self.max_age_seconds:
            samples.popleft()
        motion = ""
        growth = 1.0
        if samples:
            old_time, old_x, old_y, old_area = samples[0]
            newest_time, newest_x, newest_y, _ = samples[-1]
            dx = center_x - newest_x
            frame_delta = max(0.0, now - newest_time)
            if frame_delta > 0.02:
                if dx > 14:
                    motion = "moving right across image"
                elif dx < -14:
                    motion = "moving left across image"
            if now - old_time >= 0.45 and old_area > 0:
                growth = area / old_area
        samples.append((now, center_x, center_y, area))
        return motion, growth


def detect_objects(model: Any, frame, confidence_threshold: float, history: MotionHistory,
                   now: float | None = None, force_cpu: bool = False) -> list[Detection]:
    """Run the model's persistent multi-object tracker and convert detections."""
    if now is None:
        now = time.monotonic()
    kwargs = {"source": frame, "conf": confidence_threshold, "persist": True, "verbose": False}
    if force_cpu:
        kwargs["device"] = "cpu"
    results = model.track(**kwargs)
    if not results:
        return []
    result = results[0]
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return []

    names = model.names
    frame_height, frame_width = frame.shape[:2]
    output: list[Detection] = []
    ids = None
    try:
        if boxes.id is not None:
            ids = boxes.id.int().cpu().tolist()
    except Exception:
        ids = None

    for index, box in enumerate(boxes):
        class_id = int(box.cls[0])
        label = str(names[class_id])
        confidence = float(box.conf[0])
        x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        area = max(1, (x2 - x1) * (y2 - y1))
        track_id = int(ids[index]) if ids is not None and index < len(ids) else None
        motion, growth = history.update(track_id, cx, cy, float(area), now)
        output.append(Detection(
            label=label, confidence=confidence, x1=x1, y1=y1, x2=x2, y2=y2,
            center_x=cx, center_y=cy, direction=direction_for(cx, frame_width),
            track_id=track_id, motion_direction=motion, area_growth=growth,
            area_fraction=area / max(1, frame_width * frame_height),
        ))
    return output


def draw_detections(frame, detections: list[Detection]):
    annotated = frame.copy()
    for item in detections:
        track = f" #{item.track_id}" if item.track_id is not None else ""
        range_text = f" | ~{item.distance_m:.1f}m" if item.distance_m is not None else ""
        approach_text = " | possible approach" if item.time_to_contact_s is not None and item.time_to_contact_s < 4 else ""
        label = f"{item.label}{track} {item.confidence:.0%} | {item.direction}{range_text}{approach_text}"
        cv2.rectangle(annotated, (item.x1, item.y1), (item.x2, item.y2), (72, 214, 150), 2)
        text_y = max(22, item.y1 - 8)
        cv2.putText(annotated, label, (item.x1, text_y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.52, (72, 214, 150), 2, cv2.LINE_AA)
    return annotated


def summarize_scene(detections: list[Detection], max_items: int = 8) -> str:
    if not detections:
        return "I could not identify any objects with sufficient confidence in the current view."
    # Prefer the more confident instance per class and image-relative direction.
    best: dict[tuple[str, str], Detection] = {}
    for item in detections:
        key = (item.label, item.direction)
        if key not in best or item.confidence > best[key].confidence:
            best[key] = item
    ordered = sorted(best.values(), key=lambda d: (-d.confidence, d.center_x))[:max_items]
    phrases = []
    for item in ordered:
        phrase = f"{item.label} on the {item.direction}"
        if item.motion_direction:
            phrase += f", {item.motion_direction}"
        if item.distance_m is not None:
            qualifier = " approximate" if item.distance_spread is not None and item.distance_spread > 0.25 else " estimated"
            estimated_steps = max(1, round(item.distance_m / 0.70))
            phrase += f",{qualifier} range {item.distance_m:.1f} metres, roughly {estimated_steps} steps assuming 0.70 metres per step"
        if item.closing_speed_mps is not None and item.closing_speed_mps > 0.4:
            phrase += f", estimated closing at {item.closing_speed_mps:.1f} metres per second"
        elif item.area_growth >= 1.25:
            phrase += ", apparent size increasing"
        phrases.append(phrase)
    suffix = " Directions refer to the camera image. Any range values are model estimates and may be wrong; do not use them for safe navigation."
    return "I can see " + "; ".join(phrases) + "." + suffix

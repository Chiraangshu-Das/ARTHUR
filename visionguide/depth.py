from __future__ import annotations

import json
import sys
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from visionguide.perception import Detection


@dataclass(frozen=True)
class DepthReading:
    label: str
    track_id: int | None
    raw_distance_m: float
    distance_m: float
    spread_ratio: float
    timestamp: float


class MetricDepthEstimator:
    """Depth Anything V2 Small indoor metric model adapter.

    This estimates camera-to-pixel depth in metres. It is not a certified range sensor;
    the quality score describes local depth-map spread, not real-world error bounds.
    """

    def __init__(self, project_dir: Path, checkpoint: Path):
        self.project_dir = Path(project_dir)
        self.checkpoint = Path(checkpoint)
        vendor_metric = self.project_dir / "vendor" / "Depth-Anything-V2" / "metric_depth"
        if not (vendor_metric / "depth_anything_v2" / "dpt.py").is_file():
            raise FileNotFoundError(
                "Depth model source is missing. Run: python tools/setup_depth_model.py"
            )
        if not self.checkpoint.is_file():
            raise FileNotFoundError(
                "Metric depth checkpoint is missing. Run: python tools/setup_depth_model.py"
            )
        if str(vendor_metric) not in sys.path:
            sys.path.insert(0, str(vendor_metric))

        import torch
        from depth_anything_v2.dpt import DepthAnythingV2

        self.torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        configs = {"encoder": "vits", "features": 64, "out_channels": [48, 96, 192, 384], "max_depth": 20}
        model = DepthAnythingV2(**configs)
        try:
            state = torch.load(str(self.checkpoint), map_location="cpu", weights_only=True)
        except TypeError:
            state = torch.load(str(self.checkpoint), map_location="cpu")
        model.load_state_dict(state)
        model.eval()
        try:
            model = model.to(self.device)
        except Exception:
            self.device = "cpu"
            model = model.to("cpu")
        self.model = model

    def estimate(self, frame: np.ndarray) -> np.ndarray:
        with self.torch.inference_mode():
            depth = self.model.infer_image(frame, input_size=518)
        return np.asarray(depth, dtype=np.float32)

    @staticmethod
    def sample_detection(depth_map: np.ndarray, detection: Detection) -> tuple[float, float] | None:
        height, width = depth_map.shape[:2]
        x1 = max(0, min(width - 1, detection.x1))
        x2 = max(x1 + 1, min(width, detection.x2))
        y1 = max(0, min(height - 1, detection.y1))
        y2 = max(y1 + 1, min(height, detection.y2))
        # Use an interior crop to reduce background/edge mixing in the object box.
        bw, bh = x2 - x1, y2 - y1
        ix1, ix2 = int(x1 + bw * 0.25), int(x2 - bw * 0.25)
        iy1, iy2 = int(y1 + bh * 0.25), int(y2 - bh * 0.25)
        if ix2 <= ix1 or iy2 <= iy1:
            ix1, ix2, iy1, iy2 = x1, x2, y1, y2
        patch = depth_map[iy1:iy2, ix1:ix2]
        values = patch[np.isfinite(patch) & (patch > 0.10) & (patch <= 20.0)]
        if values.size < 4:
            return None
        # Reject pixel-level outliers, then use median depth and normalized IQR.
        p10, median, p90 = np.percentile(values, [10, 50, 90])
        spread = float((p90 - p10) / max(float(median), 0.1))
        if not np.isfinite(median):
            return None
        return float(median), spread


class MotionRiskAnalyzer:
    """Radial-closing heuristic; not a validated collision predictor."""

    CANDIDATE_CLASSES = {"person", "bicycle", "car", "motorcycle", "bus", "truck", "train", "dog"}

    def __init__(self):
        self.history: dict[tuple[str, int], deque[tuple[float, float]]] = defaultdict(lambda: deque(maxlen=7))
        self.last_alert: dict[tuple[str, int], float] = {}
        self.motions: dict[tuple[str, int], tuple[float, float | None]] = {}

    def update(self, detections: list[Detection], readings: dict[tuple[str, int | None], DepthReading], frame_width: int, now: float) -> list[str]:
        alerts: list[str] = []
        self.motions = {}
        for det in detections:
            if det.track_id is None or det.label not in self.CANDIDATE_CLASSES:
                continue
            reading = readings.get((det.label, det.track_id))
            if reading is None or reading.spread_ratio > 0.35:
                continue
            key = (det.label, det.track_id)
            history = self.history[key]
            if not history or now - history[-1][0] >= 0.45:
                history.append((now, reading.distance_m))
            while history and now - history[0][0] > 3.0:
                history.popleft()

            duration = history[-1][0] - history[0][0] if len(history) >= 2 else 0.0
            closing_speed = (history[0][1] - history[-1][1]) / duration if duration >= 0.5 else 0.0
            distance = reading.distance_m
            ttc = distance / closing_speed if closing_speed > 0.05 else float("inf")
            self.motions[key] = (closing_speed, ttc if ttc != float("inf") else None)
            if len(history) < 3 or duration < 1.2:
                continue
            # Conservative gate: centrally located tracked object, close estimated range,
            # consistent closing over several depth samples, and short estimated TTC.
            center_fraction = det.center_x / max(frame_width, 1)
            if (0.28 <= center_fraction <= 0.72 and 0.45 < distance <= 5.0
                    and closing_speed >= 0.65 and 0 < ttc <= 2.8):
                previous = self.last_alert.get(key, -1e9)
                if now - previous >= 8.0:
                    alerts.append(
                        f"Possible approaching {det.label}, estimated {distance:.1f} metres ahead. "
                        "Distance and collision risk are uncertain."
                    )
                    self.last_alert[key] = now
                    if len(alerts) >= 1:
                        break
        return alerts


class DepthWorker:
    """Low-rate depth worker that does not block webcam inference."""

    def __init__(self, camera_worker: Any, project_dir: Path, checkpoint: Path,
                 calibration_path: Path, interval_seconds: float = 1.0):
        self.camera_worker = camera_worker
        self.project_dir = Path(project_dir)
        self.checkpoint = Path(checkpoint)
        self.calibration_path = Path(calibration_path)
        self.interval_seconds = max(0.5, interval_seconds)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._status = "Depth disabled"
        self._error = ""
        self._readings: dict[tuple[str, int | None], DepthReading] = {}
        self._motions: dict[tuple[str, int], tuple[float, float | None]] = {}
        self._alerts: deque[str] = deque(maxlen=8)
        self._calibration = self._load_calibration()
        self._analyzer = MotionRiskAnalyzer()
        self._last_camera_version = -1

    def _load_calibration(self) -> float:
        try:
            data = json.loads(self.calibration_path.read_text(encoding="utf-8"))
            scale = float(data.get("scale", 1.0))
            return scale if 0.25 <= scale <= 4.0 else 1.0
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return 1.0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="visionguide-depth", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            self._set_status("Loading metric depth model…")
            estimator = MetricDepthEstimator(self.project_dir, self.checkpoint)
            self._set_status(f"Metric depth active ({estimator.device}); estimates are approximate")
            while not self._stop.is_set():
                frame, detections, version, camera_status, camera_error, _fps = self.camera_worker.snapshot()
                if frame is None or version == self._last_camera_version:
                    self._stop.wait(0.08)
                    continue
                self._last_camera_version = version
                started = time.monotonic()
                depth_map = estimator.estimate(frame)
                frame_h, frame_w = frame.shape[:2]
                if depth_map.shape != (frame_h, frame_w):
                    depth_map = cv2.resize(depth_map, (frame_w, frame_h), interpolation=cv2.INTER_LINEAR)
                now = time.monotonic()
                with self._lock:
                    scale = self._calibration
                readings: dict[tuple[str, int | None], DepthReading] = {}
                for det in detections:
                    sampled = estimator.sample_detection(depth_map, det)
                    if sampled is None:
                        continue
                    raw, spread = sampled
                    reading = DepthReading(det.label, det.track_id, raw, raw * scale, spread, now)
                    readings[(det.label, det.track_id)] = reading
                alerts = self._analyzer.update(detections, readings, frame_w, now)
                with self._lock:
                    self._readings = readings
                    self._motions = dict(self._analyzer.motions)
                    for alert in alerts:
                        self._alerts.append(alert)
                remaining = self.interval_seconds - (time.monotonic() - started)
                if remaining > 0:
                    self._stop.wait(remaining)
        except Exception as exc:
            self._set_status("Depth unavailable", str(exc))
        finally:
            if self._status.startswith("Metric depth active"):
                self._set_status("Depth stopped")

    def _set_status(self, status: str, error: str = "") -> None:
        with self._lock:
            self._status = status
            self._error = error

    def snapshot(self) -> tuple[dict[tuple[str, int | None], DepthReading], str, str]:
        with self._lock:
            return dict(self._readings), self._status, self._error

    def decorate(self, detections: list[Detection]) -> list[Detection]:
        with self._lock:
            readings = dict(self._readings)
            motions = dict(self._motions)
        decorated = []
        for det in detections:
            reading = readings.get((det.label, det.track_id))
            if reading is None and det.track_id is None:
                possible = [r for (label, _track_id), r in readings.items() if label == det.label]
                if possible:
                    reading = min(possible, key=lambda r: abs(r.timestamp - time.monotonic()))
            changes = {}
            if reading:
                changes["distance_m"] = reading.distance_m
                changes["distance_spread"] = reading.spread_ratio
            if det.track_id is not None:
                motion = motions.get((det.label, det.track_id))
                if motion:
                    changes["closing_speed_mps"] = motion[0]
                    changes["time_to_contact_s"] = motion[1]
            decorated.append(replace(det, **changes) if changes else det)
        return decorated

    def take_alerts(self) -> list[str]:
        with self._lock:
            alerts = list(self._alerts)
            self._alerts.clear()
            return alerts

    def calibrate(self, label: str, track_id: int | None, known_distance_m: float) -> float:
        if not 0.3 <= known_distance_m <= 15.0:
            raise ValueError("Known calibration distance must be between 0.3 and 15 metres.")
        with self._lock:
            reading = self._readings.get((label, track_id))
            if reading is None or reading.raw_distance_m <= 0:
                raise ValueError("The selected object's range is not available yet. Wait for a depth update.")
            new_scale = known_distance_m / reading.raw_distance_m
            if not 0.25 <= new_scale <= 4.0:
                raise ValueError("Calibration factor is outside 0.25–4.0. Check that you measured the correct visible object.")
            self._calibration = new_scale
            self.calibration_path.parent.mkdir(parents=True, exist_ok=True)
            self.calibration_path.write_text(json.dumps({
                "scale": new_scale,
                "calibrated_label": label,
                "calibrated_track_id": track_id,
                "known_distance_m": known_distance_m,
                "raw_model_distance_m": reading.raw_distance_m,
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "warning": "Single-point scale calibration; not a certified accuracy guarantee."
            }, indent=2), encoding="utf-8")
            return new_scale

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

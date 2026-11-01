from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import cv2

from visionguide.perception import Detection, MotionHistory, detect_objects, draw_detections


class VisionWorker:
    """Background webcam/model worker. It never speaks or sends data online."""
    def __init__(self, model_path: str, camera_index: int | str = 0, confidence_threshold: float = 0.35,
                 target_fps: int = 8, force_cpu: bool = False):
        self.model_path = model_path
        self.camera_index = camera_index
        self.confidence_threshold = confidence_threshold
        self.target_fps = max(1, target_fps)
        self.force_cpu = force_cpu
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._capture = None
        self._frame = None
        self._detections: list[Detection] = []
        self._version = 0
        self._status = "Waiting to initialize"
        self._error = ""
        self._fps = 0.0
        self._last_detection_at = 0.0

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="visionguide-camera", daemon=True)
        self._thread.start()

    def _set_status(self, status: str, error: str = "") -> None:
        with self._lock:
            self._status = status
            if error:
                self._error = error

    def _run(self) -> None:
        try:
            from ultralytics import YOLO
            self._set_status("Loading object-detection model…")
            model = YOLO(self.model_path)
            self._set_status("Opening camera…")
            self._capture = cv2.VideoCapture(self.camera_index)
            if not self._capture.isOpened():
                raise RuntimeError(
                    f"Camera source {self.camera_index!r} could not be opened. Close other webcam apps, "
                    "check Windows camera permissions, try another numeric index, or verify the local stream URL."
                )
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            history = MotionHistory()
            last_inference = 0.0
            frame_count = 0
            last_fps_t = time.monotonic()
            self._set_status("Camera active — audio is on demand")

            while not self._stop.is_set():
                ok, frame = self._capture.read()
                if not ok:
                    time.sleep(0.03)
                    continue
                now = time.monotonic()
                frame_count += 1
                if now - last_inference >= 1.0 / self.target_fps:
                    detections = detect_objects(
                        model, frame, self.confidence_threshold, history, now, self.force_cpu
                    )
                    last_inference = now
                    with self._lock:
                        self._detections = detections
                        self._last_detection_at = now
                with self._lock:
                    self._frame = frame.copy()
                    self._version += 1
                elapsed = now - last_fps_t
                if elapsed >= 1.0:
                    with self._lock:
                        self._fps = frame_count / elapsed
                    frame_count = 0
                    last_fps_t = now
        except Exception as exc:
            self._set_status("Camera/model error", str(exc))
        finally:
            if self._capture is not None:
                self._capture.release()
                self._capture = None
            with self._lock:
                if self._status not in ("Camera/model error",):
                    self._status = "Stopped"

    def snapshot(self) -> tuple[Any, list[Detection], int, str, str, float]:
        with self._lock:
            frame = None if self._frame is None else self._frame.copy()
            detections = list(self._detections)
            return frame, detections, self._version, self._status, self._error, self._fps

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=5)
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        with self._lock:
            self._frame = None
            self._detections = []
            self._version += 1
            self._fps = 0.0
            if self._status != "Camera/model error":
                self._status = "Camera off"

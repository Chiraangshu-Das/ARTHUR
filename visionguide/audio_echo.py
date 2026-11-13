from __future__ import annotations

import os
import queue
import threading
import time
from typing import Any


class EchoCancelledCapture:
    """Continuous, echo-cancelled microphone capture for ARTHUR's conversation mode.

    Echoff supplies timestamp-aligned WASAPI loopback (speaker reference) and
    microphone frames to WebRTC AEC. This class only buffers the cleaned near-end
    microphone signal and exposes fixed-duration 16 kHz audio windows for Whisper.
    It deliberately never falls back to raw microphone frames while TTS is active.
    """

    INPUT_RATE = 48_000
    OUTPUT_RATE = 16_000

    def __init__(self, max_buffer_seconds: float = 10.0):
        self._frames: queue.Queue[tuple[Any, bool]] = queue.Queue(
            maxsize=max(16, int(max_buffer_seconds / 0.02))
        )
        self._capture = None
        self._started = False
        self._closed = False
        self._ready = threading.Event()
        self._first_frame = threading.Event()
        self._error: str | None = None
        self._last_status: dict[str, Any] = {}
        self._lock = threading.RLock()

    @staticmethod
    def downsample_48k_to_16k(samples):
        """Convert mono 48 kHz float samples to 16 kHz with a simple box low-pass."""
        import numpy as np

        values = np.asarray(samples, dtype=np.float32).reshape(-1)
        usable = values.size - (values.size % 3)
        if usable <= 0:
            return np.zeros(0, dtype=np.float32)
        # A three-sample box filter before decimation reduces aliasing and keeps
        # the audio in Whisper's expected float32 [-1, 1] range.
        return values[:usable].reshape(-1, 3).mean(axis=1, dtype=np.float32)

    def _on_frame(self, frame) -> None:
        if self._closed:
            return
        try:
            import numpy as np

            state = getattr(frame, "state", None)
            echo_ready = bool(getattr(state, "echo_path_ready", False))
            clean = self.downsample_48k_to_16k(frame.microphone_clean)
            if clean.size == 0:
                return
            item = (clean.copy(), echo_ready)
            try:
                self._frames.put_nowait(item)
            except queue.Full:
                try:
                    self._frames.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._frames.put_nowait(item)
                except queue.Full:
                    pass
            self._first_frame.set()
            if echo_ready:
                self._ready.set()
        except Exception as exc:
            self._error = f"Could not process an echo-cancelled audio frame: {exc}"

    def _on_event(self, event) -> None:
        try:
            kind = str(getattr(event, "kind", ""))
            if kind:
                self._last_status["last_event"] = kind
        except Exception:
            pass

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            if self._closed:
                raise RuntimeError("Echo-cancelled capture instances cannot be restarted.")
            try:
                from echoff import AecCapture, AecConfig
            except Exception as exc:
                raise RuntimeError(
                    "Acoustic echo cancellation is unavailable. Install it with "
                    "`python -m pip install -r requirements-aec.txt`."
                ) from exc

            delay_ms = int(os.getenv("VISIONGUIDE_AEC_STREAM_DELAY_MS", "50"))
            warmup_seconds = float(os.getenv("VISIONGUIDE_AEC_WARMUP_SECONDS", "7.5"))
            warmup_seconds = max(1.0, min(7.5, warmup_seconds))
            config = AecConfig(
                noise_suppression=True,
                stream_delay_ms=max(0, min(500, delay_ms)),
                echo_path_warmup_s=warmup_seconds,
            )
            reference_device = os.getenv("VISIONGUIDE_AEC_REFERENCE_DEVICE", "").strip() or None
            microphone_device = os.getenv("VISIONGUIDE_AEC_MICROPHONE_DEVICE", "").strip() or None
            for variable_name, value in (
                ("VISIONGUIDE_AEC_REFERENCE_DEVICE", reference_device),
                ("VISIONGUIDE_AEC_MICROPHONE_DEVICE", microphone_device),
            ):
                if value is not None:
                    try:
                        if str(value).strip().isdigit():
                            if variable_name.endswith("REFERENCE_DEVICE"):
                                reference_device = int(value)
                            else:
                                microphone_device = int(value)
                    except ValueError:
                        pass
            self._capture = AecCapture(
                config,
                on_frame=self._on_frame,
                on_event=self._on_event,
                reference_device=reference_device,
                microphone_device=microphone_device,
                console_diagnostics=True,
            )
            try:
                self._capture.start()
                self._capture.raise_if_failed()
            except Exception:
                try:
                    self._capture.stop()
                except Exception:
                    pass
                self._capture = None
                raise
            self._started = True

        if not self._first_frame.wait(timeout=4.0):
            self.stop()
            raise RuntimeError("Echo cancellation opened, but no paired microphone/speaker frames arrived.")

    @property
    def is_running(self) -> bool:
        return self._started and not self._closed and self._capture is not None

    @property
    def echo_path_ready(self) -> bool:
        return self._ready.is_set()

    @property
    def error(self) -> str | None:
        return self._error

    def check_health(self) -> None:
        """Raise promptly when Echoff reports a capture or processing failure."""
        if self._error:
            raise RuntimeError(self._error)
        if self._capture is not None:
            try:
                self._capture.raise_if_failed()
            except Exception as exc:
                self._error = str(exc)
                raise RuntimeError(f"Acoustic echo cancellation failed: {exc}") from exc

    def wait_until_ready(self, timeout: float = 0.25) -> bool:
        return self._ready.wait(max(0.0, float(timeout)))

    def clear_pending(self) -> None:
        while True:
            try:
                self._frames.get_nowait()
            except queue.Empty:
                break

    def record_samples(
        self,
        duration_seconds: float,
        *,
        stop_event: threading.Event | None = None,
        require_echo_ready: bool = False,
        extra_timeout_seconds: float = 4.0,
    ):
        """Collect cleaned 16 kHz samples; optionally require a warmed AEC path."""
        import numpy as np

        if not self.is_running:
            raise RuntimeError("Echo-cancelled microphone capture is not running.")
        duration = max(0.2, min(float(duration_seconds), 12.0))
        target_samples = int(self.OUTPUT_RATE * duration)
        deadline = time.monotonic() + duration + max(1.0, float(extra_timeout_seconds))
        chunks = []
        collected = 0

        while collected < target_samples:
            if stop_event is not None and stop_event.is_set():
                break
            if time.monotonic() >= deadline:
                break
            try:
                samples, echo_ready = self._frames.get(timeout=0.15)
            except queue.Empty:
                if self._capture is not None:
                    try:
                        self._capture.raise_if_failed()
                    except Exception as exc:
                        self._error = str(exc)
                        raise RuntimeError(f"Acoustic echo cancellation failed: {exc}") from exc
                continue
            if require_echo_ready and not echo_ready:
                continue
            values = np.asarray(samples, dtype=np.float32).reshape(-1)
            if values.size == 0:
                continue
            needed = target_samples - collected
            if values.size > needed:
                values = values[:needed]
            chunks.append(values)
            collected += int(values.size)

        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks).astype(np.float32, copy=False)

    def status(self) -> dict[str, Any]:
        if self._capture is None:
            return {"running": False, "echo_path_ready": False, "error": self._error}
        try:
            snapshot = self._capture.status()
            data = snapshot.to_dict() if hasattr(snapshot, "to_dict") else {}
            if isinstance(data, dict):
                return data
        except Exception as exc:
            return {"running": self.is_running, "echo_path_ready": self.echo_path_ready, "error": str(exc)}
        return {"running": self.is_running, "echo_path_ready": self.echo_path_ready}

    def stop(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            capture = self._capture
            self._capture = None
        if capture is not None:
            try:
                capture.stop()
            except Exception as exc:
                self._error = self._error or str(exc)
        self._started = False
        self.clear_pending()

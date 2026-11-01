from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable


class WakeWordListener:
    """Local wake detector for a user-supplied openWakeWord-compatible model.

    The project intentionally bundles no wake-word model. Configure a compatible
    openWakeWord model for the exact wake phrase you want to use.
    """
    def __init__(self, model_path: Path, on_detected: Callable[[], None], threshold: float = 0.60, on_error: Callable[[Exception], None] | None = None):
        self.model_path = Path(model_path)
        self.on_detected = on_detected
        self.on_error = on_error
        self.threshold = float(threshold)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._error: Exception | None = None

    @property
    def error(self) -> Exception | None:
        return self._error

    def start(self) -> None:
        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"Wake-word model not found: {self.model_path}. Add a compatible openWakeWord model and set WAKE_WORD_MODEL in .env."
            )
        if not 0.1 <= self.threshold <= 0.99:
            raise ValueError("Wake-word threshold must be between 0.10 and 0.99.")
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="visionguide-wake-word", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            import numpy as np
            import sounddevice as sd
            from openwakeword.model import Model

            model = Model(wakeword_models=[str(self.model_path)], inference_framework="onnx")
            # openWakeWord's standard frame size is 80 ms at 16 kHz.
            with sd.InputStream(samplerate=16000, channels=1, dtype="int16", blocksize=1280) as stream:
                while not self._stop.is_set():
                    audio, _overflow = stream.read(1280)
                    scores = model.predict(np.asarray(audio[:, 0], dtype=np.int16))
                    if scores and max(float(value) for value in scores.values()) >= self.threshold:
                        self._stop.set()
                        self.on_detected()
                        break
        except Exception as exc:
            self._error = exc
            self._stop.set()
            if self.on_error is not None:
                self.on_error(exc)

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=timeout)

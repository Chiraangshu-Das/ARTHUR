from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class SpeechMessage:
    text: str
    priority: bool = False


class SpeechOutput:
    """Offline Windows speech output. It is silent until `say()` is explicitly called."""
    def __init__(self, rate: int = 165, enabled: bool = True):
        self.enabled = enabled
        self.rate = rate
        self._queue: queue.Queue[SpeechMessage | None] = queue.Queue(maxsize=5)
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._engine = None
        if enabled:
            self._thread = threading.Thread(target=self._worker, name="visionguide-speech", daemon=True)
            self._thread.start()
            self._ready.wait(timeout=5)

    def _worker(self) -> None:
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self.rate)
        except Exception as exc:
            print(f"[Speech] Could not initialize local TTS: {exc}")
            self.enabled = False
            self._ready.set()
            return
        self._ready.set()
        while True:
            message = self._queue.get()
            try:
                if message is None:
                    break
                self._engine.say(message.text)
                self._engine.runAndWait()
            except Exception as exc:
                print(f"[Speech] Could not speak: {exc}")
            finally:
                self._queue.task_done()
        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception as exc:
                print(f"[Speech] Could not stop voice engine cleanly: {exc}")

    def say(self, text: str, priority: bool = False) -> None:
        text = " ".join(str(text).split()).strip()
        if not text:
            return
        if not self.enabled:
            print(f"[Speech disabled] {text}")
            return
        if priority:
            while True:
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except queue.Empty:
                    break
        try:
            self._queue.put_nowait(SpeechMessage(text, priority))
        except queue.Full:
            print("[Speech] Output queue full; message was not queued.")

    def wait_until_idle(self, timeout: float = 15.0) -> bool:
        """Wait until queued speech has finished, without blocking forever."""
        deadline = time.monotonic() + max(0.0, timeout)
        while time.monotonic() < deadline:
            if self._queue.unfinished_tasks == 0:
                return True
            time.sleep(0.05)
        return self._queue.unfinished_tasks == 0

    def close(self) -> None:
        if not self.enabled or not self._thread:
            return
        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            return
        self._thread.join(timeout=4)

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
    """Offline Windows speech output through native SAPI5 on one COM worker thread."""

    def __init__(self, rate: int = 165, enabled: bool = True):
        self.enabled = bool(enabled)
        self.rate = int(rate)
        self._queue: queue.Queue[SpeechMessage | None] = queue.Queue(maxsize=5)
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._voice = None
        self._comtypes = None
        self._comtypes_client = None

        if self.enabled:
            try:
                # Import on the creating (GUI) thread. comtypes initializes COM
                # for the thread that first imports it; the speech worker then
                # performs its own balanced CoInitialize/CoUninitialize pair.
                import comtypes
                import comtypes.client
                self._comtypes = comtypes
                self._comtypes_client = comtypes.client
            except Exception as exc:
                self.enabled = False
                print(f"[Speech] Native SAPI5 requires comtypes: {exc}")
                self._ready.set()
                return

            self._thread = threading.Thread(
                target=self._worker,
                name="visionguide-speech",
                daemon=True,
            )
            self._thread.start()
            if not self._ready.wait(timeout=8.0):
                self.enabled = False
                print("[Speech] Timed out while initializing Windows SAPI5.")

    @staticmethod
    def _sapi_rate(rate: int) -> int:
        """Map the previous pyttsx3-style rate to SAPI's -10..10 range."""
        return max(-10, min(10, round((int(rate) - 175) / 20)))

    def _worker(self) -> None:
        com_initialized = False
        try:
            # COM objects must be created, used, and released on this same thread.
            self._comtypes.CoInitialize()
            com_initialized = True
            self._voice = self._comtypes_client.CreateObject("SAPI.SpVoice")
            self._voice.Rate = self._sapi_rate(self.rate)
            self._voice.Volume = 100
        except Exception as exc:
            self.enabled = False
            print(f"[Speech] Could not initialize Windows SAPI5: {exc}")
            self._ready.set()
            if com_initialized:
                try:
                    self._comtypes.CoUninitialize()
                except Exception as cleanup_exc:
                    print(f"[Speech] COM cleanup failed: {cleanup_exc}")
            return

        self._ready.set()
        try:
            while True:
                message = self._queue.get()
                try:
                    if message is None:
                        break
                    # SAPI Speak is synchronous by default, preserving queue order.
                    self._voice.Speak(message.text)
                except Exception as exc:
                    print(f"[Speech] Could not speak: {exc}")
                finally:
                    self._queue.task_done()
        finally:
            self._voice = None
            if com_initialized:
                try:
                    self._comtypes.CoUninitialize()
                except Exception as exc:
                    print(f"[Speech] COM cleanup failed: {exc}")

    def say(self, text: str, priority: bool = False) -> None:
        text = " ".join(str(text).split()).strip()
        if not text:
            return
        if not self.enabled:
            print(f"[Speech disabled] {text}")
            return

        if priority:
            # Drop queued, not-yet-spoken messages. An utterance already in progress
            # is allowed to finish so SAPI is never manipulated from another thread.
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
        """Wait until all queued utterances have completed, without blocking forever."""
        deadline = time.monotonic() + max(0.0, float(timeout))
        while time.monotonic() < deadline:
            if self._queue.unfinished_tasks == 0:
                return True
            time.sleep(0.05)
        return self._queue.unfinished_tasks == 0

    def close(self) -> None:
        if not self._thread:
            return
        if self._thread.is_alive():
            # Preserve the previous shutdown behaviour: discard pending speech and
            # let the currently playing utterance finish before the worker exits.
            while True:
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except queue.Empty:
                    break
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass
            self._thread.join(timeout=6.0)

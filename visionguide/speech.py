from __future__ import annotations

import queue
import re
import threading
import time
from dataclasses import dataclass

from visionguide.speech_renderer import split_speech_segments


@dataclass(frozen=True)
class SpeechMessage:
    text: str
    priority: bool = False


class SpeechOutput:
    """Interruptible offline Windows speech output through one SAPI5 COM thread.

    All SAPI COM calls stay on the worker thread. Other threads request pause or
    cancellation through an event; the worker performs the actual SAPI purge.
    """

    SAPI_ASYNC = 1
    SAPI_PURGE = 2
    SAPI_PURGE_ASYNC = SAPI_ASYNC | SAPI_PURGE

    def __init__(self, rate: int = 165, enabled: bool = True):
        self.enabled = bool(enabled)
        self.rate = int(rate)
        self._queue: queue.Queue[SpeechMessage | None] = queue.Queue(maxsize=5)
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._voice = None
        self._comtypes = None
        self._comtypes_client = None
        self._speaking = threading.Event()
        self._paused = False
        self._paused_segments: list[str] = []
        self._control_lock = threading.Lock()
        self._control_action: str | None = None
        self._control_event = threading.Event()
        self._current_text = ""
        self._state_lock = threading.RLock()
        self._last_error: str | None = None

        if self.enabled:
            try:
                import comtypes
                import comtypes.client
                self._comtypes = comtypes
                self._comtypes_client = comtypes.client
            except Exception as exc:
                self.enabled = False
                self._last_error = str(exc)
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
                self._last_error = "Timed out while initializing Windows SAPI5."
                print(f"[Speech] {self._last_error}")

    @staticmethod
    def _sapi_rate(rate: int) -> int:
        """Map the previous pyttsx3-style rate to SAPI's -10..10 range."""
        return max(-10, min(10, round((int(rate) - 175) / 20)))

    @staticmethod
    def _sapi_is_done(status) -> bool:
        """SAPI SRSEDone is 1; 0 means waiting, not completion."""
        try:
            return int(status.RunningState) == 1
        except Exception:
            return False

    @staticmethod
    def _remaining_after_current_word(segment: str, status) -> str:
        """Best-effort word-position resume using SAPI's current input position.

        SAPI reports positions in the input text. If the returned position does
        not look like a character boundary in this segment, restart the current
        sentence rather than cutting text at an unsafe offset.
        """
        try:
            position = int(status.InputWordPos)
            word_length = int(status.InputWordLen)
        except Exception:
            return segment
        if not (0 < position < len(segment)):
            return segment
        if not segment[position].isalnum():
            return segment
        if segment[position - 1].isalnum():
            return segment
        end = min(len(segment), position + max(1, word_length))
        remainder = segment[end:].lstrip(" ,;:-—")
        return remainder or ""

    def _set_control(self, action: str) -> None:
        with self._control_lock:
            self._control_action = action
            self._control_event.set()

    def _take_control(self) -> str | None:
        with self._control_lock:
            action = self._control_action
            self._control_action = None
            self._control_event.clear()
            return action

    def _has_inflight_message(self) -> bool:
        # Queue unfinished_tasks includes both queued messages and the message
        # currently owned by the worker. This closes the get-before-speaking race.
        with self._queue.mutex:
            return self._queue.unfinished_tasks > len(self._queue.queue)

    def _flush_queue(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break

    def _worker(self) -> None:
        com_initialized = False
        try:
            self._comtypes.CoInitialize()
            com_initialized = True
            self._voice = self._comtypes_client.CreateObject("SAPI.SpVoice")
            self._voice.Rate = self._sapi_rate(self.rate)
            self._voice.Volume = 100
        except Exception as exc:
            self.enabled = False
            self._last_error = str(exc)
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
                # A paused response keeps the worker alive but prevents later queued
                # notifications from speaking over the paused answer.
                while self.is_paused:
                    time.sleep(0.05)
                message = self._queue.get()
                if message is None:
                    self._queue.task_done()
                    break
                try:
                    self._speaking.set()
                    segments = split_speech_segments(message.text)
                    index = 0
                    interrupted = False
                    while index < len(segments):
                        control = self._take_control()
                        if control == "cancel":
                            try:
                                self._voice.Speak("", self.SAPI_PURGE_ASYNC)
                            except Exception:
                                pass
                            with self._state_lock:
                                self._paused = False
                                self._paused_segments = []
                            interrupted = True
                            break
                        if control == "pause":
                            with self._state_lock:
                                self._paused = True
                                self._paused_segments = segments[index:]
                            interrupted = True
                            break

                        segment = segments[index]
                        with self._state_lock:
                            self._current_text = segment
                        self._voice.Speak(segment, self.SAPI_ASYNC)
                        while True:
                            control = self._take_control()
                            if control in {"pause", "cancel"}:
                                try:
                                    status = self._voice.GetStatus()
                                except Exception:
                                    status = None
                                remainder = segment
                                if control == "pause" and status is not None:
                                    remainder = self._remaining_after_current_word(segment, status)
                                try:
                                    self._voice.Speak("", self.SAPI_PURGE_ASYNC)
                                except Exception as exc:
                                    self._last_error = str(exc)
                                with self._state_lock:
                                    if control == "pause":
                                        remaining = ([remainder] if remainder else []) + segments[index + 1:]
                                        self._paused_segments = remaining
                                        self._paused = True
                                    else:
                                        self._paused_segments = []
                                        self._paused = False
                                interrupted = True
                                break
                            try:
                                # RunningState == 0 means SAPI is waiting to start an
                                # asynchronous utterance. It does NOT mean playback
                                # completed. WaitUntilDone handles the queued state and
                                # is polled with a short timeout so pause/cancel stays
                                # responsive.
                                wait_until_done = getattr(self._voice, "WaitUntilDone", None)
                                if callable(wait_until_done):
                                    completed = bool(wait_until_done(40))
                                else:
                                    completed = self._sapi_is_done(self._voice.GetStatus())
                            except Exception as exc:
                                self._last_error = str(exc)
                                completed = False
                            if completed:
                                break
                            time.sleep(0.01)
                        if interrupted:
                            break
                        index += 1
                    if interrupted:
                        with self._state_lock:
                            if not self._paused:
                                self._current_text = ""
                        continue
                    with self._state_lock:
                        self._current_text = ""
                except Exception as exc:
                    self._last_error = str(exc)
                    print(f"[Speech] Could not speak: {exc}")
                finally:
                    self._speaking.clear()
                    self._queue.task_done()
        finally:
            self._speaking.clear()
            self._voice = None
            if com_initialized:
                try:
                    self._comtypes.CoUninitialize()
                except Exception as exc:
                    print(f"[Speech] COM cleanup failed: {exc}")

    @property
    def is_speaking(self) -> bool:
        return self._speaking.is_set()

    @property
    def is_paused(self) -> bool:
        with self._state_lock:
            return self._paused

    @property
    def is_busy(self) -> bool:
        return self._speaking.is_set() or self._queue.unfinished_tasks > 0 or self.is_paused

    @property
    def current_text(self) -> str:
        with self._state_lock:
            return self._current_text

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def say(self, text: str, priority: bool = False) -> None:
        text = " ".join(str(text).split()).strip()
        if not text:
            return
        if not self.enabled:
            print(f"[Speech disabled] {text}")
            return
        if priority:
            self._flush_queue()
        try:
            self._queue.put_nowait(SpeechMessage(text, priority))
        except queue.Full:
            print("[Speech] Output queue full; message was not queued.")

    def pause(self) -> bool:
        """Pause playback and retain the unspoken remainder for resume()."""
        if not self.is_busy:
            return False
        if self.is_paused:
            return True
        self._set_control("pause")
        return True

    def stop(self) -> bool:
        """Compatibility alias: stop current playback but retain it for continuation."""
        return self.pause()

    def resume(self) -> bool:
        with self._state_lock:
            if not self._paused or not self._paused_segments:
                return False
            remainder = " ".join(self._paused_segments).strip()
            self._paused_segments = []
            self._paused = False
        # The resumed answer takes precedence over queued, stale notifications.
        self._flush_queue()
        try:
            self._queue.put_nowait(SpeechMessage(remainder, priority=True))
            return True
        except queue.Full:
            with self._state_lock:
                self._paused = True
                self._paused_segments = split_speech_segments(remainder)
            return False

    def cancel(self) -> None:
        """Discard the current and queued response; unlike pause(), it cannot resume."""
        in_flight = self._speaking.is_set() or self._has_inflight_message()
        self._flush_queue()
        with self._state_lock:
            was_paused = self._paused
            self._paused = False
            self._paused_segments = []
            self._current_text = ""
        if in_flight:
            self._set_control("cancel")
        elif was_paused:
            self._set_control("cancel")
            self._take_control()

    def wait_until_idle(self, timeout: float | None = 15.0) -> bool:
        """Wait for all speech to finish; timeout=None means wait without a cutoff.

        A paused response remains busy until it is resumed or cancelled.
        """
        deadline = None if timeout is None else time.monotonic() + max(0.0, float(timeout))
        while True:
            if not self.is_busy:
                return True
            if deadline is not None and time.monotonic() >= deadline:
                return False
            time.sleep(0.05)

    def close(self) -> None:
        if not self._thread:
            return
        self.cancel()
        if self._thread.is_alive():
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                self._flush_queue()
                try:
                    self._queue.put_nowait(None)
                except queue.Full:
                    pass
            self._thread.join(timeout=6.0)

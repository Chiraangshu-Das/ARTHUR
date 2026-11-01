from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class TimerRecord:
    timer_id: int
    label: str
    duration_seconds: int
    created_monotonic: float
    deadline_monotonic: float
    timer: threading.Timer
    cancelled: bool = False


class TimerManager:
    """Thread-safe countdown timers. Expiry callbacks execute on a daemon thread."""
    def __init__(self, on_expire: Callable[[int, str], None] | None = None):
        self._on_expire = on_expire or (lambda _timer_id, _label: None)
        self._next_id = itertools.count(1)
        self._lock = threading.RLock()
        self._records: dict[int, TimerRecord] = {}
        self._closed = False

    def schedule(self, seconds: int, label: str = "Timer") -> TimerRecord:
        seconds = int(seconds)
        if not 1 <= seconds <= 7 * 24 * 60 * 60:
            raise ValueError("Timer duration must be between 1 second and 7 days.")
        label = " ".join(str(label).split()).strip() or "Timer"
        if len(label) > 100:
            raise ValueError("Timer label must be 100 characters or fewer.")
        with self._lock:
            if self._closed:
                raise RuntimeError("Timer manager is shutting down.")
            timer_id = next(self._next_id)
            created = time.monotonic()
            timer = threading.Timer(seconds, self._expire, args=(timer_id, label))
            timer.daemon = True
            record = TimerRecord(timer_id, label, seconds, created, created + seconds, timer)
            self._records[timer_id] = record
            timer.start()
            return record

    def _expire(self, timer_id: int, label: str) -> None:
        with self._lock:
            record = self._records.get(timer_id)
            if record is None or record.cancelled or self._closed:
                return
            self._records.pop(timer_id, None)
        try:
            self._on_expire(timer_id, label)
        except Exception as exc:
            # Timer thread failures must never crash the application.
            print(f"[Timer] Expiry callback failed for timer {timer_id}: {exc}")

    def cancel(self, timer_id: int) -> bool:
        with self._lock:
            record = self._records.pop(int(timer_id), None)
            if record is None:
                return False
            record.cancelled = True
            record.timer.cancel()
            return True

    def list_timers(self) -> list[dict[str, int | str]]:
        now = time.monotonic()
        with self._lock:
            return [
                {"id": r.timer_id, "label": r.label, "remaining_seconds": max(0, int(r.deadline_monotonic - now))}
                for r in sorted(self._records.values(), key=lambda item: item.deadline_monotonic)
                if not r.cancelled
            ]

    def close(self) -> None:
        with self._lock:
            self._closed = True
            records = list(self._records.values())
            self._records.clear()
        for record in records:
            record.cancelled = True
            record.timer.cancel()

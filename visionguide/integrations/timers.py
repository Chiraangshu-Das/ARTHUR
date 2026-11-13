from __future__ import annotations

import inspect
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


Recurrence = Literal["none", "daily", "weekly", "weekdays"]
_CHANNELS = ("desktop", "api")
_POLL_INTERVAL_SECONDS = 0.5
_CLAIM_LEASE_SECONDS = 30


@dataclass
class TimerRecord:
    """Compatibility record returned by the original in-memory TimerManager."""

    timer_id: int
    label: str
    duration_seconds: int
    created_monotonic: float
    deadline_monotonic: float
    timer: threading.Timer | None = None
    cancelled: bool = False


class TimerManager:
    """SQLite-backed timers and reminders with independent desktop/API delivery.

    Countdown timers and date/time reminders are stored as UTC deadlines. Two
    delivery rows are created for each occurrence: one for the desktop process
    and one for API/WebSocket clients. A delivery is claimed atomically so two
    instances of the same channel do not announce the same occurrence twice.

    Existing callers remain compatible with schedule(), cancel(), list_timers()
    and close(). The default channel is ``desktop`` for the existing Tk app.
    """

    def __init__(
        self,
        on_expire: Callable[..., None] | None = None,
        *,
        db_path: str | os.PathLike[str] | None = None,
        channel: Literal["desktop", "api"] = "desktop",
        poll_interval: float = _POLL_INTERVAL_SECONDS,
    ) -> None:
        if channel not in _CHANNELS:
            raise ValueError(f"channel must be one of {_CHANNELS!r}")
        self._on_expire = on_expire or (lambda _timer_id, _label: None)
        self._channel = channel
        self._poll_interval = max(0.05, float(poll_interval))
        if db_path is None:
            configured = os.getenv("ARTHUR_SCHEDULE_DB", "").strip()
            db_path = Path(configured).expanduser() if configured else (
                Path(__file__).resolve().parents[2] / "data" / "arthur_schedule.sqlite3"
            )
        self._db_path = Path(db_path).expanduser().resolve()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._instance_id = f"{channel}:{uuid.uuid4().hex}"
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._closed = False
        self._initialize_database()
        self._worker = threading.Thread(
            target=self._run, name=f"ArthurScheduler-{channel}", daemon=True
        )
        self._worker.start()

    @property
    def database_path(self) -> Path:
        return self._db_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def _initialize_database(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL,
                    kind TEXT NOT NULL CHECK (kind IN ('timer', 'reminder')),
                    scheduled_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    timezone_name TEXT NOT NULL DEFAULT 'UTC',
                    recurrence TEXT NOT NULL DEFAULT 'none'
                        CHECK (recurrence IN ('none', 'daily', 'weekly')),
                    weekdays_only INTEGER NOT NULL DEFAULT 0,
                    duration_seconds INTEGER,
                    status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'completed', 'cancelled'))
                );
                CREATE INDEX IF NOT EXISTS idx_schedules_due
                    ON schedules(status, scheduled_at);

                CREATE TABLE IF NOT EXISTS schedule_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_id INTEGER NOT NULL REFERENCES schedules(id),
                    occurrence_at TEXT NOT NULL,
                    channel TEXT NOT NULL CHECK (channel IN ('desktop', 'api')),
                    claimed_by TEXT,
                    claimed_at TEXT,
                    delivered_at TEXT,
                    UNIQUE(schedule_id, occurrence_at, channel)
                );
                CREATE INDEX IF NOT EXISTS idx_deliveries_pending
                    ON schedule_deliveries(channel, delivered_at, claimed_at);
                """
            )
            # Additive migration for databases created by earlier scheduler builds.
            columns = {str(row["name"]) for row in connection.execute("PRAGMA table_info(schedules)")}
            if "weekdays_only" not in columns:
                connection.execute(
                    "ALTER TABLE schedules ADD COLUMN weekdays_only INTEGER NOT NULL DEFAULT 0"
                )

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _iso_utc(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds")

    @staticmethod
    def _parse_due_at(value: str | datetime, timezone_name: str) -> datetime:
        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown time zone: {timezone_name}") from exc
        try:
            parsed = value if isinstance(value, datetime) else datetime.fromisoformat(
                str(value).strip().replace("Z", "+00:00")
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("due_at must be an ISO 8601 date-time.") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=zone)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _validate_label(label: str) -> str:
        cleaned = " ".join(str(label).split()).strip() or "Reminder"
        if len(cleaned) > 100:
            raise ValueError("Schedule label must be 100 characters or fewer.")
        return cleaned

    def _record_from_row(self, row: sqlite3.Row) -> TimerRecord:
        due = datetime.fromisoformat(row["scheduled_at"])
        remaining = max(0.0, (due - self._utc_now()).total_seconds())
        duration = int(row["duration_seconds"] or max(1, round(remaining)))
        now_mono = time.monotonic()
        return TimerRecord(
            timer_id=int(row["id"]),
            label=str(row["label"]),
            duration_seconds=duration,
            created_monotonic=now_mono - max(0.0, duration - remaining),
            deadline_monotonic=now_mono + remaining,
        )

    def _insert_schedule(
        self,
        *,
        label: str,
        kind: Literal["timer", "reminder"],
        due_at: datetime,
        timezone_name: str,
        recurrence: Recurrence,
        duration_seconds: int | None,
    ) -> TimerRecord:
        label = self._validate_label(label)
        if recurrence not in {"none", "daily", "weekly", "weekdays"}:
            raise ValueError("recurrence must be 'none', 'daily', 'weekly', or 'weekdays'.")
        weekdays_only = recurrence == "weekdays"
        stored_recurrence = "daily" if weekdays_only else recurrence
        if due_at <= self._utc_now():
            raise ValueError("The scheduled date and time must be in the future.")
        with self._connection() as connection:
            cursor = connection.execute(
                """INSERT INTO schedules
                   (label, kind, scheduled_at, created_at, timezone_name, recurrence,
                    weekdays_only, duration_seconds, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
                (
                    label,
                    kind,
                    self._iso_utc(due_at),
                    self._iso_utc(self._utc_now()),
                    timezone_name,
                    stored_recurrence,
                    1 if weekdays_only else 0,
                    duration_seconds,
                ),
            )
            row = connection.execute(
                "SELECT * FROM schedules WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return self._record_from_row(row)

    def schedule(self, seconds: int, label: str = "Timer") -> TimerRecord:
        seconds = int(seconds)
        if not 1 <= seconds <= 7 * 24 * 60 * 60:
            raise ValueError("Timer duration must be between 1 second and 7 days.")
        now = self._utc_now()
        return self._insert_schedule(
            label=label,
            kind="timer",
            due_at=now + timedelta(seconds=seconds),
            timezone_name="UTC",
            recurrence="none",
            duration_seconds=seconds,
        )

    def schedule_at(
        self,
        due_at: str | datetime,
        label: str = "Reminder",
        *,
        timezone_name: str = "Asia/Kolkata",
        recurrence: Recurrence = "none",
    ) -> TimerRecord:
        """Schedule a one-time, daily, weekly, or weekday-only reminder.

        A naive ISO date-time is interpreted in ``timezone_name``. An aware
        date-time keeps its supplied offset and is normalized to UTC.
        """
        if recurrence not in {"none", "daily", "weekly", "weekdays"}:
            raise ValueError("recurrence must be 'none', 'daily', 'weekly', or 'weekdays'.")
        parsed = self._parse_due_at(due_at, timezone_name)
        if recurrence == "weekdays":
            zone = ZoneInfo(timezone_name)
            local_due = parsed.astimezone(zone)
            now_local = self._utc_now().astimezone(zone)
            while local_due.weekday() >= 5 or local_due <= now_local:
                local_due += timedelta(days=1)
            parsed = local_due.astimezone(timezone.utc)
        return self._insert_schedule(
            label=label,
            kind="reminder",
            due_at=parsed,
            timezone_name=timezone_name,
            recurrence=recurrence,
            duration_seconds=None,
        )

    def _materialize_due_occurrences(self) -> None:
        now = self._utc_now()
        now_iso = self._iso_utc(now)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            due_rows = connection.execute(
                """SELECT * FROM schedules
                   WHERE status = 'pending' AND scheduled_at <= ?""",
                (now_iso,),
            ).fetchall()
            for row in due_rows:
                occurrence_at = str(row["scheduled_at"])
                for channel in _CHANNELS:
                    connection.execute(
                        """INSERT OR IGNORE INTO schedule_deliveries
                           (schedule_id, occurrence_at, channel)
                           VALUES (?, ?, ?)""",
                        (int(row["id"]), occurrence_at, channel),
                    )
                recurrence = str(row["recurrence"])
                if recurrence == "none":
                    connection.execute(
                        "UPDATE schedules SET status = 'completed' WHERE id = ?",
                        (int(row["id"]),),
                    )
                else:
                    zone = ZoneInfo(str(row["timezone_name"]))
                    local_due = datetime.fromisoformat(occurrence_at).astimezone(zone)
                    weekdays_only = bool(row["weekdays_only"]) if "weekdays_only" in row.keys() else False
                    increment = timedelta(days=1 if recurrence == "daily" else 7)
                    next_due = local_due + increment
                    # When the machine was off for several cycles, announce one
                    # missed occurrence, then move directly to the next future one.
                    while (
                        next_due.astimezone(timezone.utc) <= now
                        or (weekdays_only and next_due.weekday() >= 5)
                    ):
                        next_due += timedelta(days=1) if weekdays_only else increment
                    connection.execute(
                        "UPDATE schedules SET scheduled_at = ? WHERE id = ?",
                        (self._iso_utc(next_due), int(row["id"])),
                    )
            connection.commit()

    def _claim_delivery(self) -> sqlite3.Row | None:
        now = self._utc_now()
        now_iso = self._iso_utc(now)
        stale_before = self._iso_utc(now - timedelta(seconds=_CLAIM_LEASE_SECONDS))
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT * FROM schedule_deliveries
                   WHERE channel = ? AND delivered_at IS NULL
                     AND (claimed_at IS NULL OR claimed_at < ?)
                   ORDER BY id LIMIT 1""",
                (self._channel, stale_before),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            updated = connection.execute(
                """UPDATE schedule_deliveries
                   SET claimed_by = ?, claimed_at = ?
                   WHERE id = ? AND delivered_at IS NULL
                     AND (claimed_at IS NULL OR claimed_at < ?)""",
                (self._instance_id, now_iso, int(row["id"]), stale_before),
            )
            if updated.rowcount != 1:
                connection.rollback()
                return None
            connection.commit()
            return row

    def _finish_delivery(self, delivery_id: int, *, succeeded: bool) -> None:
        with self._connection() as connection:
            if succeeded:
                connection.execute(
                    """UPDATE schedule_deliveries
                       SET delivered_at = ?, claimed_by = NULL, claimed_at = NULL
                       WHERE id = ? AND claimed_by = ?""",
                    (self._iso_utc(self._utc_now()), delivery_id, self._instance_id),
                )
            else:
                connection.execute(
                    """UPDATE schedule_deliveries
                       SET claimed_by = NULL, claimed_at = NULL
                       WHERE id = ? AND claimed_by = ?""",
                    (delivery_id, self._instance_id),
                )

    def _notify(self, schedule_id: int, label: str, kind: str) -> None:
        """Preserve two-argument desktop callbacks; expose kind to newer clients."""
        callback = self._on_expire
        try:
            signature = inspect.signature(callback)
            parameters = tuple(signature.parameters.values())
            accepts_three = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in parameters) or sum(
                p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                for p in parameters
            ) >= 3
        except (TypeError, ValueError):
            accepts_three = False
        if accepts_three:
            callback(schedule_id, label, kind)
        elif kind == "reminder":
            callback(schedule_id, f"Reminder: {label}")
        else:
            callback(schedule_id, label)

    def _deliver_pending(self) -> None:
        # Bound each pass so a backlog cannot starve due-time processing.
        for _ in range(20):
            row = self._claim_delivery()
            if row is None:
                return
            delivery_id = int(row["id"])
            schedule_id = int(row["schedule_id"])
            with self._connection() as connection:
                schedule = connection.execute(
                    "SELECT label, kind FROM schedules WHERE id = ?", (schedule_id,)
                ).fetchone()
            if schedule is None:
                self._finish_delivery(delivery_id, succeeded=True)
                continue
            try:
                self._notify(schedule_id, str(schedule["label"]), str(schedule["kind"]) if "kind" in schedule.keys() else "timer")
            except Exception as exc:  # callbacks must not kill the scheduler thread
                print(f"[Scheduler] Notification callback failed for {schedule_id}: {exc}")
                self._finish_delivery(delivery_id, succeeded=False)
            else:
                self._finish_delivery(delivery_id, succeeded=True)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._materialize_due_occurrences()
                self._deliver_pending()
            except Exception as exc:
                print(f"[Scheduler] Background polling failed: {exc}")
            self._stop_event.wait(self._poll_interval)

    def cancel(self, timer_id: int) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                """UPDATE schedules SET status = 'cancelled'
                   WHERE id = ? AND status = 'pending'""",
                (int(timer_id),),
            )
            return cursor.rowcount == 1

    def cancel_reminder(self, reminder_id: int) -> bool:
        """Cancel only a pending reminder; countdown timers are left untouched."""
        with self._connection() as connection:
            cursor = connection.execute(
                """UPDATE schedules SET status = 'cancelled'
                   WHERE id = ? AND kind = 'reminder' AND status = 'pending'""",
                (int(reminder_id),),
            )
            return cursor.rowcount == 1

    def list_timers(self) -> list[dict[str, int | str]]:
        now = self._utc_now()
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT * FROM schedules
                   WHERE status = 'pending' AND kind = 'timer'
                   ORDER BY scheduled_at"""
            ).fetchall()
        result: list[dict[str, int | str]] = []
        for row in rows:
            due = datetime.fromisoformat(str(row["scheduled_at"]))
            result.append({
                "id": int(row["id"]),
                "label": str(row["label"]),
                "remaining_seconds": max(0, int((due - now).total_seconds())),
            })
        return result

    def list_schedules(self, *, include_completed: bool = False) -> list[dict[str, object]]:
        now = self._utc_now()
        where = "" if include_completed else "WHERE status = 'pending'"
        with self._connection() as connection:
            rows = connection.execute(
                f"SELECT * FROM schedules {where} ORDER BY scheduled_at"
            ).fetchall()
        schedules: list[dict[str, object]] = []
        for row in rows:
            due = datetime.fromisoformat(str(row["scheduled_at"]))
            schedules.append({
                "id": int(row["id"]),
                "label": str(row["label"]),
                "kind": str(row["kind"]),
                "due_at": str(row["scheduled_at"]),
                "timezone_name": str(row["timezone_name"]),
                "recurrence": (
                    "weekdays" if ("weekdays_only" in row.keys() and bool(row["weekdays_only"]))
                    else str(row["recurrence"])
                ),
                "status": str(row["status"]),
                "remaining_seconds": max(0, int((due - now).total_seconds())),
            })
        return schedules

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._stop_event.set()
        if self._worker.is_alive() and threading.current_thread() is not self._worker:
            self._worker.join(timeout=2.0)
        # Pending schedules remain in SQLite and resume when a manager starts again.

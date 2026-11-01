from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ActionHistory:
    """Small persistent local store for recent assistant results and per-profile preferences."""

    def __init__(self, database_path: Path):
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("""CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    transcript TEXT NOT NULL,
                    result TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )""")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_actions_created ON actions(id DESC)")
                connection.execute("""CREATE TABLE IF NOT EXISTS preferences (
                    profile_slug TEXT NOT NULL,
                    preference_key TEXT NOT NULL,
                    preference_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(profile_slug, preference_key)
                )""")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def record(self, action: str, transcript: str, result: str, *, success: bool = True) -> int:
        action = str(action).strip()[:100] or "assistant_action"
        transcript = str(transcript).strip()[:2000]
        result = str(result).strip()[:12000]
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    "INSERT INTO actions(action, transcript, result, success, created_at) VALUES (?, ?, ?, ?, ?)",
                    (action, transcript, result, int(success), created_at),
                )
                connection.execute("DELETE FROM actions WHERE id NOT IN (SELECT id FROM actions ORDER BY id DESC LIMIT 100)")
                return int(cursor.lastrowid)

    def last(self) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM actions ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def recent(self, limit: int = 5) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 20))
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT * FROM actions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def set_preference(self, profile_slug: str, key: str, value: str) -> None:
        profile_slug = str(profile_slug).strip()[:64]
        key = str(key).strip().casefold()[:80]
        value = str(value).strip()[:500]
        if not profile_slug or not key or not value:
            raise ValueError("Profile, preference key, and preference value are required.")
        updated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    "INSERT INTO preferences(profile_slug, preference_key, preference_value, updated_at) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(profile_slug, preference_key) DO UPDATE SET preference_value=excluded.preference_value, updated_at=excluded.updated_at",
                    (profile_slug, key, value, updated_at),
                )

    def get_preferences(self, profile_slug: str) -> dict[str, str]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT preference_key, preference_value FROM preferences WHERE profile_slug=?", (str(profile_slug),)
            ).fetchall()
        return {str(row["preference_key"]): str(row["preference_value"]) for row in rows}

    def delete_preferences(self, profile_slug: str) -> int:
        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute("DELETE FROM preferences WHERE profile_slug=?", (str(profile_slug),))
                return int(cursor.rowcount)


def summarize_recent_actions(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "I don't have a completed action recorded yet."
    lines = []
    for row in rows:
        result = str(row.get("result", "")).replace("\n", " ").strip()
        if len(result) > 350:
            result = result[:347] + "..."
        status = "completed" if row.get("success") else "failed"
        lines.append(f"{row.get('created_at', '')}: {row.get('transcript', row.get('action', 'Action'))} — {status}. {result}")
    return "Recent Arthur actions:\n" + "\n".join(lines)

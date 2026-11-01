
from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


class LocalMemory:
    """Small user-controlled local notes store. Never saves data implicitly."""

    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )"""
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at)"
                )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        return connection

    def add(self, content: str) -> int:
        note = " ".join(str(content).split()).strip()

        if not note:
            raise ValueError("Memory cannot be empty.")
        if len(note) > 4000:
            raise ValueError("A memory entry must be 4,000 characters or fewer.")

        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    "INSERT INTO memories(content, created_at) VALUES (?, ?)",
                    (note, created_at),
                )
                return int(cursor.lastrowid)

    def search(self, query: str = "", limit: int = 50) -> list[dict[str, object]]:
        needle = " ".join(str(query).split()).strip()
        bounded_limit = max(1, min(int(limit), 100))

        with closing(self._connect()) as connection:
            with connection:
                if not needle:
                    rows = connection.execute(
                        "SELECT id, content, created_at FROM memories "
                        "ORDER BY id DESC LIMIT ?",
                        (bounded_limit,),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        """SELECT id, content, created_at FROM memories
                           WHERE instr(lower(content), lower(?)) > 0
                           ORDER BY id DESC LIMIT ?""",
                        (needle, bounded_limit),
                    ).fetchall()

        return [dict(row) for row in rows]

    def count_matching(self, query: str) -> int:
        needle = " ".join(str(query).split()).strip()

        if not needle:
            return 0

        with closing(self._connect()) as connection:
            with connection:
                row = connection.execute(
                    """SELECT COUNT(*) AS total FROM memories
                       WHERE instr(lower(content), lower(?)) > 0""",
                    (needle,),
                ).fetchone()

        return int(row["total"])

    def delete(self, memory_id: int) -> bool:
        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    "DELETE FROM memories WHERE id = ?",
                    (int(memory_id),),
                )
                return cursor.rowcount > 0

    def delete_matching(self, query: str) -> int:
        needle = " ".join(str(query).split()).strip()

        if not needle:
            raise ValueError(
                "A non-empty phrase is required; bulk deletion is not allowed by this method."
            )

        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    """DELETE FROM memories
                       WHERE instr(lower(content), lower(?)) > 0""",
                    (needle,),
                )
                return int(cursor.rowcount)

    def count(self) -> int:
        with closing(self._connect()) as connection:
            with connection:
                row = connection.execute(
                    "SELECT COUNT(*) AS total FROM memories"
                ).fetchone()

        return int(row["total"])

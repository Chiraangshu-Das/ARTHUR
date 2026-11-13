from __future__ import annotations

import json
import threading
from collections import deque
from typing import Any


class ConversationContext:
    """Bounded, in-memory context for the current Arthur session.

    Nothing in this class is persisted to disk. Sending this context to Groq is
    controlled separately by VISIONGUIDE_SHARE_CONVERSATION_CONTEXT.
    """

    def __init__(self, max_turns: int = 8):
        self.max_turns = max(1, min(int(max_turns), 20))
        self._turns: deque[dict[str, Any]] = deque(maxlen=self.max_turns)
        self._next_id = 1
        self._lock = threading.RLock()

    @staticmethod
    def _clean_text(value: object, limit: int) -> str:
        return " ".join(str(value or "").split()).strip()[:limit]

    @classmethod
    def _clean_arguments(cls, arguments: dict[str, Any] | None) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        for key, value in (arguments or {}).items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                cleaned[str(key)[:60]] = cls._clean_text(value, 240) if isinstance(value, str) else value
            elif isinstance(value, (list, tuple)):
                items = [cls._clean_text(item, 100) for item in value[:5] if isinstance(item, (str, int, float, bool))]
                if items:
                    cleaned[str(key)[:60]] = items
        return cleaned

    def begin_turn(self, user_text: str) -> int:
        text = self._clean_text(user_text, 1200)
        if not text:
            raise ValueError("A conversation turn requires non-empty user text.")
        with self._lock:
            turn_id = self._next_id
            self._next_id += 1
            self._turns.append({"id": turn_id, "user": text, "action": "", "arguments": {}, "result": "", "success": None})
            return turn_id

    def set_action(self, turn_id: int, action: str, arguments: dict[str, Any] | None = None) -> bool:
        with self._lock:
            turn = self._find_turn(turn_id)
            if turn is None:
                return False
            turn["action"] = self._clean_text(action, 100)
            turn["arguments"] = self._clean_arguments(arguments)
            return True

    def set_result(self, turn_id: int, result: object, *, success: bool = True) -> bool:
        with self._lock:
            turn = self._find_turn(turn_id)
            if turn is None:
                return False
            if isinstance(result, (dict, list, tuple)):
                result_text = json.dumps(result, ensure_ascii=False, default=str)
            else:
                result_text = str(result)
            turn["result"] = self._clean_text(result_text, 1200)
            turn["success"] = bool(success)
            return True

    def _find_turn(self, turn_id: int) -> dict[str, Any] | None:
        return next((turn for turn in self._turns if turn["id"] == int(turn_id)), None)

    def render(self, *, exclude_turn_id: int | None = None, max_chars: int = 4200) -> str:
        """Render recent turns as compact context; the newest turns are retained."""
        bounded_chars = max(300, min(int(max_chars), 8000))
        with self._lock:
            turns = [dict(turn) for turn in self._turns if turn["id"] != exclude_turn_id]

        blocks: list[str] = []
        for index, turn in enumerate(turns, 1):
            lines = [f"Turn {index} — User: {turn['user']}"]
            if turn.get("action"):
                args = json.dumps(turn.get("arguments", {}), ensure_ascii=False, default=str)
                lines.append(f"Arthur selected action: {turn['action']} {args}")
            if turn.get("result"):
                status = "success" if turn.get("success") else "not confirmed / failed"
                lines.append(f"Arthur's recorded result ({status}): {turn['result']}")
            blocks.append("\n".join(lines))

        # Add complete newest blocks while staying inside the prompt budget.
        selected: list[str] = []
        used = 0
        for block in reversed(blocks):
            addition = len(block) + (2 if selected else 0)
            if used + addition > bounded_chars:
                remaining = bounded_chars - used
                if remaining > 80:
                    selected.append(block[:remaining].rstrip())
                break
            selected.append(block)
            used += addition
        return "\n\n".join(reversed(selected))

    def clear(self) -> None:
        with self._lock:
            self._turns.clear()

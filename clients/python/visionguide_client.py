"""Small REST/WebSocket client for desktop, mobile, and wearable prototypes."""
from __future__ import annotations

import json
import os
from typing import Any

import requests


class ArthurClient:
    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float = 30.0):
        self.base_url = (base_url or os.getenv("VISIONGUIDE_SERVER_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.token = token if token is not None else os.getenv("VISIONGUIDE_API_TOKEN", "")
        self.timeout = max(1.0, min(float(timeout), 120.0))
        self.session = requests.Session()
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        response = self.session.request(method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs)
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text}
        if not response.ok:
            raise RuntimeError(f"Arthur API returned HTTP {response.status_code}: {json.dumps(payload, ensure_ascii=False)}")
        return payload

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def command(self, text: str, device_id: str = "python-client") -> dict[str, Any]:
        return self._request("POST", "/api/v1/command", json={"text": text, "device_id": device_id})

    def confirm(self, confirmation_id: str, confirmed: bool, device_id: str = "python-client") -> dict[str, Any]:
        return self._request("POST", "/api/v1/confirm", json={
            "confirmation_id": confirmation_id, "confirmed": bool(confirmed), "device_id": device_id,
        })

    def timers(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/timers")

    def create_timer(self, seconds: int, label: str = "Reminder") -> dict[str, Any]:
        return self._request("POST", "/api/v1/timers", json={"seconds": int(seconds), "label": label})

    def cancel_timer(self, timer_id: int) -> dict[str, Any]:
        return self._request("DELETE", f"/api/v1/timers/{int(timer_id)}")

    def unread_gmail(self, limit: int = 10) -> dict[str, Any]:
        return self._request("GET", "/api/v1/workspace/gmail/unread", params={"limit": int(limit)})

    def read_gmail_message(self, message_id: str) -> dict[str, Any]:
        from urllib.parse import quote
        return self._request("GET", f"/api/v1/workspace/gmail/messages/{quote(str(message_id), safe='')}")

    def create_gmail_draft(self, to: str, subject: str, body: str) -> dict[str, Any]:
        return self._request("POST", "/api/v1/workspace/gmail/drafts", json={"to": to, "subject": subject, "body": body})

    def request_gmail_draft_send(self, draft_id: str, device_id: str = "python-client") -> dict[str, Any]:
        """Read a draft and obtain a one-use confirmation challenge; this method does not send."""
        from urllib.parse import quote
        return self._request("POST", f"/api/v1/workspace/gmail/drafts/{quote(str(draft_id), safe='')}/send", json={"device_id": device_id})

    def search_gmail(self, query: str, limit: int = 10) -> dict[str, Any]:
        return self._request("GET", "/api/v1/workspace/gmail/search", params={"q": query, "limit": int(limit)})

    def upcoming_calendar(self, days: int = 7, limit: int = 10) -> dict[str, Any]:
        return self._request("GET", "/api/v1/workspace/calendar/upcoming", params={"days": int(days), "limit": int(limit)})

    def search_calendar(self, query: str, days: int = 180) -> dict[str, Any]:
        # Natural-language queries should normally go through command() so the semantic
        # router can interpret the requested event search and preserve confirmation policy.
        return self._request("GET", "/api/v1/workspace/calendar/search", params={"q": query, "days": int(days)})

    def request_calendar_event(
        self, summary: str, start: str, end: str, timezone_name: str = "Asia/Kolkata",
        location: str = "", description: str = "", device_id: str = "python-client",
    ) -> dict[str, Any]:
        """Prepare an event preview and one-use confirmation token; this method does not create it."""
        return self._request("POST", "/api/v1/workspace/calendar/events", json={
            "summary": summary, "start": start, "end": end, "timezone_name": timezone_name,
            "location": location, "description": description, "device_id": device_id,
        })

    def transcribe_file(self, audio_path: str, model: str = "base") -> dict[str, Any]:
        from pathlib import Path
        path = Path(audio_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        with path.open("rb") as handle:
            response = self.session.post(
                f"{self.base_url}/api/v1/transcribe", params={"model": model},
                headers={"Authorization": f"Bearer {self.token}"} if self.token else {},
                files={"audio": (path.name, handle)}, timeout=max(self.timeout, 120.0),
            )
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text}
        if not response.ok:
            raise RuntimeError(f"Arthur API returned HTTP {response.status_code}: {json.dumps(payload, ensure_ascii=False)}")
        return payload

    def close(self) -> None:
        self.session.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Arthur REST command client")
    parser.add_argument("text", nargs="*", help="Natural-language command")
    parser.add_argument("--server", default=None, help="API base URL")
    parser.add_argument("--device-id", default="python-client")
    args = parser.parse_args()
    client = ArthurClient(args.server)
    try:
        if not args.text:
            print(json.dumps(client.health(), indent=2))
        else:
            print(json.dumps(client.command(" ".join(args.text), args.device_id), indent=2, ensure_ascii=False))
    finally:
        client.close()

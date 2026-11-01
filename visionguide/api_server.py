from __future__ import annotations

import asyncio
import hmac
import os
import secrets
import threading
import time
import tempfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from visionguide.cloud_ai import GeminiAssistant
from visionguide.desktop_actions import open_app, open_website, search_web, search_youtube
from visionguide.integrations.google_workspace import (
    GOOGLE_WORKSPACE_WRITE_OPERATIONS, calendar_create_event, calendar_search, calendar_upcoming,
    execute_google_workspace_operation, gmail_create_draft, gmail_draft_preview,
    gmail_read_message, gmail_search, gmail_send_draft, gmail_unread,
)
from visionguide.integrations.google_services import GoogleMapsServices, execute_google_maps_operation
from visionguide.integrations.google_cloud_services import execute_google_cloud_operation
from visionguide.integrations.gui_automation import compose_gmail_gui
from visionguide.integrations.system_controls import (
    adjust_brightness, adjust_volume, get_brightness, get_volume, list_wifi_adapters,
    media_playback, set_brightness, set_mute, set_volume, set_wifi,
)
from visionguide.integrations.timers import TimerManager
from visionguide.semantic_router import RoutedCommand, SemanticCommandRouter
from visionguide.voice_commands import transcribe_audio_file

load_dotenv()

app = FastAPI(title="Arthur Device Agent API", version="1.0.0")
gemini = GeminiAssistant()
router = SemanticCommandRouter(gemini)
_loop: asyncio.AbstractEventLoop | None = None
_websocket_clients: set[WebSocket] = set()
_pending_confirmations: dict[str, tuple[float, str, RoutedCommand]] = {}
_confirmation_lock = threading.Lock()
_CONFIRMATION_ACTIONS = {"wifi_set", "calendar_create_event", "gmail_compose", "gmail_send_current",
                         "word_write", "whatsapp_compose", "whatsapp_send_current", "type_into_window", "general_query"}
_maps_services = GoogleMapsServices()


def _needs_confirmation(route: RoutedCommand) -> bool:
    if route.action in _CONFIRMATION_ACTIONS:
        return True
    return route.action == "google_workspace_feature" and str(route.arguments.get("operation", "")).casefold() in GOOGLE_WORKSPACE_WRITE_OPERATIONS
_timers = TimerManager(lambda timer_id, label: _publish_event({"type": "timer_expired", "timer_id": timer_id, "label": label}))


class CommandRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    device_id: str = Field(default="desktop", min_length=1, max_length=100)


class ConfirmCommandRequest(BaseModel):
    confirmation_id: str = Field(min_length=20, max_length=100)
    device_id: str = Field(default="desktop", min_length=1, max_length=100)
    confirmed: bool


class TimerRequest(BaseModel):
    seconds: int = Field(ge=1, le=604800)
    label: str = Field(default="Reminder", max_length=100)


class GmailDraftRequest(BaseModel):
    to: str
    subject: str = Field(max_length=250)
    body: str = Field(max_length=100000)


class CalendarEventRequest(BaseModel):
    summary: str = Field(min_length=1, max_length=250)
    start: str
    end: str
    timezone_name: str = "Asia/Kolkata"
    location: str = ""
    description: str = ""
    device_id: str = Field(default="workspace-api-client", min_length=1, max_length=100)


class GmailSendDraftRequest(BaseModel):
    device_id: str = Field(default="workspace-api-client", min_length=1, max_length=100)


def _token() -> str:
    return os.getenv("VISIONGUIDE_API_TOKEN", "").strip()


def _create_confirmation(device_id: str, routed: RoutedCommand) -> str:
    """Store one exact intent in a bounded, expiring, device-bound confirmation registry."""
    confirmation_id = secrets.token_urlsafe(32)
    with _confirmation_lock:
        now = time.monotonic()
        for key, (created, _device_id, _route) in list(_pending_confirmations.items()):
            if now - created > 300:
                _pending_confirmations.pop(key, None)
        while len(_pending_confirmations) >= 100:
            oldest = min(_pending_confirmations, key=lambda key: _pending_confirmations[key][0])
            _pending_confirmations.pop(oldest, None)
        _pending_confirmations[confirmation_id] = (now, device_id, routed)
    return confirmation_id


def _authorized_header(authorization: str | None = Header(default=None)) -> bool:
    token = _token()
    if not token:
        # Safe for a local loopback server, but remote binding is blocked at startup below.
        return True
    expected = "Bearer " + token
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid Arthur API bearer token.")
    return True


@app.on_event("startup")
async def _startup() -> None:
    global _loop
    _loop = asyncio.get_running_loop()
    host = os.getenv("VISIONGUIDE_API_HOST", "127.0.0.1").strip()
    if host not in {"127.0.0.1", "localhost", "::1"} and not _token():
        raise RuntimeError("VISIONGUIDE_API_TOKEN is required when binding the device API to a non-loopback host.")


@app.on_event("shutdown")
async def _shutdown() -> None:
    _timers.close()


@app.get("/health")
def health(_: bool = Depends(_authorized_header)) -> dict[str, Any]:
    return {"status": "ok", "service": "visionguide-device-agent", "router": "semantic-llm-with-local-fallback"}


@app.post("/api/v1/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...), model: str = "base", _: bool = Depends(_authorized_header)
) -> dict[str, Any]:
    """Transcribe a user-submitted audio clip locally with Whisper; never forwards the audio to Gemini."""
    allowed_suffixes = {".wav", ".mp3", ".m4a", ".webm", ".ogg", ".flac", ".mp4", ".mpeg", ".mpga"}
    suffix = Path(audio.filename or "voice.wav").suffix.lower() or ".wav"
    if suffix not in allowed_suffixes:
        raise HTTPException(status_code=415, detail="Unsupported audio format. Use WAV, MP3, M4A, WebM, OGG, FLAC, or MP4 audio.")
    if model not in {"tiny", "base", "small", "medium", "large", "turbo"}:
        raise HTTPException(status_code=422, detail="Unsupported Whisper model.")
    content = await audio.read(20 * 1024 * 1024 + 1)
    if not content:
        raise HTTPException(status_code=400, detail="Audio upload is empty.")
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio upload exceeds 20 MB.")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="visionguide_audio_", suffix=suffix, delete=False) as handle:
            handle.write(content)
            temp_path = handle.name
        transcript = await asyncio.to_thread(transcribe_audio_file, temp_path, model)
        return {"transcript": transcript, "model": model, "processing": "local-whisper", "audio_forwarded_to_gemini": False}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Whisper transcription failed: {exc}") from exc
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except OSError:
                pass
        await audio.close()


@app.get("/api/v1/tools")
def tools(_: bool = Depends(_authorized_header)) -> dict[str, Any]:
    return {"tools": [
        {"name": "open_website", "device_local": True},
        {"name": "open_app", "device_local": True},
        {"name": "youtube_search", "device_local": True},
        {"name": "web_search", "device_local": True},
        {"name": "media_playback", "device_local": True, "window_targeted": True},
        {"name": "brightness_set", "device_local": True},
        {"name": "brightness_adjust", "device_local": True},
        {"name": "brightness_get", "device_local": True},
        {"name": "volume_set", "device_local": True},
        {"name": "volume_adjust", "device_local": True},
        {"name": "volume_get", "device_local": True},
        {"name": "audio_mute", "device_local": True},
        {"name": "wifi_status", "device_local": True},
        {"name": "wifi_set", "requires_confirmation": True, "device_local": True},
        {"name": "timer_set", "background": True},
        {"name": "timer_list", "background": True},
        {"name": "timer_cancel", "background": True},
        {"name": "gmail_unread", "oauth": True},
        {"name": "gmail_search", "oauth": True},
        {"name": "gmail_read_message", "oauth": True},
        {"name": "gmail_compose", "window_automation": True, "review_required": True},
        {"name": "gmail_api_send_draft", "oauth": True, "requires_confirmation": True, "draft_fingerprint_checked": True},
        {"name": "gmail_send_current", "requires_confirmation": True, "window_automation": True},
        {"name": "calendar_upcoming", "oauth": True},
        {"name": "calendar_search", "oauth": True},
        {"name": "calendar_create_event", "oauth": True, "requires_confirmation": True},
        {"name": "google_workspace_feature", "oauth": True, "scope_profile_per_service": True, "writes_require_confirmation": True},
        {"name": "google_maps_feature", "api_key": "GOOGLE_MAPS_API_KEY", "daily_caps": True},
        {"name": "google_cloud_feature", "api_key": "GOOGLE_CLOUD_API_KEY", "daily_caps": True},
        {"name": "word_write", "window_automation": True, "review_required": True},
        {"name": "whatsapp_compose", "window_automation": True, "review_required": True},
        {"name": "whatsapp_send_current", "window_automation": True, "requires_confirmation": True},
        {"name": "type_into_window", "window_automation": True, "review_required": True},
        {"name": "general_query", "text_provider": "Gemini", "requires_confirmation": True},
    ]}


@app.post("/api/v1/command")
def command(request: CommandRequest, _: bool = Depends(_authorized_header)) -> dict[str, Any]:
    routed = router.route(request.text)
    if routed.action == "unknown" and gemini.available():
        routed = RoutedCommand("general_query", {"prompt": request.text}, "text-only-fallback", 0.5)
    intent = {"name": routed.action, "arguments": routed.arguments, "source": routed.source,
              "confidence": routed.confidence}
    if _needs_confirmation(routed):
        confirmation_id = _create_confirmation(request.device_id, routed)
        preview: dict[str, Any] = {}
        for key in ("recipient", "subject", "instructions", "summary", "start", "end", "timezone_name", "location", "text", "contact", "message", "target", "prompt", "enabled", "adapter", "name", "operation", "query", "identifier", "title", "content", "range_name", "values_json", "course_id", "due", "target_language", "source_language", "language", "days", "limit"):
            if key in routed.arguments:
                value = routed.arguments[key]
                preview[key] = str(value)[:1500] if isinstance(value, str) else value
        return {"device_id": request.device_id, "transcript": request.text, "intent": intent,
                "result": {"status": "confirmation_required", "confirmation_id": confirmation_id,
                           "expires_in_seconds": 300, "preview": preview,
                           "message": "Review the action and preview in your client. Confirm it through /api/v1/confirm to execute the exact stored intent, or reject it to cancel."}}
    result = execute_route(routed, confirmed=False)
    return {"device_id": request.device_id, "transcript": request.text, "intent": intent, "result": result}


@app.post("/api/v1/confirm")
def confirm_command(request: ConfirmCommandRequest, _: bool = Depends(_authorized_header)) -> dict[str, Any]:
    with _confirmation_lock:
        item = _pending_confirmations.get(request.confirmation_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Confirmation token is invalid, expired, or already used.")
        created, device_id, routed = item
        if request.device_id != device_id:
            raise HTTPException(status_code=403, detail="Confirmation token belongs to a different client device.")
        if time.monotonic() - created > 300:
            _pending_confirmations.pop(request.confirmation_id, None)
            raise HTTPException(status_code=410, detail="Confirmation token expired. Submit the command again to review it.")
        # Consume only after verifying that the requesting device owns the token.
        _pending_confirmations.pop(request.confirmation_id, None)
    if not request.confirmed:
        return {"status": "cancelled", "intent": routed.action, "message": "Action cancelled by the user."}
    result = execute_route(routed, confirmed=True)
    return {"status": "executed", "intent": {"name": routed.action, "arguments": routed.arguments}, "result": result}


@app.post("/api/v1/timers")
def create_timer(request: TimerRequest, _: bool = Depends(_authorized_header)) -> dict[str, Any]:
    record = _timers.schedule(request.seconds, request.label)
    return {"id": record.timer_id, "label": record.label, "duration_seconds": record.duration_seconds}


@app.get("/api/v1/timers")
def get_timers(_: bool = Depends(_authorized_header)) -> dict[str, Any]:
    return {"timers": _timers.list_timers()}


@app.delete("/api/v1/timers/{timer_id}")
def delete_timer(timer_id: int, _: bool = Depends(_authorized_header)) -> dict[str, Any]:
    return {"id": timer_id, "cancelled": _timers.cancel(timer_id)}


@app.post("/api/v1/workspace/gmail/drafts")
def create_gmail_draft(request: GmailDraftRequest, _: bool = Depends(_authorized_header)) -> dict[str, Any]:
    return gmail_create_draft(request.to, request.subject, request.body)


@app.post("/api/v1/workspace/gmail/drafts/{draft_id}/send")
def send_gmail_draft(
    draft_id: str, request: GmailSendDraftRequest, _: bool = Depends(_authorized_header)
) -> dict[str, Any]:
    """Return a detailed preview and one-use confirmation token; do not send in this request."""
    try:
        preview = gmail_draft_preview(draft_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read the Gmail draft for preview: {exc}") from exc
    routed = RoutedCommand("gmail_api_send_draft", {
        "draft_id": draft_id,
        "expected_fingerprint": preview["fingerprint"],
    }, "gmail-api", 1.0)
    confirmation_id = _create_confirmation(request.device_id, routed)
    return {
        "status": "confirmation_required",
        "device_id": request.device_id,
        "confirmation_id": confirmation_id,
        "expires_in_seconds": 300,
        "preview": {"to": preview.get("to", ""), "subject": preview.get("subject", ""),
                    "body_preview": preview.get("body", "")[:2000]},
        "message": "Review the full draft in Gmail. Confirm this exact draft through /api/v1/confirm; it will be re-read and must match this preview before sending.",
    }


@app.get("/api/v1/workspace/gmail/unread")
def unread_gmail(limit: int = 10, _: bool = Depends(_authorized_header)) -> dict[str, Any]:
    return {"messages": gmail_unread(limit)}


@app.get("/api/v1/workspace/gmail/search")
def search_gmail(q: str, limit: int = 10, _: bool = Depends(_authorized_header)) -> dict[str, Any]:
    return {"messages": gmail_search(q, limit)}


@app.get("/api/v1/workspace/gmail/messages/{message_id}")
def read_gmail_message(message_id: str, _: bool = Depends(_authorized_header)) -> dict[str, Any]:
    return {"message": gmail_read_message(message_id)}


@app.get("/api/v1/workspace/calendar/upcoming")
def upcoming_calendar(days: int = 7, limit: int = 10, _: bool = Depends(_authorized_header)) -> dict[str, Any]:
    return {"events": calendar_upcoming(days, limit)}


@app.get("/api/v1/workspace/calendar/search")
def search_calendar_endpoint(q: str, days: int = 180, _: bool = Depends(_authorized_header)) -> dict[str, Any]:
    return {"events": calendar_search(q, days)}


@app.post("/api/v1/workspace/calendar/events")
def create_calendar_event(request: CalendarEventRequest, _: bool = Depends(_authorized_header)) -> dict[str, Any]:
    """Prepare a Calendar write; the actual create occurs only through /api/v1/confirm."""
    routed = RoutedCommand("calendar_create_event", {
        "summary": request.summary, "start": request.start, "end": request.end,
        "timezone_name": request.timezone_name, "location": request.location,
        "description": request.description,
    }, "calendar-api", 1.0)
    confirmation_id = _create_confirmation(request.device_id, routed)
    return {
        "status": "confirmation_required", "device_id": request.device_id,
        "confirmation_id": confirmation_id, "expires_in_seconds": 300,
        "preview": {"summary": request.summary, "start": request.start, "end": request.end,
                    "timezone_name": request.timezone_name, "location": request.location,
                    "description": request.description},
        "message": "Review the event details, then approve this exact write through /api/v1/confirm.",
    }


async def _broadcast_event(event: dict[str, Any]) -> None:
    stale: list[WebSocket] = []
    for client in tuple(_websocket_clients):
        try:
            await client.send_json(event)
        except Exception:
            stale.append(client)
    for client in stale:
        _websocket_clients.discard(client)


def _publish_event(event: dict[str, Any]) -> None:
    loop = _loop
    if loop is not None and loop.is_running():
        try:
            asyncio.run_coroutine_threadsafe(_broadcast_event(event), loop)
        except RuntimeError:
            pass


@app.websocket("/ws/notifications")
async def notifications(websocket: WebSocket) -> None:
    expected = _token()
    await websocket.accept()
    try:
        # Authenticate in the first frame rather than a URL query parameter (which can leak to logs).
        if expected:
            auth_frame = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            supplied = auth_frame.removeprefix("auth:") if auth_frame.startswith("auth:") else ""
            if not hmac.compare_digest(supplied, expected):
                await websocket.close(code=4401, reason="Unauthorized")
                return
        else:
            # Local-only service has no bearer token; ignore the client's handshake message.
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
        _websocket_clients.add(websocket)
        await websocket.send_json({"type": "connected", "service": "visionguide-device-agent"})
        while True:
            message = await websocket.receive_text()
            if message.strip().lower() == "ping":
                await websocket.send_json({"type": "heartbeat"})
    except (WebSocketDisconnect, RuntimeError, asyncio.TimeoutError):
        pass
    finally:
        _websocket_clients.discard(websocket)


def execute_route(route: RoutedCommand, *, confirmed: bool = False) -> dict[str, Any]:
    """Execute one allowlisted intent with argument and permission validation."""
    action, args = route.action, dict(route.arguments)
    try:
        if action == "google_workspace_feature":
            operation = str(args.get("operation", "")).casefold()
            if operation in GOOGLE_WORKSPACE_WRITE_OPERATIONS and not confirmed:
                preview = {key: (str(value)[:1500] if isinstance(value, str) else value)
                           for key, value in args.items() if key != "operation"}
                return {"status": "confirmation_required", "message": "Review the Google Workspace write operation and its preview before continuing.", "operation": operation, "preview": preview}
            return {"status": "ok", **execute_google_workspace_operation(operation, args, confirmed=confirmed)}
        if action == "google_maps_feature":
            return {"status": "ok", **execute_google_maps_operation(str(args.get("operation", "")), args, service=_maps_services)}
        if action == "google_cloud_feature":
            return {"status": "ok", **execute_google_cloud_operation(str(args.get("operation", "")), args)}
        if action == "general_query":
            return {"status": "ok", "answer": gemini.ask_text(str(args.get("prompt", "")))}
        if action == "open_website":
            return {"status": "ok", "message": open_website(str(args.get("name", "")))}
        if action == "open_app":
            return {"status": "ok", "message": open_app(str(args.get("name", "")))}
        if action == "youtube_search":
            return {"status": "ok", "message": search_youtube(str(args.get("query", "")))}
        if action == "web_search":
            return {"status": "ok", "message": search_web(str(args.get("query", "")))}
        if action == "media_playback":
            return {"status": "ok", "message": media_playback(str(args.get("action", "toggle")), int(args.get("seconds", 10)))}
        if action == "brightness_set":
            return {"status": "ok", "message": set_brightness(int(args["level"]))}
        if action == "brightness_adjust":
            return {"status": "ok", "message": adjust_brightness(int(args["delta"]))}
        if action == "brightness_get":
            return {"status": "ok", "brightness": get_brightness()}
        if action == "volume_set":
            return {"status": "ok", "message": set_volume(int(args["level"]))}
        if action == "volume_adjust":
            return {"status": "ok", "message": adjust_volume(int(args["delta"]))}
        if action == "volume_get":
            return {"status": "ok", **get_volume()}
        if action == "wifi_status":
            return {"status": "ok", "adapters": list_wifi_adapters()}
        if action == "audio_mute":
            return {"status": "ok", "message": set_mute(bool(args.get("muted", True)))}
        if action == "wifi_set":
            if not confirmed:
                return {"status": "confirmation_required", "message": "Confirm changing the network adapter state; this can disconnect the client.", "preview": args}
            return {"status": "ok", "message": set_wifi(bool(args.get("enabled")), str(args.get("adapter", "Wi-Fi")))}
        if action == "wifi_status":
            return {"status": "ok", "adapters": list_wifi_adapters()}
        if action == "brightness_get":
            return {"status": "ok", "brightness": get_brightness()}
        if action == "volume_get":
            return {"status": "ok", **get_volume()}
        if action == "timer_set":
            record = _timers.schedule(int(args.get("seconds", 0)), str(args.get("label", "Reminder")))
            return {"status": "ok", "timer": {"id": record.timer_id, "label": record.label, "duration_seconds": record.duration_seconds}}
        if action == "timer_list":
            return {"status": "ok", "timers": _timers.list_timers()}
        if action == "timer_cancel":
            cancelled = _timers.cancel(int(args.get("id", 0)))
            return {"status": "ok" if cancelled else "not_found", "cancelled": cancelled}
        if action == "gmail_unread":
            include_body = bool(args.get("include_body", False))
            messages = gmail_unread(int(args.get("limit", 10)), include_body=include_body)
            return {"status": "ok", "messages": messages, "count": len(messages), "bodies_included": include_body}
        if action == "gmail_read_message":
            return {"status": "ok", "message": gmail_read_message(str(args.get("message_id", "")))}
        if action == "gmail_search":
            messages = gmail_search(str(args.get("query", "")), int(args.get("limit", 10)))
            return {"status": "ok", "messages": messages, "count": len(messages)}
        if action == "calendar_upcoming":
            events = calendar_upcoming(int(args.get("days", 7)), int(args.get("limit", 10)))
            return {"status": "ok", "events": events, "count": len(events)}
        if action == "calendar_search":
            events = calendar_search(str(args.get("query", "")), int(args.get("days", 180)))
            return {"status": "ok", "events": events, "count": len(events)}
        if action == "calendar_create_event":
            if not confirmed:
                return {"status": "confirmation_required", "message": "Review event details before it is added to Calendar.", "preview": args}
            return {"status": "ok", "event": calendar_create_event(
                str(args["summary"]), str(args["start"]), str(args["end"]), str(args.get("timezone_name", "Asia/Kolkata")),
                location=str(args.get("location", "")), description=str(args.get("description", "")), confirmed=True)}
        if action == "gmail_api_send_draft":
            if not confirmed:
                return {"status": "confirmation_required", "message": "Review the complete draft before sending."}
            return {"status": "ok", **gmail_send_draft(
                str(args.get("draft_id", "")), confirmed=True,
                expected_fingerprint=str(args.get("expected_fingerprint", "")),
            )}
        if action == "gmail_compose":
            if not confirmed:
                return {"status": "confirmation_required", "message": "This will send the drafting instructions to Gemini and enter a draft into the local Gmail window. It will not send the email.", "preview": {"recipient": args.get("recipient", ""), "subject": args.get("subject", ""), "instructions": args.get("instructions", "")}}
            recipient = str(args.get("recipient", ""))
            subject = str(args.get("subject", ""))
            instructions = str(args.get("instructions", ""))
            body = gemini.ask_text("Write a professional email body only. Do not invent facts. User's drafting instructions: " + instructions)
            message = compose_gmail_gui(recipient, subject, body, send=False)
            return {"status": "ok", "draft_open": True, "recipient": recipient, "subject": subject, "body_preview": body[:1500], "message": message}
        if action == "word_write":
            from visionguide.integrations.gui_automation import word_write_document
            if not confirmed:
                return {"status": "confirmation_required", "message": "This opens a new Word document and pastes text. It will not save/share the file.", "preview": str(args.get("text", ""))[:1000]}
            return {"status": "ok", "message": word_write_document(str(args.get("text", "")))}
        if action == "whatsapp_compose":
            from visionguide.integrations.gui_automation import compose_whatsapp_gui
            if not confirmed:
                return {"status": "confirmation_required", "message": "This opens WhatsApp Web and types an unsent draft. Verify the selected recipient before sending.", "preview": {"contact": args.get("contact", ""), "message": str(args.get("message", ""))[:1000]}}
            return {"status": "ok", "message": compose_whatsapp_gui(str(args.get("contact", "")), str(args.get("message", "")), send=False)}
        if action == "whatsapp_send_current":
            if not confirmed:
                return {"status": "confirmation_required", "message": "Verify visible WhatsApp chat title and message, then confirm sending."}
            from visionguide.integrations.gui_automation import send_current_whatsapp
            return {"status": "send_shortcut_issued", "message": send_current_whatsapp(confirmed_send=True)}
        if action == "type_into_window":
            if not confirmed:
                return {"status": "confirmation_required", "message": "This pastes text into a target app window without submitting it.", "preview": {"target": args.get("target", ""), "text": str(args.get("text", ""))[:1000]}}
            from visionguide.integrations.gui_automation import type_into_window
            return {"status": "ok", "message": type_into_window(str(args.get("target", "")), str(args.get("text", "")))}
        if action == "gmail_send_current":
            if not confirmed:
                return {"status": "confirmation_required", "message": "Review the current Gmail draft and explicitly confirm sending via Ctrl+Enter."}
            # The user has confirmed; target the Gmail window and issue the send shortcut.
            from visionguide.integrations.gui_automation import activate_window
            import pyautogui
            title = activate_window("gmail", timeout=5)
            pyautogui.hotkey("ctrl", "enter")
            return {"status": "sent_shortcut_issued", "message": f"Ctrl+Enter issued in {title!r}; verify Gmail's Sent state."}
        return {"status": "unsupported", "message": f"Intent {action!r} requires the desktop client, a camera adapter, or a tool not exposed by this device service."}
    except Exception as exc:
        return {"status": "error", "error_type": exc.__class__.__name__, "message": str(exc)}


def main() -> None:
    import uvicorn
    host = os.getenv("VISIONGUIDE_API_HOST", "127.0.0.1").strip()
    port = int(os.getenv("VISIONGUIDE_API_PORT", "8000"))
    uvicorn.run("visionguide.api_server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()

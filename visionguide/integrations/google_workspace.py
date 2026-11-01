from __future__ import annotations

import base64
import html
import os
import re
import json
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Request scopes per feature profile, not every scope enabled in Cloud Console.
# This limits consent and lets users authorize a new API only when they use it.
GMAIL_READONLY = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_COMPOSE = "https://www.googleapis.com/auth/gmail.compose"
GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send"
CALENDAR_EVENTS_READONLY = "https://www.googleapis.com/auth/calendar.events.readonly"
CALENDAR_EVENTS = "https://www.googleapis.com/auth/calendar.events"
CALENDAR_READONLY = "https://www.googleapis.com/auth/calendar.readonly"  # backward compatibility
SCOPES = [GMAIL_READONLY, GMAIL_COMPOSE, GMAIL_SEND, CALENDAR_EVENTS_READONLY, CALENDAR_EVENTS]

_SCOPE_PROFILES: dict[str, tuple[str, ...]] = {
    "core": tuple(SCOPES),
    "gmail_send": ("https://www.googleapis.com/auth/gmail.send",),
    "gmail_compose": ("https://www.googleapis.com/auth/gmail.compose",),
    "drive_metadata": ("https://www.googleapis.com/auth/drive.metadata.readonly",),
    "drive_search": ("https://www.googleapis.com/auth/drive.metadata.readonly",),
    "docs_read": ("https://www.googleapis.com/auth/documents.readonly",),
    "docs_write": ("https://www.googleapis.com/auth/documents",),
    "sheets_read": ("https://www.googleapis.com/auth/spreadsheets.readonly",),
    "sheets_write": ("https://www.googleapis.com/auth/spreadsheets",),
    "slides_read": ("https://www.googleapis.com/auth/presentations.readonly",),
    "slides_write": ("https://www.googleapis.com/auth/presentations",),
    "tasks_read": ("https://www.googleapis.com/auth/tasks.readonly",),
    "tasks_write": ("https://www.googleapis.com/auth/tasks",),
    "people_profile": (
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ),
    "people_contacts": ("https://www.googleapis.com/auth/contacts.readonly",),
    "classroom_courses": ("https://www.googleapis.com/auth/classroom.courses.readonly",),
    "classroom_work": (
        "https://www.googleapis.com/auth/classroom.courses.readonly",
        "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
        "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly",
    ),
    "classroom_announcements": (
        "https://www.googleapis.com/auth/classroom.courses.readonly",
        "https://www.googleapis.com/auth/classroom.announcements.readonly",
    ),
    "meet_read": ("https://www.googleapis.com/auth/meetings.space.readonly",),
    "meet_create": ("https://www.googleapis.com/auth/meetings.space.created",),
    "youtube_read": ("https://www.googleapis.com/auth/youtube.readonly",),
    "forms_read": ("https://www.googleapis.com/auth/forms.body.readonly",),
    "forms_write": ("https://www.googleapis.com/auth/forms.body",),
    "cloud_translation": ("https://www.googleapis.com/auth/cloud-translation",),
    "cloud_language": ("https://www.googleapis.com/auth/cloud-language",),
    # Additional narrow OAuth profiles requested for the extended Workspace API layer.
    "identity_openid": ("openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"),
    "people_contacts_write": ("https://www.googleapis.com/auth/contacts",),
    "people_other_contacts": ("https://www.googleapis.com/auth/contacts.other.readonly",),
    "people_agerange": ("https://www.googleapis.com/auth/profile.agerange.read",),
    "people_addresses": ("https://www.googleapis.com/auth/user.addresses.read",),
    "people_birthday": ("https://www.googleapis.com/auth/user.birthday.read",),
    "people_emails": ("https://www.googleapis.com/auth/user.emails.read",),
    "people_gender": ("https://www.googleapis.com/auth/user.gender.read",),
    "people_organization": ("https://www.googleapis.com/auth/user.organization.read",),
    "people_phones": ("https://www.googleapis.com/auth/user.phonenumbers.read",),
    "calendar_readonly": ("https://www.googleapis.com/auth/calendar.readonly",),
    "calendar_full": ("https://www.googleapis.com/auth/calendar",),
    "calendar_list_read": ("https://www.googleapis.com/auth/calendar.calendarlist.readonly",),
    "calendar_list_write": ("https://www.googleapis.com/auth/calendar.calendarlist",),
    "calendar_events_read": ("https://www.googleapis.com/auth/calendar.events.readonly",),
    "calendar_events_write": ("https://www.googleapis.com/auth/calendar.events",),
    "calendar_events_owned_read": ("https://www.googleapis.com/auth/calendar.events.owned.readonly",),
    "calendar_events_owned_write": ("https://www.googleapis.com/auth/calendar.events.owned",),
    "calendar_events_freebusy": ("https://www.googleapis.com/auth/calendar.events.freebusy",),
    "calendar_events_public": ("https://www.googleapis.com/auth/calendar.events.public.readonly",),
    "calendar_events_owned_read": ("https://www.googleapis.com/auth/calendar.events.owned.readonly",),
    "calendar_events_owned_write": ("https://www.googleapis.com/auth/calendar.events.owned",),
    "calendar_calendar_read": ("https://www.googleapis.com/auth/calendar.calendars.readonly",),
    "calendar_calendar_write": ("https://www.googleapis.com/auth/calendar.calendars",),
    "calendar_app_created": ("https://www.googleapis.com/auth/calendar.app.created",),
    "calendar_settings_read": ("https://www.googleapis.com/auth/calendar.settings.readonly",),
    "calendar_settings_write": ("https://www.googleapis.com/auth/calendar.settings",),
    "calendar_freebusy": ("https://www.googleapis.com/auth/calendar.freebusy",),
    "calendar_acl_read": ("https://www.googleapis.com/auth/calendar.acls.readonly",),
    "calendar_acl_write": ("https://www.googleapis.com/auth/calendar.acls",),
    "gmail_messages_read": ("https://www.googleapis.com/auth/gmail.messages.readonly",),
    "gmail_metadata": ("https://www.googleapis.com/auth/gmail.metadata",),
    "gmail_user_read": ("https://www.googleapis.com/auth/gmail.user.readonly",),
    "gmail_modify": ("https://www.googleapis.com/auth/gmail.modify",),
    "gmail_messages_modify": ("https://www.googleapis.com/auth/gmail.messages.modify",),
    "gmail_mail_full": ("https://mail.google.com/",),
    "gmail_messages_full": ("https://www.googleapis.com/auth/gmail.messages",),
    "gmail_drafts_create_narrow": ("https://www.googleapis.com/auth/gmail.drafts.create",),
    "gmail_insert": ("https://www.googleapis.com/auth/gmail.insert",),
    "gmail_drafts_read": ("https://www.googleapis.com/auth/gmail.drafts.readonly",),
    "gmail_drafts_write": ("https://www.googleapis.com/auth/gmail.drafts",),
    "gmail_labels_read": ("https://www.googleapis.com/auth/gmail.labels.readonly",),
    "gmail_labels_write": ("https://www.googleapis.com/auth/gmail.labels",),
    "gmail_labels_create_narrow": ("https://www.googleapis.com/auth/gmail.labels.create",),
    "gmail_settings_read": ("https://www.googleapis.com/auth/gmail.settings.readonly",),
    "gmail_settings_write": ("https://www.googleapis.com/auth/gmail.settings.basic",),
    "gmail_filters_read": ("https://www.googleapis.com/auth/gmail.settings.filters.readonly",),
    "gmail_filters_write": ("https://www.googleapis.com/auth/gmail.settings.filters",),
    "gmail_forwarding_read": ("https://www.googleapis.com/auth/gmail.settings.forwarding.readonly",),
    "gmail_forwarding_write": ("https://www.googleapis.com/auth/gmail.settings.forwarding",),
    "gmail_autoforward_read": ("https://www.googleapis.com/auth/gmail.settings.autoforwarding.readonly",),
    "gmail_autoforward_write": ("https://www.googleapis.com/auth/gmail.settings.autoforwarding",),
    "gmail_sendas_read": ("https://www.googleapis.com/auth/gmail.settings.sendas.readonly",),
    "gmail_sendas_write": ("https://www.googleapis.com/auth/gmail.settings.sendas",),
    "gmail_sharing": ("https://www.googleapis.com/auth/gmail.settings.sharing",),
    "gmail_delegates_read": ("https://www.googleapis.com/auth/gmail.settings.delegates.readonly",),
    "gmail_delegates_write": ("https://www.googleapis.com/auth/gmail.settings.delegates",),
    "gmail_notifications": ("https://www.googleapis.com/auth/gmail.notifications", "https://www.googleapis.com/auth/gmail.readonly"),
    "gmail_send_self": ("https://www.googleapis.com/auth/gmail.send.self",),
    "drive_full": ("https://www.googleapis.com/auth/drive",),
    "drive_readonly": ("https://www.googleapis.com/auth/drive.readonly",),
    "drive_metadata_write": ("https://www.googleapis.com/auth/drive.metadata",),
    "drive_item_write": ("https://www.googleapis.com/auth/drive.item",),
    "drive_item_read": ("https://www.googleapis.com/auth/drive.item.readonly",),
    "drive_item_collaboration_read": ("https://www.googleapis.com/auth/drive.item.collaboration.readonly",),
    "drive_file_scope": ("https://www.googleapis.com/auth/drive.file",),
    "drive_meet_read": ("https://www.googleapis.com/auth/drive.meet.readonly",),
    "drive_activity_read": ("https://www.googleapis.com/auth/drive.activity.readonly",),
    "drive_activity_write": ("https://www.googleapis.com/auth/drive.activity",),
    "drive_scripts": ("https://www.googleapis.com/auth/drive.scripts",),
    "drive_appdata": ("https://www.googleapis.com/auth/drive.appdata",),
    "drive_install": ("https://www.googleapis.com/auth/drive.install",),
    "drive_apps_read": ("https://www.googleapis.com/auth/drive.apps.readonly",),
    "drive_apps_write": ("https://www.googleapis.com/auth/drive.apps",),
    "drive_photos_read": ("https://www.googleapis.com/auth/drive.photos.readonly",),
    "generative_tuning_read": ("https://www.googleapis.com/auth/generative-language.tuning.readonly",),
    "generative_tuning_write": ("https://www.googleapis.com/auth/generative-language.tuning",),
    "generative_retriever_read": ("https://www.googleapis.com/auth/generative-language.retriever.readonly",),
    "generative_retriever_write": ("https://www.googleapis.com/auth/generative-language.retriever",),
    "generative_peruserquota": ("https://www.googleapis.com/auth/generative-language.peruserquota",),
    "classroom_rosters_read": ("https://www.googleapis.com/auth/classroom.rosters.readonly",),
    "classroom_rosters_write": ("https://www.googleapis.com/auth/classroom.rosters",),
    "classroom_students_work_read": ("https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",),
    "classroom_students_work_admin_read": ("https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",),
    "classroom_students_work_write": ("https://www.googleapis.com/auth/classroom.coursework.students",),
    "classroom_coursework_write": ("https://www.googleapis.com/auth/classroom.coursework.me",),
    "classroom_materials_write": ("https://www.googleapis.com/auth/classroom.courseworkmaterials",),
    "classroom_announcements_write": ("https://www.googleapis.com/auth/classroom.announcements",),
    "classroom_topics_read": ("https://www.googleapis.com/auth/classroom.topics.readonly",),
    "classroom_topics_write": ("https://www.googleapis.com/auth/classroom.topics",),
    "classroom_guardians_me": ("https://www.googleapis.com/auth/classroom.guardianlinks.me.readonly",),
    "classroom_guardians_students_read": ("https://www.googleapis.com/auth/classroom.guardianlinks.students.readonly",),
    "classroom_guardians_students_write": ("https://www.googleapis.com/auth/classroom.guardianlinks.students",),
    "classroom_profile_emails": ("https://www.googleapis.com/auth/classroom.profile.emails",),
    "classroom_profile_photos": ("https://www.googleapis.com/auth/classroom.profile.photos",),
    "classroom_push": ("https://www.googleapis.com/auth/classroom.push-notifications",),
    "classroom_courses_write": ("https://www.googleapis.com/auth/classroom.courses",),
    "classroom_addon_student": ("https://www.googleapis.com/auth/classroom.addons.student",),
    "classroom_addon_teacher": ("https://www.googleapis.com/auth/classroom.addons.teacher",),
    "classroom_practice_sets": ("https://www.googleapis.com/auth/classroom.practicesets",),
    "meet_settings": ("https://www.googleapis.com/auth/meetings.space.settings",),
    "meet_media_read": ("https://www.googleapis.com/auth/meetings.conference.media.readonly",),
    "meet_media_audio_read": ("https://www.googleapis.com/auth/meetings.conference.media.audio.readonly",),
    "meet_media_video_read": ("https://www.googleapis.com/auth/meetings.conference.media.video.readonly",),
    "meet_hardware": ("https://www.googleapis.com/auth/meetings.hardware",),
    "youtube_full": ("https://www.googleapis.com/auth/youtube",),
    "youtube_force_ssl": ("https://www.googleapis.com/auth/youtube.force-ssl",),
    "youtube_upload": ("https://www.googleapis.com/auth/youtube.upload",),
    "youtube_download": ("https://www.googleapis.com/auth/youtube.download",),
    "youtube_partner": ("https://www.googleapis.com/auth/youtubepartner",),
    "youtube_partner_audit": ("https://www.googleapis.com/auth/youtubepartner-channel-audit",),
    "youtube_memberships": ("https://www.googleapis.com/auth/youtube.channel-memberships.creator",),
    "youtube_third_party_link": ("https://www.googleapis.com/auth/youtube.third-party-link.creator",),
    "forms_responses_read": ("https://www.googleapis.com/auth/forms.responses.readonly",),
    "documents_full": ("https://www.googleapis.com/auth/documents",),
    "documents_read": ("https://www.googleapis.com/auth/documents.readonly",),
    "spreadsheets_full": ("https://www.googleapis.com/auth/spreadsheets",),
    "spreadsheets_read": ("https://www.googleapis.com/auth/spreadsheets.readonly",),
    "presentations_full": ("https://www.googleapis.com/auth/presentations",),
    "presentations_read": ("https://www.googleapis.com/auth/presentations.readonly",),
    "tasks_full": ("https://www.googleapis.com/auth/tasks",),
    "tasks_readonly": ("https://www.googleapis.com/auth/tasks.readonly",),
    "drive_docs_alias": ("https://www.googleapis.com/auth/docs",),
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _credentials_path() -> Path:
    value = Path(os.getenv("GOOGLE_OAUTH_CLIENT_FILE", "credentials/google_oauth_client.json")).expanduser()
    return value if value.is_absolute() else _project_root() / value


def _token_path(profile: str = "core") -> Path:
    if profile not in _SCOPE_PROFILES:
        raise ValueError("Unknown Google OAuth scope profile.")
    value = Path(os.getenv("GOOGLE_TOKEN_DIR", "data/google_tokens")).expanduser()
    directory = value if value.is_absolute() else _project_root() / value
    directory.mkdir(parents=True, exist_ok=True)
    filename = "google_workspace_token.json" if profile == "core" else f"google_{profile}_token.json"
    return directory / filename


def _credentials(profile: str = "core"):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise RuntimeError("Google Workspace needs google-api-python-client, google-auth-httplib2, and google-auth-oauthlib; install requirements-integrations.txt.") from exc
    if profile not in _SCOPE_PROFILES:
        raise ValueError("Unknown Google OAuth scope profile.")
    scopes = list(_SCOPE_PROFILES[profile])
    client_file = _credentials_path()
    if not client_file.is_file():
        raise FileNotFoundError(
            f"Google OAuth client file was not found at {client_file}. Create a Desktop OAuth client in Google Cloud Console and place its JSON there."
        )
    token_file = _token_path(profile)
    creds = Credentials.from_authorized_user_file(str(token_file), scopes) if token_file.is_file() else None
    if creds and creds.valid and creds.has_scopes(scopes):
        return creds
    if creds and creds.expired and creds.refresh_token and creds.has_scopes(scopes):
        creds.refresh(Request())
    else:
        # Scope profile tokens are isolated: adding a service never silently expands the
        # permissions on the existing Gmail/Calendar token.
        flow = InstalledAppFlow.from_client_secrets_file(str(client_file), scopes=scopes)
        creds = flow.run_local_server(port=0, open_browser=True)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    try:
        os.chmod(token_file, 0o600)
    except OSError:
        pass
    return creds


def _service(api: str, version: str, profile: str = "core"):
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("Google Workspace APIs require google-api-python-client. Install requirements-integrations.txt.") from exc
    return build(api, version, credentials=_credentials(profile), cache_discovery=False)


def gmail_unread(limit: int = 10, *, include_body: bool = False) -> list[dict[str, str]]:
    limit = max(1, min(int(limit), 20 if include_body else 50))
    service = _service("gmail", "v1")
    listed = service.users().messages().list(userId="me", q="is:unread", maxResults=limit).execute()
    output = []
    for item in listed.get("messages", []):
        message = service.users().messages().get(
            userId="me", id=item["id"], format="full" if include_body else "metadata",
            metadataHeaders=["From", "To", "Subject", "Date"],
        ).execute()
        headers = {h["name"].lower(): h.get("value", "") for h in message.get("payload", {}).get("headers", [])}
        row = {
            "id": item["id"], "thread_id": message.get("threadId", ""),
            "from": headers.get("from", ""), "to": headers.get("to", ""),
            "subject": headers.get("subject", "(no subject)"), "date": headers.get("date", ""),
            "snippet": message.get("snippet", ""),
        }
        if include_body:
            row["body"] = _extract_message_body(message.get("payload", {}))[:16000]
        output.append(row)
    return output


def gmail_search(query: str, limit: int = 10) -> list[dict[str, str]]:
    query = " ".join(str(query).split()).strip()
    if not query:
        raise ValueError("Provide a Gmail search query, for example 'from:professor newer_than:30d'.")
    if len(query) > 500:
        raise ValueError("Gmail search query must be 500 characters or fewer.")
    limit = max(1, min(int(limit), 50))
    service = _service("gmail", "v1")
    listed = service.users().messages().list(userId="me", q=query, maxResults=limit).execute()
    output = []
    for item in listed.get("messages", []):
        message = service.users().messages().get(userId="me", id=item["id"], format="metadata", metadataHeaders=["From", "To", "Subject", "Date"]).execute()
        headers = {h["name"].lower(): h.get("value", "") for h in message.get("payload", {}).get("headers", [])}
        output.append({
            "id": item["id"], "thread_id": message.get("threadId", ""),
            "from": headers.get("from", ""), "to": headers.get("to", ""),
            "subject": headers.get("subject", "(no subject)"), "date": headers.get("date", ""),
            "snippet": message.get("snippet", ""),
        })
    return output


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs):
        if tag in {"script", "style", "head"}:
            self._skip_depth += 1
        elif tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str):
        if tag in {"script", "style", "head"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag in {"p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str):
        if not self._skip_depth:
            self.parts.append(data)


def _decode_part(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_message_body(payload: dict[str, Any]) -> str:
    plain: list[str] = []
    html_parts: list[str] = []

    def walk(part: dict[str, Any]) -> None:
        mime = str(part.get("mimeType", "")).lower()
        data = str(part.get("body", {}).get("data", ""))
        if data:
            decoded = _decode_part(data)
            if mime == "text/plain":
                plain.append(decoded)
            elif mime == "text/html":
                html_parts.append(decoded)
        for child in part.get("parts", []) or []:
            if isinstance(child, dict):
                walk(child)

    walk(payload)
    if plain:
        body = "\n".join(plain)
    elif html_parts:
        parser = _HTMLText()
        parser.feed("\n".join(html_parts))
        body = "".join(parser.parts)
        body = html.unescape(body)
    else:
        body = ""
    return "\n".join(line.rstrip() for line in body.splitlines()).strip()


def gmail_read_message(message_id: str) -> dict[str, str]:
    message_id = str(message_id).strip()
    if not message_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", message_id):
        raise ValueError("Invalid Gmail message ID.")
    service = _service("gmail", "v1")
    message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    headers = {h["name"].lower(): h.get("value", "") for h in message.get("payload", {}).get("headers", [])}
    return {"id": message_id, "thread_id": str(message.get("threadId", "")),
            "from": headers.get("from", ""), "to": headers.get("to", ""),
            "subject": headers.get("subject", "(no subject)"), "date": headers.get("date", ""),
            "snippet": str(message.get("snippet", "")), "body": _extract_message_body(message.get("payload", {}))[:30000]}


def gmail_create_draft(to: str, subject: str, body: str) -> dict[str, str]:
    to = _validate_email(to)
    subject = " ".join(str(subject).split()).strip()
    body = str(body).strip()
    if not subject:
        raise ValueError("Email subject is required.")
    if not body:
        raise ValueError("Email body is required.")
    if len(subject) > 250 or len(body) > 100_000:
        raise ValueError("Email subject/body exceeds supported length.")
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    service = _service("gmail", "v1")
    draft = service.users().drafts().create(userId="me", body={"message": {"raw": encoded}}).execute()
    return {"id": str(draft.get("id", "")), "message_id": str(draft.get("message", {}).get("id", "")), "to": to, "subject": subject}


def _get_gmail_draft(draft_id: str) -> dict[str, Any]:
    draft_id = str(draft_id).strip()
    if not draft_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", draft_id):
        raise ValueError("Invalid Gmail draft ID.")
    service = _service("gmail", "v1")
    draft = service.users().drafts().get(userId="me", id=draft_id, format="full").execute()
    message = draft.get("message", {})
    headers = {h["name"].lower(): h.get("value", "") for h in message.get("payload", {}).get("headers", [])}
    body = _extract_message_body(message.get("payload", {}))
    details = {
        "draft_id": draft_id,
        "to": headers.get("to", ""),
        "subject": headers.get("subject", "(no subject)"),
        "date": headers.get("date", ""),
        "body": body,
    }
    digest_material = json.dumps(
        {key: details[key] for key in ("to", "subject", "body")},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    details["fingerprint"] = hashlib.sha256(digest_material).hexdigest()
    return details


def gmail_draft_preview(draft_id: str) -> dict[str, str]:
    """Read the exact draft fields so a client can show a send-confirmation preview."""
    return _get_gmail_draft(draft_id)


def gmail_send_draft(
    draft_id: str, *, confirmed: bool = False, expected_fingerprint: str | None = None,
) -> dict[str, str]:
    if not confirmed:
        raise PermissionError("Sending email requires explicit user confirmation after reviewing recipient, subject, and body.")
    draft_id = str(draft_id).strip()
    current = _get_gmail_draft(draft_id)
    if expected_fingerprint is not None and not hmac.compare_digest(current["fingerprint"], str(expected_fingerprint)):
        raise RuntimeError("The Gmail draft changed after the confirmation preview. Review it again and request a new confirmation.")
    service = _service("gmail", "v1")
    sent = service.users().drafts().send(userId="me", body={"id": draft_id}).execute()
    return {"id": str(sent.get("id", "")), "thread_id": str(sent.get("threadId", "")), "status": "sent"}


def calendar_upcoming(days: int = 7, limit: int = 10) -> list[dict[str, str]]:
    days = max(1, min(int(days), 366))
    limit = max(1, min(int(limit), 50))
    now = datetime.now(timezone.utc)
    service = _service("calendar", "v3")
    result = service.events().list(
        calendarId="primary", timeMin=now.isoformat(), timeMax=(now + timedelta(days=days)).isoformat(),
        maxResults=limit, singleEvents=True, orderBy="startTime",
    ).execute()
    return [
        {"id": str(event.get("id", "")), "summary": str(event.get("summary", "(no title)")),
         "start": str(event.get("start", {}).get("dateTime", event.get("start", {}).get("date", ""))),
         "end": str(event.get("end", {}).get("dateTime", event.get("end", {}).get("date", ""))),
         "location": str(event.get("location", "")), "html_link": str(event.get("htmlLink", ""))}
        for event in result.get("items", [])
    ]


def calendar_search(query: str, days: int = 180, limit: int = 50) -> list[dict[str, str]]:
    query = " ".join(str(query).split()).strip()
    if not query:
        raise ValueError("Provide words to search for in calendar event titles/descriptions.")
    days = max(1, min(int(days), 730))
    limit = max(1, min(int(limit), 100))
    now = datetime.now(timezone.utc)
    service = _service("calendar", "v3")
    result = service.events().list(
        calendarId="primary", timeMin=(now - timedelta(days=days // 4)).isoformat(),
        timeMax=(now + timedelta(days=days)).isoformat(), maxResults=limit,
        singleEvents=True, orderBy="startTime", q=query,
    ).execute()
    return [
        {"id": str(e.get("id", "")), "summary": str(e.get("summary", "(no title)")),
         "start": str(e.get("start", {}).get("dateTime", e.get("start", {}).get("date", ""))),
         "end": str(e.get("end", {}).get("dateTime", e.get("end", {}).get("date", ""))),
         "location": str(e.get("location", "")), "html_link": str(e.get("htmlLink", ""))}
        for e in result.get("items", [])
    ]


def calendar_create_event(
    summary: str, start: str, end: str, timezone_name: str = "Asia/Kolkata", *,
    location: str = "", description: str = "", confirmed: bool = False,
) -> dict[str, str]:
    if not confirmed:
        raise PermissionError("Creating a calendar event requires explicit confirmation of title, time, and timezone.")
    summary = " ".join(str(summary).split()).strip()
    if not summary or len(summary) > 250:
        raise ValueError("Event title is required and must be 250 characters or fewer.")
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone {timezone_name!r}. Use an IANA timezone such as Asia/Kolkata.") from exc

    def parse_time(value: str) -> datetime:
        text = str(value).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError("Event start/end must be ISO 8601 date-times, for example 2026-10-26T15:00:00+05:30.") from exc
        return dt.replace(tzinfo=tz) if dt.tzinfo is None else dt

    start_dt, end_dt = parse_time(start), parse_time(end)
    if end_dt <= start_dt:
        raise ValueError("Event end must be later than event start.")
    if end_dt - start_dt > timedelta(days=7):
        raise ValueError("A single event cannot exceed seven days.")
    service = _service("calendar", "v3")
    event = {
        "summary": summary, "location": str(location).strip()[:500], "description": str(description).strip()[:5000],
        "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone_name},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone_name},
    }
    created = service.events().insert(calendarId="primary", body=event).execute()
    return {"id": str(created.get("id", "")), "summary": summary,
            "start": str(created.get("start", {}).get("dateTime", "")),
            "end": str(created.get("end", {}).get("dateTime", "")),
            "html_link": str(created.get("htmlLink", ""))}


def _validate_email(value: str) -> str:
    value = str(value).strip()
    # Strict single-recipient address validation; multi-recipient lists require explicit UI support.
    if len(value) > 254 or not re.fullmatch(r"[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+", value):
        raise ValueError("Provide one valid email address.")
    return value


# ---- Optional Google Workspace service adapters ---------------------------------
# Every API obtains a separate minimally scoped token (see _SCOPE_PROFILES). Read
# calls remain read-only; every write operation requires confirmed=True.

def _validate_resource_id(value: str, label: str = "resource ID") -> str:
    value = str(value).strip()
    if not value or len(value) > 250 or not re.fullmatch(r"[A-Za-z0-9_:-]+", value):
        raise ValueError(f"Invalid {label}.")
    return value


def _require_confirmed(confirmed: bool, action: str) -> None:
    if not confirmed:
        raise PermissionError(f"{action} requires explicit user confirmation after reviewing the details.")


def drive_search(query: str, limit: int = 10) -> list[dict[str, str]]:
    query = " ".join(str(query).split()).strip()
    if not query:
        raise ValueError("Provide a file name or phrase to search in Google Drive.")
    if len(query) > 200:
        raise ValueError("Drive search text must be 200 characters or fewer.")
    limit = max(1, min(int(limit), 50))
    escaped = query.replace("\\", "\\\\").replace("'", "\\'")
    service = _service("drive", "v3", "drive_search")
    result = service.files().list(
        q=f"trashed = false and name contains '{escaped}'",
        pageSize=limit, orderBy="modifiedTime desc",
        fields="files(id,name,mimeType,modifiedTime,webViewLink)",
        spaces="drive",
    ).execute()
    return [{key: str(row.get(key, "")) for key in ("id", "name", "mimeType", "modifiedTime", "webViewLink")}
            for row in result.get("files", [])]


def _document_text(content: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    def visit(items: list[dict[str, Any]]) -> None:
        for item in items:
            paragraph = item.get("paragraph")
            if isinstance(paragraph, dict):
                for element in paragraph.get("elements", []) or []:
                    run = element.get("textRun", {})
                    if run.get("content"):
                        chunks.append(str(run["content"]))
            table = item.get("table")
            if isinstance(table, dict):
                for row in table.get("tableRows", []) or []:
                    for cell in row.get("tableCells", []) or []:
                        visit(cell.get("content", []) or [])
            toc = item.get("tableOfContents")
            if isinstance(toc, dict):
                visit(toc.get("content", []) or [])
    visit(content)
    return "".join(chunks).strip()


def docs_read(document_id: str) -> dict[str, str]:
    document_id = _validate_resource_id(document_id, "Google Docs document ID")
    doc = _service("docs", "v1", "docs_read").documents().get(documentId=document_id).execute()
    body = doc.get("body", {}).get("content", []) or []
    return {"document_id": str(doc.get("documentId", document_id)), "title": str(doc.get("title", "Untitled")),
            "text": _document_text(body)[:50000], "url": f"https://docs.google.com/document/d/{document_id}/edit"}


def docs_create(title: str, content: str, *, confirmed: bool = False) -> dict[str, str]:
    _require_confirmed(confirmed, "Creating a Google Doc")
    title = " ".join(str(title).split()).strip()
    content = str(content).strip()
    if not title or len(title) > 250:
        raise ValueError("Google Docs title is required and must be 250 characters or fewer.")
    if len(content) > 50000:
        raise ValueError("Google Docs content exceeds 50,000 characters.")
    service = _service("docs", "v1", "docs_write")
    created = service.documents().create(body={"title": title}).execute()
    doc_id = str(created.get("documentId", ""))
    if content and doc_id:
        service.documents().batchUpdate(documentId=doc_id, body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]}).execute()
    return {"document_id": doc_id, "title": title, "url": f"https://docs.google.com/document/d/{doc_id}/edit"}


def sheets_read(spreadsheet_id: str, range_name: str = "A1:Z100") -> dict[str, Any]:
    spreadsheet_id = _validate_resource_id(spreadsheet_id, "Google Sheets spreadsheet ID")
    range_name = str(range_name).strip()
    if not range_name or len(range_name) > 250 or "!" in range_name and len(range_name.split("!", 1)[0]) > 100:
        raise ValueError("Provide a valid A1 notation range, such as Sheet1!A1:D20.")
    result = _service("sheets", "v4", "sheets_read").spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=range_name, majorDimension="ROWS",
    ).execute()
    values = result.get("values", []) or []
    return {"spreadsheet_id": spreadsheet_id, "range": str(result.get("range", range_name)),
            "values": values[:100], "url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"}


def sheets_update(spreadsheet_id: str, range_name: str, values_json: str, *, confirmed: bool = False) -> dict[str, Any]:
    _require_confirmed(confirmed, "Updating Google Sheets")
    spreadsheet_id = _validate_resource_id(spreadsheet_id, "Google Sheets spreadsheet ID")
    range_name = str(range_name).strip()
    if not range_name or len(range_name) > 250:
        raise ValueError("Provide an A1 notation range, such as Sheet1!A1:B2.")
    try:
        values = json.loads(values_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Sheet values must be JSON, for example [[\"Name\",\"Age\"],[\"Asha\",20]].") from exc
    if not isinstance(values, list) or not values or len(values) > 100 or any(not isinstance(row, list) or not row or len(row) > 30 for row in values):
        raise ValueError("Sheet values must contain 1–100 non-empty rows, with at most 30 cells per row.")
    if sum(len(row) for row in values) > 1000:
        raise ValueError("Sheet update is limited to 1,000 cells per request.")
    result = _service("sheets", "v4", "sheets_write").spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=range_name, valueInputOption="RAW",
        body={"majorDimension": "ROWS", "values": values},
    ).execute()
    return {"spreadsheet_id": spreadsheet_id, "updated_range": str(result.get("updatedRange", range_name)),
            "updated_cells": int(result.get("updatedCells", 0)), "url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"}


def slides_read(presentation_id: str) -> dict[str, Any]:
    presentation_id = _validate_resource_id(presentation_id, "Google Slides presentation ID")
    presentation = _service("slides", "v1", "slides_read").presentations().get(
        presentationId=presentation_id, fields="presentationId,title,slides(objectId,pageElements(shape(text(textElements(textRun(content))))))",
    ).execute()
    slide_text: list[dict[str, Any]] = []
    for index, slide in enumerate(presentation.get("slides", []) or [], 1):
        chunks: list[str] = []
        for element in slide.get("pageElements", []) or []:
            shape = element.get("shape", {})
            for paragraph in shape.get("text", {}).get("textElements", []) or []:
                if paragraph.get("textRun", {}).get("content"):
                    chunks.append(str(paragraph["textRun"]["content"]))
        slide_text.append({"slide": index, "text": "".join(chunks).strip()[:5000]})
    return {"presentation_id": presentation_id, "title": str(presentation.get("title", "Untitled")),
            "slides": slide_text[:100], "url": f"https://docs.google.com/presentation/d/{presentation_id}/edit"}


def slides_create(title: str, *, confirmed: bool = False) -> dict[str, str]:
    _require_confirmed(confirmed, "Creating a Google Slides presentation")
    title = " ".join(str(title).split()).strip()
    if not title or len(title) > 250:
        raise ValueError("Presentation title is required and must be 250 characters or fewer.")
    created = _service("slides", "v1", "slides_write").presentations().create(body={"title": title}).execute()
    presentation_id = str(created.get("presentationId", ""))
    return {"presentation_id": presentation_id, "title": title,
            "url": f"https://docs.google.com/presentation/d/{presentation_id}/edit"}


def tasks_list(limit: int = 20) -> list[dict[str, str]]:
    limit = max(1, min(int(limit), 100))
    service = _service("tasks", "v1", "tasks_read")
    result = service.tasks().list(tasklist="@default", maxResults=limit, showCompleted=False, showHidden=False).execute()
    return [{"id": str(t.get("id", "")), "title": str(t.get("title", "")), "notes": str(t.get("notes", "")),
             "due": str(t.get("due", "")), "status": str(t.get("status", "needsAction"))}
            for t in result.get("items", []) or []]


def tasks_create(title: str, notes: str = "", due: str = "", *, confirmed: bool = False) -> dict[str, str]:
    _require_confirmed(confirmed, "Creating a Google Task")
    title = " ".join(str(title).split()).strip()
    if not title or len(title) > 1024:
        raise ValueError("Task title is required and must be 1,024 characters or fewer.")
    task: dict[str, str] = {"title": title}
    if notes:
        task["notes"] = str(notes).strip()[:8000]
    if due:
        try:
            parsed_due = datetime.fromisoformat(str(due).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Task due date must be an ISO 8601 date-time.") from exc
        if parsed_due.tzinfo is None:
            raise ValueError("Task due date must include a timezone offset or Z.")
        task["due"] = parsed_due.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    created = _service("tasks", "v1", "tasks_write").tasks().insert(tasklist="@default", body=task).execute()
    return {"id": str(created.get("id", "")), "title": str(created.get("title", title)),
            "due": str(created.get("due", "")), "status": str(created.get("status", "needsAction"))}


def google_profile() -> dict[str, Any]:
    person = _service("people", "v1", "people_profile").people().get(resourceName="people/me", personFields="names,emailAddresses,photos").execute()
    return {"name": (person.get("names") or [{}])[0].get("displayName", ""),
            "email": (person.get("emailAddresses") or [{}])[0].get("value", ""),
            "photo_url": (person.get("photos") or [{}])[0].get("url", "")}


def people_search_contacts(query: str, limit: int = 10) -> list[dict[str, str]]:
    query = " ".join(str(query).split()).strip()
    if not query:
        raise ValueError("Provide a name or email to search Google Contacts.")
    limit = max(1, min(int(limit), 30))
    result = _service("people", "v1", "people_contacts").people().searchContacts(
        query=query, readMask="names,emailAddresses,phoneNumbers", pageSize=limit,
    ).execute()
    rows = []
    for item in result.get("results", []) or []:
        person = item.get("person", {}) or {}
        rows.append({"name": (person.get("names") or [{}])[0].get("displayName", ""),
                     "email": (person.get("emailAddresses") or [{}])[0].get("value", ""),
                     "phone": (person.get("phoneNumbers") or [{}])[0].get("value", "")})
    return rows


def classroom_courses(limit: int = 20) -> list[dict[str, str]]:
    limit = max(1, min(int(limit), 100))
    result = _service("classroom", "v1", "classroom_courses").courses().list(pageSize=limit, courseStates=["ACTIVE"]).execute()
    return [{"id": str(c.get("id", "")), "name": str(c.get("name", "")), "section": str(c.get("section", "")),
             "state": str(c.get("courseState", "")), "url": str(c.get("alternateLink", ""))}
            for c in result.get("courses", []) or []]


def classroom_coursework(course_id: str, limit: int = 20) -> list[dict[str, str]]:
    course_id = _validate_resource_id(course_id, "Google Classroom course ID")
    limit = max(1, min(int(limit), 100))
    result = _service("classroom", "v1", "classroom_work").courses().courseWork().list(
        courseId=course_id, pageSize=limit, orderBy="dueDate asc",
    ).execute()
    return [{"id": str(w.get("id", "")), "title": str(w.get("title", "")),
             "description": str(w.get("description", ""))[:2000], "state": str(w.get("state", "")),
             "due_date": str(w.get("dueDate", "")), "url": str(w.get("alternateLink", ""))}
            for w in result.get("courseWork", []) or []]


def classroom_announcements(course_id: str, limit: int = 20) -> list[dict[str, str]]:
    course_id = _validate_resource_id(course_id, "Google Classroom course ID")
    limit = max(1, min(int(limit), 100))
    result = _service("classroom", "v1", "classroom_announcements").courses().announcements().list(
        courseId=course_id, pageSize=limit, orderBy="updateTime desc",
    ).execute()
    return [{"id": str(a.get("id", "")), "text": str(a.get("text", ""))[:3000],
             "state": str(a.get("state", "")), "update_time": str(a.get("updateTime", ""))}
            for a in result.get("announcements", []) or []]


def meet_create_space(*, confirmed: bool = False) -> dict[str, str]:
    _require_confirmed(confirmed, "Creating a Google Meet space")
    created = _service("meet", "v2", "meet_create").spaces().create(body={}).execute()
    return {"name": str(created.get("name", "")), "meeting_uri": str(created.get("meetingUri", "")),
            "meeting_code": str(created.get("meetingCode", ""))}


def youtube_search_videos(query: str, limit: int = 5) -> list[dict[str, str]]:
    query = " ".join(str(query).split()).strip()
    if not query:
        raise ValueError("Provide a YouTube search query.")
    if len(query) > 200:
        raise ValueError("YouTube query must be 200 characters or fewer.")
    limit = max(1, min(int(limit), 25))
    result = _service("youtube", "v3", "youtube_read").search().list(
        part="snippet", q=query, type="video", maxResults=limit, safeSearch="moderate",
    ).execute()
    return [{"video_id": str(item.get("id", {}).get("videoId", "")),
             "title": str(item.get("snippet", {}).get("title", "")),
             "channel": str(item.get("snippet", {}).get("channelTitle", "")),
             "published_at": str(item.get("snippet", {}).get("publishedAt", "")),
             "url": "https://www.youtube.com/watch?v=" + str(item.get("id", {}).get("videoId", ""))}
            for item in result.get("items", []) or []]


def forms_read(form_id: str) -> dict[str, Any]:
    form_id = _validate_resource_id(form_id, "Google Forms form ID")
    form = _service("forms", "v1", "forms_read").forms().get(formId=form_id).execute()
    items = []
    for item in form.get("items", []) or []:
        question = item.get("questionItem", {}).get("question", {})
        items.append({"title": str(item.get("title", "")), "question_id": str(question.get("questionId", "")),
                      "required": bool(question.get("required", False)),
                      "question_type": next((key for key in question if key not in {"questionId", "required"}), "")})
    return {"form_id": form_id, "title": str(form.get("info", {}).get("title", "")), "items": items[:200],
            "url": str(form.get("responderUri", ""))}


def forms_create(title: str, *, confirmed: bool = False) -> dict[str, str]:
    _require_confirmed(confirmed, "Creating a Google Form")
    title = " ".join(str(title).split()).strip()
    if not title or len(title) > 250:
        raise ValueError("Form title is required and must be 250 characters or fewer.")
    created = _service("forms", "v1", "forms_write").forms().create(body={"info": {"title": title}}).execute()
    form_id = str(created.get("formId", ""))
    return {"form_id": form_id, "title": title, "url": str(created.get("responderUri", "")),
            "edit_url": f"https://docs.google.com/forms/d/{form_id}/edit"}


def execute_google_workspace_operation(operation: str, args: dict[str, Any], *, confirmed: bool = False) -> dict[str, Any]:
    """Dispatcher for the explicitly allowlisted Workspace features used by voice/API clients."""
    op = str(operation).strip().casefold()
    limit = int(args.get("limit", 10) or 10)
    if op == "drive_search":
        return {"kind": op, "files": drive_search(str(args.get("query", "")), limit)}
    if op == "docs_read":
        return {"kind": op, "document": docs_read(str(args.get("identifier", "")))}
    if op == "docs_create":
        return {"kind": op, "document": docs_create(str(args.get("title", "")), str(args.get("content", "")), confirmed=confirmed)}
    if op == "sheets_read":
        return {"kind": op, "sheet": sheets_read(str(args.get("identifier", "")), str(args.get("range_name", "A1:Z100")))}
    if op == "sheets_update":
        return {"kind": op, "sheet": sheets_update(str(args.get("identifier", "")), str(args.get("range_name", "")), str(args.get("values_json", "")), confirmed=confirmed)}
    if op == "slides_read":
        return {"kind": op, "presentation": slides_read(str(args.get("identifier", "")))}
    if op == "slides_create":
        return {"kind": op, "presentation": slides_create(str(args.get("title", "")), confirmed=confirmed)}
    if op == "tasks_list":
        return {"kind": op, "tasks": tasks_list(limit)}
    if op == "tasks_create":
        return {"kind": op, "task": tasks_create(str(args.get("title", "")), str(args.get("content", "")), str(args.get("due", "")), confirmed=confirmed)}
    if op == "profile":
        return {"kind": op, "profile": google_profile()}
    if op == "contacts_search":
        return {"kind": op, "contacts": people_search_contacts(str(args.get("query", "")), limit)}
    if op == "classroom_courses":
        return {"kind": op, "courses": classroom_courses(limit)}
    if op == "classroom_coursework":
        return {"kind": op, "coursework": classroom_coursework(str(args.get("course_id", args.get("identifier", ""))), limit)}
    if op == "classroom_announcements":
        return {"kind": op, "announcements": classroom_announcements(str(args.get("course_id", args.get("identifier", ""))), limit)}
    if op == "meet_create":
        return {"kind": op, "meeting": meet_create_space(confirmed=confirmed)}
    if op == "youtube_search":
        return {"kind": op, "videos": youtube_search_videos(str(args.get("query", "")), min(limit, 25))}
    if op == "forms_read":
        return {"kind": op, "form": forms_read(str(args.get("identifier", "")))}
    if op == "forms_create":
        return {"kind": op, "form": forms_create(str(args.get("title", "")), confirmed=confirmed)}
    # Extended profiles only load when the user invokes a mapped API operation.
    from visionguide.integrations.google_workspace_extended import (
        EXTENDED_OPERATIONS,
        execute_google_workspace_extended_operation,
    )
    if op in EXTENDED_OPERATIONS:
        return execute_google_workspace_extended_operation(op, args, confirmed=confirmed)
    raise ValueError(f"Unsupported Google Workspace operation: {operation!r}.")


try:
    from visionguide.integrations.google_workspace_extended import EXTENDED_WRITE_OPERATIONS
except Exception:  # Keep core Gmail/Calendar tools importable if an optional extended import fails.
    EXTENDED_WRITE_OPERATIONS = frozenset()

GOOGLE_WORKSPACE_WRITE_OPERATIONS = frozenset({
    "docs_create", "sheets_update", "slides_create", "tasks_create", "meet_create", "forms_create",
}) | EXTENDED_WRITE_OPERATIONS

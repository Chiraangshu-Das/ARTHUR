"""Extended, explicit Google Workspace operation adapters.

This module exposes a finite allowlist of service operations. It does not provide
an arbitrary URL/HTTP or shell escape hatch. Each OAuth scope family gets its own
local token file through google_workspace._credentials(), and every state-changing
operation is confirmation-gated by the caller and rechecked here.
"""
from __future__ import annotations

import base64
import json
import os
import re
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from visionguide.integrations import google_workspace as gw

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Operations that change, delete, send, or publish account data. The GUI/API layer
# must show the user the action details and obtain an explicit confirmation.
EXTENDED_WRITE_OPERATIONS = frozenset({
    "calendar_create", "calendar_update", "calendar_delete", "calendar_subscribe", "calendar_unsubscribe",
    "calendar_owned_event_create", "calendar_owned_event_update", "calendar_owned_event_delete", "calendar_app_created_calendar_create",
    "calendar_app_created_event_create", "calendar_app_created_event_update", "calendar_app_created_event_delete",
    "calendar_event_create", "calendar_event_update", "calendar_event_delete", "calendar_acl_create",
    "calendar_acl_update", "calendar_acl_delete", "gmail_send", "gmail_message_modify", "gmail_message_delete",
    "gmail_message_insert", "gmail_draft_create", "gmail_draft_update", "gmail_draft_delete", "gmail_draft_send",
    "gmail_label_create", "gmail_label_update", "gmail_label_delete", "gmail_filter_create", "gmail_filter_delete",
    "gmail_forwarding_create", "gmail_forwarding_delete", "gmail_autoforward_update", "gmail_sendas_create",
    "gmail_sendas_update", "gmail_sendas_delete", "gmail_delegate_create", "gmail_delegate_delete",
    "gmail_notifications_watch", "gmail_notifications_stop", "gmail_setting_update", "gmail_send_to_self", "gmail_compose_send", "gmail_compose_draft_create", "drive_file_create", "drive_file_update", "drive_file_delete", "drive_file_copy",
    "drive_permission_create", "drive_permission_update", "drive_permission_delete", "drive_script_create",
    "drive_script_update", "drive_appdata_create", "drive_appdata_delete", "drive_item_update", "drive_item_delete", "drive_metadata_update", "docs_replace_text", "docs_insert_text", "docs_batch_update", "sheets_create",
    "sheets_append", "sheets_clear", "sheets_batch_update", "slides_batch_update", "tasks_update",
    "tasks_delete", "tasks_complete", "tasks_reopen", "people_contact_create", "people_contact_update",
    "people_contact_delete", "classroom_course_create", "classroom_course_update", "classroom_course_delete",
    "classroom_student_add", "classroom_student_remove", "classroom_teacher_add", "classroom_teacher_remove",
    "classroom_coursework_create", "classroom_coursework_update", "classroom_coursework_delete",
    "classroom_submission_update", "classroom_submission_turn_in", "classroom_submission_reclaim",
    "classroom_submission_return", "classroom_material_create", "classroom_material_update", "classroom_material_delete",
    "classroom_announcement_create", "classroom_announcement_update", "classroom_announcement_delete",
    "classroom_topic_create", "classroom_topic_update", "classroom_topic_delete", "classroom_guardian_create",
    "classroom_guardian_delete", "classroom_registration_create", "classroom_registration_delete",
    "meet_space_update", "meet_end_conference", "youtube_upload", "youtube_video_update", "youtube_video_delete",
    "youtube_playlist_create", "youtube_playlist_update", "youtube_playlist_delete", "youtube_playlist_item_add",
    "youtube_playlist_item_delete", "youtube_comment_insert", "forms_update", "forms_response_watch_create",
    "forms_response_watch_delete", "generative_tuning_delete", "generative_retriever_create", "generative_retriever_delete",
})


def _id(value: Any, label: str = "resource ID") -> str:
    return gw._validate_resource_id(str(value or "").strip(), label)


def _text(value: Any, label: str, maximum: int = 10000, required: bool = False) -> str:
    result = str(value if value is not None else "").strip()
    if required and not result:
        raise ValueError(f"{label} is required.")
    if len(result) > maximum:
        raise ValueError(f"{label} must be {maximum:,} characters or fewer.")
    return result


def _json_object(value: Any, label: str = "payload_json") -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        result = value
    else:
        try:
            result = json.loads(str(value))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{label} must contain valid JSON object data.") from exc
    if not isinstance(result, dict):
        raise ValueError(f"{label} must decode to a JSON object.")
    if len(json.dumps(result, ensure_ascii=False)) > 100_000:
        raise ValueError(f"{label} must be 100,000 characters or fewer.")
    return result


def _require_confirmed(confirmed: bool, action: str) -> None:
    gw._require_confirmed(confirmed, action)


def _svc(api: str, version: str, profile: str):
    return gw._service(api, version, profile)


def _list_result(result: dict[str, Any], key: str, limit: int) -> list[dict[str, Any]]:
    value = result.get(key, []) or []
    return [x for x in value[:max(1, min(int(limit), 100))] if isinstance(x, dict)]


# ------------------------------- Calendar ----------------------------------
def _calendar(operation: str, a: dict[str, Any], confirmed: bool) -> dict[str, Any]:
    limit = max(1, min(int(a.get("limit", 20) or 20), 250))
    if operation == "calendar_list":
        s = _svc("calendar", "v3", "calendar_list_read")
        return {"calendars": _list_result(s.calendarList().list(maxResults=limit, showHidden=True).execute(), "items", limit)}
    if operation in {"calendar_create", "calendar_app_created_calendar_create"}:
        _require_confirmed(confirmed, "Creating a secondary Google Calendar")
        body = _json_object(a.get("payload_json")) or {"summary": _text(a.get("title"), "Calendar title", 250, True)}
        calendar_profile = "calendar_app_created" if operation == "calendar_app_created_calendar_create" else "calendar_calendar_write"
        result = _svc("calendar", "v3", calendar_profile).calendars().insert(body=body).execute()
        return {"calendar": result}
    if operation == "calendar_get":
        cid = _id(a.get("identifier"), "calendar ID")
        result = _svc("calendar", "v3", "calendar_calendar_read").calendars().get(calendarId=cid).execute()
        return {"calendar": result}
    if operation == "calendar_update":
        _require_confirmed(confirmed, "Updating a Google Calendar")
        cid = _id(a.get("identifier"), "calendar ID")
        body = _json_object(a.get("payload_json"))
        if not body:
            body = {k: a[k] for k in ("title", "description", "location", "timeZone") if a.get(k) is not None}
            if "title" in body:
                body["summary"] = body.pop("title")
        if not body:
            raise ValueError("Provide payload_json with calendar fields to update.")
        return {"calendar": _svc("calendar", "v3", "calendar_calendar_write").calendars().patch(calendarId=cid, body=body).execute()}
    if operation == "calendar_delete":
        _require_confirmed(confirmed, "Deleting a Google Calendar")
        cid = _id(a.get("identifier"), "calendar ID")
        _svc("calendar", "v3", "calendar_full").calendars().delete(calendarId=cid).execute()
        return {"deleted_calendar_id": cid}
    if operation == "calendar_subscribe":
        _require_confirmed(confirmed, "Adding a calendar to the subscribed calendar list")
        cid = _id(a.get("identifier"), "calendar ID")
        body = _json_object(a.get("payload_json")) or {"id": cid}
        return {"calendar_list_entry": _svc("calendar", "v3", "calendar_list_write").calendarList().insert(body=body).execute()}
    if operation == "calendar_unsubscribe":
        _require_confirmed(confirmed, "Removing a calendar from the subscribed calendar list")
        cid = _id(a.get("identifier"), "calendar ID")
        _svc("calendar", "v3", "calendar_list_write").calendarList().delete(calendarId=cid).execute()
        return {"unsubscribed_calendar_id": cid}
    if operation in {"calendar_events_list", "calendar_readonly_events", "calendar_public_events", "calendar_owned_events_list", "calendar_app_created_events_list"}:
        cid = _text(a.get("calendar_id") or a.get("identifier") or "primary", "calendar ID", 250, True)
        kwargs: dict[str, Any] = {"calendarId": cid, "maxResults": limit, "singleEvents": True, "orderBy": "startTime"}
        if a.get("time_min"):
            kwargs["timeMin"] = _text(a.get("time_min"), "time_min", 50, True)
        if a.get("time_max"):
            kwargs["timeMax"] = _text(a.get("time_max"), "time_max", 50, True)
        if a.get("query"):
            kwargs["q"] = _text(a.get("query"), "query", 250)
        profile = {
            "calendar_readonly_events": "calendar_readonly",
            "calendar_public_events": "calendar_events_public",
            "calendar_owned_events_list": "calendar_events_owned_read",
            "calendar_app_created_events_list": "calendar_app_created",
        }.get(operation, "calendar_events_read")
        return {"events": _list_result(_svc("calendar", "v3", profile).events().list(**kwargs).execute(), "items", limit)}
    if operation in {"calendar_event_get", "calendar_owned_event_get", "calendar_app_created_event_get"}:
        cid = _text(a.get("calendar_id") or "primary", "calendar ID", 250, True)
        eid = _id(a.get("identifier"), "event ID")
        read_profile = {
            "calendar_owned_event_get": "calendar_events_owned_read",
            "calendar_app_created_event_get": "calendar_app_created",
        }.get(operation, "calendar_events_read")
        return {"event": _svc("calendar", "v3", read_profile).events().get(calendarId=cid, eventId=eid).execute()}
    if operation in {"calendar_event_create", "calendar_owned_event_create", "calendar_app_created_event_create"}:
        _require_confirmed(confirmed, "Creating a Google Calendar event")
        cid = _text(a.get("calendar_id") or "primary", "calendar ID", 250, True)
        body = _json_object(a.get("payload_json"))
        if not body:
            title = _text(a.get("title"), "Event title", 250, True)
            start = _text(a.get("start_time"), "start_time", 80, True)
            end = _text(a.get("end_time"), "end_time", 80, True)
            timezone = _text(a.get("timezone") or os.getenv("VISIONGUIDE_TIMEZONE", "Asia/Kolkata"), "timezone", 80, True)
            body = {"summary": title, "start": {"dateTime": start, "timeZone": timezone}, "end": {"dateTime": end, "timeZone": timezone}}
        if not isinstance(body.get("start"), dict) or not isinstance(body.get("end"), dict):
            raise ValueError("Event payload must contain start and end objects.")
        write_profile = {
            "calendar_owned_event_create": "calendar_events_owned_write",
            "calendar_app_created_event_create": "calendar_app_created",
        }.get(operation, "calendar_events_write")
        return {"event": _svc("calendar", "v3", write_profile).events().insert(calendarId=cid, body=body).execute()}
    if operation in {"calendar_event_update", "calendar_owned_event_update", "calendar_app_created_event_update"}:
        _require_confirmed(confirmed, "Updating a Google Calendar event")
        cid = _text(a.get("calendar_id") or "primary", "calendar ID", 250, True)
        eid = _id(a.get("identifier"), "event ID")
        body = _json_object(a.get("payload_json"))
        if not body:
            raise ValueError("Provide payload_json with event fields to update.")
        write_profile = {
            "calendar_owned_event_update": "calendar_events_owned_write",
            "calendar_app_created_event_update": "calendar_app_created",
        }.get(operation, "calendar_events_write")
        return {"event": _svc("calendar", "v3", write_profile).events().patch(calendarId=cid, eventId=eid, body=body).execute()}
    if operation in {"calendar_event_delete", "calendar_owned_event_delete", "calendar_app_created_event_delete"}:
        _require_confirmed(confirmed, "Deleting a Google Calendar event")
        cid = _text(a.get("calendar_id") or "primary", "calendar ID", 250, True)
        eid = _id(a.get("identifier"), "event ID")
        delete_profile = {
            "calendar_owned_event_delete": "calendar_events_owned_write",
            "calendar_app_created_event_delete": "calendar_app_created",
        }.get(operation, "calendar_events_write")
        _svc("calendar", "v3", delete_profile).events().delete(calendarId=cid, eventId=eid).execute()
        return {"deleted_event_id": eid}
    if operation in {"calendar_freebusy", "calendar_events_freebusy"}:
        start = _text(a.get("start_time") or a.get("time_min"), "start_time", 80, True)
        end = _text(a.get("end_time") or a.get("time_max"), "end_time", 80, True)
        raw_ids = a.get("calendar_ids") or a.get("identifier") or "primary"
        ids = [x.strip() for x in (raw_ids if isinstance(raw_ids, list) else str(raw_ids).split(",")) if str(x).strip()]
        if not ids or len(ids) > 50:
            raise ValueError("Provide between 1 and 50 calendar IDs.")
        body = {"timeMin": start, "timeMax": end, "items": [{"id": x} for x in ids]}
        freebusy_profile = "calendar_events_freebusy" if operation == "calendar_events_freebusy" else "calendar_freebusy"
        result = _svc("calendar", "v3", freebusy_profile).freebusy().query(body=body).execute()
        return {"calendars": result.get("calendars", {}), "time_min": start, "time_max": end}
    if operation == "calendar_settings_list":
        return {"settings": _list_result(_svc("calendar", "v3", "calendar_settings_read").settings().list(maxResults=limit).execute(), "items", limit)}
    if operation == "calendar_setting_get":
        name = _text(a.get("identifier"), "setting name", 100, True)
        return {"setting": _svc("calendar", "v3", "calendar_settings_read").settings().get(setting=name).execute()}
    if operation in {"calendar_acl_list", "calendar_acl_create", "calendar_acl_update", "calendar_acl_delete"}:
        cid = _text(a.get("calendar_id") or "primary", "calendar ID", 250, True)
        svc = _svc("calendar", "v3", "calendar_acl_read" if operation == "calendar_acl_list" else "calendar_acl_write")
        if operation == "calendar_acl_list":
            return {"rules": _list_result(svc.acl().list(calendarId=cid, maxResults=limit).execute(), "items", limit)}
        _require_confirmed(confirmed, f"{operation.replace('_', ' ')}")
        body = _json_object(a.get("payload_json"))
        if operation == "calendar_acl_create":
            if not body:
                raise ValueError("ACL creation requires payload_json containing scope and role.")
            return {"rule": svc.acl().insert(calendarId=cid, body=body).execute()}
        rule_id = _id(a.get("rule_id") or a.get("identifier"), "ACL rule ID")
        if operation == "calendar_acl_update":
            if not body:
                raise ValueError("ACL update requires payload_json.")
            return {"rule": svc.acl().patch(calendarId=cid, ruleId=rule_id, body=body).execute()}
        svc.acl().delete(calendarId=cid, ruleId=rule_id).execute()
        return {"deleted_acl_rule_id": rule_id}
    raise ValueError(f"Unsupported Calendar operation: {operation}")


# ---------------------------------- Gmail ----------------------------------
def _gmail(operation: str, a: dict[str, Any], confirmed: bool) -> dict[str, Any]:
    limit = max(1, min(int(a.get("limit", 20) or 20), 100))
    if operation in {"gmail_messages_list", "gmail_metadata_list"}:
        query = _text(a.get("query", ""), "Gmail search query", 500)
        profile = "gmail_metadata" if operation == "gmail_metadata_list" else "gmail_messages_read"
        listed = _svc("gmail", "v1", profile).users().messages().list(userId="me", q=query or "in:anywhere", maxResults=limit).execute()
        return {"messages": _list_result(listed, "messages", limit), "result_size_estimate": listed.get("resultSizeEstimate", 0)}
    if operation == "gmail_message_read":
        mid = _id(a.get("identifier"), "Gmail message ID")
        fmt = str(a.get("format") or "full").lower()
        if fmt not in {"full", "metadata", "minimal"}:
            raise ValueError("Gmail message format must be full, metadata, or minimal.")
        result = _svc("gmail", "v1", "gmail_messages_read").users().messages().get(userId="me", id=mid, format=fmt, metadataHeaders=["From", "To", "Subject", "Date"]).execute()
        return {"message": result}
    if operation == "gmail_message_modify":
        _require_confirmed(confirmed, "Changing Gmail message labels/read state")
        mid = _id(a.get("identifier"), "Gmail message ID")
        add = a.get("add_label_ids") or []
        remove = a.get("remove_label_ids") or []
        if not isinstance(add, list) or not isinstance(remove, list):
            raise ValueError("add_label_ids and remove_label_ids must be JSON arrays.")
        body = {"addLabelIds": [str(v) for v in add][:100], "removeLabelIds": [str(v) for v in remove][:100]}
        return {"message": _svc("gmail", "v1", "gmail_messages_modify").users().messages().modify(userId="me", id=mid, body=body).execute()}
    if operation == "gmail_message_delete":
        _require_confirmed(confirmed, "Permanently deleting a Gmail message")
        mid = _id(a.get("identifier"), "Gmail message ID")
        _svc("gmail", "v1", "gmail_messages_full").users().messages().delete(userId="me", id=mid).execute()
        return {"permanently_deleted_message_id": mid}
    if operation == "gmail_message_insert":
        _require_confirmed(confirmed, "Inserting a raw message into Gmail")
        raw_text = _text(a.get("content"), "raw RFC822 email content", 100_000, True)
        raw = base64.urlsafe_b64encode(raw_text.encode("utf-8")).decode("ascii").rstrip("=")
        result = _svc("gmail", "v1", "gmail_insert").users().messages().insert(userId="me", body={"raw": raw}).execute()
        return {"message": result}
    if operation in {"gmail_send", "gmail_compose_send"}:
        _require_confirmed(confirmed, "Sending an email from Gmail")
        recipient = gw._validate_email(_text(a.get("recipient"), "recipient", 254, True))
        subject = _text(a.get("title") or a.get("subject"), "email subject", 500)
        body_text = _text(a.get("content") or a.get("body"), "email body", 100_000, True)
        message = EmailMessage()
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body_text)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")
        send_profile = "gmail_compose" if operation == "gmail_compose_send" else "gmail_send"
        result = _svc("gmail", "v1", send_profile).users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"message_id": str(result.get("id", "")), "thread_id": str(result.get("threadId", "")), "recipient": recipient, "subject": subject}
    if operation in {"gmail_drafts_list", "gmail_draft_read"}:
        service = _svc("gmail", "v1", "gmail_drafts_read" if operation == "gmail_drafts_list" else "gmail_drafts_read")
        if operation == "gmail_drafts_list":
            listed = service.users().drafts().list(userId="me", maxResults=limit).execute()
            return {"drafts": _list_result(listed, "drafts", limit)}
        did = _id(a.get("identifier"), "Gmail draft ID")
        return {"draft": service.users().drafts().get(userId="me", id=did, format="full").execute()}
    if operation in {"gmail_draft_create", "gmail_draft_update", "gmail_draft_send", "gmail_compose_draft_create"}:
        _require_confirmed(confirmed, operation.replace("_", " "))
        if operation == "gmail_draft_send":
            did = _id(a.get("identifier"), "Gmail draft ID")
            result = _svc("gmail", "v1", "gmail_drafts_write").users().drafts().send(userId="me", body={"id": did}).execute()
            return {"sent_message_id": str(result.get("id", "")), "thread_id": str(result.get("threadId", ""))}
        recipient = gw._validate_email(_text(a.get("recipient"), "recipient", 254, True))
        message = EmailMessage()
        message["To"] = recipient
        message["Subject"] = _text(a.get("title") or a.get("subject"), "email subject", 500)
        message.set_content(_text(a.get("content") or a.get("body"), "email body", 100_000, True))
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")
        create_profile = "gmail_compose" if operation == "gmail_compose_draft_create" else ("gmail_drafts_create_narrow" if operation == "gmail_draft_create" else "gmail_drafts_write")
        service = _svc("gmail", "v1", create_profile)
        payload: dict[str, Any] = {"message": {"raw": raw}}
        if operation in {"gmail_draft_create", "gmail_compose_draft_create"}:
            result = service.users().drafts().create(userId="me", body=payload).execute()
        else:
            did = _id(a.get("identifier"), "Gmail draft ID")
            payload["id"] = did
            result = service.users().drafts().update(userId="me", id=did, body=payload).execute()
        return {"draft_id": str(result.get("id", "")), "message_id": str((result.get("message") or {}).get("id", "")), "recipient": recipient, "subject": message["Subject"]}
    if operation == "gmail_draft_delete":
        _require_confirmed(confirmed, "Deleting a Gmail draft")
        did = _id(a.get("identifier"), "Gmail draft ID")
        _svc("gmail", "v1", "gmail_drafts_write").users().drafts().delete(userId="me", id=did).execute()
        return {"deleted_draft_id": did}
    if operation in {"gmail_labels_list", "gmail_label_create", "gmail_label_update", "gmail_label_delete"}:
        read = operation == "gmail_labels_list"
        profile = "gmail_labels_read" if read else ("gmail_labels_create_narrow" if operation == "gmail_label_create" else "gmail_labels_write")
        service = _svc("gmail", "v1", profile)
        if read:
            listed = service.users().labels().list(userId="me").execute()
            return {"labels": _list_result(listed, "labels", limit)}
        _require_confirmed(confirmed, operation.replace("_", " "))
        if operation == "gmail_label_create":
            body = _json_object(a.get("payload_json")) or {"name": _text(a.get("title"), "label name", 225, True), "labelListVisibility": "labelShow", "messageListVisibility": "show"}
            return {"label": service.users().labels().create(userId="me", body=body).execute()}
        lid = _id(a.get("identifier"), "Gmail label ID")
        if operation == "gmail_label_update":
            body = _json_object(a.get("payload_json"))
            if not body:
                raise ValueError("Provide payload_json to update a Gmail label.")
            return {"label": service.users().labels().patch(userId="me", id=lid, body=body).execute()}
        service.users().labels().delete(userId="me", id=lid).execute()
        return {"deleted_label_id": lid}
    if operation in {"gmail_filters_list", "gmail_filter_create", "gmail_filter_delete"}:
        service = _svc("gmail", "v1", "gmail_filters_read" if operation == "gmail_filters_list" else "gmail_filters_write")
        if operation == "gmail_filters_list":
            return {"filters": _list_result(service.users().settings().filters().list(userId="me").execute(), "filter", limit)}
        _require_confirmed(confirmed, operation.replace("_", " "))
        if operation == "gmail_filter_create":
            body = _json_object(a.get("payload_json"))
            if not body.get("criteria") or not body.get("action"):
                raise ValueError("payload_json must contain Gmail filter criteria and action objects.")
            return {"filter": service.users().settings().filters().create(userId="me", body=body).execute()}
        fid = _id(a.get("identifier"), "Gmail filter ID")
        service.users().settings().filters().delete(userId="me", id=fid).execute()
        return {"deleted_filter_id": fid}
    if operation in {"gmail_settings_list", "gmail_setting_get"}:
        service = _svc("gmail", "v1", "gmail_settings_read")
        if operation == "gmail_settings_list":
            settings = service.users().settings()
            result = {}
            for key, method in (("imap", "getImap"), ("pop", "getPop"), ("vacation", "getVacation"), ("language", "getLanguage")):
                try:
                    result[key] = getattr(settings, method)(userId="me").execute()
                except Exception as exc:
                    result[key] = {"unavailable": str(exc)[:400]}
            return {"settings": result}
        setting = _text(a.get("identifier"), "Gmail settings resource", 100, True)
        # Explicit safe allowlist of read-only settings resources.
        readers = {"imap": "getImap", "pop": "getPop", "vacation": "getVacation", "language": "getLanguage", "auto_forwarding": "getAutoForwarding", "send_as": "list"}
        method = readers.get(setting.casefold())
        if method is None:
            raise ValueError("Supported Gmail setting names: imap, pop, vacation, language, auto_forwarding, send_as.")
        settings = service.users().settings()
        if setting.casefold() == "send_as":
            return {"settings": settings.sendAs().list(userId="me").execute()}
        return {"setting": getattr(settings, method)(userId="me").execute()}
    if operation in {"gmail_forwarding_list", "gmail_forwarding_create", "gmail_forwarding_delete"}:
        service = _svc("gmail", "v1", "gmail_forwarding_read" if operation == "gmail_forwarding_list" else "gmail_forwarding_write")
        obj = service.users().settings().forwardingAddresses()
        if operation == "gmail_forwarding_list":
            return {"forwarding_addresses": _list_result(obj.list(userId="me").execute(), "forwardingAddresses", limit)}
        _require_confirmed(confirmed, operation.replace("_", " "))
        address = gw._validate_email(_text(a.get("recipient"), "forwarding email", 254, True))
        if operation == "gmail_forwarding_create":
            return {"forwarding_address": obj.create(userId="me", body={"forwardingEmail": address}).execute()}
        obj.delete(userId="me", forwardingEmail=address).execute()
        return {"deleted_forwarding_email": address}
    if operation in {"gmail_autoforward_get", "gmail_autoforward_update"}:
        service = _svc("gmail", "v1", "gmail_autoforward_read" if operation == "gmail_autoforward_get" else "gmail_autoforward_write")
        obj = service.users().settings().getAutoForwarding(userId="me").execute()
        if operation == "gmail_autoforward_get":
            return {"auto_forwarding": obj}
        _require_confirmed(confirmed, "Changing automatic Gmail forwarding")
        body = _json_object(a.get("payload_json"))
        if not body:
            raise ValueError("Provide payload_json with enabled, emailAddress, and disposition fields.")
        return {"auto_forwarding": service.users().settings().updateAutoForwarding(userId="me", body=body).execute()}
    if operation in {"gmail_sendas_list", "gmail_sendas_create", "gmail_sendas_update", "gmail_sendas_delete"}:
        service = _svc("gmail", "v1", "gmail_sendas_read" if operation == "gmail_sendas_list" else "gmail_sendas_write")
        obj = service.users().settings().sendAs()
        if operation == "gmail_sendas_list":
            return {"send_as": _list_result(obj.list(userId="me").execute(), "sendAs", limit)}
        _require_confirmed(confirmed, operation.replace("_", " "))
        email = gw._validate_email(_text(a.get("recipient"), "send-as email", 254, True))
        if operation == "gmail_sendas_create":
            body = _json_object(a.get("payload_json")) or {"sendAsEmail": email, "displayName": _text(a.get("title") or email, "display name", 225)}
            return {"send_as": obj.create(userId="me", body=body).execute()}
        if operation == "gmail_sendas_update":
            body = _json_object(a.get("payload_json"))
            if not body:
                raise ValueError("Provide payload_json with send-as fields to update.")
            return {"send_as": obj.update(userId="me", sendAsEmail=email, body=body).execute()}
        obj.delete(userId="me", sendAsEmail=email).execute()
        return {"deleted_send_as_email": email}
    if operation in {"gmail_delegates_list", "gmail_delegate_create", "gmail_delegate_delete"}:
        service = _svc("gmail", "v1", "gmail_delegates_read" if operation == "gmail_delegates_list" else "gmail_delegates_write")
        obj = service.users().settings().delegates()
        if operation == "gmail_delegates_list":
            return {"delegates": _list_result(obj.list(userId="me").execute(), "delegates", limit)}
        _require_confirmed(confirmed, "Changing Gmail delegation")
        email = gw._validate_email(_text(a.get("recipient"), "delegate email", 254, True))
        if operation == "gmail_delegate_create":
            return {"delegate": obj.create(userId="me", body={"delegateEmail": email}).execute()}
        obj.delete(userId="me", delegateEmail=email).execute()
        return {"deleted_delegate_email": email}
    if operation in {"gmail_notifications_watch", "gmail_notifications_stop"}:
        _require_confirmed(confirmed, "Starting or stopping Gmail push notifications")
        if operation == "gmail_notifications_stop":
            result = _svc("gmail", "v1", "gmail_notifications").users().stop(userId="me").execute()
            return {"status": "stopped", **(result if isinstance(result, dict) else {})}
        topic = _text(a.get("topic_name"), "Pub/Sub topic_name", 500, True)
        if not topic.startswith("projects/") or "/topics/" not in topic:
            raise ValueError("topic_name must use projects/{project}/topics/{topic}.")
        result = _svc("gmail", "v1", "gmail_notifications").users().watch(userId="me", body={"topicName": topic, "labelIds": ["INBOX"]}).execute()
        return {"watch": result}
    if operation == "gmail_setting_update":
        _require_confirmed(confirmed, "Updating Gmail account settings")
        setting = _text(a.get("setting_name") or a.get("identifier"), "Gmail settings resource", 100, True).casefold()
        body = _json_object(a.get("payload_json"))
        updaters = {"imap": "updateImap", "pop": "updatePop", "vacation": "updateVacation", "language": "updateLanguage"}
        if setting not in updaters or not body:
            raise ValueError("Supported writable Gmail setting_name values: imap, pop, vacation, language; payload_json is required.")
        result = getattr(_svc("gmail", "v1", "gmail_settings_write").users().settings(), updaters[setting])(userId="me", body=body).execute()
        return {"setting": result}
    if operation == "gmail_user_metadata":
        result = _svc("gmail", "v1", "gmail_user_read").users().getProfile(userId="me").execute()
        return {"profile": result}
    if operation == "gmail_send_to_self":
        _require_confirmed(confirmed, "Sending email to the signed-in Gmail account")
        me = _svc("gmail", "v1", "gmail_user_read").users().getProfile(userId="me").execute()
        address = gw._validate_email(str(me.get("emailAddress", "")))
        message = EmailMessage()
        message["To"] = address
        message["Subject"] = _text(a.get("title") or a.get("subject"), "email subject", 500)
        message.set_content(_text(a.get("content") or a.get("body"), "email body", 100_000, True))
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")
        result = _svc("gmail", "v1", "gmail_send_self").users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"message_id": str(result.get("id", "")), "recipient": address}
    raise ValueError(f"Unsupported Gmail operation: {operation}")


# ----------------------------------- Drive ---------------------------------
def _drive(operation: str, a: dict[str, Any], confirmed: bool) -> dict[str, Any]:
    limit = max(1, min(int(a.get("limit", 20) or 20), 100))
    if operation in {"drive_files_list", "drive_meet_files_list", "drive_appdata_list", "drive_apps_list"}:
        if operation == "drive_apps_list":
            result = _svc("drive", "v3", "drive_apps_read").apps().list().execute()
            return {"apps": _list_result(result, "items", limit)}
        profile = "drive_meet_read" if operation == "drive_meet_files_list" else ("drive_appdata" if operation == "drive_appdata_list" else "drive_readonly")
        kwargs: dict[str, Any] = {"pageSize": limit, "orderBy": "modifiedTime desc", "fields": "files(id,name,mimeType,modifiedTime,webViewLink,owners(displayName,emailAddress),size,trashed)", "spaces": "appDataFolder" if operation == "drive_appdata_list" else "drive"}
        query = _text(a.get("query"), "Drive query", 500)
        if operation == "drive_appdata_list":
            kwargs["q"] = "trashed = false"
        elif query:
            escaped = query.replace("\\", "\\\\").replace("'", "\\'")
            kwargs["q"] = f"trashed = false and name contains '{escaped}'"
        result = _svc("drive", "v3", profile).files().list(**kwargs).execute()
        return {"files": _list_result(result, "files", limit)}
    if operation == "drive_file_get":
        fid = _id(a.get("identifier"), "Drive file ID")
        return {"file": _svc("drive", "v3", "drive_readonly").files().get(fileId=fid, fields="id,name,mimeType,description,modifiedTime,createdTime,webViewLink,owners,parents,permissions,size,trashed,appProperties,properties").execute()}
    if operation in {"drive_file_create", "drive_file_update", "drive_file_copy", "drive_file_delete"}:
        _require_confirmed(confirmed, operation.replace("_", " "))
        service = _svc("drive", "v3", "drive_full")
        if operation == "drive_file_create":
            body = _json_object(a.get("payload_json"))
            if not body:
                body = {"name": _text(a.get("title"), "file name", 250, True), "mimeType": "text/plain"}
            content = _text(a.get("content"), "file content", 1_000_000)
            if content:
                import io
                from googleapiclient.http import MediaIoBaseUpload
                media = MediaIoBaseUpload(io.BytesIO(content.encode("utf-8")), mimetype=str(body.get("mimeType", "text/plain")), resumable=False)
                result = _svc("drive", "v3", "drive_file_scope").files().create(body=body, media_body=media, fields="id,name,mimeType,webViewLink").execute()
            else:
                result = _svc("drive", "v3", "drive_file_scope").files().create(body=body, fields="id,name,mimeType,webViewLink").execute()
            return {"file": result}
        fid = _id(a.get("identifier"), "Drive file ID")
        if operation == "drive_file_update":
            body = _json_object(a.get("payload_json"))
            if not body:
                raise ValueError("Provide payload_json with Drive file metadata to update.")
            return {"file": service.files().update(fileId=fid, body=body, fields="id,name,mimeType,modifiedTime,webViewLink,trashed").execute()}
        if operation == "drive_file_copy":
            body = _json_object(a.get("payload_json")) or {"name": _text(a.get("title"), "copy name", 250, True)}
            return {"file": service.files().copy(fileId=fid, body=body, fields="id,name,mimeType,webViewLink").execute()}
        service.files().delete(fileId=fid).execute()
        return {"deleted_file_id": fid}
    if operation in {"drive_permission_list", "drive_permission_create", "drive_permission_update", "drive_permission_delete"}:
        fid = _id(a.get("identifier"), "Drive file ID")
        service = _svc("drive", "v3", "drive_readonly" if operation == "drive_permission_list" else "drive_full")
        obj = service.permissions()
        if operation == "drive_permission_list":
            return {"permissions": _list_result(obj.list(fileId=fid, fields="permissions(id,type,role,emailAddress,domain,allowFileDiscovery)").execute(), "permissions", limit)}
        _require_confirmed(confirmed, operation.replace("_", " "))
        if operation == "drive_permission_create":
            body = _json_object(a.get("payload_json"))
            if not body.get("type") or not body.get("role"):
                raise ValueError("Permission creation requires payload_json with type and role.")
            return {"permission": obj.create(fileId=fid, body=body, sendNotificationEmail=bool(a.get("send_notification", False)), fields="id,type,role,emailAddress,domain").execute()}
        pid = _id(a.get("permission_id"), "Drive permission ID")
        if operation == "drive_permission_update":
            body = _json_object(a.get("payload_json"))
            if not body:
                raise ValueError("Permission update requires payload_json.")
            return {"permission": obj.update(fileId=fid, permissionId=pid, body=body, fields="id,type,role,emailAddress,domain").execute()}
        obj.delete(fileId=fid, permissionId=pid).execute()
        return {"deleted_permission_id": pid, "file_id": fid}
    if operation == "drive_activity_list":
        fid = _id(a.get("identifier"), "Drive file ID")
        body = {"itemName": f"items/{fid}", "pageSize": limit, "filter": _text(a.get("query"), "Drive Activity filter", 500)}
        body = {k: v for k, v in body.items() if v}
        result = _svc("driveactivity", "v2", "drive_activity_read").activity().query(body=body).execute()
        return {"activities": _list_result(result, "activities", limit)}
    if operation in {"drive_script_get", "drive_script_create", "drive_script_update"}:
        service = _svc("script", "v1", "drive_scripts")
        if operation == "drive_script_create":
            _require_confirmed(confirmed, "Creating a Google Apps Script project")
            title = _text(a.get("title"), "Apps Script project title", 250, True)
            return {"script": service.projects().create(body={"title": title}).execute()}
        sid = _id(a.get("identifier"), "Apps Script project ID")
        if operation == "drive_script_get":
            return {"script": service.projects().getContent(scriptId=sid).execute()}
        _require_confirmed(confirmed, "Updating Google Apps Script source code")
        body = _json_object(a.get("payload_json"))
        if not isinstance(body.get("files"), list) or not body["files"]:
            raise ValueError("Apps Script update requires payload_json containing a non-empty files array.")
        return {"script": service.projects().updateContent(scriptId=sid, body=body).execute()}
    if operation in {"drive_appdata_create", "drive_appdata_delete"}:
        _require_confirmed(confirmed, operation.replace("_", " "))
        service = _svc("drive", "v3", "drive_appdata")
        if operation == "drive_appdata_create":
            name = _text(a.get("title"), "application data file name", 250, True)
            content = _text(a.get("content"), "application data content", 1_000_000)
            body = {"name": name, "parents": ["appDataFolder"], "mimeType": "text/plain"}
            if content:
                import io
                from googleapiclient.http import MediaIoBaseUpload
                media = MediaIoBaseUpload(io.BytesIO(content.encode("utf-8")), mimetype="text/plain", resumable=False)
                result = service.files().create(body=body, media_body=media, fields="id,name,mimeType,modifiedTime").execute()
            else:
                result = service.files().create(body=body, fields="id,name,mimeType,modifiedTime").execute()
            return {"file": result}
        fid = _id(a.get("identifier"), "application data file ID")
        service.files().delete(fileId=fid).execute()
        return {"deleted_appdata_file_id": fid}
    if operation in {"drive_item_list", "drive_item_get", "drive_collaboration_item_list", "drive_collaboration_item_get"}:
        is_collaboration_item = operation.startswith("drive_collaboration_")
        service = _svc("drive", "v3", "drive_item_collaboration_read" if is_collaboration_item else "drive_item_read")
        if operation.endswith("_get"):
            fid = _id(a.get("identifier"), "Drive item ID")
            return {"item": service.files().get(fileId=fid, fields="id,name,mimeType,description,modifiedTime,createdTime,webViewLink,parents,trashed").execute()}
        kwargs = {"pageSize": limit, "fields": "files(id,name,mimeType,modifiedTime,webViewLink,parents,trashed)"}
        query = _text(a.get("query"), "Drive item query", 500)
        if query:
            escaped = query.replace("\\", "\\\\").replace("'", "\\'")
            kwargs["q"] = f"trashed = false and name contains '{escaped}'"
        return {"items": _list_result(service.files().list(**kwargs).execute(), "files", limit)}
    if operation in {"drive_item_update", "drive_item_delete"}:
        _require_confirmed(confirmed, operation.replace("_", " "))
        fid = _id(a.get("identifier"), "Drive item ID")
        service = _svc("drive", "v3", "drive_item_write")
        if operation == "drive_item_update":
            body = _json_object(a.get("payload_json"))
            if not body:
                raise ValueError("Provide payload_json for the fields to update on the selected Drive item.")
            return {"item": service.files().update(fileId=fid, body=body, fields="id,name,mimeType,description,modifiedTime,webViewLink,trashed").execute()}
        service.files().delete(fileId=fid).execute()
        return {"deleted_item_id": fid}
    if operation == "drive_metadata_update":
        _require_confirmed(confirmed, "Updating Drive file metadata")
        fid = _id(a.get("identifier"), "Drive file ID")
        body = _json_object(a.get("payload_json"))
        allowed_fields = {"name", "description", "starred", "appProperties", "properties"}
        if not body or set(body) - allowed_fields:
            raise ValueError("Drive metadata update accepts only name, description, starred, appProperties, or properties.")
        return {"file": _svc("drive", "v3", "drive_metadata_write").files().update(fileId=fid, body=body, fields="id,name,description,starred,appProperties,properties,modifiedTime").execute()}
    if operation == "drive_about":
        return {"about": _svc("drive", "v3", "drive_metadata").about().get(fields="user,storageQuota,maxImportSizes,maxUploadSize").execute()}
    if operation == "drive_photo_files_list":
        # Drive API operations can list image/video items in Drive; this intentionally does
        # not claim access to Google Photos Library's separate media-management API.
        kwargs = {"pageSize": limit, "q": "trashed = false and (mimeType contains 'image/' or mimeType contains 'video/')", "spaces": "drive", "fields": "files(id,name,mimeType,modifiedTime,webViewLink)"}
        result = _svc("drive", "v3", "drive_photos_read").files().list(**kwargs).execute()
        return {"files": _list_result(result, "files", limit)}
    raise ValueError(f"Unsupported Drive operation: {operation}")


# ----------------------------- Docs / Sheets / Slides ----------------------
def _documents(operation: str, a: dict[str, Any], confirmed: bool) -> dict[str, Any]:
    if operation == "docs_replace_text":
        _require_confirmed(confirmed, "Replacing text throughout a Google Doc")
        did = _id(a.get("identifier"), "Google Docs document ID")
        find = _text(a.get("query"), "text to find", 5000, True)
        repl = _text(a.get("content"), "replacement text", 20000)
        body = {"requests": [{"replaceAllText": {"containsText": {"text": find, "matchCase": bool(a.get("match_case", False))}, "replaceText": repl}}]}
        result = _svc("docs", "v1", "docs_write").documents().batchUpdate(documentId=did, body=body).execute()
        return {"document_id": did, "replacements": result.get("replies", [])}
    if operation == "docs_insert_text":
        _require_confirmed(confirmed, "Inserting text into a Google Doc")
        did = _id(a.get("identifier"), "Google Docs document ID")
        text = _text(a.get("content"), "text to insert", 50_000, True)
        index = int(a.get("index", 1) or 1)
        if not 1 <= index <= 2_000_000:
            raise ValueError("Document insertion index must be between 1 and 2,000,000.")
        body = {"requests": [{"insertText": {"location": {"index": index}, "text": text}}]}
        return {"document_id": did, "result": _svc("docs", "v1", "docs_write").documents().batchUpdate(documentId=did, body=body).execute()}
    if operation == "docs_batch_update":
        _require_confirmed(confirmed, "Applying a Google Docs batch update")
        did = _id(a.get("identifier"), "Google Docs document ID")
        body = _json_object(a.get("payload_json"))
        requests = body.get("requests")
        allowed = {"insertText", "deleteContentRange", "replaceAllText", "updateTextStyle", "updateParagraphStyle", "createParagraphBullets", "deleteParagraphBullets", "insertInlineImage", "insertTable"}
        if not isinstance(requests, list) or not requests or len(requests) > 100 or any(not isinstance(r, dict) or len(r) != 1 or next(iter(r)) not in allowed for r in requests):
            raise ValueError("Docs requests must be 1–100 objects using the documented allowlisted edit request types.")
        return {"result": _svc("docs", "v1", "docs_write").documents().batchUpdate(documentId=did, body={"requests": requests}).execute()}
    raise ValueError(f"Unsupported Docs operation: {operation}")


def _sheets(operation: str, a: dict[str, Any], confirmed: bool) -> dict[str, Any]:
    if operation == "sheets_create":
        _require_confirmed(confirmed, "Creating a Google spreadsheet")
        body = _json_object(a.get("payload_json")) or {"properties": {"title": _text(a.get("title"), "spreadsheet title", 250, True)}}
        return {"spreadsheet": _svc("sheets", "v4", "sheets_write").spreadsheets().create(body=body).execute()}
    sid = _id(a.get("identifier"), "Spreadsheet ID")
    range_name = _text(a.get("range_name") or "A1:Z100", "range_name", 300, True)
    if operation == "sheets_append":
        _require_confirmed(confirmed, "Appending rows to Google Sheets")
        values = _json_object(a.get("payload_json")).get("values")
        if not isinstance(values, list) or not values:
            raise ValueError("payload_json must contain a non-empty values array.")
        return {"result": _svc("sheets", "v4", "sheets_write").spreadsheets().values().append(spreadsheetId=sid, range=range_name, valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS", body={"values": values}).execute()}
    if operation == "sheets_clear":
        _require_confirmed(confirmed, "Clearing a Google Sheets range")
        return {"result": _svc("sheets", "v4", "sheets_write").spreadsheets().values().clear(spreadsheetId=sid, range=range_name, body={}).execute()}
    if operation == "sheets_batch_update":
        _require_confirmed(confirmed, "Applying a Google Sheets structural update")
        body = _json_object(a.get("payload_json"))
        requests = body.get("requests")
        allowed = {"addSheet", "deleteSheet", "updateSheetProperties", "repeatCell", "updateCells", "appendCells", "addConditionalFormatRule", "deleteConditionalFormatRule", "mergeCells", "unmergeCells", "autoResizeDimensions", "updateDimensionProperties", "insertDimension", "deleteDimension", "copyPaste", "sortRange", "setBasicFilter", "clearBasicFilter", "updateSpreadsheetProperties"}
        if not isinstance(requests, list) or not requests or len(requests) > 100 or any(not isinstance(r, dict) or len(r) != 1 or next(iter(r)) not in allowed for r in requests):
            raise ValueError("Sheets requests must be 1–100 objects using the documented allowlisted request types.")
        return {"result": _svc("sheets", "v4", "sheets_write").spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": requests}).execute()}
    raise ValueError(f"Unsupported Sheets operation: {operation}")


def _slides(operation: str, a: dict[str, Any], confirmed: bool) -> dict[str, Any]:
    _require_confirmed(confirmed, "Applying a Google Slides presentation update")
    pid = _id(a.get("identifier"), "Presentation ID")
    body = _json_object(a.get("payload_json"))
    requests = body.get("requests")
    allowed = {"createSlide", "deleteObject", "createShape", "insertText", "replaceAllText", "updateTextStyle", "updateShapeProperties", "createImage", "createLine", "updatePageProperties", "updateSlidesPosition", "duplicateObject", "updateParagraphStyle"}
    if not isinstance(requests, list) or not requests or len(requests) > 100 or any(not isinstance(r, dict) or len(r) != 1 or next(iter(r)) not in allowed for r in requests):
        raise ValueError("Slides requests must be 1–100 objects using the documented allowlisted request types.")
    return {"result": _svc("slides", "v1", "slides_write").presentations().batchUpdate(presentationId=pid, body={"requests": requests}).execute()}


# ---------------------------------- Tasks ----------------------------------
def _tasks(operation: str, a: dict[str, Any], confirmed: bool) -> dict[str, Any]:
    service = _svc("tasks", "v1", "tasks_read" if operation == "tasks_list" else "tasks_write")
    if operation == "tasks_list":
        result = service.tasks().list(tasklist="@default", maxResults=max(1, min(int(a.get("limit", 20) or 20), 100)), showCompleted=True, showHidden=True).execute()
        return {"tasks": _list_result(result, "items", int(a.get("limit", 20) or 20))}
    if operation == "tasks_create":
        _require_confirmed(confirmed, "Creating a Google Task")
        title = _text(a.get("title"), "task title", 1024, True)
        body: dict[str, Any] = {"title": title}
        if a.get("content"):
            body["notes"] = _text(a.get("content"), "task notes", 8000)
        if a.get("due"):
            body["due"] = _text(a.get("due"), "task due date", 80, True)
        return {"task": service.tasks().insert(tasklist="@default", body=body).execute()}
    tid = _id(a.get("identifier"), "Google Task ID")
    if operation == "tasks_delete":
        _require_confirmed(confirmed, "Deleting a Google Task")
        service.tasks().delete(tasklist="@default", task=tid).execute()
        return {"deleted_task_id": tid}
    if operation == "tasks_complete" or operation == "tasks_reopen":
        _require_confirmed(confirmed, "Changing Google Task status")
        current = service.tasks().get(tasklist="@default", task=tid).execute()
        current["status"] = "completed" if operation == "tasks_complete" else "needsAction"
        return {"task": service.tasks().update(tasklist="@default", task=tid, body=current).execute()}
    if operation == "tasks_update":
        _require_confirmed(confirmed, "Updating a Google Task")
        body = _json_object(a.get("payload_json"))
        if not body:
            for src, dst in (("title", "title"), ("content", "notes"), ("due", "due")):
                if a.get(src) is not None:
                    body[dst] = a[src]
        if not body:
            raise ValueError("Provide payload_json or task fields to update.")
        current = service.tasks().get(tasklist="@default", task=tid).execute()
        current.update(body)
        return {"task": service.tasks().update(tasklist="@default", task=tid, body=current).execute()}
    raise ValueError(f"Unsupported Tasks operation: {operation}")


# ---------------------------------- People ---------------------------------
def _people(operation: str, a: dict[str, Any], confirmed: bool) -> dict[str, Any]:
    limit = max(1, min(int(a.get("limit", 20) or 20), 100))
    if operation == "google_identity":
        result = _oauth_rest("identity_openid", "GET", "https://openidconnect.googleapis.com/v1/userinfo")
        return {"identity": result}
    if operation == "people_other_contacts_list":
        result = _svc("people", "v1", "people_other_contacts").otherContacts().list(readMask="names,emailAddresses,phoneNumbers", pageSize=limit).execute()
        return {"contacts": _list_result(result, "otherContacts", limit)}
    if operation == "people_user_profile":
        # Separate user-data scope profiles keep optional personal attributes opt-in.
        requested = a.get("fields") or ["names", "emailAddresses", "photos"]
        if not isinstance(requested, list):
            raise ValueError("fields must be a JSON array of People API personFields.")
        allowed = {"names", "emailAddresses", "photos", "phoneNumbers", "addresses", "birthdays", "genders", "ageRanges", "organizations"}
        fields = [str(v) for v in requested if str(v) in allowed]
        if not fields:
            raise ValueError("No supported profile fields were selected.")
        field_scope_map = {"emailAddresses": "people_emails", "addresses": "people_addresses", "birthdays": "people_birthday", "genders": "people_gender", "ageRanges": "people_agerange", "organizations": "people_organization", "phoneNumbers": "people_phones"}
        needed_scopes = ["https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]
        for f in fields:
            prof = field_scope_map.get(f)
            if prof:
                needed_scopes.extend(gw._SCOPE_PROFILES[prof])
        profile = "people_profile_ext_" + "_".join(sorted(fields))
        gw._SCOPE_PROFILES[profile] = tuple(dict.fromkeys(needed_scopes))
        result = _svc("people", "v1", profile).people().get(resourceName="people/me", personFields=",".join(fields)).execute()
        return {"profile": result}
    if operation == "people_contacts_search":
        q = _text(a.get("query"), "contact query", 250, True)
        result = _svc("people", "v1", "people_contacts").people().searchContacts(query=q, readMask="names,emailAddresses,phoneNumbers,organizations,addresses", pageSize=limit).execute()
        return {"contacts": _list_result(result, "results", limit)}
    if operation in {"people_contact_create", "people_contact_update", "people_contact_delete"}:
        _require_confirmed(confirmed, operation.replace("_", " "))
        service = _svc("people", "v1", "people_contacts_write").people()
        if operation == "people_contact_create":
            body = _json_object(a.get("payload_json"))
            if not body.get("names") and not body.get("emailAddresses"):
                raise ValueError("Contact creation requires payload_json with names and/or emailAddresses.")
            return {"contact": service.createContact(body=body).execute()}
        resource = _text(a.get("identifier"), "contact resourceName", 250, True)
        if operation == "people_contact_delete":
            if not resource.startswith("people/"):
                raise ValueError("Contact identifier must be a People API resourceName such as people/c123.")
            service.deleteContact(resourceName=resource).execute()
            return {"deleted_resource_name": resource}
        body = _json_object(a.get("payload_json"))
        update_fields = _text(a.get("update_fields") or "names,emailAddresses,phoneNumbers,addresses,organizations", "update_fields", 500, True)
        if not body:
            raise ValueError("Contact update requires payload_json.")
        return {"contact": service.updateContact(resourceName=resource, body=body, updatePersonFields=update_fields).execute()}
    raise ValueError(f"Unsupported People operation: {operation}")


# -------------------------------- Classroom --------------------------------
def _classroom(operation: str, a: dict[str, Any], confirmed: bool) -> dict[str, Any]:
    limit = max(1, min(int(a.get("limit", 20) or 20), 100))
    course_id = _text(a.get("course_id") or a.get("identifier"), "course ID", 250)
    if operation == "classroom_student_profile":
        user_id = _text(a.get("user_id") or a.get("identifier"), "Classroom user ID", 250, True)
        # Keep extra personal fields out of the default response; request them only when selected.
        requested = a.get("fields") or ["id", "name"]
        if not isinstance(requested, list):
            raise ValueError("fields must be a JSON array chosen from id, name, emailAddress, photoUrl.")
        allowed = {"id", "name", "emailAddress", "photoUrl"}
        fields = [str(value) for value in requested if str(value) in allowed]
        if not fields:
            raise ValueError("Select at least one supported Classroom profile field.")
        scopes = ["https://www.googleapis.com/auth/classroom.courses.readonly"]
        if "emailAddress" in fields:
            scopes.append("https://www.googleapis.com/auth/classroom.profile.emails")
        if "photoUrl" in fields:
            scopes.append("https://www.googleapis.com/auth/classroom.profile.photos")
        profile_name = "classroom_profile_" + "_".join(sorted(fields))
        gw._SCOPE_PROFILES[profile_name] = tuple(dict.fromkeys(scopes))
        result = _svc("classroom", "v1", profile_name).userProfiles().get(userId=user_id).execute()
        if "emailAddress" not in fields:
            result.pop("emailAddress", None)
        if "photoUrl" not in fields:
            result.pop("photoUrl", None)
        return {"profile": result}
    if operation == "classroom_courses":
        result = _svc("classroom", "v1", "classroom_courses").courses().list(pageSize=limit, courseStates=["ACTIVE"]).execute()
        return {"courses": _list_result(result, "courses", limit)}
    if operation == "classroom_course_get":
        cid = _id(course_id, "course ID")
        return {"course": _svc("classroom", "v1", "classroom_courses").courses().get(id=cid).execute()}
    if operation in {"classroom_course_create", "classroom_course_update", "classroom_course_delete"}:
        _require_confirmed(confirmed, operation.replace("_", " "))
        if operation == "classroom_course_create":
            body = _json_object(a.get("payload_json"))
            if not body.get("name"):
                body["name"] = _text(a.get("title"), "course name", 250, True)
            return {"course": _svc("classroom", "v1", "classroom_courses_write").courses().create(body=body).execute()}
        cid = _id(course_id, "course ID")
        if operation == "classroom_course_delete":
            _svc("classroom", "v1", "classroom_courses_write").courses().delete(id=cid).execute()
            return {"deleted_course_id": cid}
        body = _json_object(a.get("payload_json"))
        if not body:
            raise ValueError("Course update requires payload_json.")
        return {"course": _svc("classroom", "v1", "classroom_courses_write").courses().patch(id=cid, updateMask=",".join(body.keys()), body=body).execute()}
    if operation in {"classroom_coursework", "classroom_coursework_create", "classroom_coursework_update", "classroom_coursework_delete"}:
        cid = _id(course_id, "course ID")
        svc = _svc("classroom", "v1", "classroom_work" if operation == "classroom_coursework" else "classroom_coursework_write")
        if operation == "classroom_coursework":
            return {"coursework": _list_result(svc.courses().courseWork().list(courseId=cid, pageSize=limit, orderBy="dueDate asc").execute(), "courseWork", limit)}
        _require_confirmed(confirmed, operation.replace("_", " "))
        if operation == "classroom_coursework_create":
            body = _json_object(a.get("payload_json"))
            if not body.get("title"):
                body["title"] = _text(a.get("title"), "coursework title", 250, True)
            # State and materials are API-defined; caller only supplies a JSON object.
            return {"coursework": svc.courses().courseWork().create(courseId=cid, body=body).execute()}
        wid = _id(a.get("item_id") or a.get("resource_id"), "coursework ID")
        if operation == "classroom_coursework_delete":
            svc.courses().courseWork().delete(courseId=cid, id=wid).execute()
            return {"deleted_coursework_id": wid}
        body = _json_object(a.get("payload_json"))
        if not body:
            raise ValueError("Coursework update requires payload_json.")
        return {"coursework": svc.courses().courseWork().patch(courseId=cid, id=wid, updateMask=",".join(body.keys()), body=body).execute()}
    if operation in {"classroom_announcements", "classroom_announcement_create", "classroom_announcement_update", "classroom_announcement_delete"}:
        cid = _id(course_id, "course ID")
        svc = _svc("classroom", "v1", "classroom_announcements" if operation == "classroom_announcements" else "classroom_announcements_write")
        if operation == "classroom_announcements":
            return {"announcements": _list_result(svc.courses().announcements().list(courseId=cid, pageSize=limit, orderBy="updateTime desc").execute(), "announcements", limit)}
        _require_confirmed(confirmed, operation.replace("_", " "))
        if operation == "classroom_announcement_create":
            body = _json_object(a.get("payload_json"))
            if not body.get("text"):
                body["text"] = _text(a.get("content"), "announcement text", 30000, True)
            return {"announcement": svc.courses().announcements().create(courseId=cid, body=body).execute()}
        aid = _id(a.get("item_id") or a.get("resource_id"), "announcement ID")
        if operation == "classroom_announcement_delete":
            svc.courses().announcements().delete(courseId=cid, id=aid).execute()
            return {"deleted_announcement_id": aid}
        body = _json_object(a.get("payload_json"))
        if not body:
            raise ValueError("Announcement update requires payload_json.")
        return {"announcement": svc.courses().announcements().patch(courseId=cid, id=aid, updateMask=",".join(body.keys()), body=body).execute()}
    if operation in {"classroom_materials", "classroom_material_create", "classroom_material_update", "classroom_material_delete"}:
        cid = _id(course_id, "course ID")
        svc = _svc("classroom", "v1", "classroom_work" if operation == "classroom_materials" else "classroom_materials_write")
        if operation == "classroom_materials":
            return {"materials": _list_result(svc.courses().courseWorkMaterials().list(courseId=cid, pageSize=limit).execute(), "courseWorkMaterial", limit)}
        _require_confirmed(confirmed, operation.replace("_", " "))
        if operation == "classroom_material_create":
            body = _json_object(a.get("payload_json"))
            if not body.get("title"):
                body["title"] = _text(a.get("title"), "material title", 250, True)
            return {"material": svc.courses().courseWorkMaterials().create(courseId=cid, body=body).execute()}
        mid = _id(a.get("item_id") or a.get("resource_id"), "classwork material ID")
        if operation == "classroom_material_delete":
            svc.courses().courseWorkMaterials().delete(courseId=cid, id=mid).execute()
            return {"deleted_material_id": mid}
        body = _json_object(a.get("payload_json"))
        if not body:
            raise ValueError("Material update requires payload_json.")
        return {"material": svc.courses().courseWorkMaterials().patch(courseId=cid, id=mid, updateMask=",".join(body.keys()), body=body).execute()}
    if operation in {"classroom_topics", "classroom_topic_create", "classroom_topic_update", "classroom_topic_delete"}:
        cid = _id(course_id, "course ID")
        svc = _svc("classroom", "v1", "classroom_topics_read" if operation == "classroom_topics" else "classroom_topics_write")
        if operation == "classroom_topics":
            return {"topics": _list_result(svc.courses().topics().list(courseId=cid, pageSize=limit).execute(), "topic", limit)}
        _require_confirmed(confirmed, operation.replace("_", " "))
        if operation == "classroom_topic_create":
            title = _text(a.get("title"), "topic title", 250, True)
            return {"topic": svc.courses().topics().create(courseId=cid, body={"name": title}).execute()}
        tid = _id(a.get("item_id") or a.get("resource_id"), "topic ID")
        if operation == "classroom_topic_delete":
            svc.courses().topics().delete(courseId=cid, id=tid).execute()
            return {"deleted_topic_id": tid}
        body = _json_object(a.get("payload_json"))
        if not body:
            raise ValueError("Topic update requires payload_json.")
        return {"topic": svc.courses().topics().patch(courseId=cid, id=tid, updateMask=",".join(body.keys()), body=body).execute()}
    if operation in {"classroom_students_list", "classroom_teachers_list", "classroom_student_add", "classroom_student_remove", "classroom_teacher_add", "classroom_teacher_remove"}:
        cid = _id(course_id, "course ID")
        students = operation.startswith("classroom_student")
        read = operation.endswith("_list")
        profile = "classroom_rosters_read" if read else "classroom_rosters_write"
        svc = _svc("classroom", "v1", profile).courses()
        collection = svc.students() if students else svc.teachers()
        if read:
            key = "students" if students else "teachers"
            return {key: _list_result(collection.list(courseId=cid, pageSize=limit).execute(), key, limit)}
        _require_confirmed(confirmed, operation.replace("_", " "))
        email = _text(a.get("recipient") or a.get("email"), "student/teacher email", 254, True)
        if "_add" in operation:
            return {"person": collection.create(courseId=cid, body={"userId": email}).execute()}
        collection.delete(courseId=cid, userId=email).execute()
        return {"removed_user": email, "course_id": cid}
    if operation in {"classroom_submissions_list", "classroom_submission_update", "classroom_submission_turn_in", "classroom_submission_reclaim", "classroom_submission_return"}:
        cid = _id(course_id, "course ID")
        wid = _id(a.get("item_id") or a.get("resource_id"), "coursework ID")
        if operation == "classroom_submissions_list":
            user_id = _text(a.get("user_id") or "me", "student user ID", 250, True)
            profile = "classroom_students_work_read" if user_id.casefold() == "me" else "classroom_students_work_admin_read"
        else:
            profile = "classroom_students_work_write"
        svc = _svc("classroom", "v1", profile).courses().courseWork().studentSubmissions()
        if operation == "classroom_submissions_list":
            return {"submissions": _list_result(svc.list(courseId=cid, courseWorkId=wid, userId=user_id, pageSize=limit).execute(), "studentSubmissions", limit)}
        _require_confirmed(confirmed, operation.replace("_", " "))
        sid = _id(a.get("submission_id"), "student submission ID")
        if operation == "classroom_submission_update":
            body = _json_object(a.get("payload_json"))
            if not body:
                raise ValueError("Submission update requires payload_json.")
            return {"submission": svc.patch(courseId=cid, courseWorkId=wid, id=sid, updateMask=",".join(body.keys()), body=body).execute()}
        if operation == "classroom_submission_turn_in":
            return {"result": svc.turnIn(courseId=cid, courseWorkId=wid, id=sid, body={}).execute()}
        if operation == "classroom_submission_reclaim":
            return {"result": svc.reclaim(courseId=cid, courseWorkId=wid, id=sid, body={}).execute()}
        return {"result": svc.return_(courseId=cid, courseWorkId=wid, id=sid, body={}).execute()}
    if operation in {"classroom_guardians_me", "classroom_guardians_list", "classroom_guardian_create", "classroom_guardian_delete"}:
        if operation == "classroom_guardians_me":
            profile = "classroom_guardians_me"
            result = _svc("classroom", "v1", profile).userProfiles().guardianInvitations().list(studentId="me", pageSize=limit).execute()
            return {"guardian_invitations": _list_result(result, "guardianInvitations", limit)}
        sid = _text(a.get("student_id"), "student ID", 250, True)
        if operation == "classroom_guardians_list":
            result = _svc("classroom", "v1", "classroom_guardians_students_read").userProfiles().guardians().list(studentId=sid, pageSize=limit).execute()
            return {"guardians": _list_result(result, "guardians", limit)}
        _require_confirmed(confirmed, operation.replace("_", " "))
        svc = _svc("classroom", "v1", "classroom_guardians_students_write").userProfiles().guardians()
        if operation == "classroom_guardian_create":
            email = gw._validate_email(_text(a.get("recipient"), "guardian email", 254, True))
            return {"guardian": svc.create(studentId=sid, body={"guardianId": email}).execute()}
        gid = _text(a.get("guardian_id") or a.get("recipient"), "guardian ID/email", 254, True)
        svc.delete(studentId=sid, guardianId=gid).execute()
        return {"deleted_guardian": gid}
    if operation in {"classroom_registration_create", "classroom_registration_delete"}:
        _require_confirmed(confirmed, operation.replace("_", " "))
        svc = _svc("classroom", "v1", "classroom_push").registrations()
        if operation == "classroom_registration_create":
            body = _json_object(a.get("payload_json"))
            if not body.get("feed") or not body.get("cloudPubsubTopic"):
                raise ValueError("Registration payload requires feed and cloudPubsubTopic objects.")
            return {"registration": svc.create(body=body).execute()}
        rid = _id(a.get("identifier"), "registration ID")
        svc.delete(registrationId=rid).execute()
        return {"deleted_registration_id": rid}
    raise ValueError(f"Unsupported Classroom operation: {operation}")


# ----------------------------------- Meet ----------------------------------
def _meet(operation: str, a: dict[str, Any], confirmed: bool) -> dict[str, Any]:
    if operation == "meet_space_create":
        _require_confirmed(confirmed, "Creating a Google Meet space")
        body = _json_object(a.get("payload_json"))
        return {"space": _svc("meet", "v2", "meet_create").spaces().create(body=body).execute()}
    if operation in {"meet_space_get", "meet_space_update", "meet_end_conference"}:
        name = _text(a.get("identifier"), "Meet space name or meeting code", 250, True)
        if not name.startswith("spaces/") and not re.fullmatch(r"[A-Za-z0-9-]{5,100}", name):
            raise ValueError("Provide a Meet space resource name or meeting code.")
        if not name.startswith("spaces/"):
            name = f"spaces/{name}"
        if operation == "meet_space_get":
            return {"space": _svc("meet", "v2", "meet_read").spaces().get(name=name).execute()}
        _require_confirmed(confirmed, "Updating or ending a Google Meet conference")
        if operation == "meet_end_conference":
            return {"result": _svc("meet", "v2", "meet_create").spaces().endActiveConference(name=name, body={}).execute()}
        body = _json_object(a.get("payload_json"))
        if not body:
            raise ValueError("Meet space update requires payload_json.")
        update_mask = _text(a.get("update_mask") or ",".join(body.keys()), "update_mask", 1000, True)
        return {"space": _svc("meet", "v2", "meet_settings").spaces().patch(name=name, updateMask=update_mask, body=body).execute()}
    if operation in {"meet_conference_records", "meet_recordings_list", "meet_transcripts_list", "meet_participants_list"}:
        limit = max(1, min(int(a.get("limit", 20) or 20), 100))
        parent = _text(a.get("parent") or a.get("identifier"), "conference record or Meet parent resource", 250)
        service = _svc("meet", "v2", "meet_read")
        if operation == "meet_conference_records":
            params = {"pageSize": limit}
            if parent:
                params["filter"] = _text(a.get("query") or f"space.name=\"{parent}\"", "conference filter", 500)
            return {"conference_records": _list_result(service.conferenceRecords().list(**params).execute(), "conferenceRecords", limit)}
        if not parent.startswith("conferenceRecords/"):
            parent = f"conferenceRecords/{_id(parent, 'conference record ID')}"
        if operation == "meet_recordings_list":
            return {"recordings": _list_result(service.conferenceRecords().recordings().list(parent=parent, pageSize=limit).execute(), "recordings", limit)}
        if operation == "meet_transcripts_list":
            return {"transcripts": _list_result(service.conferenceRecords().transcripts().list(parent=parent, pageSize=limit).execute(), "transcripts", limit)}
        return {"participants": _list_result(service.conferenceRecords().participants().list(parent=parent, pageSize=limit).execute(), "participants", limit)}
    raise ValueError(f"Unsupported Meet operation: {operation}")


# -------------------------------- YouTube ----------------------------------
def _youtube(operation: str, a: dict[str, Any], confirmed: bool) -> dict[str, Any]:
    limit = max(1, min(int(a.get("limit", 20) or 20), 50))
    if operation == "youtube_channel":
        result = _svc("youtube", "v3", "youtube_read").channels().list(part="snippet,contentDetails,statistics,status", mine=True, maxResults=limit).execute()
        return {"channels": _list_result(result, "items", limit)}
    if operation == "youtube_my_videos":
        channel = _svc("youtube", "v3", "youtube_read").channels().list(part="contentDetails", mine=True, maxResults=1).execute()
        items = channel.get("items", []) or []
        if not items:
            return {"videos": [], "message": "No channel returned for the authenticated account."}
        playlist_id = items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        result = _svc("youtube", "v3", "youtube_read").playlistItems().list(part="snippet,contentDetails", playlistId=playlist_id, maxResults=limit).execute()
        return {"videos": _list_result(result, "items", limit)}
    if operation in {"youtube_playlist_list", "youtube_playlist_create", "youtube_playlist_update", "youtube_playlist_delete", "youtube_playlist_item_add", "youtube_playlist_item_delete"}:
        if operation == "youtube_playlist_list":
            result = _svc("youtube", "v3", "youtube_read").playlists().list(part="snippet,status,contentDetails", mine=True, maxResults=limit).execute()
            return {"playlists": _list_result(result, "items", limit)}
        _require_confirmed(confirmed, operation.replace("_", " "))
        if operation == "youtube_playlist_create":
            title = _text(a.get("title"), "playlist title", 150, True)
            body = {"snippet": {"title": title, "description": _text(a.get("content"), "playlist description", 5000)}, "status": {"privacyStatus": str(a.get("privacy") or "private")}}
            if body["status"]["privacyStatus"] not in {"private", "unlisted", "public"}:
                raise ValueError("privacy must be private, unlisted, or public.")
            return {"playlist": _svc("youtube", "v3", "youtube_full").playlists().insert(part="snippet,status", body=body).execute()}
        pid = _id(a.get("identifier"), "YouTube playlist ID")
        if operation == "youtube_playlist_update":
            body = _json_object(a.get("payload_json"))
            if not body:
                raise ValueError("Playlist update requires payload_json.")
            return {"playlist": _svc("youtube", "v3", "youtube_full").playlists().update(part=",".join(body.keys()), body={"id": pid, **body}).execute()}
        if operation == "youtube_playlist_delete":
            _svc("youtube", "v3", "youtube_full").playlists().delete(id=pid).execute()
            return {"deleted_playlist_id": pid}
        if operation == "youtube_playlist_item_add":
            video_id = _id(a.get("video_id"), "YouTube video ID")
            body = {"snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}
            return {"playlist_item": _svc("youtube", "v3", "youtube_full").playlistItems().insert(part="snippet", body=body).execute()}
        item_id = _id(a.get("item_id"), "YouTube playlist item ID")
        _svc("youtube", "v3", "youtube_full").playlistItems().delete(id=item_id).execute()
        return {"deleted_playlist_item_id": item_id}
    if operation in {"youtube_upload", "youtube_video_update", "youtube_video_delete", "youtube_comment_insert"}:
        _require_confirmed(confirmed, operation.replace("_", " "))
        service = _svc("youtube", "v3", "youtube_upload" if operation == "youtube_upload" else "youtube_force_ssl")
        if operation == "youtube_upload":
            path_value = _text(a.get("file_path"), "video file path", 1000, True)
            path = Path(path_value).expanduser().resolve()
            if not path.is_file() or path.suffix.lower() not in {".mp4", ".mov", ".mpeg", ".mpg", ".avi", ".wmv", ".flv", ".webm", ".3gp"}:
                raise ValueError("Select an existing video file with a supported video extension.")
            from googleapiclient.http import MediaFileUpload
            body = {"snippet": {"title": _text(a.get("title"), "video title", 100, True), "description": _text(a.get("content"), "video description", 5000)}, "status": {"privacyStatus": str(a.get("privacy") or "private")}}
            if body["status"]["privacyStatus"] not in {"private", "unlisted", "public"}:
                raise ValueError("privacy must be private, unlisted, or public.")
            upload = MediaFileUpload(str(path), chunksize=8 * 1024 * 1024, resumable=True)
            result = service.videos().insert(part="snippet,status", body=body, media_body=upload).execute()
            return {"video": result}
        if operation == "youtube_video_update":
            vid = _id(a.get("identifier"), "YouTube video ID")
            body = _json_object(a.get("payload_json"))
            if not body:
                raise ValueError("Video update requires payload_json with snippet/status fields.")
            body["id"] = vid
            return {"video": service.videos().update(part=",".join(k for k in body.keys() if k != "id"), body=body).execute()}
        if operation == "youtube_video_delete":
            vid = _id(a.get("identifier"), "YouTube video ID")
            service.videos().delete(id=vid).execute()
            return {"deleted_video_id": vid}
        video_id = _id(a.get("video_id") or a.get("identifier"), "YouTube video ID")
        text = _text(a.get("content"), "comment text", 10000, True)
        body = {"snippet": {"topLevelComment": {"snippet": {"textOriginal": text}}, "videoId": video_id}}
        return {"comment": service.commentThreads().insert(part="snippet", body=body).execute()}
    if operation == "youtube_memberships":
        result = _svc("youtube", "v3", "youtube_memberships").members().list(part="snippet", mode="all_current", maxResults=limit).execute()
        return {"members": _list_result(result, "items", limit)}
    raise ValueError(f"Unsupported YouTube operation: {operation}")


# ---------------------------------- Forms ----------------------------------
def _forms(operation: str, a: dict[str, Any], confirmed: bool) -> dict[str, Any]:
    form_id = _id(a.get("identifier"), "Google Form ID")
    if operation == "forms_responses_list":
        limit = max(1, min(int(a.get("limit", 50) or 50), 5000))
        params: dict[str, Any] = {"formId": form_id, "pageSize": min(limit, 500)}
        if a.get("page_token"):
            params["pageToken"] = _text(a.get("page_token"), "page token", 1000)
        result = _svc("forms", "v1", "forms_responses_read").forms().responses().list(**params).execute()
        return {"responses": result.get("responses", []) or [], "next_page_token": result.get("nextPageToken", "")}
    if operation == "forms_response_get":
        rid = _id(a.get("response_id"), "Google Form response ID")
        result = _svc("forms", "v1", "forms_responses_read").forms().responses().get(formId=form_id, responseId=rid).execute()
        return {"response": result}
    if operation == "forms_update":
        _require_confirmed(confirmed, "Updating a Google Form")
        body = _json_object(a.get("payload_json"))
        requests = body.get("requests")
        allowed = {"updateFormInfo", "updateItem", "createItem", "deleteItem", "moveItem", "updateSettings"}
        if not isinstance(requests, list) or not requests or len(requests) > 100 or any(not isinstance(r, dict) or len(r) != 1 or next(iter(r)) not in allowed for r in requests):
            raise ValueError("Form requests must be 1–100 objects using the documented allowlisted request types.")
        result = _svc("forms", "v1", "forms_write").forms().batchUpdate(formId=form_id, body={"requests": requests}).execute()
        return {"result": result}
    if operation == "forms_response_watch_create":
        _require_confirmed(confirmed, "Subscribing to Google Form response notifications")
        body = _json_object(a.get("payload_json"))
        if not body.get("watchType") or not body.get("target"):
            raise ValueError("Watch creation requires payload_json with watchType and target.")
        return {"watch": _svc("forms", "v1", "forms_write").forms().watches().create(formId=form_id, body=body).execute()}
    if operation == "forms_response_watch_delete":
        _require_confirmed(confirmed, "Deleting a Google Form response notification watch")
        wid = _id(a.get("watch_id"), "Forms watch ID")
        _svc("forms", "v1", "forms_write").forms().watches().delete(formId=form_id, watchId=wid).execute()
        return {"deleted_watch_id": wid}
    raise ValueError(f"Unsupported Forms operation: {operation}")


# -------------------------- Generative Language API ------------------------
def _oauth_rest(profile: str, method: str, url: str, *, body: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
    from google.auth.transport.requests import AuthorizedSession
    session = AuthorizedSession(gw._credentials(profile))
    try:
        response = session.request(method, url, json=body, params=params, timeout=25)
        response.raise_for_status()
        if not response.content:
            return {"status": "ok"}
        payload = response.json()
        return payload if isinstance(payload, dict) else {"items": payload}
    except Exception as exc:
        # Google's API error payload is useful for configuration and permission diagnosis.
        detail = ""
        try:
            detail = response.text[:800]
        except Exception:
            pass
        raise RuntimeError(f"Generative Language API request failed: {exc}.{(' ' + detail) if detail else ''}") from exc
    finally:
        session.close()


def _generative(operation: str, a: dict[str, Any], confirmed: bool) -> dict[str, Any]:
    base = "https://generativelanguage.googleapis.com/v1beta"
    name = _text(a.get("identifier"), "resource name", 300)
    if operation == "generative_tuned_models_list":
        return _oauth_rest("generative_tuning_read", "GET", f"{base}/tunedModels", params={"pageSize": max(1, min(int(a.get("limit", 20) or 20), 100))})
    if operation == "generative_tuned_model_get":
        if not name.startswith("tunedModels/"):
            name = "tunedModels/" + _id(name, "tuned model ID")
        return _oauth_rest("generative_tuning_read", "GET", f"{base}/{name}")
    if operation == "generative_tuning_delete":
        _require_confirmed(confirmed, "Deleting a tuned Gemini model")
        if not name.startswith("tunedModels/"):
            name = "tunedModels/" + _id(name, "tuned model ID")
        return _oauth_rest("generative_tuning_write", "DELETE", f"{base}/{name}")
    if operation == "generative_retriever_list":
        return _oauth_rest("generative_retriever_read", "GET", f"{base}/corpora", params={"pageSize": max(1, min(int(a.get("limit", 20) or 20), 100))})
    if operation == "generative_retriever_get":
        if not name.startswith("corpora/"):
            name = "corpora/" + _id(name, "retriever corpus ID")
        return _oauth_rest("generative_retriever_read", "GET", f"{base}/{name}")
    if operation == "generative_retriever_create":
        _require_confirmed(confirmed, "Creating a Gemini semantic-retriever corpus")
        body = _json_object(a.get("payload_json")) or {"name": _text(a.get("title"), "corpus name", 250, True)}
        return _oauth_rest("generative_retriever_write", "POST", f"{base}/corpora", body=body)
    if operation == "generative_retriever_delete":
        _require_confirmed(confirmed, "Deleting a Gemini semantic-retriever corpus")
        if not name.startswith("corpora/"):
            name = "corpora/" + _id(name, "retriever corpus ID")
        return _oauth_rest("generative_retriever_write", "DELETE", f"{base}/{name}")
    if operation == "generative_retriever_query":
        if not name.startswith("corpora/"):
            name = "corpora/" + _id(name, "retriever corpus ID")
        body = _json_object(a.get("payload_json")) or {"query": _text(a.get("query"), "retrieval query", 10000, True)}
        # API method names are fixed here; the caller cannot choose an arbitrary endpoint.
        return _oauth_rest("generative_retriever_read", "POST", f"{base}/{name}:query", body=body)
    if operation == "generative_peruserquota_status":
        # This scope authorizes account-based quota usage but does not itself expose a
        # standalone quota REST endpoint. The product-facing generation path remains Gemini API-key based.
        return {"kind": operation, "available": False, "reason": "The scope is consent metadata for per-user quota access, not a standalone quota query endpoint; existing Gemini generation uses GEMINI_API_KEY."}
    raise ValueError(f"Unsupported Generative Language operation: {operation}")


# --------------------------- Main allowlisted router -----------------------
_OPERATION_GROUPS = {
    "calendar": {"calendar_list", "calendar_create", "calendar_app_created_calendar_create", "calendar_get", "calendar_update", "calendar_delete", "calendar_subscribe", "calendar_unsubscribe", "calendar_events_list", "calendar_readonly_events", "calendar_public_events", "calendar_event_get", "calendar_event_create", "calendar_event_update", "calendar_event_delete", "calendar_owned_events_list", "calendar_owned_event_get", "calendar_owned_event_create", "calendar_owned_event_update", "calendar_owned_event_delete", "calendar_app_created_events_list", "calendar_app_created_event_get", "calendar_app_created_event_create", "calendar_app_created_event_update", "calendar_app_created_event_delete", "calendar_freebusy", "calendar_events_freebusy", "calendar_settings_list", "calendar_setting_get", "calendar_acl_list", "calendar_acl_create", "calendar_acl_update", "calendar_acl_delete"},
    "gmail": {"gmail_messages_list", "gmail_metadata_list", "gmail_message_read", "gmail_message_modify", "gmail_message_delete", "gmail_message_insert", "gmail_send", "gmail_drafts_list", "gmail_draft_read", "gmail_draft_create", "gmail_draft_update", "gmail_draft_delete", "gmail_draft_send", "gmail_labels_list", "gmail_label_create", "gmail_label_update", "gmail_label_delete", "gmail_filters_list", "gmail_filter_create", "gmail_filter_delete", "gmail_settings_list", "gmail_setting_get", "gmail_forwarding_list", "gmail_forwarding_create", "gmail_forwarding_delete", "gmail_autoforward_get", "gmail_autoforward_update", "gmail_sendas_list", "gmail_sendas_create", "gmail_sendas_update", "gmail_sendas_delete", "gmail_delegates_list", "gmail_delegate_create", "gmail_delegate_delete", "gmail_notifications_watch", "gmail_notifications_stop", "gmail_setting_update", "gmail_user_metadata", "gmail_send_to_self", "gmail_compose_send", "gmail_compose_draft_create"},
    "drive": {"drive_files_list", "drive_meet_files_list", "drive_appdata_list", "drive_appdata_create", "drive_appdata_delete", "drive_apps_list", "drive_file_get", "drive_file_create", "drive_file_update", "drive_file_copy", "drive_file_delete", "drive_permission_list", "drive_permission_create", "drive_permission_update", "drive_permission_delete", "drive_activity_list", "drive_script_get", "drive_script_create", "drive_script_update", "drive_about", "drive_photo_files_list", "drive_item_list", "drive_item_get", "drive_collaboration_item_list", "drive_collaboration_item_get", "drive_item_update", "drive_item_delete", "drive_metadata_update"},
    "docs": {"docs_replace_text", "docs_insert_text", "docs_batch_update"},
    "sheets": {"sheets_create", "sheets_append", "sheets_clear", "sheets_batch_update"},
    "slides": {"slides_batch_update"},
    "tasks": {"tasks_list", "tasks_create", "tasks_update", "tasks_delete", "tasks_complete", "tasks_reopen"},
    "people": {"people_other_contacts_list", "people_user_profile", "people_contacts_search", "people_contact_create", "people_contact_update", "people_contact_delete", "google_identity"},
    "classroom": {"classroom_courses", "classroom_course_get", "classroom_course_create", "classroom_course_update", "classroom_course_delete", "classroom_coursework", "classroom_coursework_create", "classroom_coursework_update", "classroom_coursework_delete", "classroom_announcements", "classroom_announcement_create", "classroom_announcement_update", "classroom_announcement_delete", "classroom_materials", "classroom_material_create", "classroom_material_update", "classroom_material_delete", "classroom_topics", "classroom_topic_create", "classroom_topic_update", "classroom_topic_delete", "classroom_students_list", "classroom_teachers_list", "classroom_student_add", "classroom_student_remove", "classroom_teacher_add", "classroom_teacher_remove", "classroom_submissions_list", "classroom_submission_update", "classroom_submission_turn_in", "classroom_submission_reclaim", "classroom_submission_return", "classroom_guardians_me", "classroom_guardians_list", "classroom_guardian_create", "classroom_guardian_delete", "classroom_registration_create", "classroom_registration_delete", "classroom_student_profile"},
    "meet": {"meet_space_create", "meet_space_get", "meet_space_update", "meet_end_conference", "meet_conference_records", "meet_recordings_list", "meet_transcripts_list", "meet_participants_list"},
    "youtube": {"youtube_channel", "youtube_my_videos", "youtube_playlist_list", "youtube_playlist_create", "youtube_playlist_update", "youtube_playlist_delete", "youtube_playlist_item_add", "youtube_playlist_item_delete", "youtube_upload", "youtube_video_update", "youtube_video_delete", "youtube_comment_insert", "youtube_memberships"},
    "forms": {"forms_responses_list", "forms_response_get", "forms_update", "forms_response_watch_create", "forms_response_watch_delete"},
    "generative": {"generative_tuned_models_list", "generative_tuned_model_get", "generative_tuning_delete", "generative_retriever_list", "generative_retriever_get", "generative_retriever_create", "generative_retriever_delete", "generative_retriever_query", "generative_peruserquota_status"},
}

EXTENDED_OPERATIONS = frozenset().union(*_OPERATION_GROUPS.values())


def execute_google_workspace_extended_operation(operation: str, args: dict[str, Any], *, confirmed: bool = False) -> dict[str, Any]:
    """Run one operation from the explicit service allowlist."""
    op = str(operation or "").strip().casefold()
    a = args if isinstance(args, dict) else {}
    if op not in EXTENDED_OPERATIONS:
        raise ValueError(f"Unsupported extended Google Workspace operation: {operation!r}.")
    # Enforce the confirmation policy before validating arguments, acquiring OAuth
    # tokens, constructing API clients, or making any provider request.
    if op in EXTENDED_WRITE_OPERATIONS and not confirmed:
        raise PermissionError(f"{op.replace('_', ' ')} requires explicit user confirmation after reviewing the details.")
    if op in _OPERATION_GROUPS["calendar"]:
        return {"kind": op, **_calendar(op, a, confirmed)}
    if op in _OPERATION_GROUPS["gmail"]:
        return {"kind": op, **_gmail(op, a, confirmed)}
    if op in _OPERATION_GROUPS["drive"]:
        return {"kind": op, **_drive(op, a, confirmed)}
    if op in _OPERATION_GROUPS["docs"]:
        return {"kind": op, **_documents(op, a, confirmed)}
    if op in _OPERATION_GROUPS["sheets"]:
        return {"kind": op, **_sheets(op, a, confirmed)}
    if op in _OPERATION_GROUPS["slides"]:
        return {"kind": op, **_slides(op, a, confirmed)}
    if op in _OPERATION_GROUPS["tasks"]:
        return {"kind": op, **_tasks(op, a, confirmed)}
    if op in _OPERATION_GROUPS["people"]:
        return {"kind": op, **_people(op, a, confirmed)}
    if op in _OPERATION_GROUPS["classroom"]:
        return {"kind": op, **_classroom(op, a, confirmed)}
    if op in _OPERATION_GROUPS["meet"]:
        return {"kind": op, **_meet(op, a, confirmed)}
    if op in _OPERATION_GROUPS["youtube"]:
        return {"kind": op, **_youtube(op, a, confirmed)}
    if op in _OPERATION_GROUPS["forms"]:
        return {"kind": op, **_forms(op, a, confirmed)}
    if op in _OPERATION_GROUPS["generative"]:
        return {"kind": op, **_generative(op, a, confirmed)}
    raise ValueError(f"No handler for {op!r}.")


def google_scope_capability_report() -> dict[str, Any]:
    """Return local wiring status; does not imply Cloud APIs are enabled or approved."""
    statuses = {
        "implemented": sorted(EXTENDED_OPERATIONS),
        "scope_profiles": {name: list(scopes) for name, scopes in sorted(gw._SCOPE_PROFILES.items())},
        "requires_separate_product_runtime": [
            "gmail.addons.current.action.compose", "gmail.addons.current.message.action",
            "gmail.addons.current.message.metadata", "gmail.addons.current.message.readonly",
        ],
        "not_executable_by_scope_alone": [
            "meetings.conference.media.readonly", "meetings.conference.media.audio.readonly",
            "meetings.conference.media.video.readonly", "meetings.hardware", "generative-language.peruserquota",
            "youtube.download", "youtube.third-party-link.creator", "youtubepartner-channel-audit",
        ],
        "requires_provider_or_admin_approval": [
            "restricted Gmail/Drive scopes and verification", "Google Classroom education-domain access",
            "YouTube partner/channel membership capabilities", "Google Meet hardware administration",
            "LinkedIn Learning API access", "Classroom add-on attachment runtime and practice-set APIs",
        ],
        "notes": [
            "Each Google feature opens its own OAuth consent profile and token file; authorization is not automatic.",
            "Cloud API enablement, OAuth consent-screen verification, Workspace administrator policy and billing remain external prerequisites.",
            "drive.photos.readonly is not treated as an implementation of the separate Google Photos Library API.",
            "calendar.settings has no Calendar API settings write method; the adapter supports settings read only.",
            "drive.activity is read-only in the exposed REST adapter because Drive Activity API v2 provides query, not an activity-write endpoint.",
            "drive.install is an installation/integration permission, not a general REST resource endpoint in this app.",
            "drive.apps is exposed as a read-only apps listing where the Drive API has a corresponding endpoint; no arbitrary app-install or app-store management action is synthesized.",
            "Gmail add-on current-message/action scopes require an installed Gmail add-on runtime and are not desktop OAuth features.",
            "Meet conference media capture and Meet hardware control require product-specific access/runtime and are not implied by the scope string.",
        ],
    }
    return statuses


# If semantic_router imported this module first, google_workspace may have encountered
# an in-progress import. Reconcile the shared confirmation set once this module is complete.
_base_writes = {"docs_create", "sheets_update", "slides_create", "tasks_create", "meet_create", "forms_create"}
try:
    gw.GOOGLE_WORKSPACE_WRITE_OPERATIONS = frozenset(_base_writes) | EXTENDED_WRITE_OPERATIONS
except Exception:
    pass

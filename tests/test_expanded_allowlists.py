from visionguide.desktop_actions import WEBSITE_URLS, WINDOWS_APPS, WINDOWS_URIS, SETTINGS_URIS
from visionguide.scene_commands import parse_voice_command
from visionguide.semantic_router import _FUNCTIONS


def _tool(name):
    return next(item for item in _FUNCTIONS if item["name"] == name)


def _enum(tool_name, field):
    return _tool(tool_name)["parameters"]["properties"][field]["enum"]


def test_requested_websites_are_in_launcher_and_router_allowlists():
    expected = {"leetcode", "gemini", "netlify", "render", "claude", "google classroom", "google docs", "google sheets", "google meet", "google cloud console", "neon db", "google contacts", "contacts", "linkedin learning", "coursera", "swayam", "swaym", "linkedln learning", "nptel"}
    assert expected <= set(WEBSITE_URLS)
    assert expected <= set(_enum("open_website", "name"))


def test_requested_desktop_apps_and_settings_have_allowlist_entries():
    expected_apps = {"powerpoint", "excel", "wps office", "wps docs", "wps slides", "wps sheets", "wps pdf", "arduino", "autocad 2026", "python idle", "picasa 3", "media player", "photos", "clock", "recycle bin", "whatsapp", "edge"}
    expected_settings = {"airplane mode", "eye comfort", "energy saver"}
    assert expected_apps <= set(WINDOWS_APPS) | set(WINDOWS_URIS) | set(SETTINGS_URIS) | {"instagram"}
    assert expected_apps <= set(_enum("open_app", "name"))
    assert expected_settings <= set(WINDOWS_URIS) | set(SETTINGS_URIS)
    assert expected_settings <= set(_enum("open_app", "name"))


def test_local_voice_parser_routes_added_aliases_to_allowlisted_actions():
    assert parse_voice_command("open leetcode") == ("open_website", "leetcode")
    assert parse_voice_command("open google sheets") == ("open_website", "google sheets")
    assert parse_voice_command("open linkedln learning") == ("open_website", "linkedin learning")
    assert parse_voice_command("open swaym") == ("open_website", "swayam")
    assert parse_voice_command("open powerpoint") == ("open_app", "powerpoint")
    assert parse_voice_command("open eye comfort") == ("open_app", "eye comfort")
    assert parse_voice_command("open whatsapp") == ("open_app", "whatsapp")


def test_google_workspace_extended_operations_are_exposed_to_semantic_router():
    from visionguide.integrations.google_workspace_extended import EXTENDED_OPERATIONS
    declared = set(_enum("google_workspace_feature", "operation"))
    assert set(EXTENDED_OPERATIONS) <= declared
    assert {"google_identity", "calendar_owned_events_list", "calendar_app_created_event_create", "drive_metadata_update", "drive_collaboration_item_get", "classroom_student_profile"} <= declared


def test_scope_profiles_and_confirmation_guards_cover_extended_features():
    import pytest
    from visionguide.integrations.google_workspace import _SCOPE_PROFILES, GOOGLE_WORKSPACE_WRITE_OPERATIONS
    from visionguide.integrations.google_workspace_extended import (
        EXTENDED_OPERATIONS, EXTENDED_WRITE_OPERATIONS,
        execute_google_workspace_extended_operation, google_scope_capability_report,
    )

    assert set(EXTENDED_WRITE_OPERATIONS) <= set(GOOGLE_WORKSPACE_WRITE_OPERATIONS)
    assert set(EXTENDED_WRITE_OPERATIONS) <= set(EXTENDED_OPERATIONS)
    required_profiles = {
        "identity_openid", "calendar_events_owned_read", "calendar_events_owned_write",
        "calendar_app_created", "gmail_compose", "gmail_labels_create_narrow",
        "gmail_drafts_create_narrow", "drive_metadata_write", "drive_item_read",
        "drive_item_write", "drive_item_collaboration_read", "drive_appdata", "classroom_profile_emails",
        "classroom_profile_photos", "meet_media_audio_read", "youtube_upload",
        "forms_responses_read", "generative_retriever_read",
    }
    assert required_profiles <= set(_SCOPE_PROFILES)

    # A representative selection of sends/creates/deletes must reject execution before validation/API access.
    # Every declared write must be rejected before validation/OAuth/API setup when not confirmed.
    for operation in EXTENDED_WRITE_OPERATIONS:
        with pytest.raises(PermissionError):
            execute_google_workspace_extended_operation(operation, {}, confirmed=False)

    status = google_scope_capability_report()
    assert "gmail.addons.current.message.action" in status["requires_separate_product_runtime"]
    assert "meetings.conference.media.audio.readonly" in status["not_executable_by_scope_alone"]
    assert "scope_profiles" in status

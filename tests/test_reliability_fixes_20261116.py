from __future__ import annotations

import ctypes
import sys
import threading
import types
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest

from visionguide.app import ArthurApp
from visionguide.integrations import google_workspace
from visionguide.integrations.gui_automation import submit_typed_field
from visionguide.perception import Detection
from visionguide.semantic_router import SemanticCommandRouter
from visionguide.speech import SpeechOutput


def test_swin3d_checkpoint_normalizer_removes_module_and_base_model_prefixes():
    from visionguide.sign_language import ISLRecognizer

    weights = object()
    normalized = ISLRecognizer._normalize_checkpoint_state_dict({
        "module.base_model.patch_embed.proj.weight": weights,
        "base_model.classification_head.0.weight": "classifier-weight",
    })
    assert normalized == {
        "patch_embed.proj.weight": weights,
        "head.weight": "classifier-weight",
    }


def test_swin3d_checkpoint_normalizer_rejects_key_collisions():
    from visionguide.sign_language import ISLRecognizer

    with pytest.raises(RuntimeError, match="duplicate parameter"):
        ISLRecognizer._normalize_checkpoint_state_dict({
            "patch_embed.proj.weight": 1,
            "base_model.patch_embed.proj.weight": 2,
        })


def test_sapi_waiting_state_is_not_mistaken_for_completed_speech():
    assert SpeechOutput._sapi_is_done(types.SimpleNamespace(RunningState=0)) is False
    assert SpeechOutput._sapi_is_done(types.SimpleNamespace(RunningState=1)) is True
    assert SpeechOutput._sapi_is_done(types.SimpleNamespace(RunningState=2)) is False


def test_pause_button_requests_sapi_pause_before_waiting_for_aec_listener():
    calls = []

    class FakeSpeech:
        is_paused = False
        def pause(self):
            calls.append("pause")
            return True

    class FakeStatus:
        def set(self, _value):
            pass

    app = object.__new__(ArthurApp)
    app.speech = FakeSpeech()
    app._speech_interrupt_stop = threading.Event()
    app._stop_speech_interrupt_listener = lambda: calls.append("stop-listener")
    app.conversation_active = False
    app.status_var = FakeStatus()
    app._append_output = lambda _message: None
    app.pause_speech()
    assert calls == ["pause", "stop-listener"]


def test_cancel_button_purges_sapi_before_waiting_for_aec_listener():
    calls = []

    class FakeSpeech:
        def cancel(self):
            calls.append("cancel")

    class FakeStatus:
        def set(self, _value):
            pass

    app = object.__new__(ArthurApp)
    app.speech = FakeSpeech()
    app._speech_interrupt_stop = threading.Event()
    app._stop_speech_interrupt_listener = lambda: calls.append("stop-listener")
    app.status_var = FakeStatus()
    app._append_output = lambda _message: None
    app.cancel_speech()
    assert calls == ["cancel", "stop-listener"]


def test_scene_description_uploads_the_captured_frame_to_groq_after_consent():
    frame = np.zeros((30, 40, 3), dtype=np.uint8)
    detection = Detection("chair", 0.91, 2, 3, 20, 25, 11, 14, "left")
    calls = {}

    class FakeDepth:
        def decorate(self, detections):
            return detections
        def snapshot(self):
            return {}, "Metric depth active", ""

    class FakeGroq:
        def available(self):
            return True
        def ask_about_frame(self, prompt, received_frame, use_web_search):
            calls["prompt"] = prompt
            calls["frame"] = received_frame
            calls["web_search"] = use_web_search
            return "Groq scene description"

    class FakeStatus:
        def set(self, value):
            calls["status"] = value

    app = object.__new__(ArthurApp)
    app._camera_snapshot_for_task = lambda wait_for_detection: (frame, [detection])
    app.depth_worker = FakeDepth()
    app.gemini = FakeGroq()
    app._ask_yes_no = lambda *_args, **_kwargs: True
    app.status_var = FakeStatus()
    app._set_output = lambda value: calls.setdefault("output", value)
    app._say = lambda value: calls.setdefault("spoken", value)
    app._run_async = lambda action, function: calls.update(action=action, async_result=function())

    ArthurApp.describe_scene(app)

    assert calls["action"] == "gemini"
    assert calls["async_result"] == "Groq scene description"
    assert calls["frame"] is frame
    assert calls["web_search"] is False
    assert "chair" in calls["prompt"]
    assert "Metric depth active" in calls["prompt"]


def test_scene_description_falls_back_to_local_summary_when_groq_is_not_configured():
    frame = np.zeros((30, 40, 3), dtype=np.uint8)
    detection = Detection("chair", 0.91, 2, 3, 20, 25, 11, 14, "left")
    calls = {}

    class FakeGroq:
        def available(self):
            return False

    class FakeStatus:
        def set(self, _value):
            pass

    app = object.__new__(ArthurApp)
    app._camera_snapshot_for_task = lambda wait_for_detection: (frame, [detection])
    app.depth_worker = None
    app.gemini = FakeGroq()
    app.status_var = FakeStatus()
    app._set_output = lambda value: calls.setdefault("output", value)
    app._say = lambda value: calls.setdefault("spoken", value)
    app.describe_scene = ArthurApp.describe_scene.__get__(app, ArthurApp)

    ArthurApp.describe_scene(app)
    assert "chair" in calls["output"]
    assert "Groq vision is not configured" in calls["output"]


def test_voice_router_has_local_scene_face_bluetooth_and_keyboard_routes():
    router = SemanticCommandRouter(enable_local_semantic=False)
    assert router.route("Describe the scene").action == "describe"
    assert router.route("What is in front of me?").action == "describe"
    assert router.route("Tell me about this product").action == "product_lookup"
    assert router.route("Do you recognize me?").action == "face_identify"
    assert router.route("Turn Bluetooth on").arguments == {"enabled": True}
    assert router.route("Turn Bluetooth off").arguments == {"enabled": False}
    assert router.route("Open the on-screen keyboard").action == "keyboard_toggle"
    assert router.route("Bring up the virtual keyboard").action == "keyboard_toggle"
    assert router.route("Turn on the virtual keyboard").action == "keyboard_toggle"
    assert router.route("Enable Arthur's virtual keyboard").action == "keyboard_toggle"
    assert router.route("Switch on the air keyboard").action == "keyboard_toggle"


def test_calendar_create_reads_back_inserted_event_before_claiming_verified():
    event_resource = Mock()
    inserted = {
        "id": "event-123", "summary": "Review", "start": {"dateTime": "2026-11-20T10:00:00+05:30"},
        "end": {"dateTime": "2026-11-20T10:30:00+05:30"}, "htmlLink": "https://calendar.google.com/event?eid=123",
    }
    event_resource.insert.return_value.execute.return_value = inserted
    event_resource.get.return_value.execute.return_value = inserted
    service = types.SimpleNamespace(events=lambda: event_resource)

    with patch.object(google_workspace, "_service", return_value=service):
        result = google_workspace.calendar_create_event(
            "Review", "2026-11-20T10:00:00", "2026-11-20T10:30:00", "Asia/Kolkata", confirmed=True,
        )

    assert result["verified"] == "true"
    assert result["id"] == "event-123"
    event_resource.get.assert_called_once_with(calendarId="primary", eventId="event-123")


def test_calendar_insert_without_successful_readback_is_not_reported_as_verified():
    event_resource = Mock()
    inserted = {"id": "event-456", "summary": "Review", "start": {}, "end": {}}
    event_resource.insert.return_value.execute.return_value = inserted
    event_resource.get.return_value.execute.side_effect = RuntimeError("read denied")
    service = types.SimpleNamespace(events=lambda: event_resource)

    with patch.object(google_workspace, "_service", return_value=service):
        result = google_workspace.calendar_create_event(
            "Review", "2026-11-20T10:00:00", "2026-11-20T10:30:00", "Asia/Kolkata", confirmed=True,
        )

    assert result["verified"] == "false"
    assert "read denied" in result["verification_error"]


def test_gui_enter_allows_unidentified_safe_search_field_but_not_unconfirmed_composer():
    user32 = types.SimpleNamespace(
        IsWindow=lambda hwnd: hwnd == 123,
        GetForegroundWindow=lambda: 123,
        GetWindowTextLengthW=lambda hwnd: len("Google Drive"),
        GetWindowTextW=lambda hwnd, buffer, size: setattr(buffer, "value", "Google Drive"),
    )
    pyautogui = types.ModuleType("pyautogui")
    pyautogui.FAILSAFE = False
    calls = []
    pyautogui.press = lambda key: calls.append(key)
    with patch("visionguide.integrations.gui_automation.os.name", "nt"), \
         patch.object(ctypes, "windll", types.SimpleNamespace(user32=user32), create=True), \
         patch("visionguide.integrations.gui_automation.capture_focused_control_identity", return_value=None), \
         patch.dict(sys.modules, {"pyautogui": pyautogui}):
        result = submit_typed_field(123, "Google Drive", "google drive", "search box", None)
        assert "Pressed Enter" in result
        with pytest.raises(RuntimeError, match="without confirmation"):
            submit_typed_field(123, "Google Drive", "whatsapp", "message box", None)
        submit_typed_field(123, "Google Drive", "whatsapp", "message box", None, confirmed_submission=True)
    assert calls == ["enter", "enter"]


def test_geocode_error_exposes_google_provider_diagnostic():
    class FakeResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"status": "REQUEST_DENIED", "error_message": "API key not authorized"}

    from visionguide.integrations.google_services import GoogleMapsServices
    with patch("visionguide.integrations.google_services.requests.get", return_value=FakeResponse()):
        service = GoogleMapsServices(api_key="test-key", cache_path=Path("/tmp") / "arthur-geocode-regression.sqlite3")
        with pytest.raises(RuntimeError) as error:
            service.geocode("Kolkata")
    assert "API key not authorized" in str(error.value)
    assert "Geocoding API" in str(error.value)


def test_product_lookup_uses_fresh_camera_frame_and_depth_decorated_detections():
    frame = np.zeros((24, 32, 3), dtype=np.uint8)
    detection = Detection("bottle", 0.88, 1, 2, 20, 22, 10, 12, "center")
    decorated = Detection("bottle", 0.88, 1, 2, 20, 22, 10, 12, "center", distance_m=0.8)
    calls = {}

    class FakeDepth:
        def decorate(self, items):
            assert items == [detection]
            return [decorated]
        def snapshot(self):
            return {}, "Metric depth active", "estimated range only"

    app = object.__new__(ArthurApp)
    app._pending_field_context = None
    app._camera_snapshot_for_task = lambda wait_for_detection: (frame, [detection])
    app.depth_worker = FakeDepth()
    app._ask_yes_no = lambda *_args, **_kwargs: True
    app._research_visible_item = lambda *args: calls.setdefault("research_args", args) or "researched"
    app._run_async = lambda action, function: calls.update(action=action, result=function())
    app._set_output = lambda value: calls.setdefault("output", value)
    app._say = lambda value: calls.setdefault("spoken", value)

    from visionguide.semantic_router import RoutedCommand
    ArthurApp._dispatch_routed_command_impl(
        app, "Tell me about this bottle", RoutedCommand("product_lookup", {"query": "Tell me about this bottle"})
    )

    assert calls["action"] == "product_lookup"
    received_frame, query, received_detections, depth_status, depth_error = calls["research_args"]
    assert received_frame is frame
    assert query == "Tell me about this bottle"
    assert received_detections == [decorated]
    assert depth_status == "Metric depth active"
    assert depth_error == "estimated range only"


def test_api_calendar_listing_defaults_to_thirty_days():
    from visionguide import api_server
    from visionguide.semantic_router import RoutedCommand

    with patch.object(api_server, "calendar_upcoming", return_value=[]) as listing:
        result = api_server.execute_route(RoutedCommand("calendar_upcoming", {}))
    assert result["status"] == "ok"
    listing.assert_called_once_with(30, 20)

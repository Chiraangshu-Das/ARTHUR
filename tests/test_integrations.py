import threading
import unittest

from visionguide.semantic_router import SemanticCommandRouter
from visionguide.integrations.timers import TimerManager
from visionguide.integrations.google_workspace import _extract_message_body, _validate_email, gmail_send_draft
from visionguide.integrations.gui_automation import compose_gmail_gui
from visionguide.integrations.system_controls import media_playback, set_brightness


class SemanticRoutingIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.router = SemanticCommandRouter(enable_local_semantic=False)

    def test_site_aliases_route_to_same_tool(self):
        a = self.router.route("Open YouTube")
        b = self.router.route("Take me to YouTube")
        self.assertEqual((a.action, a.arguments), (b.action, b.arguments))
        self.assertEqual(a.action, "open_website")

    def test_brightness_absolute_and_relative(self):
        self.assertEqual(self.router.route("Set brightness to 45 percent").arguments["level"], 45)
        self.assertEqual(self.router.route("Make the screen brighter").arguments["delta"], 10)

    def test_volume_relative_and_absolute(self):
        self.assertEqual(self.router.route("Set volume to 25 percent").arguments["level"], 25)
        self.assertEqual(self.router.route("Turn the volume down").arguments["delta"], -10)

    def test_mute_unmute(self):
        self.assertTrue(self.router.route("Mute audio").arguments["muted"])
        self.assertFalse(self.router.route("Unmute audio").arguments["muted"])

    def test_wifi_state_requires_explicit_command(self):
        self.assertFalse(self.router.route("Turn Wi-Fi off").arguments["enabled"])
        self.assertTrue(self.router.route("Turn on Wi-Fi").arguments["enabled"])

    def test_timer_duration_words_and_digits(self):
        self.assertEqual(self.router.route("Set a timer for five minutes").arguments["seconds"], 300)
        self.assertEqual(self.router.route("Remind me in 2 hours").arguments["seconds"], 7200)

    def test_media_skip(self):
        routed = self.router.route("Skip ahead 30 seconds")
        self.assertEqual(routed.action, "media_playback")
        self.assertEqual(routed.arguments["action"], "forward")
        self.assertEqual(routed.arguments["seconds"], 30)

    def test_unread_mail_read_body_intent(self):
        routed = self.router.route("Read my unread emails")
        self.assertEqual(routed.action, "gmail_unread")
        self.assertTrue(routed.arguments["include_body"])


class TimerManagerTests(unittest.TestCase):
    def test_cancel_timer(self):
        manager = TimerManager()
        try:
            record = manager.schedule(5, "cancel me")
            self.assertTrue(manager.cancel(record.timer_id))
            self.assertFalse(manager.cancel(record.timer_id))
            self.assertEqual(manager.list_timers(), [])
        finally:
            manager.close()

    def test_expiry_callback_runs(self):
        fired = threading.Event()
        seen = []
        manager = TimerManager(lambda timer_id, label: (seen.append((timer_id, label)), fired.set()))
        try:
            record = manager.schedule(1, "test timer")
            self.assertTrue(fired.wait(2.5))
            self.assertEqual(seen, [(record.timer_id, "test timer")])
            self.assertEqual(manager.list_timers(), [])
        finally:
            manager.close()

    def test_invalid_timer_duration(self):
        manager = TimerManager()
        try:
            with self.assertRaises(ValueError):
                manager.schedule(0)
        finally:
            manager.close()


class ProviderAndSafetyTests(unittest.TestCase):
    def test_email_address_validation(self):
        self.assertEqual(_validate_email("person@example.com"), "person@example.com")
        with self.assertRaises(ValueError):
            _validate_email("one@example.com, two@example.com")

    def test_body_extraction_from_plain_text(self):
        import base64
        text = "Hello Arthur"
        data = base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")
        self.assertEqual(_extract_message_body({"mimeType": "text/plain", "body": {"data": data}}), text)

    def test_gmail_send_requires_explicit_confirmation(self):
        with self.assertRaises(PermissionError):
            compose_gmail_gui("person@example.com", "Subject", "Body", send=True, confirmed_send=False)

    def test_gmail_api_draft_changed_after_preview_is_not_sent(self):
        from unittest.mock import patch
        current = {"draft_id": "draft1", "to": "person@example.com", "subject": "Changed", "body": "New body", "fingerprint": "new-fingerprint"}
        with patch("visionguide.integrations.google_workspace._get_gmail_draft", return_value=current), \
             patch("visionguide.integrations.google_workspace._service") as service:
            with self.assertRaisesRegex(RuntimeError, "changed after the confirmation preview"):
                gmail_send_draft("draft1", confirmed=True, expected_fingerprint="old-fingerprint")
            service.assert_not_called()

    def test_invalid_media_action_is_rejected_before_gui_import(self):
        with self.assertRaises(ValueError):
            media_playback("delete all videos")

    def test_invalid_brightness_level_is_rejected(self):
        with self.assertRaises(ValueError):
            set_brightness(101)


if __name__ == "__main__":
    unittest.main()

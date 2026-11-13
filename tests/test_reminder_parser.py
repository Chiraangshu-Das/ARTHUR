from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from visionguide.semantic_router import SemanticCommandRouter


class ReminderCommandRoutingTests(unittest.TestCase):
    def setUp(self):
        self.router = SemanticCommandRouter(enable_local_semantic=False)

    def test_tomorrow_at_time_routes_to_one_time_reminder(self):
        now = datetime(2026, 11, 13, 18, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        args = self.router._parse_reminder_request(
            "Remind me to call Alex tomorrow at 9 AM.", now=now
        )
        self.assertEqual(args["label"], "call Alex")
        self.assertEqual(args["recurrence"], "none")
        self.assertEqual(datetime.fromisoformat(args["due_at"]).day, 14)
        routed = self.router.route("Remind me to call Alex tomorrow at 9 AM.")
        self.assertEqual(routed.action, "reminder_schedule")

    def test_next_monday_means_the_next_upcoming_monday(self):
        now = datetime(2026, 11, 13, 18, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        args = self.router._parse_reminder_request("Remind me next Monday at 9 AM", now=now)
        self.assertEqual(datetime.fromisoformat(args["due_at"]).date().isoformat(), "2026-11-16")

    def test_daily_and_weekly_recurrence(self):
        now = datetime(2026, 11, 13, 7, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        daily = self.router._parse_reminder_request("Remind me to study every day at 8 AM", now=now)
        weekly = self.router._parse_reminder_request("Remind me every Monday at 9 AM", now=now)
        self.assertEqual(daily["recurrence"], "daily")
        self.assertEqual(daily["label"], "study")
        self.assertEqual(weekly["recurrence"], "weekly")
        self.assertEqual(datetime.fromisoformat(weekly["due_at"]).weekday(), 0)

    def test_weekday_recurrence(self):
        now = datetime(2026, 11, 13, 7, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        args = self.router._parse_reminder_request("Remind me to study every weekday at 8 AM", now=now)
        self.assertEqual(args["recurrence"], "weekdays")
        self.assertEqual(datetime.fromisoformat(args["due_at"]).weekday(), 4)

    def test_set_reminder_does_not_leave_a_spurious_for_label(self):
        now = datetime(2026, 11, 13, 18, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        args = self.router._parse_reminder_request("Set a reminder for tomorrow at 9 AM", now=now)
        self.assertEqual(args["label"], "Reminder")

    def test_countdown_remains_timer(self):
        routed = self.router.route("Remind me in five minutes")
        self.assertEqual(routed.action, "timer_set")
        self.assertEqual(routed.arguments["seconds"], 300)

    def test_reminder_listing_and_cancellation(self):
        self.assertEqual(self.router.route("Show my reminders").action, "reminder_list")
        cancelled = self.router.route("Cancel reminder number 3")
        self.assertEqual(cancelled.action, "reminder_cancel")
        self.assertEqual(cancelled.arguments["id"], 3)


if __name__ == "__main__":
    unittest.main()

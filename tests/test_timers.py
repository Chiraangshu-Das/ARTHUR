from __future__ import annotations

import threading
import time
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from tempfile import TemporaryDirectory

from visionguide.integrations.timers import TimerManager


class PersistentTimerManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "scheduler.sqlite3"
        self.managers: list[TimerManager] = []

    def tearDown(self) -> None:
        for manager in self.managers:
            manager.close()
        self.temp_dir.cleanup()

    def manager(self, callback=None, *, channel="desktop", poll_interval=0.05):
        manager = TimerManager(
            callback,
            db_path=self.db_path,
            channel=channel,
            poll_interval=poll_interval,
        )
        self.managers.append(manager)
        return manager

    def test_timer_survives_manager_restart(self):
        first = self.manager()
        record = first.schedule(120, "Persist me")
        first.close()

        second = self.manager()
        active = second.list_timers()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["id"], record.timer_id)
        self.assertEqual(active[0]["label"], "Persist me")
        self.assertGreater(active[0]["remaining_seconds"], 0)
        self.assertTrue(second.cancel(record.timer_id))

    def test_desktop_and_api_receive_independent_deliveries(self):
        desktop_events: list[tuple[int, str]] = []
        api_events: list[tuple[int, str]] = []
        desktop_ready = threading.Event()
        api_ready = threading.Event()

        desktop = self.manager(
            lambda timer_id, label: (desktop_events.append((timer_id, label)), desktop_ready.set()),
            channel="desktop",
        )
        api = self.manager(
            lambda timer_id, label: (api_events.append((timer_id, label)), api_ready.set()),
            channel="api",
        )
        record = desktop.schedule(1, "Shared reminder")

        self.assertTrue(desktop_ready.wait(4))
        self.assertTrue(api_ready.wait(4))
        self.assertEqual(desktop_events, [(record.timer_id, "Shared reminder")])
        self.assertEqual(api_events, [(record.timer_id, "Shared reminder")])

    def test_scheduled_daily_reminder_advances_after_delivery(self):
        events: list[tuple[int, str]] = []
        delivered = threading.Event()
        manager = self.manager(
            lambda timer_id, label, kind: (events.append((timer_id, label, kind)), delivered.set())
        )
        due = datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(seconds=2)
        record = manager.schedule_at(
            due.replace(tzinfo=None).isoformat(timespec="microseconds"),
            "Daily stand-up",
            timezone_name="Asia/Kolkata",
            recurrence="daily",
        )

        self.assertTrue(delivered.wait(4))
        self.assertEqual(events, [(record.timer_id, "Daily stand-up", "reminder")])
        listed = manager.list_schedules()
        current = next(item for item in listed if item["id"] == record.timer_id)
        self.assertEqual(current["recurrence"], "daily")
        self.assertEqual(current["status"], "pending")
        self.assertGreater(current["remaining_seconds"], 60 * 60 * 20)

    def test_cancel_prevents_delivery(self):
        events: list[tuple[int, str]] = []
        manager = self.manager(lambda timer_id, label: events.append((timer_id, label)))
        record = manager.schedule(1, "Cancel me")
        self.assertTrue(manager.cancel(record.timer_id))
        time.sleep(1.2)
        self.assertEqual(events, [])

    def test_invalid_time_zone_and_past_time_are_rejected(self):
        manager = self.manager()
        with self.assertRaises(ValueError):
            manager.schedule_at(datetime.now() + timedelta(hours=1), timezone_name="Mars/Olympus")
        with self.assertRaises(ValueError):
            manager.schedule_at(datetime.now() - timedelta(minutes=1))


if __name__ == "__main__":
    unittest.main()

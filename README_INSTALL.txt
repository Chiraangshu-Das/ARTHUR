ARTHUR — Persistent Reminder Integration Patch
================================================

This patch is built against the ARTHUR-main source archive supplied for this
conversation. It updates only the scheduler, API, semantic router, desktop
notification handler, and scheduler/router tests.

WHAT IT ADDS
------------
1. Natural-language one-time reminders, for example:
   - "Remind me to call Alex tomorrow at 9 AM."
   - "Set a reminder for tomorrow at 9 AM."
2. Daily, weekly, and weekday-only recurring reminders:
   - "Remind me to study every day at 8 AM."
   - "Remind me every Monday at 9 AM."
   - "Remind me to study every weekday at 8 AM."
3. Reminder listing and cancellation:
   - "Show my reminders."
   - "Cancel reminder number 3."
4. Countdown separation:
   - "Remind me in five minutes." remains a countdown timer.
5. Desktop notifications distinguish "Reminder ... is due" from
   "Timer ... finished" and speak both through the existing speech output.
6. API reminder cancellation is restricted to reminder records, so a reminder
   ID cannot accidentally cancel a countdown timer.
7. Weekday recurrence skips Saturdays and Sundays. Existing scheduler databases
   are upgraded through an additive SQLite column migration.

INSTALLATION
------------
1. Extract this ZIP directly into the ARTHUR project root. You should then have:
   ARTHUR\arthur_reminder_integration_patch\install_patch.ps1
2. Open PowerShell in the ARTHUR project root (the folder containing main.py).
3. Run:

   powershell -ExecutionPolicy Bypass -File .\arthur_reminder_integration_patch\install_patch.ps1

The installer creates timestamped .bak backups beside every existing file it
replaces. It does not modify .env, credentials, or unrelated project files.

VALIDATION
----------
Run the focused tests first:

   python -m pytest tests\test_timers.py tests\test_reminder_parser.py -q

Then run the full project suite:

   python -m pytest -q

The uploaded source plus this patch passed:
   - py_compile for timers.py, api_server.py, semantic_router.py, and app.py
   - 180 passed, 5 subtests passed, 4 warnings in the full pytest suite

The warnings are existing FastAPI on_event deprecation warnings. No test failed.

TIME ZONE
---------
The parser defaults to Asia/Kolkata and respects VISIONGUIDE_TIMEZONE when set.
On Windows, Python's zoneinfo database may require tzdata. The project's
requirements-integrations.txt already declares tzdata; install it only if you
see a ZoneInfoNotFoundError:

   python -m pip install tzdata

NOTES
-----
- The desktop and API continue sharing the scheduler SQLite database at the
  configured ARTHUR_SCHEDULE_DB path, or data\arthur_schedule.sqlite3 by default.
- Reminders are local scheduler records, not Google Calendar events.
- Existing countdown timer commands and APIs remain available.
- The deterministic parser handles common spoken English date/time phrases.
  More unusual wording/date formats can still be routed through Groq's typed
  reminder_schedule function when Groq is configured.

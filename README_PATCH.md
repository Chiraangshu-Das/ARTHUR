# ARTHUR persistent timers and scheduled reminders

This patch replaces the in-memory timer store with a SQLite-backed scheduler while keeping the existing `TimerManager.schedule()`, `cancel()`, `list_timers()` and `close()` interface.

## Files in this patch

- `visionguide/integrations/timers.py` — persistent countdowns, one-time reminders, daily/weekly recurrence, restart recovery, and separate desktop/API notification deliveries.
- `visionguide/api_server.py` — API timer manager uses the `api` delivery channel and exposes reminder endpoints plus internal reminder route handlers.
- `tests/test_timers.py` — persistence, cancellation, recurrence, timezone validation, and cross-channel notification tests.

`api_server.py` was prepared against the complete version you pasted in this conversation. Back up the current file before replacing it.

## Install

From the ARTHUR project root in the activated `.venv`:

```powershell
python -m pip install tzdata
```

`tzdata` supplies IANA time-zone definitions on Windows for `zoneinfo`, including `Asia/Kolkata`.

Copy the files into the matching paths, preserving the existing project folders. The new scheduler creates `data\arthur_schedule.sqlite3` automatically. Both the desktop app and API resolve the same default database path from the package location.

To use a custom location, set `ARTHUR_SCHEDULE_DB` in `.env`. The desktop and API processes must use the same path.

## Verify

```powershell
python -m pytest tests\test_timers.py -q
python -m py_compile visionguide\integrations\timers.py visionguide\api_server.py
```

The five scheduler tests included here passed in the patch-building environment. This is not a run of the full ARTHUR test suite.

## API usage

Create a reminder (naive date-times are interpreted in the requested time zone):

```powershell
$body = @{
    due_at = "2026-11-14T09:00:00"
    label = "Team meeting"
    timezone_name = "Asia/Kolkata"
    recurrence = "none" # none, daily, or weekly
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/reminders" `
  -ContentType "application/json" `
  -Headers @{ Authorization = "Bearer $env:VISIONGUIDE_API_TOKEN" } `
  -Body $body
```

List pending reminders:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/reminders" `
  -Headers @{ Authorization = "Bearer $env:VISIONGUIDE_API_TOKEN" }
```

Cancel a reminder by its returned numeric ID:

```powershell
Invoke-RestMethod -Method Delete `
  -Uri "http://127.0.0.1:8000/api/v1/reminders/1" `
  -Headers @{ Authorization = "Bearer $env:VISIONGUIDE_API_TOKEN" }
```

The API WebSocket emits `reminder_due` for scheduled reminders and retains `timer_expired` for countdown timers. Desktop deliveries are independent. To let the desktop handler distinguish the two cleanly, make these two targeted edits in `visionguide\app.py`.

Change the existing TimerManager construction from a two-argument callback to:

```python
self.timer_manager = TimerManager(
    lambda timer_id, label, kind: self._async_messages.put(
        ("timer_expired", (timer_id, label, kind))
    )
)
```

Then change the `timer_expired` branch in `_drain_async_messages` to:

```python
elif action == "timer_expired":
    timer_id, label, kind = result
    if kind == "reminder":
        message = f"Reminder: {label}."
        self.status_var.set("Reminder due")
    else:
        message = f"Timer {timer_id} finished: {label}."
        self.status_var.set("Timer completed")
    self._append_output(message)
    self._say(message, priority=True)
```

## Remaining voice-router integration

The timer engine, desktop delivery callback contract, and API endpoints are implemented here. Natural-language voice routing for phrases such as “remind me tomorrow at nine” still needs targeted edits to `semantic_router.py` and the desktop command dispatcher. Those source sections were not included in the code you pasted, so I have not guessed their surrounding implementation. The next source-extraction command is included in the chat response.

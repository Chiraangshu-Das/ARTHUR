# Arthur Integrations and Setup

This guide maps each user-visible capability to its source adapter, runtime prerequisites, command flow and validation requirements. All listed modules belong to the project architecture; environment variables and runtime checks control credentials, privacy, operating-system support and permissions.

An integration being present in the source does not guarantee that its external service, model, hardware, account permissions or operating-system dependencies are configured. Follow the relevant setup and validation steps before relying on a capability.

## 1. Gemini function calling and semantic fallback

**Source:** `visionguide/semantic_router.py`, `visionguide/cloud_ai.py`  
**Configuration:** `GEMINI_API_KEY`, `GEMINI_MODEL`, `VISIONGUIDE_TIMEZONE`, `VISIONGUIDE_LOCAL_SEMANTIC`, `VISIONGUIDE_SEMANTIC_MODEL`, `VISIONGUIDE_SEMANTIC_THRESHOLD`.

Routing order:

1. Gemini selects one declared typed function when configured.
2. The existing local command parser handles known deterministic commands.
3. High-value local patterns handle simple brightness, volume, mute, Wi-Fi, timer, playback and unread-mail requests without an embedding model.
4. SentenceTransformers compares unseen paraphrases against registered intent examples.
5. If no local intent matches, desktop text-only fallback asks the user before sending the transcript to Gemini. The API client presents a confirmation before a text-only Gemini request.

The router uses `automatic_function_calling` disabled: Gemini returns a proposed function call but does not execute local Python. Only registered functions are accepted. Arguments are reduced to primitive JSON types and are checked again by the executor.

The local semantic matcher loads `sentence-transformers/all-MiniLM-L6-v2` on first use when needed. Set `VISIONGUIDE_LOCAL_SEMANTIC=0` to use the parser/pattern path without embedding inference. The first semantic-model load may download model weights unless they are already cached.

For Calendar expressions, `VISIONGUIDE_TIMEZONE` (default `Asia/Kolkata`) and current local date/time are sent as routing context. If a user omits key event details, ask a follow-up rather than inventing recipients, event titles or dates.

## 2. Speech input and transcription

**Source:** `visionguide/voice_commands.py`, `visionguide/api_server.py`, `clients/flutter/lib/main.dart`  
**Packages:** `openai-whisper`, `sounddevice`, `numpy`, FFmpeg; Flutter `speech_to_text`, `record`, `path_provider`.

On Windows, use the explicit voice-command capture button or the locally armed wake-word feature. `record_and_transcribe()` records a bounded interval at 16 kHz and sends it to local Whisper inference. `transcribe_audio_file()` reuses a cached Whisper model for a supplied audio path.

The API `POST /api/v1/transcribe` accepts multipart audio and permits WAV, MP3, M4A, WebM, OGG, FLAC, MP4 or MPEG-family extensions up to 20 MB. It writes a temporary file, runs Whisper on the server machine, deletes the temporary file, and returns the transcript. This endpoint does not send audio to Gemini.

The mobile app's standard device-speech button uses the mobile speech plugin; the separate “Record for Whisper” path sends the audio to the configured device API for local Whisper processing. In this context, *local* means local to the machine running the API, not necessarily the phone.

The wake-word detector and the explicit recording/transcription path are separate components. The wake-word model must be compatible with openWakeWord and configured through `WAKE_WORD_MODEL`. Verify the actual model filename, wake phrase, conversation timeout and recording behaviour against the installed implementation. Do not assume that enabling wake-word detection automatically validates continuous conversation or a particular chunk duration.

## 3. Browser and Windows controls

**Source:** `visionguide/integrations/system_controls.py`, `visionguide/desktop_actions.py`  
**Packages:** `pyautogui`, `pygetwindow`, `screen-brightness-control`, `pycaw`, `comtypes`.

### Browser playback

`media_playback(action, seconds)` activates an existing browser window matching YouTube/browser keywords, then uses YouTube keyboard shortcuts:

| Action | Shortcut behaviour |
|---|---|
| `play`, `pause`, `toggle` | Press `K` to toggle player state |
| `stop` | Press `K`; stop is implemented as pause |
| `next` / `previous` | `Shift+N` / `Shift+P` |
| `forward` / `back` | Repeat `L` / `J` in approximate ten-second increments |

Playback depends on the player page being open and focused. The browser adapter does not query a definitive playback state. If the shortcut did not affect the video, focus the player and retry.

### Display brightness

`get_brightness()`, `set_brightness(level)`, and `adjust_brightness(delta)` use `screen-brightness-control`. Levels are bounded 0–100; relative changes are limited to ±50 percentage points. The display driver/monitor must expose controllable brightness. A returned provider value is a request/result, not calibrated luminance in nits.

### System audio

`get_volume()`, `set_volume(level)`, `adjust_volume(delta)`, and `set_mute(muted)` use Pycaw/COM and Windows Core Audio. Master output volume is reported as a 0–100 scalar and mute state as a boolean. These functions intentionally fail with a clear OS support error on non-Windows systems.

### Wi-Fi adapter

`list_wifi_adapters()` parses `netsh interface show interface`; `set_wifi(enabled, adapter)` verifies the requested adapter name is present before running `netsh interface set interface`. Configure `VISIONGUIDE_WIFI_ADAPTER` when the interface is not named `Wi-Fi`.

The caller must confirm before state changes, and an elevated process may be required. The OS response can confirm the command was accepted, but connectivity should still be checked afterward.

## 4. GUI automation and multistep workflows

**Source:** `visionguide/integrations/gui_automation.py`, `visionguide/app.py`, `visionguide/api_server.py`  
**Packages:** `pyautogui`, `pygetwindow`, `pyperclip`.

The executor targets an allowlist of known windows. `activate_window()` finds a title by keyword and restores/activates the window. `type_into_window()` pastes text only into Gmail, Word, WhatsApp Web, Google Docs, Notepad or VS Code; it never submits the text. PyAutoGUI's emergency corner failsafe stays enabled.

### Gmail GUI compose

`compose_gmail_gui(recipient, subject, body, send=False)` validates a single email address, opens Gmail, activates a Gmail window, uses the Gmail `C` keyboard shortcut, enters recipient/subject/body by clipboard paste, and leaves the compose window open for review. Enable Gmail keyboard shortcuts in Gmail settings. If the page layout or focus differs, stop and correct the draft instead of continuing blindly.

The desktop command flow can accept an email recipient, subject and writing instructions; it asks before sending those instructions to Gemini, generates a proposed body, and inserts it into Gmail. The separate “send email” action asks the user to verify recipient, subject and body, then issues `Ctrl+Enter`. The result text explicitly says to verify the Sent state; sending a shortcut is not proof of delivery.

The API can create an actual Gmail API draft through `POST /api/v1/workspace/gmail/drafts`. The send endpoint first reads the draft and returns its recipient, subject and body preview together with a one-use confirmation token. On confirmation, the server re-reads the draft and compares a fingerprint of recipient, subject and full body before sending; if the draft changed after preview, sending is rejected and the user must review it again.

### Word

`word_write_document(text)` launches Word, creates a new document and pastes the text. It does not save or share the document. The user must review and save it.

### WhatsApp Web

`compose_whatsapp_gui(contact, message, send=False)` opens WhatsApp Web, invokes the New Chat shortcut, types the contact search and message, and leaves the message unsent. The visible conversation may be selected incorrectly if the web UI or search timing differs. Verify the chat title and complete message before using “send WhatsApp message.” The send helper cannot run unless its caller provides `confirmed_send=True` after confirmation.

### Workflow sequencing

Compound intents such as “draft an email to this address about this topic” are one registered workflow. Other actions can be chained as consecutive voice commands. High-impact actions remain distinct end steps, and every sequence should inspect the target window and visible result before proceeding. PyAutoGUI keyboard injection is not a transaction and does not guarantee the currently focused widget is the intended one.

## 5. Gmail and Google Calendar API via OAuth 2.0

**Source:** `visionguide/integrations/google_workspace.py`, FastAPI endpoints in `visionguide/api_server.py`  
**Packages:** `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib`.

### Google Cloud setup

1. Enable Gmail API and Google Calendar API in the Cloud project.
2. Configure the OAuth consent screen and authorised test users/audience.
3. Create a Desktop App OAuth client and download its JSON.
4. Place it at `credentials/google_oauth_client.json`, or set `GOOGLE_OAUTH_CLIENT_FILE`.
5. Use a Gmail/Calendar command to open the installed-app OAuth flow and grant the requested scopes.

The core Gmail/Calendar token requests only these scopes:

- Gmail read: `https://www.googleapis.com/auth/gmail.readonly`
- Gmail compose: `https://www.googleapis.com/auth/gmail.compose`
- Gmail send: `https://www.googleapis.com/auth/gmail.send`
- Calendar event read: `https://www.googleapis.com/auth/calendar.events.readonly`
- Calendar event create/update: `https://www.googleapis.com/auth/calendar.events`

Workspace operations use separate per-feature OAuth token files in `data/google_tokens/`; they do not silently expand the core Gmail/Calendar token. The full list of mapped operations, feature-specific scopes and product/API limits is in `GOOGLE_SCOPE_FEATURE_MATRIX.md`. Each profile requests consent only when a matching operation is first used. A scope change may require a fresh consent flow; tokens must never be copied into source control or sent to anyone.

Google Cloud Console API enablement is separate from OAuth scope configuration. Enable the relevant service API for each feature (Drive API, Docs API, Sheets API, Slides API, Tasks API, People API, Classroom API, Meet REST API, YouTube Data API v3, Forms API, Cloud Translation API, and Cloud Natural Language API). Only request scope profiles for features you intend to use.

The Google Auth Platform scope catalogue is not a list of features that already work, and you should not request add-on-only, administration, deletion, broad Drive, or Meet media-capture scopes for this desktop app unless a future feature specifically needs them.

### Gmail operations

- `gmail_unread(limit, include_body=False)`: unread message summary metadata; body retrieval when requested is limited per message.
- `gmail_search(query, limit)`: Gmail search syntax (for example `from:professor newer_than:30d`).
- `gmail_read_message(message_id)`: returns a single message's metadata and decoded body.
- `gmail_create_draft(to, subject, body)`: creates a named Gmail draft using the API.
- `gmail_send_draft(draft_id, confirmed=True)`: sends the specified draft only when the caller explicitly confirms it.

Email helpers accept one validated recipient for the supported GUI draft path; multi-recipient handling should be added deliberately rather than inferred from a spoken string. Full email bodies are not written to routine logs.

### Calendar operations

- `calendar_upcoming(days, limit)`: upcoming events from the primary calendar.
- `calendar_search(query, days)`: searches event metadata using Calendar `q`.
- `calendar_create_event(summary, start, end, timezone_name, ..., confirmed=True)`: validates title bounds, ISO 8601 time, IANA timezone, start/end ordering and duration before writing.

The desktop flow shows title, start, end, timezone and location in its confirmation dialog. The API event endpoint returns a one-use, device-bound confirmation token. Only a confirmation request for that token executes the event write. Calendar event creation has no attendees/recurrence support in the present adapter.

## 6. Timers and reminders

**Source:** `visionguide/integrations/timers.py`, `visionguide/app.py`, `visionguide/api_server.py`.

`TimerManager` uses `threading.Timer` with bounded 1-second to 7-day durations, `time.monotonic()` deadlines, thread-safe state, unique IDs, cancellation, listing, and graceful shutdown. Desktop expiry events are marshalled through an async message queue. API expiry events are published to connected clients using `WS /ws/notifications`.

These are volatile process-local countdowns. They do not survive app/server restarts. Google Calendar writes are the separate integration for events that need to persist.

## 7. Unified system-wide air virtual keyboard and hand gestures

**Source:** `visionguide/system_virtual_keyboard.py`, `visionguide/gesture_mouse.py`, `visionguide/app.py`  
**Packages:** `mediapipe`, `pyautogui`, `pygetwindow`.

Download the supported Hand Landmarker task file with `python tools/download_hand_model.py`; it is saved to `models/hand_landmarker.task`.

There is one visible virtual keyboard: the system-wide air virtual keyboard. Mouse clicks select keys; the hand-gesture pointer and pinch-click can select the same keys; voice commands such as “type exactly hello world” paste literal text into a currently focused Windows field after confirmation and a short focus-selection delay.

The keyboard supports letters, numbers, symbols via Shift, Space, Tab, Enter, Backspace, Caps Lock, modifiers, function keys and navigation. The topmost overlay attempts to use Windows `WS_EX_NOACTIVATE` so key clicks do not steal focus from the target app. This behaviour must be verified on the target Windows build/application; UI automation cannot reliably verify all custom fields.

`GestureMouse` maps index-tip movement to the system cursor with smoothing, uses thumb-index pinch for a debounced click, reserves the rightmost 18% of the mirrored camera frame for vertical scrolling, and detects horizontal swipes across a short time window to change browser tabs.

Since pointer control is globally active while enabled, disable it before entering credentials or using payment/administrative UIs. PyAutoGUI's emergency corner failsafe remains active.

## 8. Google Maps Platform, Weather API and public visual search

**Source:** `visionguide/integrations/google_services.py`, `visionguide/navigation.py`, `visionguide/app.py`.

`GoogleMapsServices` uses `GOOGLE_MAPS_API_KEY` only for Maps Platform calls: Geocoding, Weather, Routes, Places API (New), Air Quality, Pollen forecasts, Time Zone, Roads snap-to-road, and explicitly authorized network geolocation. Places requests use a narrow response field mask; place/air-quality/time-zone lookups are cached locally, and weather/pollen caches use shorter-lived data.

Daily usage caps and a SQLite counter under `data/cache/` reduce accidental loops; caps are application-side only and do not replace Cloud quotas/budgets. Geolocation uploads Wi-Fi identifiers only when `consent_confirmed=True`; the module does not collect Wi-Fi identifiers itself.

Cloud Vision Web Detection uses the separately restricted `GOOGLE_CLOUD_API_KEY` or `GOOGLE_VISION_API_KEY`; do not expect a Maps-only restricted key to work for Vision. Cloud Translation and Cloud Natural Language use separate OAuth scope profiles (`cloud-translation` and `cloud-language`) and do not use the Gemini API key. Enable Cloud Vision API only if image web-detection is required; enable Cloud Translation/Natural Language API in the OAuth project's Cloud project before using those actions. Their text inputs are sent to Google for processing but are not cached by this module.

The current Python desktop app does not embed Maps JavaScript, Android/iOS SDKs, Maps Embed, or Map Tiles renderers; those APIs are for browser/mobile/map-renderer clients rather than an ordinary Python REST adapter. The route preview opens a Google Maps URL, not an in-app SDK. Enable only the APIs needed by the client actually using them, restrict each key by API and application type, activate billing if required, and set quota/budget alerts. Verify current pricing and regional availability before relying on an endpoint.

`NavigationSession` asks for Windows Runtime device location, speaks provider maneuver instructions, and recalculates after repeated route deviation. It opens a Google Maps route preview as well, but that browser preview is not a native in-app navigation SDK. Install `requirements-navigation.txt`, enable Windows Location and grant permission. GPS availability, route coverage, maneuver timing and rerouting need testing on the target Windows machine. This is best-effort prototype guidance, not a certified navigation or road-safety system.

Camera-based product/visual search asks for explicit approval before the selected image goes to Gemini and Cloud Vision. Visual search can return public pages and similar-image leads; it is not identity verification. OCR text can be noisy, and product specifications should be checked against manufacturer sources/manuals.

### Additional supported Google APIs

- **Places API (New):** text search by query, optional named-location bias, minimal fields, one-hour cache.
- **Air Quality API / Pollen API / Time Zone API / Roads API:** explicit lookup functions with bounded inputs and per-day request caps; pollen requests are limited to the API's five-day maximum and road snapping accepts at most 100 points.
- **Geolocation API:** callable only with explicitly supplied Wi-Fi access-point records and an explicit consent flag. It does not scrape nearby network identifiers from Windows.
- **Cloud Translation / Cloud Natural Language:** translate text or analyze sentiment/entities/syntax/categories using separate OAuth profiles; private text is not saved to local cache by these adapters.
- **Drive, Docs, Sheets, Slides, Tasks, People/Contacts, Classroom, Meet, YouTube, Forms:** supported read operations and selected create/update operations are exposed through `google_workspace_feature`. All external writes (Docs/Slides/Forms creation, Sheets updates, Tasks creation, Meet-space creation and Calendar event creation) require explicit client confirmation. Sheet writes use `RAW` input to avoid executing text as formulas, and the read/write limits are bounded.

The adapters are implemented but actual access still depends on enabling the associated API in the Cloud project, configuring the applicable OAuth scope profile in Google Auth Platform, completing the first-run consent flow, and having permission to the requested resource. Classroom roles/education domain, Workspace editions, account settings, API quotas and regional coverage can restrict availability. See `GOOGLE_SCOPE_FEATURE_MATRIX.md` for the exact boundary between implemented REST operations and runtime- or approval-gated product features.

The web launcher has fixed destinations for Google Cloud Console, Neon, Google Classroom/Contacts, LeetCode, LinkedIn Learning, Coursera, SWAYAM and NPTEL; that launcher allowlist does not grant programmatic API access to those third-party services.

## 9. Local face recognition and preferences

**Source:** `visionguide/face_memory.py`, `visionguide/action_history.py`, `visionguide/app.py`.

OpenCV LBPH remains the baseline local recognizer. If DeepFace is installed and local embeddings can be computed, normalized embeddings are stored locally for consenting enrolled users and compared with the LBPH prediction. If both predictors return different enrolled identities, the result is Unknown rather than a forced match.

DeepFace is optional because it adds large TensorFlow/model dependencies; install `requirements-face.txt` separately if suitable. Recognition thresholds and camera coverage still affect reliability. Enrol one consenting person at a time; multiple visible faces do not trigger a personalized greeting.

Per-profile preferences persist in `data/action_history.sqlite3` and are deleted when the matching profile is deleted. Never use local face recognition to identify strangers from the public web.

## 10. Action history, arithmetic and result follow-ups

`ActionHistory` records a bounded recent list of actions/results in SQLite and stores profile-specific preferences. “What did you do?” / “What was the result?” retrieves the last stored result without overwriting the result being queried.

A restricted AST arithmetic parser handles basic operations without executing Python or shell input. “Type 2+2=” remains literal input; “calculate 2+2” uses the arithmetic parser; “open Calculator and sum 2+2” launches Calculator and enters the expression while clearly reporting that the displayed Calculator result was not visually verified.

## 11. FastAPI client-server service

Start with `python main.py --serve-api`. The default bind is loopback. Set `VISIONGUIDE_API_TOKEN` before binding to a non-loopback address; the server refuses non-loopback startup without a token. Configure Windows Firewall for a private network and use TLS/authentication for remote deployment.

The service provides a command endpoint, one-time confirmation endpoint, local Whisper upload endpoint (20 MB cap), timer endpoints, Workspace endpoints, and WebSocket timer notifications. Confirmation IDs are random, expire after five minutes, bind to the requesting `device_id`, and are single-use. They protect the exact intent/arguments that the client reviewed.

The Python client at `clients/python/visionguide_client.py` supports health checks, commands, confirmation, timers, Gmail unread/search/read/draft-preview operations, upcoming/search Calendar queries, event preview, and audio-file transcription. Run:

```powershell
python clients/python/visionguide_client.py "open YouTube" --server http://127.0.0.1:8000
```

after starting the API.

## 12. Flutter client

`clients/flutter/lib/main.dart` implements server URL/token fields, health check, WebSocket events, short voice-command transcription via `speech_to_text`, manual command text, recorded WAV upload to `/api/v1/transcribe`, and confirmation dialogs.

A Flutter SDK is needed to generate native platform scaffolding and compile. On Android configure `INTERNET` and `RECORD_AUDIO`; on iOS configure microphone and speech-recognition usage descriptions. Test networking on an actual phone using the host laptop's LAN IP, not `127.0.0.1` from the phone.

The Flutter directory is a client starter, not a signed mobile release. Native platform builds and physical-device behaviour require separate validation.

## 13. ISL

The current integrated ISL implementation is an **isolated-sign video classifier**, not a continuous sentence translator.

### Current model

- **Architecture:** Torchvision Swin3D-S.
- **Classes:** 76 isolated-sign classes.
- **Checkpoint:** `models/isl/swin3d_s/ISL_best_model.pt`.
- **Dataset directory used by the current project workflow:** `data/isl_dataset/ProcessedData_vivit`.
- **Input:** a temporal clip of 32 video frames, not a single still image.
- **Output:** a predicted class label and confidence score for one isolated sign.
- **Processing:** local model inference.

The inference dependencies are listed separately in `requirements-signs.txt`:

```powershell
pip install -r requirements-signs.txt
```

The current Swin3D-S path does not use the previous TensorFlow LSTM model for ISL inference. MediaPipe remains used for hand-gesture control; it is not the current ISL recognition model.

### Continuous ISL development boundary

Continuous sentence-level sign-to-text requires a separate temporal sequence model and decoding pipeline. Text-to-sign is a distinct output adapter. These capabilities should not be described as completed features of the current 76-class isolated-sign classifier.

See `CONTINUOUS_ISL.md` for the proposed architecture and development requirements. Model availability, dataset provenance, signer permissions, held-out signer evaluation, sequence-level metrics, non-manual cues, and confidence/reject behaviour must be addressed before claiming a reliable continuous translation capability.

Offline classifier evaluation does not establish live-camera integration, signer-independent generalization, or real-world translation quality. Validate the camera-to-prediction flow separately on the target Windows machine.
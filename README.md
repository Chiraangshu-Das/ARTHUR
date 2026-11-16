# ARTHUR — Project README

**Documentation date:** 17 November 2026  
**Project:** ARTHUR — Windows desktop assistive AI and device-agent project

### Project overview

ARTHUR stands for Autonomous Reasoning, Thinking, Hearing, Understanding, Responding System which is a local-first Windows desktop assistant with voice interaction, typed semantic command routing, camera-based perception, document/screen workflows, Windows/browser controls, Google Workspace and Maps integrations, user-controlled local preferences, a FastAPI device-agent service, and starter Python/Flutter clients. The desktop application is the reference implementation; connecting a mobile client to the API does not grant it direct control of the phone's hardware or operating system.

Core design principles documented for the project:

- Use local deterministic commands and typed registered tools for actions. Groq proposes a function when configured; local code validates and executes it. Model-generated shell/Python is not executed.
- Keep camera, microphone, screen, face-profile and local-note data on-device unless a particular workflow explicitly needs an external provider. Ask for approval before sending a camera image or screenshot to an external vision service.
- Keep state-changing or externally visible operations behind a separate review/confirmation step. Drafting is distinct from sending; typing is distinct from submitting; editing a document is distinct from saving it.
- Report attempts, provider errors and verified results accurately. A keyboard shortcut being issued is not proof that a message was delivered, a video changed state or a resource was updated.
- Treat depth, navigation, face recognition, object detection and sign recognition as assistive/prototype capabilities with explicit uncertainty—not certified safety, identity or translation systems.

### Windows launch commands

Run these from PowerShell in the ARTHUR project root:

```powershell
cd E:\Chiraangshu\MyWorkspace\ARTHUR
.\.venv\Scripts\Activate.ps1
python main.py
```

Start the FastAPI device-agent service instead of the Tk desktop UI:

```powershell
python main.py --serve-api
```

The documented API development default is `127.0.0.1:8000`; `/docs` provides the local OpenAPI explorer. A non-loopback bind requires `VISIONGUIDE_API_TOKEN`, and a token alone does not make public internet exposure safe. Use firewall restrictions and TLS/authentication for any remote deployment.

The validation report identifies Python 3.11 x64 on Windows as the reference desktop runtime baseline. Some recorded build-container validation runs used Linux/Python 3.13; do not treat those as proof of Windows hardware integration.

### Main source locations

| Path | Main responsibility |
|---|---|
| `main.py` | Desktop entry point or `--serve-api` entry point |
| `visionguide/app.py` | Tk desktop UI, camera/status controls, speech routing, permission prompts and result display |
| `visionguide/semantic_router.py` | Groq function calling, local patterns, parser fallback, embedding similarity and typed routed commands |
| `visionguide/voice_commands.py` | Bounded microphone recording and Whisper transcription |
| `visionguide/scene_commands.py` | Local deterministic command parsing |
| `visionguide/desktop_actions.py` | Allowlisted website and Windows application launchers |
| `visionguide/integrations/system_controls.py` | Browser playback, display brightness, master audio and Wi-Fi adapter control |
| `visionguide/integrations/gui_automation.py` | Window targeting and GUI typing/drafting workflows |
| `visionguide/integrations/google_workspace.py` | Gmail/Calendar and extended Google Workspace API operations/OAuth |
| `visionguide/integrations/google_services.py` | Google Maps Platform, Weather, Routes, Geocoding and Cloud Vision adapters |
| `visionguide/navigation.py` | Windows location provider, spoken route guidance and best-effort rerouting |
| `visionguide/gesture_mouse.py` | MediaPipe pointer, pinch click, scrolling and browser-tab gestures |
| `visionguide/system_virtual_keyboard.py` | Unified system-wide air virtual keyboard |
| `visionguide/face_memory.py` | Local face profiles and optional DeepFace embedding comparison |
| `visionguide/action_history.py` | Bounded local action/result history and per-profile preferences |
| `visionguide/sign_language.py` | Isolated-sign ISL Swin3D-S classifier/inference path |
| `visionguide/api_server.py` | FastAPI request models, authentication, command executor, confirmation store, timers and WebSockets |
| `clients/python/visionguide_client.py` | Python REST client |
| `clients/flutter/lib/main.dart` | Flutter mobile command client starter |

### Current documented capability boundaries

- **Voice and AI:** Whisper transcription; Groq function calling; local deterministic patterns and SentenceTransformers similarity fallback; text-only Groq fallback for unmatched ordinary requests. Recent conversation context is local unless `VISIONGUIDE_SHARE_CONVERSATION_CONTEXT=1` is explicitly enabled.
- **Typing and desktop control:** allowlisted applications/windows, browser shortcuts, clipboard typing, Word/WhatsApp/Gmail draft flows, system brightness/audio and named Wi-Fi adapter controls. Focus and actual UI outcomes require Windows testing.
- **Vision:** local camera/object detection, OCR, scene/product queries, optional Depth Anything V2 metric-depth estimation and consent-gated external image analysis. A local detection or depth estimate is not proof of exact identity, distance or hazard safety.
- **Google services:** OAuth-backed Workspace operations and Maps Platform/Cloud services where APIs, scopes, billing, account permissions and quotas permit. Every write/send/delete/publish action needs its relevant confirmation.
- **Gestures:** opt-in MediaPipe pointer, pinch-click, scroll, browser-tab swipes and unified air keyboard.
- **ISL:** the integrated classifier documented here is a 76-class isolated-sign Swin3D-S video classifier using 32 frames. It is not a continuous sentence-level translator. Continuous ISL-to-text and text-to-ISL are separate future model paths.
- **API/mobile:** FastAPI device agent, Python client and Flutter starter; the API runs actions on the host machine. The Flutter folder is not a signed mobile release.

## Documentation status and important conflicts

The source notes were written across multiple patch/build dates. They contain historical instructions and some descriptions that conflict with later notes. These points are called out so the consolidated README does not accidentally turn an old patch proposal into a claim about the current code:

1. **Speech interruption / AEC:** `SPEECH_INTERRUPTION_GUIDE.md` describes the earlier short-window approach and explicitly says it is not true AEC. The later `AEC_AUDIO_FIX_GUIDE.md` and `AEC_READINESS_CALIBRATION.md` describe the Echoff WASAPI loopback + microphone AEC path and the calibrated readiness gate. Treat the older guide as historical context; verify the currently installed `visionguide/speech.py` and AEC integration before relying on the newer behavior.
2. **Timers/reminders:** `README_PATCH.md` describes a SQLite-backed persistent scheduler and `/api/v1/reminders` endpoints, but `ARCHITECTURE.md`, `COMMAND_CATALOGUE.md` and `ROADMAP.md` describe in-process countdown timers that do not survive application shutdown. The documentation archive alone cannot establish whether the persistent scheduler patch was merged into the live source. Do not claim restart-persistent reminders until the source contains the SQLite scheduler, reminder endpoints and desktop delivery integration and the relevant tests pass.
3. **Local date/time patch:** `arthur_local_datetime.patch` is a separate patch artifact, not applied as part of this README. The included `README.txt` says it was validated for patch-application compatibility and Python syntax against uploaded source snapshots, not executed in the local runtime. Do not delete the patch until local application is confirmed; see the cleanup checklist near the end of this README.
4. **Validation counts:** test counts in the source notes refer to different project snapshots and focused patch suites. They are not additive and must not be combined into one cumulative count. The build-specific full validation report dated 13 November 2026 records 225 passed and 4 warnings; the 16 November reliability note records its own patch validation boundary. Rerun tests on the exact current source before release.
5. **Model assets:** the 16 November reliability notes report that certain weights in the uploaded archive were Git LFS pointer files, not usable model binaries. This is an archive-specific finding and does not prove that the current local `models` folder is still missing weights. Preserve actual `.pt`/`.pth` model checkpoints and verify their size/hash before replacing or deleting them.
6. **Wake phrase:** older notes mention a “Hello Arthur” model while `WAKE_WORD_SETUP.md` specifies “Hey Arthur”. The trained model's trigger phrase, model path and configured phrase must match. Do not relabel a model trained for a different phrase.
7. **Google capability counts:** the documented 197 operations, 118 state-changing operations and 146 OAuth profiles are build-specific registry snapshots. API enablement, scopes, account type, admin approval, provider quotas and product eligibility still govern live availability.

## Safe cleanup checklist

Before removing the old standalone documentation files, replace the project's root `README.md` with this consolidated file, open it in GitHub/VS Code to verify formatting, and ensure it is in the correct repository root beside `main.py` and `visionguide/`. After that, the other Markdown/text files listed as consolidated below can be removed if no external script or packaging process explicitly references them. Keep `requirements*.txt`, source files, model weights, credentials, `.env`, databases and user data untouched.

The standalone `.patch` file and `test_depth_output.npy` are handled separately after the documentation archive. See the final section, **Patch and generated test-file cleanup**.

---

# Consolidated technical documentation

The following sections preserve the full contents of the original documentation and text files. Their original filenames are shown to retain provenance. Patch-installation snippets are historical instructions: use them only when their corresponding patch has not already been applied and the target source matches the patch context.


## Original file: `ARCHITECTURE.md`

### Arthur Technical Architecture

#### 1. Runtime components

Arthur uses a local-first Windows desktop application plus a FastAPI device-agent service. A small Python REST client and a Flutter client starter communicate with the service. The design keeps tools close to the resources they control: Windows input, brightness, audio, network interfaces, active application windows, and local files execute on the Windows device agent.

Camera frames, microphone recordings, screenshots, face profiles, and local notes are intended to remain on-device unless a workflow explicitly requires an external service and the user approves the relevant upload or transmission. The desktop application is the reference implementation; the Flutter client is a mobile interface starter, not a replacement for Windows device-level integrations.

##### Source map

| Source | Responsibility |
|---|---|
| `main.py` | Desktop entry point or `--serve-api` entry point |
| `visionguide/app.py` | Tk desktop UI, camera/status controls, speech routing, permission prompts and result display |
| `visionguide/voice_commands.py` | On-demand microphone recording and Whisper transcription; file-based transcription |
| `visionguide/semantic_router.py` | Groq function calling, rule/parser fallback, local intent patterns, embedding similarity, typed `RoutedCommand` |
| `visionguide/scene_commands.py` | Existing local deterministic command parser |
| `visionguide/desktop_actions.py` | Website and allowlisted Windows application launchers |
| `visionguide/integrations/system_controls.py` | Browser playback, display brightness, master audio, Wi-Fi adapter control |
| `visionguide/integrations/gui_automation.py` | Window targeting, clipboard paste, Gmail/Word/WhatsApp GUI workflows |
| `visionguide/integrations/google_workspace.py` | Gmail/Calendar API operations and OAuth credential lifecycle |
| `visionguide/integrations/timers.py` | Thread-safe in-process countdown timers |
| `visionguide/api_server.py` | FastAPI request models, auth, command routing/execution, confirmation store, timer endpoints and WebSockets |
| `visionguide/gesture_mouse.py` | Calibrated MediaPipe system pointer, pinch clicks, right-edge scrolling and browser-tab swipes |
| `visionguide/system_virtual_keyboard.py` | One system-wide air virtual keyboard; mouse and gesture selection; keyboard input into the currently focused target |
| `visionguide/face_memory.py` | Local LBPH face profiles with optional DeepFace embedding fusion |
| `visionguide/action_history.py` | Bounded local action/result history and persistent per-profile preferences |
| `visionguide/integrations/google_services.py` | Capped/cached Google Geocoding, Weather, Routes and Vision Web Detection adapters |
| `visionguide/navigation.py` | Windows location provider, spoken route guidance and best-effort off-route rerouting |
| `visionguide/sign_language.py` | Isolated-sign ISL Swin3D-S classifier and inference path |
| `clients/python/visionguide_client.py` | Python REST client |
| `clients/flutter/lib/main.dart` | Flutter mobile command UI, microphone/speech integration, REST and WebSocket client |

#### 2. Command lifecycle

1. **Capture.** The desktop records audio only after an explicit voice-command action or after the locally armed wake-word flow activates. The Flutter starter supports short device-native speech recognition and recorded audio sent to the service for Whisper transcription.
2. **Transcribe.** Whisper returns text. It does not execute tools and is not given a shell or application-control interface.
3. **Route.** `SemanticCommandRouter.route()` attempts Groq function calling when a Groq API key is configured. If routing is unavailable, it checks the existing local parser, deterministic high-value patterns, and a SentenceTransformers cosine-similarity matcher. The local similarity model loads on first use and uses `VISIONGUIDE_SEMANTIC_THRESHOLD`.
4. **Validate.** The router returns a `RoutedCommand` with an action name, primitive typed arguments, source, and confidence. Tool names are registered in `_FUNCTIONS`; execution is a separate layer. The executor checks allowed website/app/window names, argument ranges and OS/provider prerequisites.
5. **Confirm.** Ordinary text-only requests are sent to Groq directly. State-changing actions (save, update, delete, submit, send, publish), network disconnection, and sensitive GUI/image-upload workflows require a separate confirmation checkpoint. The API returns a random one-use confirmation ID bound to the `device_id`; the token expires after five minutes and is consumed after approval or cancellation.
6. **Execute.** Local desktop actions execute on Windows. Gmail/Calendar API requests run with the authenticated Google account. A GUI workflow types into a selected known window and leaves a draft open unless a separately confirmed send command is issued.
7. **Verify and respond.** Result text and status are returned to the desktop, HTTP client, or timer WebSocket. A keyboard shortcut being issued is not proof of final delivery; the user/application status must be checked.

##### Semantic function calling

`visionguide/semantic_router.py` declares functions for websites, apps, vision/document intents, media playback, display/audio/network controls, timers, Gmail, Calendar, GUI drafting and text-only general queries. `automatic_function_calling` is disabled for the router request: Groq proposes a function and the local code decides what happens next. No model-generated Python or shell string is evaluated.

Calendar routing receives the configured local date/time and `VISIONGUIDE_TIMEZONE` (defaults to `Asia/Kolkata`) so phrases such as “tomorrow at 10” can be resolved. The router should ask for clarification when a required event detail or recipient is ambiguous.

Fallback order when Groq function calling is unavailable: legacy local parser → high-value deterministic patterns → local SentenceTransformers similarity → text-only Groq query. Ordinary text-only requests are sent directly to Groq by both the desktop client and authenticated API client, without a second confirmation prompt. The current request text is sent; prior conversation context remains local unless `VISIONGUIDE_SHARE_CONVERSATION_CONTEXT=1` is explicitly enabled.

The text-only Groq fallback does not automatically include camera frames or screenshots. Visual requests that require an external vision service follow a separate image-selection and permission path.

#### 3. Client-server design

```text
Flutter / Python client / desktop UI
         | REST JSON commands
         | REST audio upload for Whisper
         | WebSocket notifications
         v
 FastAPI device-agent service
         | SemanticCommandRouter
         | confirmation store + executor
         +-- local timers
         +-- Windows device integrations
         +-- Gmail and Calendar OAuth APIs
```

The Windows desktop client and API service are separate processes. Starting `python main.py --serve-api` launches the API agent, not the Tk camera UI. The API executes only the actions available to that service process. Camera descriptions, local frames, and Tk-specific state remain in the desktop application unless a future client-side camera adapter sends an explicitly selected payload through a documented endpoint.

The Flutter starter can communicate with the service, submit commands or audio, and receive notifications. It does not gain remote access to the phone's operating system, camera, cursor, or network adapter merely by connecting to the Windows API.

##### API routes

- `GET /health`
- `GET /api/v1/tools`
- `POST /api/v1/command`
- `POST /api/v1/confirm`
- `POST /api/v1/transcribe` (multipart audio upload; maximum 20 MB)
- `POST /api/v1/timers`, `GET /api/v1/timers`, `DELETE /api/v1/timers/{timer_id}`
- `POST /api/v1/workspace/gmail/drafts`
- `POST /api/v1/workspace/gmail/drafts/{draft_id}/send` (returns a one-use confirmation challenge after reading the draft preview)
- `GET /api/v1/workspace/gmail/unread`
- `GET /api/v1/workspace/gmail/search?q=...`
- `GET /api/v1/workspace/gmail/messages/{message_id}`
- `GET /api/v1/workspace/calendar/upcoming`
- `GET /api/v1/workspace/calendar/search?q=...`
- `POST /api/v1/workspace/calendar/events` (returns a one-use confirmation challenge for the supplied event)
- `WS /ws/notifications`

`/docs` exposes the local OpenAPI explorer. HTTP endpoints use the `Authorization: Bearer <token>` header when `VISIONGUIDE_API_TOKEN` is configured. A non-loopback bind is rejected at startup unless a token exists. Use TLS and network restrictions for remote deployments; the API itself is a development device-agent service, not a hardened internet-facing gateway.

Authentication, confirmation, and network exposure are separate concerns. A configured API token does not by itself make an internet-facing deployment secure.

#### 4. Windows system and browser controls

- **Media:** `media_playback()` targets a browser window title (prefers YouTube) through PyGetWindow and uses YouTube keyboard shortcuts (`K`, `J`, `L`, `Shift+N`, `Shift+P`). The browser player must be focused. Stop maps to pause; `K` is a toggle rather than an idempotent play/pause state query.
- **Brightness:** `screen-brightness-control` queries/sets percentage values. Hardware and external monitor support depends on the display/driver.
- **Audio:** Pycaw reads and adjusts Windows master output level and mute state through the Core Audio endpoint API.
- **Wi-Fi:** `netsh interface show interface` enumerates Windows interfaces; `netsh interface set interface` changes only a named adapter that was found. The UI/API confirmation must precede this action. Windows policy or adapter privileges may deny the operation.
- **GUI:** PyAutoGUI injects keys/pastes and PyGetWindow activates allowlisted windows. The executor never starts arbitrary shell commands from transcribed text. PyAutoGUI fail-safe remains enabled.

GUI automation depends on the target application being available and correctly focused. Clipboard paste and keyboard injection are best-effort input operations; they do not guarantee that the intended application accepted, saved, or delivered the content.

#### 5. Timers, threads and event handling

`TimerManager` creates `threading.Timer` workers, maintains a lock-protected ID registry, uses monotonic deadlines, supports cancellation and stops its callbacks during shutdown. Timer callbacks run away from the Tk UI loop; `app.py` passes events through its async queue. The FastAPI timer callback publishes a `timer_expired` WebSocket event when connected clients are present. Countdown timers are in-process and are cleared when the process stops; persistent calendar scheduling is a separate Google Calendar write.

These timers are not persistent reminders: they do not survive process termination, a machine restart, or an API service restart.

#### 6. Workspace services

`google_workspace.py` uses `InstalledAppFlow` for desktop OAuth and the Google API client libraries. Access/refresh tokens are stored under `data/google_tokens/`, outside version control. Supported operations:

- Gmail unread metadata and body text when requested, inbox query search, read one message, create API draft, send a named draft after explicit confirmation.
- Calendar list upcoming primary-calendar events, search event summaries/descriptions, create a validated event after confirmation.

Scopes are defined in the module. OAuth consent and test-user configuration must be completed in Google Cloud Console. API quota, revoked grants, scope changes and account policy errors are returned through the provider adapter; remove the local token file to force re-consent after changing scopes.

The desktop's GUI path is separate: it uses Gmail's compose keyboard shortcut, pastes the user-approved recipient/subject and Groq-generated body, then leaves the draft for review. The send action activates Gmail and issues Ctrl+Enter only after explicit confirmation.

The API and GUI paths have different execution and verification characteristics. An API draft operation is not the same as typing into Gmail's graphical interface, and neither should be reported as successfully sent until the relevant provider or application confirms the result.

#### 7. Air mouse and ISL

##### Air mouse

`GestureMouse` consumes the current camera frame through MediaPipe Hand Landmarker. The index fingertip maps to the cursor; thumb-index pinch produces a debounced left click; the rightmost 18% of the mirrored camera frame is reserved for vertical scrolling. The user must enable it and can disable it in the desktop UI; camera loss and PyAutoGUI fail-safe stop control.

The unified system-wide virtual keyboard is controlled through mouse interaction and the gesture pointer's pinch-click path. Literal voice typing can paste into the currently focused target after confirmation. The older prompt-only `air_keyboard.py` module remains in the source tree for compatibility but is not a second visible/active keyboard in the desktop UI.

##### Indian Sign Language

The current isolated-sign classifier uses **Torchvision Swin3D-S**, not the older MediaPipe Holistic plus TensorFlow LSTM pipeline.

- Checkpoint: `models/isl/swin3d_s/ISL_best_model.pt`
- Architecture: `torchvision.models.video.swin3d_s(weights=None, num_classes=76)`
- Dataset path: `data/isl_dataset/ProcessedData_vivit`
- Class count: 76
- Inference input: a 32-frame video clip, not a single still image
- Preprocessing: resize the shortest edge to 256 pixels, center crop to 224×224, convert to RGB, rescale to `[-1, 1]`, and construct the model input tensor in `[B, C, T, H, W]` order.

The inference path uses a background worker to collect frames and produce predictions. The intended recognizer interface accepts BGR camera frames and returns a predicted label with confidence or no result. The desktop flow includes sign-mode activation, confidence thresholding and duplicate suppression.

The model supports isolated signs from its 76-class vocabulary. It does not provide continuous sentence-level sign-to-text translation or text-to-sign generation. Those require separate sequence modelling, linguistic processing and evaluation.

MediaPipe remains part of the hand-gesture control path; it is not the current ISL classifier. Classifier evaluation results do not establish live-camera reliability, signer-independent generalization or continuous translation performance.

#### 8. Failure handling and invariants

- A failed provider call does not become a success response.
- The camera remains silent until requested; screen/camera upload requires explicit UI permission.
- A route cannot broaden the registered tool allowlist.
- Recipient, contact, target window and full message body must be verified before sending.
- Confirmation tokens are one-use, device-bound and time-limited.
- Wi-Fi, Calendar and send actions report failure when the operating system/provider rejects the call.
- The project does not claim that inferred distance, detection absence or a single image proves a path safe.
- Local inference does not imply that every feature in the wider application is offline; Groq, Google Workspace and Google Cloud adapters require their respective credentials and network access.
- Face recognition is limited to locally enrolled profiles. It is not a general-purpose stranger-identification or internet face-search feature.
- Optional DeepFace embedding fusion does not establish biometric identity accuracy or suitability for security-critical authentication.

#### Newly integrated assistive workflows

- **Action/result memory:** executed commands are recorded to bounded local SQLite history; follow-up questions retrieve the last action without overwriting the result being queried.
- **Unified keyboard/gesture path:** one system-wide virtual keyboard is controlled by mouse clicks and hand-pointer pinch clicks; literal voice typing can paste into the currently focused target after confirmation. The older prompt-only `air_keyboard.py` module remains in the source tree for compatibility but is not a second visible/active keyboard in the desktop UI.
- **Local profile preferences:** enrolled-user preferences persist across restarts and are cleared when the profile is deleted. Unknown/multiple-face views do not inherit preferences. Optional DeepFace embeddings are fused with LBPH when available, and mismatched predictions are treated as unknown.
- **Maps and route guidance:** REST adapters cache responses and apply per-device request caps. `NavigationSession` uses Windows geolocation when installed and available, speaks route instructions, and recalculates after repeated off-route readings. This is a prototype, not a certified navigation SDK or safety service; live acceptance testing on the target machine is required.
- **Visual search and cloud vision:** Google Cloud Vision Web Detection and other external visual services require their configured credentials and an explicitly approved image payload. Local object detection and external image research are separate workflows; local detection does not itself require uploading an image.
- **Privacy and storage:** user notes are stored locally in SQLite when requested and can be searched or deleted. Face profiles and preferences are local profile data; their persistence and deletion behavior should be verified against the actual storage implementation before release.

## Original file: `COMMAND_CATALOGUE.md`

### Arthur Spoken Command Catalogue

Commands are natural-language intents, not magic exact strings. Groq function calling routes common paraphrases to the same typed tool when configured. Local parsing/patterns and SentenceTransformers similarity provide fallback routing. If an argument cannot be safely inferred, ask for clarification rather than guessing.

A recognized command is not proof that the requested action succeeded. Arthur must report execution results accurately and distinguish a completed action from an attempted action, an unavailable capability or a provider error.

#### 1. Websites, search and applications

- “Open YouTube.” / “Take me to YouTube.” / “Put YouTube on screen.”
- “Open Gmail.” / “Take me to Google Drive.” / “Open WhatsApp Web.”
- “Search YouTube for binary search trees.”
- “Search the web for the Python datetime documentation.”
- “Open Calculator.” / “Open Notepad.” / “Open Settings.” / “Open VS Code.”
- “Open the Documents folder.” / “Open my latest PDF.”

Website and app targets use allowlists; arbitrary transcribed strings are never passed to a shell. Available app names depend on the installed Windows application and PATH configuration.

If a file reference such as “my latest PDF” matches multiple possible files or cannot be resolved reliably, Arthur should ask the user to select the intended file rather than opening an arbitrary result.

#### 2. Browser media controls

- “Pause the YouTube video.” / “Play the video.” / “Stop the video.”
- “Skip ahead 30 seconds.” / “Go back ten seconds.”
- “Play the next video.” / “Go to the previous video.”

The playback adapter activates a matching browser window and sends YouTube keyboard shortcuts. `K` toggles playback and stop maps to pause; player focus matters. Skip durations are approximate in ten-second increments.

These are keyboard-shortcut actions, not guaranteed playback-state detection. Arthur should not claim that playback changed unless the action can be verified.

#### 3. Display, audio and network

- “Set brightness to 45 percent.” / “Make the screen brighter.” / “Dim the display.”
- “What is the current brightness?”
- “Set volume to 25 percent.” / “Turn the volume up.” / “Make it quieter.”
- “What is the system volume?” / “Mute system audio.” / “Unmute sound.”
- “Show Wi-Fi adapter status.” / “Turn the Wi-Fi adapter off.” / “Enable the Wi-Fi adapter named Wi-Fi.”

Brightness and volume percentages are bounded. Wi-Fi changes identify the requested adapter and require a user confirmation; this may interrupt the network and may require elevated Windows permissions.

#### 4. Timers and reminders

- “Set a timer for five minutes.”
- “Start a 30-second countdown.”
- “Remind me in two hours to check the build.”
- “List my active timers.”
- “Cancel timer 2.”

Countdowns run in background threads and return a timer ID. These timers are in-process; they do not persist after app/server shutdown.

A timer reminder is not automatically a persistent Calendar event or a scheduled notification that survives an application restart. Calendar events are a separate integration.

#### 5. Camera and local vision

- “What is in front of me?” / “Describe the camera view.”
- “Is there a chair?” / “Can you see a television?”
- “Read the text on this page.” / “Scan this label.”
- “Take a snapshot.”
- “Start the camera.” / “Stop the camera.”
- “Enable proactive safety alerts.” / “Disable safety alerts.”

The camera remains silent until asked. A detected object may be missed; not detecting an object is not proof that it is absent.

Camera upload to Groq requires a separate prompt/consent gate. Distance and hazard analysis are not certified mobility guidance. Proactive safety alerts should not be treated as a replacement for environmental awareness or mobility assistance.

#### 6. Screen, OCR and documents

- “Take a screenshot.”
- “Read the text on my screen.” (local OCR)
- “Explain what is on my screen.” (asks before screenshot upload)
- “Open a document.”
- “Search this document for recursion.”
- “Find the word stack on the last scanned page.”
- “Open my latest PDF.”

Screenshots are saved locally unless the user separately requests AI screen description and confirms upload. Document operations may open a file picker so the user can choose a source explicitly.

Local OCR and AI screen description are separate operations. AI screen description requires its own upload approval; a request to read screen text locally does not authorize sending the screenshot to an external service.

#### 7. Gmail — OAuth API and GUI workflow

After configuring Google Cloud OAuth and authenticating:

- “Read my unread emails.” / “Check unread Gmail.”
- “Search Gmail for messages from my professor this month.”
- “Read the email with subject about the lab report.” (choose/read a specific result as supported by current client context)
- “Draft an email to student@example.com with subject Project update about the latest build.”
- “Prepare a Gmail draft to team@example.com with subject Meeting notes; say that the test run passed and ask for review.”
- “Send email.”

Gmail API operations support unread metadata/body, inbox search, reading by message ID, API draft creation and explicit draft send.

The desktop GUI workflow opens Gmail, uses its compose shortcut, pastes the recipient, subject and Groq-generated body, and leaves the draft open for review. To send from the active GUI draft, the user must separately say “send email” and confirm the displayed recipient/subject/body. Enable Gmail keyboard shortcuts for GUI compose.

Never infer an email address from a person's name when no uniquely known address is supplied. Review the full message before sending. A send shortcut is not proof of delivery; verify Gmail's Sent state.

#### 8. Google Calendar — OAuth API

- “What meetings do I have this week?”
- “Show upcoming calendar events.”
- “Search calendar for the design review.”
- “Schedule a meeting called project review tomorrow at 10 AM for 30 minutes.”

The router uses current date/time and `VISIONGUIDE_TIMEZONE`. The app must confirm title, start, end and timezone before creating an event.

If the time, date or duration is unclear, clarify before writing. Current adapter supports upcoming event listing, metadata search and single-event creation; attendees and recurrence are not part of the current event form.

For Google Drive and Docs, the extended allowlisted API adapter also exposes confirmed writes and deletes:

- “Update Google Drive file [FILE_ID] with this content: [text].” (content upload requires confirmation)
- “Update Google Drive file [FILE_ID] metadata to [JSON].” (metadata update requires confirmation)
- “Delete Google Drive file [FILE_ID].” (requires confirmation)
- “Delete content from Google Doc [DOCUMENT_ID] between index 10 and 25.” (range deletion requires confirmation)

The operation must have a valid resource ID and the matching Google OAuth scope. Google Docs API changes are saved automatically after a confirmed API update.

#### 9. Word, WhatsApp Web and window typing

- “Open Word and write this draft: [dictated text].”
- “Paste this text into Notepad: [dictated text].”
- “Prepare a WhatsApp Web message to Alex: [message].”
- “Send WhatsApp message.”
- “Type this text in the Gmail window: [text].”
- “Type hello in Microsoft Word.” (inserts at Word's current cursor/selection using Office automation; opens a blank document only if Word has none)
- “Save it.” (saves the active Word document after confirmation; an unnamed document is saved with a timestamped name under `Documents/ARTHUR`)
- “Save the Word document as report.docx.” (saves in `Documents/ARTHUR`; refuses to overwrite an existing file)
- “Replace old phrase with new phrase in Word.” (previews and confirms the replacement; leaves the document modified but unsaved)
- “Delete selected text in Word.” (previews the current selection and confirms; verifies the selection has not changed before deletion)
- “Type Taylor Swift in YouTube search box.” (focuses the YouTube search field, pastes, and does not submit)
- “Type example.com in Chrome address bar.” (focuses the browser omnibox and pastes, but does not navigate)
- “Close YouTube.” / “Close the Gmail tab.” (asks for confirmation, then closes the matching active browser tab without terminating the browser)

Word text insertion and replacement leave the document unsaved until you explicitly say “save it” and confirm. WhatsApp drafts remain unsent. Text paste targets are allowlisted. Word operations require `pywin32` and a Windows desktop installation of Microsoft Word.

Before sending a WhatsApp message, confirm the visible chat title and complete message body; before email send, confirm recipient, subject and body. A GUI workflow stops on a missing window or error. Browser-tab closing only identifies the active tab shown in the Chrome/Edge/Firefox/Brave/Vivaldi/Opera window title; background tabs are not selected automatically.

For generic “Type exactly …”, Arthur captures the foreground window before confirmation, then restores and verifies that same window before pasting. If Arthur itself was foreground (for example, after clicking Push to Talk), name the target explicitly. Arbitrary webpage fields are not guessed: only known focus routes such as YouTube's search shortcut and the Chrome/Edge address bar are automated.

#### 10. Unified system-wide air virtual keyboard and hand gestures

- “Open the virtual keyboard.” / “Close the virtual keyboard.”
- “Type exactly Hello, world.” (literal text; confirmation before paste, does not submit)
- “Calculate 2+2.” (safe local arithmetic) / “Open Calculator and sum 2+2.” (launch Calculator, enter expression, report the locally computed result with a display-verification caveat)
- “Focus on YouTube search bar.” (sends the known search-focus shortcut; verify field focus)
- “Enable hand gestures.” / “Disable hand gestures.”
- Move index fingertip to control the system pointer.
- Pinch thumb and index finger to click.
- Enter the right-edge gesture strip and slide vertically to scroll.
- Swipe left for the previous browser tab, right for the next browser tab.

There is one visible virtual keyboard: the system-wide air virtual keyboard. Mouse clicks, gesture pointer/pinch and voice literal typing can all enter text into the focused Windows application.

Download the Hand Landmarker model first. The camera must see the hand; cursor movement is on-device and PyAutoGUI fail-safe remains active. Avoid gestures while entering passwords, approving transactions or editing sensitive material.

Literal typing and command execution are separate actions. “Type exactly...” enters text and does not submit it or execute it as a command.

#### 11. Weather, routes and live navigation

- “Tell me today's weather in Kolkata.”
- “Get directions from Salt Lake to Howrah by motorcycle.”
- “Navigate to Howrah.” (asks permission to use live Windows location and start turn-by-turn guidance when configured)
- “Stop navigation.”

Weather returns provider-sourced current conditions. Routes support driving, two-wheeler where enabled, walking, cycling and transit where available; traffic-aware ETA is requested for driving/two-wheeler routes.

Live navigation polls location, speaks maneuver updates and recalculates after repeated off-route readings. It requires Windows location permission, enabled Google APIs and a valid key.

This is best-effort prototype guidance, not a certified mobility/navigation safety service. Location availability, route quality, provider responses and GPS accuracy can affect guidance.

#### 12. Product/object lookup and public visual search

- “Tell me about this air fryer.”
- “What product is this?”
- “Search this object online.”

Arthur asks for consent before uploading the compressed camera frame to Groq and/or Google Cloud Vision. It can combine OCR, visual inference, public page matches and similar-image leads, with uncertainty called out.

A visual match never proves a person's identity or an exact model number. Similar-image results should be treated as research leads, not definitive identification.

#### 13. ISL

- “Start ISL isolated-sign recognition.”
- “Stop ISL recognition.”

The current runtime path is isolated-label ISL classification. Continuous sentence-level translation and text-to-sign have separate model, output and evaluation requirements documented in `CONTINUOUS_ISL.md`.

The current classifier recognizes only its supported isolated-sign vocabulary. It does not provide continuous sentence-level translation or general sign-language conversation.

#### 14. API / mobile examples

Once `python main.py --serve-api` is running:

- Python: `python clients/python/visionguide_client.py "open YouTube" --server http://127.0.0.1:8000`
- Flutter: connect to the server URL, enter its bearer token when enabled, and use text, short speech, or recorded-audio Whisper transcription.
- High-impact API commands return a confirmation ID and a preview. The client must post that exact token and device ID to `/api/v1/confirm`; IDs expire after five minutes and can be used once.

The FastAPI service executes device operations on the machine hosting the service. A connected Flutter client does not automatically gain direct control over the phone's operating system, camera, cursor or network adapter.

#### 15. Additional Google APIs (OAuth or Maps key as noted)

The following examples use the installed-app OAuth flow for Workspace/Cloud services and `GOOGLE_MAPS_API_KEY` for Maps Platform lookups. The first use of a feature may open a separate consent flow for that feature's narrow token profile.

##### Maps Platform (Maps API key)

- “Find nearby pharmacies in Kolkata.” / “Search cafes near Park Street, Kolkata.”
- “Tell me the air quality in Kolkata.”
- “Check the pollen forecast in Kolkata.”
- “What is the time zone in Tokyo?”

Road snapping is exposed to typed tool/API clients because it requires a JSON path of latitude/longitude pairs.

Geolocation is also an API-level operation: it needs caller-supplied Wi-Fi access-point data and an explicit consent flag; Arthur does not collect nearby Wi-Fi MAC addresses automatically.

Maps JavaScript, Embed, mobile SDK and Map Tiles restrictions do not add an in-app Python renderer.

##### Google Cloud language services (OAuth)

- “Translate hello world to Hindi.”
- “Analyze the sentiment of this text: The product is excellent and useful.”
- “Find entities in this text: Ada Lovelace worked in London.”
- “Analyze the grammar of this sentence: The quick fox jumps.”
- “Classify this text: [provide a paragraph of at least 20 characters].”

Text is sent to Google Cloud for the explicitly requested operation and is not cached by the integration. Translation and Natural Language APIs must be enabled in the same Cloud project as the OAuth client.

##### Workspace and productivity (OAuth)

- “Search my Google Drive for project plan.”
- “Read Google Doc DOCUMENT_ID.”
- “Read Google Sheet SPREADSHEET_ID range Sheet1!A1:D20.”
- “Read Google Slides PRESENTATION_ID.”
- “List my Google Tasks.” / “Show my Google profile.”
- “Search my Google Contacts for Asha.”
- “Show my Google Classroom courses.”
- “Read coursework for Classroom course COURSE_ID.”
- “Show announcements for Classroom course COURSE_ID.”
- “Search YouTube for Python tutorials.”
- “Read Google Form FORM_ID.”
- “Create a Google Meet link.”

Creating Docs, Slides, Tasks, Forms and Meet spaces, and updating a Sheet, require an explicit confirmation through the app/API client.

All other state-changing operations exposed through the extended Workspace dispatcher also pass through the central confirmation gate. The examples above are not an exhaustive list of operations or confirmation requirements.

Resource-ID examples above are placeholders: replace them with real IDs from the corresponding Google URL. The feature-specific profile and REST operation map is in `GOOGLE_SCOPE_FEATURE_MATRIX.md`.

Scope consent, API enablement, verification, account role and product eligibility are independent prerequisites. Gmail add-on contextual permissions, Meet real-time media capture, Classroom add-on attachment context/practice sets, Drive Activity writes, Google Photos Library access, Meet hardware administration, and YouTube partner/download features remain runtime- or approval-gated rather than being claimed from scope presence alone.

#### General AI fallback

- “Explain binary search trees with an example.”
- “Help me draft a project report outline.”
- “What is the difference between threads and async tasks?”

Unmatched ordinary text requests are sent directly to Groq by the desktop and authenticated API client. Arthur does not ask “send this to Groq?” or announce that a local command was not found. The current request text is sent; prior conversation context is not included unless `VISIONGUIDE_SHARE_CONVERSATION_CONTEXT=1` is enabled.

General Groq Q&A is text-only unless an image-specific action was explicitly requested and confirmed separately. Sends, saves, updates, deletions, submissions, account changes, and image/screenshot uploads continue to use their own confirmation checkpoints.

#### 16. Extended website launcher allowlist

The `open_website` tool and local voice parser support Google Cloud Console, Neon DB, Google Classroom, Google Contacts/Contacts, LeetCode, LinkedIn Learning, Coursera, SWAYAM and NPTEL. Common typo/voice aliases `linkedln learning` and `swaym` are normalized to LinkedIn Learning and SWAYAM.

Opening one of these sites is browser navigation only; it does not automate a login or bypass the site provider's permissions.

## Original file: `INTEGRATIONS.md`

### Arthur Integrations and Setup

This guide maps each user-visible capability to its source adapter, runtime prerequisites, command flow and validation requirements. All listed modules belong to the project architecture; environment variables and runtime checks control credentials, privacy, operating-system support and permissions.

An integration being present in the source does not guarantee that its external service, model, hardware, account permissions or operating-system dependencies are configured. Follow the relevant setup and validation steps before relying on a capability.

#### 1. Groq function calling and semantic fallback

**Source:** `visionguide/semantic_router.py`, `visionguide/cloud_ai.py`  
**Configuration:** `GROQ_API_KEY`, `GROQ_MODEL`, `VISIONGUIDE_TIMEZONE`, `VISIONGUIDE_LOCAL_SEMANTIC`, `VISIONGUIDE_SEMANTIC_MODEL`, `VISIONGUIDE_SEMANTIC_THRESHOLD`.

Routing order:

1. Groq selects one declared typed function when configured.
2. The existing local command parser handles known deterministic commands.
3. High-value local patterns handle simple brightness, volume, mute, Wi-Fi, timer, playback and unread-mail requests without an embedding model.
4. SentenceTransformers compares unseen paraphrases against registered intent examples.
5. If no local intent matches, Arthur sends the ordinary text request directly to Groq from the desktop or authenticated API client. It does not ask for another “send to Groq?” confirmation. Previous conversation context is excluded unless `VISIONGUIDE_SHARE_CONVERSATION_CONTEXT=1` is enabled.

The router uses `automatic_function_calling` disabled: Groq returns a proposed function call but does not execute local Python. Only registered functions are accepted. Arguments are reduced to primitive JSON types and are checked again by the executor.

The local semantic matcher loads `sentence-transformers/all-MiniLM-L6-v2` on first use when needed. Set `VISIONGUIDE_LOCAL_SEMANTIC=0` to use the parser/pattern path without embedding inference. The first semantic-model load may download model weights unless they are already cached.

For Calendar expressions, `VISIONGUIDE_TIMEZONE` (default `Asia/Kolkata`) and current local date/time are sent as routing context. If a user omits key event details, ask a follow-up rather than inventing recipients, event titles or dates.

#### 2. Speech input and transcription

**Source:** `visionguide/voice_commands.py`, `visionguide/api_server.py`, `clients/flutter/lib/main.dart`  
**Packages:** `openai-whisper`, `sounddevice`, `numpy`, FFmpeg; Flutter `speech_to_text`, `record`, `path_provider`.

On Windows, use the explicit voice-command capture button or the locally armed wake-word feature. `record_and_transcribe()` records a bounded interval at 16 kHz and sends it to local Whisper inference. `transcribe_audio_file()` reuses a cached Whisper model for a supplied audio path.

The API `POST /api/v1/transcribe` accepts multipart audio and permits WAV, MP3, M4A, WebM, OGG, FLAC, MP4 or MPEG-family extensions up to 20 MB. It writes a temporary file, runs Whisper on the server machine, deletes the temporary file, and returns the transcript. This endpoint does not send audio to Groq.

The mobile app's standard device-speech button uses the mobile speech plugin; the separate “Record for Whisper” path sends the audio to the configured device API for local Whisper processing. In this context, *local* means local to the machine running the API, not necessarily the phone.

The wake-word detector and the explicit recording/transcription path are separate components. The wake-word model must be compatible with openWakeWord and configured through `WAKE_WORD_MODEL`. Verify the actual model filename, wake phrase, conversation timeout and recording behaviour against the installed implementation. Do not assume that enabling wake-word detection automatically validates continuous conversation or a particular chunk duration.

#### 3. Browser and Windows controls

**Source:** `visionguide/integrations/system_controls.py`, `visionguide/desktop_actions.py`  
**Packages:** `pyautogui`, `pygetwindow`, `screen-brightness-control`, `pycaw`, `comtypes`.

##### Browser playback

`media_playback(action, seconds)` activates an existing browser window matching YouTube/browser keywords, then uses YouTube keyboard shortcuts:

| Action | Shortcut behaviour |
|---|---|
| `play`, `pause`, `toggle` | Press `K` to toggle player state |
| `stop` | Press `K`; stop is implemented as pause |
| `next` / `previous` | `Shift+N` / `Shift+P` |
| `forward` / `back` | Repeat `L` / `J` in approximate ten-second increments |

Playback depends on the player page being open and focused. The browser adapter does not query a definitive playback state. If the shortcut did not affect the video, focus the player and retry.

##### Display brightness

`get_brightness()`, `set_brightness(level)`, and `adjust_brightness(delta)` use `screen-brightness-control`. Levels are bounded 0–100; relative changes are limited to ±50 percentage points. The display driver/monitor must expose controllable brightness. A returned provider value is a request/result, not calibrated luminance in nits.

##### System audio

`get_volume()`, `set_volume(level)`, `adjust_volume(delta)`, and `set_mute(muted)` use Pycaw/COM and Windows Core Audio. Master output volume is reported as a 0–100 scalar and mute state as a boolean. These functions intentionally fail with a clear OS support error on non-Windows systems.

##### Wi-Fi adapter

`list_wifi_adapters()` parses `netsh interface show interface`; `set_wifi(enabled, adapter)` verifies the requested adapter name is present before running `netsh interface set interface`. Configure `VISIONGUIDE_WIFI_ADAPTER` when the interface is not named `Wi-Fi`.

The caller must confirm before state changes, and an elevated process may be required. The OS response can confirm the command was accepted, but connectivity should still be checked afterward.

#### 4. GUI automation and multistep workflows

**Source:** `visionguide/integrations/gui_automation.py`, `visionguide/app.py`, `visionguide/api_server.py`  
**Packages:** `pyautogui`, `pygetwindow`, `pyperclip`.

The executor targets an allowlist of known windows. `activate_window()` finds a title by keyword and restores/activates the window. `type_into_window()` pastes text only into Gmail, Word, WhatsApp Web, Google Docs, Notepad or VS Code; it never submits the text. PyAutoGUI's emergency corner failsafe stays enabled.

##### Gmail GUI compose

`compose_gmail_gui(recipient, subject, body, send=False)` validates a single email address, opens Gmail, activates a Gmail window, uses the Gmail `C` keyboard shortcut, enters recipient/subject/body by clipboard paste, and leaves the compose window open for review. Enable Gmail keyboard shortcuts in Gmail settings. If the page layout or focus differs, stop and correct the draft instead of continuing blindly.

The desktop command flow can accept an email recipient, subject and writing instructions; it sends the text drafting instructions directly to Groq, generates a proposed body, and inserts it into Gmail after a preview/confirmation checkpoint. The separate “send email” action asks the user to verify recipient, subject and body, then issues `Ctrl+Enter`. The result text explicitly says to verify the Sent state; sending a shortcut is not proof of delivery.

The API can create an actual Gmail API draft through `POST /api/v1/workspace/gmail/drafts`. The send endpoint first reads the draft and returns its recipient, subject and body preview together with a one-use confirmation token. On confirmation, the server re-reads the draft and compares a fingerprint of recipient, subject and full body before sending; if the draft changed after preview, sending is rejected and the user must review it again.

##### Word

`word_write_document(text)` launches Word, creates a new document and pastes the text. It does not save or share the document. The user must review and save it.

##### Word save and edit operations

- “Save it” saves the active Word document. An unnamed document is saved under `Documents/ARTHUR` with a timestamped filename. “Save Word document as report.docx” supplies a safe filename in that folder. Both require confirmation; existing files are not overwritten.
- “Replace old text with new text in Word” previews and confirms the replacement before changing the active document. The document remains modified but unsaved.
- “Delete selected text in Word” reads the current selection, previews it, and confirms before deleting. The helper verifies that the selection has not changed since preview. The document remains modified but unsaved.

##### WhatsApp Web

`compose_whatsapp_gui(contact, message, send=False)` opens WhatsApp Web, invokes the New Chat shortcut, types the contact search and message, and leaves the message unsent. The visible conversation may be selected incorrectly if the web UI or search timing differs. Verify the chat title and complete message before using “send WhatsApp message.” The send helper cannot run unless its caller provides `confirmed_send=True` after confirmation.

##### Workflow sequencing

Compound intents such as “draft an email to this address about this topic” are one registered workflow. Other actions can be chained as consecutive voice commands. High-impact actions remain distinct end steps, and every sequence should inspect the target window and visible result before proceeding. PyAutoGUI keyboard injection is not a transaction and does not guarantee the currently focused widget is the intended one.

#### 5. Gmail and Google Calendar API via OAuth 2.0

**Source:** `visionguide/integrations/google_workspace.py`, FastAPI endpoints in `visionguide/api_server.py`  
**Packages:** `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib`.

##### Google Cloud setup

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

##### Gmail operations

- `gmail_unread(limit, include_body=False)`: unread message summary metadata; body retrieval when requested is limited per message.
- `gmail_search(query, limit)`: Gmail search syntax (for example `from:professor newer_than:30d`).
- `gmail_read_message(message_id)`: returns a single message's metadata and decoded body.
- `gmail_create_draft(to, subject, body)`: creates a named Gmail draft using the API.
- `gmail_send_draft(draft_id, confirmed=True)`: sends the specified draft only when the caller explicitly confirms it.

Email helpers accept one validated recipient for the supported GUI draft path; multi-recipient handling should be added deliberately rather than inferred from a spoken string. Full email bodies are not written to routine logs.

##### Calendar operations

- `calendar_upcoming(days, limit)`: upcoming events from the primary calendar.
- `calendar_search(query, days)`: searches event metadata using Calendar `q`.
- `calendar_create_event(summary, start, end, timezone_name, ..., confirmed=True)`: validates title bounds, ISO 8601 time, IANA timezone, start/end ordering and duration before writing.

The desktop flow shows title, start, end, timezone and location in its confirmation dialog. The API event endpoint returns a one-use, device-bound confirmation token. Only a confirmation request for that token executes the event write. Calendar event creation has no attendees/recurrence support in the present adapter.

#### 6. Timers and reminders

**Source:** `visionguide/integrations/timers.py`, `visionguide/app.py`, `visionguide/api_server.py`.

`TimerManager` uses `threading.Timer` with bounded 1-second to 7-day durations, `time.monotonic()` deadlines, thread-safe state, unique IDs, cancellation, listing, and graceful shutdown. Desktop expiry events are marshalled through an async message queue. API expiry events are published to connected clients using `WS /ws/notifications`.

These are volatile process-local countdowns. They do not survive app/server restarts. Google Calendar writes are the separate integration for events that need to persist.

#### 7. Unified system-wide air virtual keyboard and hand gestures

**Source:** `visionguide/system_virtual_keyboard.py`, `visionguide/gesture_mouse.py`, `visionguide/app.py`  
**Packages:** `mediapipe`, `pyautogui`, `pygetwindow`.

Download the supported Hand Landmarker task file with `python tools/download_hand_model.py`; it is saved to `models/hand_landmarker.task`.

There is one visible virtual keyboard: the system-wide air virtual keyboard. Mouse clicks select keys; the hand-gesture pointer and pinch-click can select the same keys; voice commands such as “type exactly hello world” paste literal text into a currently focused Windows field after confirmation and a short focus-selection delay.

The keyboard supports letters, numbers, symbols via Shift, Space, Tab, Enter, Backspace, Caps Lock, modifiers, function keys and navigation. The topmost overlay attempts to use Windows `WS_EX_NOACTIVATE` so key clicks do not steal focus from the target app. This behaviour must be verified on the target Windows build/application; UI automation cannot reliably verify all custom fields.

`GestureMouse` maps index-tip movement to the system cursor with smoothing, uses thumb-index pinch for a debounced click, reserves the rightmost 18% of the mirrored camera frame for vertical scrolling, and detects horizontal swipes across a short time window to change browser tabs.

Since pointer control is globally active while enabled, disable it before entering credentials or using payment/administrative UIs. PyAutoGUI's emergency corner failsafe remains active.

#### 8. Google Maps Platform, Weather API and public visual search

**Source:** `visionguide/integrations/google_services.py`, `visionguide/navigation.py`, `visionguide/app.py`.

`GoogleMapsServices` uses `GOOGLE_MAPS_API_KEY` only for Maps Platform calls: Geocoding, Weather, Routes, Places API (New), Air Quality, Pollen forecasts, Time Zone, Roads snap-to-road, and explicitly authorized network geolocation. Places requests use a narrow response field mask; place/air-quality/time-zone lookups are cached locally, and weather/pollen caches use shorter-lived data.

Daily usage caps and a SQLite counter under `data/cache/` reduce accidental loops; caps are application-side only and do not replace Cloud quotas/budgets. Geolocation uploads Wi-Fi identifiers only when `consent_confirmed=True`; the module does not collect Wi-Fi identifiers itself.

Cloud Vision Web Detection uses the separately restricted `GOOGLE_CLOUD_API_KEY` or `GOOGLE_VISION_API_KEY`; do not expect a Maps-only restricted key to work for Vision. Cloud Translation and Cloud Natural Language use separate OAuth scope profiles (`cloud-translation` and `cloud-language`) and do not use the Groq API key. Enable Cloud Vision API only if image web-detection is required; enable Cloud Translation/Natural Language API in the OAuth project's Cloud project before using those actions. Their text inputs are sent to Google for processing but are not cached by this module.

The current Python desktop app does not embed Maps JavaScript, Android/iOS SDKs, Maps Embed, or Map Tiles renderers; those APIs are for browser/mobile/map-renderer clients rather than an ordinary Python REST adapter. The route preview opens a Google Maps URL, not an in-app SDK. Enable only the APIs needed by the client actually using them, restrict each key by API and application type, activate billing if required, and set quota/budget alerts. Verify current pricing and regional availability before relying on an endpoint.

`NavigationSession` asks for Windows Runtime device location, speaks provider maneuver instructions, and recalculates after repeated route deviation. It opens a Google Maps route preview as well, but that browser preview is not a native in-app navigation SDK. Install `requirements-navigation.txt`, enable Windows Location and grant permission. GPS availability, route coverage, maneuver timing and rerouting need testing on the target Windows machine. This is best-effort prototype guidance, not a certified navigation or road-safety system.

Camera-based product/visual search asks for explicit approval before the selected image goes to Groq and Cloud Vision. Visual search can return public pages and similar-image leads; it is not identity verification. OCR text can be noisy, and product specifications should be checked against manufacturer sources/manuals.

##### Additional supported Google APIs

- **Places API (New):** text search by query, optional named-location bias, minimal fields, one-hour cache.
- **Air Quality API / Pollen API / Time Zone API / Roads API:** explicit lookup functions with bounded inputs and per-day request caps; pollen requests are limited to the API's five-day maximum and road snapping accepts at most 100 points.
- **Geolocation API:** callable only with explicitly supplied Wi-Fi access-point records and an explicit consent flag. It does not scrape nearby network identifiers from Windows.
- **Cloud Translation / Cloud Natural Language:** translate text or analyze sentiment/entities/syntax/categories using separate OAuth profiles; private text is not saved to local cache by these adapters.
- **Drive, Docs, Sheets, Slides, Tasks, People/Contacts, Classroom, Meet, YouTube, Forms:** supported read operations and selected create/update operations are exposed through `google_workspace_feature`. All external writes (Docs/Slides/Forms creation, Sheets updates, Tasks creation, Meet-space creation and Calendar event creation) require explicit client confirmation. Sheet writes use `RAW` input to avoid executing text as formulas, and the read/write limits are bounded.

The adapters are implemented but actual access still depends on enabling the associated API in the Cloud project, configuring the applicable OAuth scope profile in Google Auth Platform, completing the first-run consent flow, and having permission to the requested resource. Classroom roles/education domain, Workspace editions, account settings, API quotas and regional coverage can restrict availability. See `GOOGLE_SCOPE_FEATURE_MATRIX.md` for the exact boundary between implemented REST operations and runtime- or approval-gated product features.

The web launcher has fixed destinations for Google Cloud Console, Neon, Google Classroom/Contacts, LeetCode, LinkedIn Learning, Coursera, SWAYAM and NPTEL; that launcher allowlist does not grant programmatic API access to those third-party services.

#### 9. Local face recognition and preferences

**Source:** `visionguide/face_memory.py`, `visionguide/action_history.py`, `visionguide/app.py`.

OpenCV LBPH remains the baseline local recognizer. If DeepFace is installed and local embeddings can be computed, normalized embeddings are stored locally for consenting enrolled users and compared with the LBPH prediction. If both predictors return different enrolled identities, the result is Unknown rather than a forced match.

DeepFace is optional because it adds large TensorFlow/model dependencies; install `requirements-face.txt` separately if suitable. Recognition thresholds and camera coverage still affect reliability. Enrol one consenting person at a time; multiple visible faces do not trigger a personalized greeting.

Per-profile preferences persist in `data/action_history.sqlite3` and are deleted when the matching profile is deleted. Never use local face recognition to identify strangers from the public web.

#### 10. Action history, arithmetic and result follow-ups

`ActionHistory` records a bounded recent list of actions/results in SQLite and stores profile-specific preferences. “What did you do?” / “What was the result?” retrieves the last stored result without overwriting the result being queried.

A restricted AST arithmetic parser handles basic operations without executing Python or shell input. “Type 2+2=” remains literal input; “calculate 2+2” uses the arithmetic parser; “open Calculator and sum 2+2” launches Calculator and enters the expression while clearly reporting that the displayed Calculator result was not visually verified.

#### 11. FastAPI client-server service

Start with `python main.py --serve-api`. The default bind is loopback. Set `VISIONGUIDE_API_TOKEN` before binding to a non-loopback address; the server refuses non-loopback startup without a token. Configure Windows Firewall for a private network and use TLS/authentication for remote deployment.

The service provides a command endpoint, one-time confirmation endpoint, local Whisper upload endpoint (20 MB cap), timer endpoints, Workspace endpoints, and WebSocket timer notifications. Confirmation IDs are random, expire after five minutes, bind to the requesting `device_id`, and are single-use. They protect the exact intent/arguments that the client reviewed.

The Python client at `clients/python/visionguide_client.py` supports health checks, commands, confirmation, timers, Gmail unread/search/read/draft-preview operations, upcoming/search Calendar queries, event preview, and audio-file transcription. Run:

```powershell
python clients/python/visionguide_client.py "open YouTube" --server http://127.0.0.1:8000
```

after starting the API.

#### 12. Flutter client

`clients/flutter/lib/main.dart` implements server URL/token fields, health check, WebSocket events, short voice-command transcription via `speech_to_text`, manual command text, recorded WAV upload to `/api/v1/transcribe`, and confirmation dialogs.

A Flutter SDK is needed to generate native platform scaffolding and compile. On Android configure `INTERNET` and `RECORD_AUDIO`; on iOS configure microphone and speech-recognition usage descriptions. Test networking on an actual phone using the host laptop's LAN IP, not `127.0.0.1` from the phone.

The Flutter directory is a client starter, not a signed mobile release. Native platform builds and physical-device behaviour require separate validation.

#### 13. ISL

The current integrated ISL implementation is an **isolated-sign video classifier**, not a continuous sentence translator.

##### Current model

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

##### Continuous ISL development boundary

Continuous sentence-level sign-to-text requires a separate temporal sequence model and decoding pipeline. Text-to-sign is a distinct output adapter. These capabilities should not be described as completed features of the current 76-class isolated-sign classifier.

See `CONTINUOUS_ISL.md` for the proposed architecture and development requirements. Model availability, dataset provenance, signer permissions, held-out signer evaluation, sequence-level metrics, non-manual cues, and confidence/reject behaviour must be addressed before claiming a reliable continuous translation capability.

Offline classifier evaluation does not establish live-camera integration, signer-independent generalization, or real-world translation quality. Validate the camera-to-prediction flow separately on the target Windows machine.

## Original file: `GOOGLE_SCOPE_FEATURE_MATRIX.md`

### Arthur — Google OAuth Scope / Feature Matrix

This document describes the Google Workspace and Generative Language operations currently wired into Arthur. It is a local implementation inventory, **not** a claim that every Google API is enabled, verified, or approved for the signed-in account.

**Current registry snapshot:** 197 extended API operations, 118 extended state-changing operations, and 146 feature-specific OAuth scope profiles. All 118 extended state-changing operations are confirmation-gated. The semantic router exposes the full operation registry. These counts describe the local implementation at the time this document was prepared; they should be regenerated from the code whenever the registry or scope profiles change.

The 146 OAuth profiles are feature-specific authorization configurations. They should not be interpreted as 146 distinct Google scope strings.

This inventory describes local handlers and authorization configurations. Provider eligibility and service enablement still require live-account acceptance testing.

#### Authorization model

- OAuth credentials are acquired with a feature-specific profile in `visionguide/integrations/google_workspace.py`; token files are isolated under `data/google_tokens/`.
- `google_workspace_feature` is exposed through the typed semantic-router tool. Its operation enum is generated from the finite operation allowlist in `google_workspace_extended.py`, keeping the router's declared operation set aligned with the registered operations.
- Externally visible or destructive writes require explicit confirmation. The current confirmation set covers the extended write operations and the core Docs/Sheets/Slides/Tasks/Meet/Forms actions.
- Confirmation is an Arthur application-level safeguard. It is separate from Google's OAuth authorization and API permission checks.
- A scope in Google Auth Platform does not itself enable the API or add a handler. Google Cloud API enablement, the correct consent scopes, OAuth verification, account eligibility, Workspace administrator policy, quotas, and resource permissions are separate prerequisites.
- The desktop OAuth app does **not** request the whole catalog on every login. It requests the profile for the specific capability being used. This avoids merging highly privileged scopes into a single default token.
- A registered operation does not establish that the signed-in account can use it. The actual result depends on the granted scopes, API availability, account type, administrator policy, resource permissions, and provider-side restrictions.

#### Implemented API-backed capabilities

| API / scope family | Operations wired in Arthur | Notes |
|---|---|---|
| OpenID Connect / `openid`, `userinfo.email`, `userinfo.profile` | `google_identity`, `people_user_profile`, core `profile` | The identity operation calls the OpenID Connect userinfo endpoint. Extra profile fields are opt-in and request the corresponding People API scope. |
| Calendar read/event scopes | `calendar_list`, `calendar_get`, `calendar_events_list`, `calendar_readonly_events`, `calendar_public_events`, `calendar_event_get`, `calendar_freebusy`, `calendar_events_freebusy`, `calendar_settings_list`, `calendar_setting_get` | Covers CalendarList, event lookup, free/busy and settings read. Public calendar lookup requires a public calendar ID and the public-readonly scope. |
| Calendar write/share scopes | `calendar_create`, `calendar_app_created_calendar_create`, `calendar_update`, `calendar_delete`, `calendar_subscribe`, `calendar_unsubscribe`, `calendar_event_create/update/delete`, `calendar_owned_events_list/get/create/update/delete`, `calendar_app_created_events_list/get/create/update/delete`, `calendar_acl_list/create/update/delete` | Owned-event operations use `calendar.events.owned[.readonly]`. App-created event operations use `calendar.app.created` and must target a calendar created by this app. ACL/calendar deletion and other writes require confirmation. |
| Gmail message/mail scopes | `gmail_messages_list`, `gmail_metadata_list`, `gmail_message_read/modify/delete/insert`, `gmail_send`, `gmail_compose_send`, `gmail_send_to_self`, `gmail_user_metadata` | Uses per-operation scopes including messages-readonly, messages-modify, messages, metadata, insert, send, compose, send-self and user-readonly. Message deletion is permanently destructive and confirmation-gated. |
| Gmail draft/label scopes | `gmail_drafts_list`, `gmail_draft_read/create/update/delete/send`, `gmail_compose_draft_create`, `gmail_labels_list/create/update/delete` | Draft creation can use the create-only or compose profile. Label creation uses the create-specific scope; update/delete uses the labels write scope. |
| Gmail settings / mail-management scopes | `gmail_settings_list`, `gmail_setting_get/update`, `gmail_filters_list/create/delete`, forwarding address list/create/delete, automatic-forwarding get/update, send-as list/create/update/delete, delegates list/create/delete, `gmail_notifications_watch/stop` | Write operations require explicit confirmation. Gmail push notifications also require a configured Pub/Sub topic and appropriate Cloud Pub/Sub/API permissions. |
| Drive read / metadata / item scopes | `drive_files_list`, `drive_file_get`, `drive_about`, `drive_item_list/get/update/delete`, `drive_collaboration_item_list/get`, `drive_metadata_update`, `drive_meet_files_list`, `drive_photo_files_list` | The item-scoped paths use `drive.item[.readonly]`. Metadata updates accept only selected metadata fields. `drive_photo_files_list` lists image/video files in Drive; it is not a Google Photos Library implementation. |
| Drive file/share scopes | `drive_file_create/update/copy/delete`, `drive_permission_list/create/update/delete` | File operations and permission/share changes are confirmation-gated. Broad restricted Drive access requires consent-screen verification and may require additional review. |
| Drive app data / Apps Script / Activity | `drive_appdata_list/create/delete`, `drive_apps_list`, `drive_script_get/create/update`, `drive_activity_list` | App data is constrained to the appDataFolder. Apps Script source update and creation require confirmation. Drive Activity is query-only in this adapter because its REST API exposes a query method, not an activity-write endpoint. |
| Google Docs | Core `docs_read`, `docs_create`; extended `docs_replace_text`, `docs_insert_text`, `docs_batch_update` | Write requests are limited to an explicit set of Docs API request types and require confirmation. |
| Google Sheets | Core `sheets_read`, `sheets_update`; extended `sheets_create`, `sheets_append`, `sheets_clear`, `sheets_batch_update` | Structural requests use an explicit request allowlist. Writes require confirmation. |
| Google Slides | Core `slides_read`, `slides_create`; extended `slides_batch_update` | Batch update request types are allowlisted and require confirmation. |
| Google Tasks | `tasks_list/create/update/delete/complete/reopen` | Task changes require confirmation. Current default task list is `@default`. |
| People / Contacts | `people_user_profile`, `people_contacts_search`, `people_contact_create/update/delete`, `people_other_contacts_list` | Profile data may include email/name/photo/phone/birthday/address/gender/age-range/organization fields only when those requested fields/scopes are enabled; `user.emails.read` is requested when emailAddresses are selected. Contacts writes require confirmation. |
| Google Classroom courses / rosters | `classroom_courses`, `classroom_course_get/create/update/delete`, `classroom_students_list`, `classroom_teachers_list`, `classroom_student_add/remove`, `classroom_teacher_add/remove`, `classroom_student_profile` | Course and roster writes require confirmation. Access is limited by the signed-in account role, Classroom API policies and the education domain. Email/photo fields need their corresponding profile scopes. |
| Google Classroom classwork | `classroom_coursework`, `classroom_coursework_create/update/delete`, `classroom_materials`, `classroom_material_create/update/delete`, `classroom_topics`, `classroom_topic_create/update/delete`, `classroom_announcements`, `classroom_announcement_create/update/delete` | Operations are subject to teacher/owner roles. Each mutation requires confirmation. |
| Google Classroom submissions / guardians / notifications | `classroom_submissions_list/update/turn_in/reclaim/return`, `classroom_guardians_me/list/create/delete`, `classroom_registration_create/delete` | The submissions read path selects the `me` scope for the current user's submission and the admin/student-submissions scope when a different student is requested. Guardian and roster access is restricted by Classroom role/policy. Push registration requires the configured Pub/Sub target. |
| Google Meet REST API | `meet_space_create/get/update`, `meet_end_conference`, `meet_conference_records`, `meet_recordings_list`, `meet_transcripts_list`, `meet_participants_list` | This is Meet REST metadata/artifact access; it is not live call audio/video capture. Recording/transcript resources only exist when the organization/account and conference produced them and the caller has permission. |
| YouTube Data API v3 | `youtube_search` (core), `youtube_channel`, `youtube_my_videos`, playlist list/create/update/delete/item add/remove, `youtube_upload`, `youtube_video_update/delete`, `youtube_comment_insert`, `youtube_memberships` | Uploads, publication, changes and deletes require confirmation. Channel-member endpoints and some YouTube account capabilities require specific account eligibility and approved API access. |
| Google Forms API | Core `forms_read/create`; extended `forms_responses_list/get`, `forms_update`, `forms_response_watch_create/delete` | Response data is private. Form edits and notification watch changes require confirmation. |
| Generative Language API | `generative_tuned_models_list`, `generative_tuned_model_get`, `generative_tuning_delete`, `generative_retriever_list/get/create/delete/query`, `generative_peruserquota_status` | Tuning/retriever operations use OAuth-specific profiles. `generative_peruserquota_status` honestly returns unavailable because that scope has no standalone quota-query endpoint in this adapter. Arthur's primary text, tool-routing, and vision generation uses Groq; these Google Generative Language administration operations remain separate OAuth-backed features. |
| Cloud Translation / Cloud Natural Language | Existing OAuth-backed translation and text-analysis adapters | Requires each corresponding Cloud API enabled and its feature profile consented. |
| Google Maps Platform / Cloud Vision | Existing Routes, Geocoding, Weather, Places, Air Quality, Pollen, Time Zone, Roads, consented Geolocation and Cloud Vision Web Detection adapters | Use API keys with API restrictions; these are separate from OAuth Workspace scopes. See `.env.example` and `INTEGRATIONS.md`. |

#### Scope features that cannot be provided by a desktop OAuth token alone

| Scope family / item | Status and reason |
|---|---|
| `gmail.addons.current.action.compose`, `gmail.addons.current.message.action`, `gmail.addons.current.message.metadata`, `gmail.addons.current.message.readonly` | Not desktop features. They are contextual scopes for a Google Workspace/Gmail add-on runtime and active-message/add-on interactions. Equivalent desktop Gmail operations are implemented through Gmail API scopes, but they cannot reproduce the add-on context lifecycle. |
| `calendar.settings` | The Calendar API settings resource exposes list/get operations in this adapter/API surface; the scope string does not create a settings-write method. `calendar.settings.readonly` is implemented. |
| `drive.activity` write permission | Drive Activity API v2 is exposed via its query operation. There is no activity-write operation in this adapter; viewing activity is implemented with `drive.activity.readonly`. |
| `drive.install` | Installation/integration permission rather than a general file CRUD REST operation. The desktop app does not claim to install an app into Drive. |
| `drive.photos.readonly` | The current operation lists Drive image/video files. It does not manage Google Photos albums or media; that separate product surface is not implemented here. |
| `classroom.addons.student`, `classroom.addons.teacher` | Classroom add-on attachment operations run in the Classroom add-on context and are not the same as the desktop Classroom REST integration. Not implemented as add-on attachment lifecycle handlers. |
| `classroom.practicesets` | The scope is listed in the consent catalogue, but a stable public API surface for the requested create/read/delete workflow is not exposed in this desktop adapter. Not claimed implemented. |
| `meetings.conference.media.readonly`, `.audio.readonly`, `.video.readonly` | Live media capture is separate from Meet REST records/participants/transcripts and requires its specific client/runtime and eligibility. Google currently says the Meet Media API is no longer accepting new Developer Preview signups. |
| `meetings.hardware` | Organization-level Meet hardware history/control needs product/admin-specific APIs and privileges; no hardware-control handler is exposed. |
| `generative-language.peruserquota` | The scope does not by itself provide a standalone quota-query REST endpoint. The capability report returns this as unavailable rather than fabricating quota data. |
| `youtube.download` | Arthur does not download YouTube media files. The YouTube Data API is not treated as an unrestricted video-file download API. |
| `youtube.third-party-link.creator`, `youtubepartner`, `youtubepartner-channel-audit` | Partner/content-owner or account-linking features require dedicated product access, account eligibility and often provider approval. They are not implemented as general-purpose channel administration. |
| `gmail.settings.sharing` | The adapter exposes the documented delegate list/create/delete workflow through the Gmail delegates scopes. It does not provide arbitrary mail delegation policy administration beyond those endpoints. |
| `drive.apps` write, broad organization administration | Only operations with a corresponding supported REST method are exposed. A scope being writable in the consent catalogue does not mean there is a general endpoint to create/install arbitrary Drive apps or administer a Workspace organization. |

#### Third-party website launcher allowlist

These fixed website aliases are available to `open_website` and the local voice parser:

- Google Cloud Console — [https://console.cloud.google.com/](https://console.cloud.google.com/)
- Neon — [https://console.neon.tech/](https://console.neon.tech/)
- Google Classroom — [https://classroom.google.com/](https://classroom.google.com/)
- Google Contacts / Contacts — [https://contacts.google.com/](https://contacts.google.com/)
- LeetCode — [https://leetcode.com/](https://leetcode.com/)
- LinkedIn Learning (including the user's typed spelling `linkedln learning`) — [https://www.linkedin.com/learning/](https://www.linkedin.com/learning/)
- Coursera — [https://www.coursera.org/](https://www.coursera.org/)
- SWAYAM (including the voice/typing alias `swaym`) — [https://swayam.gov.in/](https://swayam.gov.in/)
- NPTEL — [https://nptel.ac.in/](https://nptel.ac.in/)

This is a trusted browser-launch allowlist, not OAuth/API access to Neon, LeetCode, LinkedIn Learning, Coursera, SWAYAM, or NPTEL. These sites remain subject to their own login, terms, and supported APIs.

#### First-run checklist

1. Put your Desktop OAuth JSON at `credentials/google_oauth_client.json` or point `GOOGLE_OAUTH_CLIENT_FILE` to your existing path.
2. Merge new variables from `.env.example` into your existing `.env`; do not replace a populated `.env` with a template.
3. Enable each Cloud API you actually use. Configure OAuth consent scopes separately from API-key restrictions.
4. Start Arthur and invoke one requested feature; complete the feature-specific consent flow and verify the result against the resource in Google's own UI.
5. Test read and write operations separately. For write operations, verify that Arthur presents the confirmation details before making the change.
6. Do not share `credentials/`, `data/google_tokens/`, `.env`, or any token file in issues, screenshots, source control or archives.

## Original file: `SECURITY_AND_PERMISSIONS.md`

### Arthur Security, Privacy and Permission Policy

This policy applies to the Windows client, FastAPI device agent, Google Workspace adapters, and remote client starters.

#### 1. Camera, microphone and screen privacy

- Camera capture may run locally for the active view but it does not produce spontaneous scene narration. Narration and OCR/read-aloud happen after a user request.
- Microphone recording starts only after a voice-command action or explicitly armed wake-word flow. Keep a visible listening/recording state and a stop control.
- Camera frames and screenshots are not sent to Groq or Cloud Vision as a side effect of routine command transcription. Product/visual search and screen-description upload must be a distinct user-approved action because the frame may contain people or private information.
- API audio uploads are bounded to 20 MB, saved to a temporary file for local Whisper, and removed in a `finally` cleanup path. The transcript is returned to the client; the audio is not passed to Groq by that endpoint.
- Local memory, face templates, screenshots, voice recordings and Google OAuth tokens are data with different retention needs. Store each only in its intended local directory; do not commit `data/`, `.env`, credentials or tokens.

#### 2. Semantic routing and tool execution

- The LLM receives a registered function catalogue, not a Python interpreter, terminal, shell, arbitrary URL launcher or unrestricted file-system tool.
- Function calling is returned as data with automatic execution disabled. The executor chooses from a finite action registry, validates arguments and checks device/provider capability.
- Local parser/pattern and embedding routes must use the same typed tool executor and policy checks as LLM-selected intents.
- Ordinary text-only Groq fallback is sent directly from the desktop or authenticated API client without an additional prompt. Only the current request text is sent by default; recent conversation context stays local unless explicitly enabled. Camera/screen bytes never accompany this fallback and remain protected by separate upload confirmations.
- Tool responses must distinguish a requested action from an observed result. A keyboard shortcut or provider submission is not proof of email delivery, playback state, meeting attendance or network connectivity.

#### 3. Confirmation policy

Ordinary text-only requests are sent directly to Groq without an extra consent dialog. This is a deliberate user-configured behaviour: the current request text is sent automatically, while prior conversation context remains local unless sharing is explicitly enabled.

Require an explicit user review/confirmation step before:

- Sending Gmail messages or WhatsApp messages.
- Creating or modifying Google Calendar events.
- Disabling/enabling a network adapter.
- Saving, replacing or deleting Word document content, including the current selection.
- Creating, updating, replacing, or deleting Google Drive/Docs/Workspace content or account settings.
- Uploading camera images, screenshots, or other private visual data to an external AI service.
- Executing GUI workflows that paste sensitive text into a known application.
- Other irreversible or externally visible actions added to the tool registry.

Gmail and WhatsApp compose workflows create drafts and stop before sending. The send step must be a separate action. A UI confirmation should show recipients/contacts, subject, complete message, or calendar title/time/timezone in enough detail to review. Never accept a vague “yes” as confirmation for an action whose target or content is not displayed.

#### 4. FastAPI network boundary

- Development default: bind `VISIONGUIDE_API_HOST=127.0.0.1`.
- Binding to a non-loopback host requires `VISIONGUIDE_API_TOKEN`; the app fails startup if it is absent.
- Supply the token as `Authorization: Bearer <token>` over HTTP and authenticate WebSocket connections with the first frame `auth:<token>` rather than a URL query parameter.
- Confirmation IDs are high-entropy, one-use, expire after five minutes and are bound to the requesting `device_id`. IDs expire from the bounded in-memory store; only the exact stored intent can be executed after approval.
- Apply firewall restrictions to private networks. Do not expose the device API directly to the public internet. Remote deployment requires TLS/WSS, strong authentication, rate limiting, audit identifiers, request budgets, revocation and per-device authorization.
- `/api/v1/transcribe` limits body size and allowed audio extensions. Add reverse-proxy limits, request timeouts and rate limits in a deployed gateway.

The development bearer token is one shared secret; it is not a production identity or per-user authorization system. The current service does not implement a full device-pairing lifecycle or production audit database.

#### 5. OAuth and Google data

- Use the installed-app OAuth flow with the per-feature scope profiles in `visionguide/integrations/google_workspace.py`. Cloud Translation and Natural Language use dedicated OAuth profiles too; Groq uses `GROQ_API_KEY` and does not need Groq OAuth scopes for normal text/image generation.
- Store `credentials/google_oauth_client.json` and every `data/google_tokens/google_*.json` file locally and outside source control. Restrict machine account access and back up neither file to a public repository.
- Request only the scopes needed by enabled workflows. Gmail reading, sending, Contacts, Drive, Classroom, and Cloud scopes can expose private data. Do not select every scope in the Data Access catalogue simply because it is listed; add-on-only, admin, media-capture, deletion, and broad Drive permissions are not needed by this desktop integration.
- The Maps API key and Cloud Vision API key use API-key restrictions. Cloud Translation and Natural Language use OAuth scopes. API enablement, OAuth scope configuration, and API-key restrictions are separate settings and all must match the intended integration.
- Never print access/refresh tokens or full email bodies in debug logs. Responses may include private email content; show and speak only what the user requested.
- Provide a revoke/disconnect workflow for deployed builds; to force a fresh local consent in the current package, revoke the app grant in the Google account and delete the local token file.

#### 6. GUI and operating-system controls

- `pygetwindow` identifies active target windows by title keyword; title matching is not identity proof. Verify the window and current field focus before pasting sensitive content.
- `PyAutoGUI.FAILSAFE` remains enabled. Stop a workflow if a window cannot be located, the title changes unexpectedly, or a checkpoint fails.
- Website and application launch use allowlists. Never call `subprocess(..., shell=True)` with user/model text, and do not add a generic “execute code” tool to the semantic registry.
- `netsh` changes a specific adapter only after checking its name and obtaining confirmation; this may interrupt API connectivity.
- Brightness and audio values are validated and bounded. Hardware/driver results are surfaced without claiming every external display supports brightness control.
- System-wide hand gestures are explicitly armed. They move the pointer, click keys in the unified air virtual keyboard, scroll and switch tabs. Do not enable them while entering credentials, editing sensitive records or approving transactions. The top-left PyAutoGUI failsafe remains active. The keyboard overlay attempts to use Windows `WS_EX_NOACTIVATE` so key clicks do not take focus away from the target app; test this with each target program.

#### 7. Face and ISL data

##### Face data

Face memory must be opt-in and limited to people who have consented to be enrolled. OpenCV LBPH is retained and optional DeepFace embeddings can improve local enrolled-user comparison; if models conflict, return Unknown rather than forcing a personalized match.

Samples and embedding vectors stay locally under `data/faces/` and must not be included in project ZIPs. Use the local enrolled-person workflow; do not identify a stranger from a face or run public-web reverse face identification.

Visual Web Detection is a separate public-page/similar-image search and its matches are not identity verification. Visible text on a badge can be read when explicitly requested, but it is separate from face identity.

##### Indian Sign Language data

Arthur's current ISL recognition pipeline uses a Torchvision Swin3D-S video classifier with 76 isolated-sign classes.

- The recognizer processes a sequence of 32 video frames rather than classifying a single still image.
- Inference is performed locally using the checkpoint at `models/isl/swin3d_s/ISL_best_model.pt`.
- The current pipeline supports isolated-sign recognition only. It does not provide continuous sentence-level ISL translation or general-purpose sign-language conversation.
- MediaPipe Holistic and the previous TensorFlow LSTM architecture are not the active Swin3D ISL inference pipeline. MediaPipe remains relevant to gesture-control functionality.
- ISL samples, trained checkpoints, class labels and sign-recognition outputs may contain biometric and linguistic information. Protect them accordingly.

Use signer consent, dataset/model manifests, provenance and explicit retention policies. Do not include private signer samples or trained model assets in public project archives unless their licences and consent conditions permit redistribution.

ISL validation must be separate from other sign languages and should evaluate unseen signers, natural sequence context, signing speed, camera position and lighting. A classifier prediction is not guaranteed to be correct and should not be presented as a definitive translation without appropriate context.

#### 8. Logs, retention and reporting

Log command IDs, route/action names, timing and success/failure categories—not credentials, full email bodies, raw audio, camera frames or personal notes.

The timer service is in-process and the current API has no durable audit database; do not promise persistent delivery after a process exit.

The mobile starter does not persist API credentials in secure device storage yet; use it as a development client until a platform-native secure storage and pairing lifecycle is added.

#### 9. Location, navigation and cloud API budget guardrails

- Live navigation uses Windows Location services only after the user opts in. Enable/allow location in Windows Settings; live position is used for route progress and is not stored as a user profile. Disable navigation to stop polling.
- Maps Platform calls use `GOOGLE_MAPS_API_KEY`; optional Cloud Vision uses a separately restricted `GOOGLE_CLOUD_API_KEY`/`GOOGLE_VISION_API_KEY`; Cloud Translation and Natural Language use OAuth profile tokens. The application maintains per-device daily counters and local cache for Maps data, but this is not a replacement for project-level quotas, API restrictions, Cloud Billing budget alerts or monitoring other apps that share the billing account.
- Place names/coordinates and derived weather/air-quality/pollen/time-zone data may be cached locally. User-supplied text for translation/natural-language analysis is not cached by those adapters, but is sent to Google when the request is executed. Wi-Fi access-point identifiers are never collected locally by this code; any provided identifiers are sent only after explicit consent.
- Traffic-aware Routes and two-wheeler routing can use higher-priced SKUs. Check current country-specific prices/SKUs before enabling them; a Google Cloud key does not guarantee free usage.
- A route result, GPS poll, or off-route trigger can fail due to missing permission, unavailable position, poor coverage, quota, billing or network issues. Arthur must state these failures clearly and is not a certified navigation or mobility-safety aid.
- Word save, replace, and selected-text deletion each require a dedicated confirmation. Delete checks that the active selection still matches the preview before changing the document. Google Workspace create/update/delete operations remain confirmation-gated by their executor, not merely by the language model.

## Original file: `CONTINUOUS_ISL.md`

### Indian Sign Language (ISL) Architecture

#### Scope

Arthur's sign-language scope is Indian Sign Language only. The current isolated-sign classifier pipeline remains a supported component. The architecture also defines distinct adapters for continuous ISL-to-text translation and text-to-ISL presentation.

Sign recognition and sign generation are separate machine-learning problems and must use ISL-specific datasets, models, annotation conventions, validation and language expertise. A sequence of isolated labels is not automatically a grammatical ISL sentence.

The current isolated-sign classifier is a video-based Swin3D-S model. Continuous ISL-to-text translation and text-to-ISL presentation remain separate architectural capabilities and must not be represented as implemented merely because their adapter contracts are documented.

#### 1. Isolated-sign classifier pipeline

The existing Python sign module, `visionguide/sign_language.py`, is the initial isolated-sign integration path.

##### Current implementation

- **Architecture:** Torchvision Swin3D-S video classifier.
- **Class count:** 76 isolated-sign classes.
- **Checkpoint:** `models/isl/swin3d_s/ISL_best_model.pt`.
- **Dataset directory:** `data/isl_dataset/ProcessedData_vivit`.
- **Inference input:** A temporal clip of 32 frames, rather than a single still image.
- **Processing:** Resize the shortest edge to 256 pixels while preserving aspect ratio, center-crop to 224 × 224, convert to RGB, and normalize pixel values to the `[-1, 1]` range.
- **Tensor layout:** `[B, C, T, H, W]`.
- **Execution:** Local PyTorch/Torchvision inference.

The checkpoint uses a 76-class classification head. Its `classification_head.0.` parameters are mapped to the Torchvision model's `head.` parameters during loading.

##### Intended inference workflow

1. Capture a bounded sequence of camera frames.
2. Prepare a 32-frame clip using the preprocessing configuration associated with the trained checkpoint.
3. Run Swin3D-S inference locally.
4. Return the predicted class label and confidence.
5. Return `unknown/reject` when confidence is below the configured threshold.
6. Display the predicted label and allow the user to correct it. Speak only when the user has enabled speech output for sign recognition.

The current integration uses a background inference worker that collects frames and schedules predictions. The application handles repeated-label suppression and sign-mode state.

##### Dataset and model requirements

Maintain a model manifest containing:

- Dataset name, source URL and provenance.
- Dataset licence and permitted uses.
- Signer consent and relevant data restrictions.
- Class names and versioned label map.
- Checkpoint hash and model architecture.
- Preprocessing configuration and version.
- Training and evaluation split methodology.
- Device requirements and dependency versions.
- Last validation date and known limitations.

Dataset labels describe the collected vocabulary. They must not imply that the model understands arbitrary connected signing, facial grammar or context unless those behaviours are explicitly trained and evaluated.

The current 76-class classifier supports isolated-sign recognition only. It is not a continuous sentence translator.

#### 2. Continuous ISL-to-text adapter

Continuous ISL-to-text translation is a separate model and integration path. It must not be implemented by simply concatenating predictions from the isolated-sign classifier.

The stable interface accepts a bounded sequence from the client camera and returns structured output:

```json
{
  "task_id": "string",
  "language": "ISL",
  "text": "recognized/translated text",
  "gloss_sequence": ["..."],
  "confidence": 0.0,
  "alternatives": [],
  "model_id": "string",
  "warnings": [],
  "needs_correction": false
}
```

`gloss_sequence` may be empty when the model produces text directly. Values must never be fabricated merely to fill a field. Preserve timestamps where the model provides alignment.

The client must show confidence and uncertainty, allow correction, and distinguish a raw recognized gloss sequence from a translated natural-language sentence.

##### Research and data sources

- **ISLTranslate** describes ISL-English sentence/phrase pairs and translation benchmarks: <https://aclanthology.org/2023.findings-acl.665/>. Treat this as a research dataset/benchmark and confirm the applicable dataset conditions before use.
- **ISH-NEWS** describes ISL sentence-video research and a transformer baseline: <https://www.nature.com/articles/s41598-026-60893-0>. Source-video redistribution and dataset-use restrictions must be reviewed independently.
- **Sid-V5/isl-translator** describes a continuous ISL recognition pipeline: <https://github.com/Sid-V5/isl-translator>. Evaluate its current code, checkpoint availability, licence, dependency constraints and GPU requirements before integrating it. Do not equate a repository description or published metric with validation on the Arthur client.

These are research references, not proof that their models or datasets are already integrated into Arthur.

The project must keep a model manifest recording checkpoint hash, source URL, licence, training/evaluation datasets, preprocessing version, device requirements and last validation date. Research metrics must be reproduced or cited accurately and must not be presented as real-world guarantees.

#### 3. Text-to-ISL presentation adapter

Text-to-sign requires its own ISL-appropriate linguistic pipeline and rendering output, for example, a validated signer video sequence or a signing avatar.

It must not simply map every English word to a sign clip or reuse material from another sign language. The adapter contract should accept target text plus the chosen output mode, then return ISL-specific clip/pose/sequence metadata and clear limitations.

Validate translations with fluent ISL signers and Deaf-community reviewers. Preserve grammar, non-manual signals, two-handed articulation and spatial agreement where the representation supports them.

When no supported signing is available, ask for a simpler rephrasing or state that the requested expression is not represented. Do not invent a sign.

Text-to-ISL generation is a separate capability; the existence of the isolated-sign recognition model does not provide this functionality.

#### 4. Evaluation and user experience

- Split evaluation by signer, not just by randomly shuffled clips, to measure generalization to unseen signers.
- Test natural connected signing, different lighting/backgrounds, signing speed, occlusion, one- and two-handed signs, clothing, camera distance and front-facing/side angle.
- Report word error rate or sentence-level metrics when suitable; document vocabulary coverage, signer count, environment and failure categories.
- For isolated-sign classification, report top-1/top-5 accuracy, macro and weighted F1, per-class performance, confusion patterns and inference latency.
- Add correction and retry controls. Do not automatically send a predicted sign translation to another person without showing the user what will be sent.
- Keep video local unless a chosen service requires a remote transfer and the user confirms it.
- Do not advertise the system as a certified interpreter or safety-critical communication service solely because a model produces text.

##### Current isolated-classifier evaluation limitations

The previously reported Swin3D-S evaluation recorded:

| Metric | Reported result |
|---|---:|
| Top-1 accuracy | 80.75% |
| Top-5 accuracy | 99.47% |
| Macro F1 | 0.8150 |
| Weighted F1 | 0.7854 |
| Inference time | Approximately 400–410 ms |
| Peak GPU memory | Approximately 925 MB |

These results came from a stratified random split, not a signer-held-out evaluation. They therefore do not establish generalization to unseen signers. Some classes also have very small test samples.

These are isolated-classifier evaluation results, not continuous translation metrics or evidence of live-camera integration.

#### 5. Relationship to other vision components

ISL recognition and gesture control may share camera infrastructure, but they have different capture requirements and interaction semantics.

- The current ISL classifier uses the Swin3D-S temporal video pipeline.
- MediaPipe remains part of Arthur's gesture-control pipeline; it is not the current Swin3D ISL inference model.
- Gesture mouse and sign recognition must have separate mode handling.
- A hand-click event must not trigger sign classification unintentionally.
- Hand-landmark debug output must never be exposed as a sign translation.
- Use a single capture broker with explicit modes and mutual exclusion where simultaneous camera consumers are unsupported.

The application must make the active camera mode clear and release camera resources when the corresponding mode is stopped.

## Original file: `RESEARCH_NOTES.md`

### Arthur — public research and architecture decisions

Research pass performed on 24 October 2026 using official product support pages, model cards, upstream GitHub repositories, a public ISL dataset catalogue, and official API documentation. This is a targeted engineering review, not a systematic benchmark or a review of every forum thread. No physical-scene accuracy test has been performed with the user's camera.

#### What existing products already do

| Product | Capabilities documented by the vendor | Design implication for Arthur |
|---|---|---|
| Microsoft Seeing AI | Focused channels for text/documents, products, scenes and enrolled people, plus richer scene descriptions and document chat. | Keep user-triggered tasks and focused modes; OCR should be a separate operation from general scene description. |
| Google Lookout | Text, documents, currency, food labels, image descriptions and a Find-object mode; Explore is explicitly marked beta/less accurate in current help. | Make object search a first-class command and avoid claiming all scene perception is equally reliable. |
| Envision Glasses | Scan text, batch scan, describe scene, find objects/people, face teaching, colours and companion/agent workflows. | Model personal memory as explicit user-controlled data; have a distinct scene-Q&A workflow. |
| OrCam MyEye 3 Pro | Reads printed/screen text, recognises enrolled faces and products, finds requested words, and includes interactive AI magnification features. | Build OCR word lookup as a first-class capability, rather than treating a page as just an image caption. |
| Ray-Ban Meta | Hands-free visual Q&A and creative/general assistant use; the official FAQ describes cloud processing of camera images. | Make cloud uploads explicit and disclose when image frames or text are sent off-device. |
| Aira | Live human visual interpretation by trained agents through a phone camera, rather than an all-AI model. | Human assistance is a valuable fallback for high-stakes/ambiguous navigation, but is outside this offline prototype. |

Official links:

- Seeing AI: <https://blogs.microsoft.com/accessibility/seeing-ai-app-launches-on-android-including-new-and-updated-features-and-new-languages/>
- Lookout: <https://support.google.com/accessibility/android/answer/9031274>
- Envision scene description and follow-up: <https://support.letsenvision.com/hc/en-us/articles/7603823400849-Describe-Scene>
- Envision Professional Edition features: <https://shop.letsenvision.com/en-in/products/glasses-professional>
- OrCam MyEye 3 Pro: <https://www.orcam.com/en-gb/orcam-myeye-3-pro>
- Ray-Ban Meta FAQ: <https://india.ray-ban.com/ray-ban-meta-faq>
- Aira human assistance: <https://www.aira.io/>

These feature pages do **not** establish that any product offers a single, general, validated system that combines monocular metric distance, collision prediction, free-form air keyboard, and general sign-language translation. Product features and availability vary by hardware, software version, country, language and subscription.

#### Upstream open-source components applied

##### 1. Depth Anything V2 Metric Small — indoor Hypersim

- Upstream code: <https://github.com/DepthAnything/Depth-Anything-V2/tree/main/metric_depth>
- Metric indoor Small checkpoint: <https://huggingface.co/depth-anything/Depth-Anything-V2-Metric-Hypersim-Small>
- The model card lists Apache-2.0 for the Small metric checkpoint and a 99.2 MB file. The corresponding model is intended for indoor metric-depth estimation from the Hypersim training setup; a different model exists for outdoor Virtual KITTI 2 scenes.
- Applied: model setup/downloader, depth map inference, robust median sampling in the interior of detected object boxes, one-point scale calibration, and temporal radial-depth-change heuristic.
- Not claimed: a camera-calibration guarantee, accurate steps for every user, reliable outdoor estimates or a validated safety system. The prototype's single-point scale factor cannot correct every object- and scene-dependent model error.

##### 2. MediaPipe Hand Landmarker

- Official guide: <https://developers.google.com/edge/mediapipe/solutions/vision/gesture_recognizer>
- Applied: hand landmarks for explicit air-mouse cursor control and gesture-based interaction with the unified air virtual keyboard. Gesture control is an opt-in interaction mode with activation and disable controls.
- The current air-gesture implementation includes pointer movement, pinch-click, scrolling, browser-tab swipes, smoothing and calibration. The virtual keyboard is integrated into the desktop interaction workflow.
- Not claimed: a complete gesture vocabulary, sign-language understanding or reliable focus preservation in every third-party application. Gesture tracking is not the same task as recognizing a natural sign language.
- MediaPipe is not the active ISL inference architecture. The current ISL classifier uses a separate video-based Swin3D model.

##### 3. Current Indian Sign Language classifier — Swin3D-S

- Architecture: Torchvision `swin3d_s`, configured for 76 output classes.
- Checkpoint: `models/isl/swin3d_s/ISL_best_model.pt`.
- Dataset directory used by the current training/evaluation workflow: `data/isl_dataset/ProcessedData_vivit`.
- Inference uses a 32-frame video clip, with local preprocessing and model execution.
- Applied: an isolated-sign classification pipeline with a local checkpoint and a limited vocabulary. The current inference path is separate from MediaPipe gesture tracking.
- Not claimed: continuous sentence interpretation, ISL grammar translation, signer-independent generalization, or communication-grade performance. A 76-class isolated-sign classifier is not a continuous ISL translation system.
- Independent evaluation results should be reported with their methodology and limitations. A random stratified video split is not equivalent to a signer-held-out evaluation and does not establish generalization to unseen signers.

**Dataset provenance limitation:** The Amrita SLR dataset catalogue below is a research reference, but its presence in this document does not establish that the current Swin3D checkpoint was trained on that dataset. Confirm the actual checkpoint training data, source, licensing and preprocessing provenance before attributing the current model to a particular dataset.

##### 4. Amrita SLR — Real Time ISL Dataset (research reference)

- Dataset page: <https://data.mendeley.com/datasets/dtg9s785v8/1>
- Dataset record lists 50 common ISL signs, approximately 16 recordings per class and seven signers; it is about 1.36 GB and licensed CC BY 4.0 according to the record.
- This is a potentially relevant public dataset reference for ISL research. It should not be represented as the confirmed source of the current Swin3D checkpoint without training records or other provenance evidence.
- The earlier landmark-sequence/LSTM approach is not the current ISL inference architecture.

##### 5. OpenCV, Tesseract, SQLite and Whisper

- OpenCV packaging/licensing: <https://github.com/opencv/opencv-python>
- Tesseract OCR: <https://github.com/tesseract-ocr/tesseract>
- Whisper: <https://github.com/openai/whisper>
- Applied: camera/video capture, image preprocessing and perspective-correction attempt, local OCR wrapper, local notes memory using SQLite, and locally run Whisper transcription.
- These components serve distinct functions. OpenCV handles image/video processing, Tesseract provides OCR, SQLite stores local notes, and Whisper handles speech transcription. Their presence does not by itself establish end-to-end accuracy or reliability.

##### 6. YOLO26 / Ultralytics license

- Upstream repository: <https://github.com/ultralytics/ultralytics>
- Ultralytics currently describes AGPL-3.0 and a separate enterprise license. The user's existing `yolo26n.pt` file is preserved for continuity.
- A permissively licensed end-to-end application cannot be assumed while relying on this component; confirm current terms for redistribution/commercial use.

#### Specific engineering changes from research

1. **User-commanded speech:** The app has no startup spoken greeting or continuous narration. Online image requests and microphone recording require separate user actions; image sharing requires confirmation.
2. **Separate local and online reasoning:** Local YOLO summaries work without an API key; Groq can describe visual details and answer general questions only after an explicit request. Text-only AI does not attach a camera image.
3. **Depth separated from detection:** Depth is an opt-in model because it is large and can be slow. Calibration is stored separately and marked approximate.
4. **Safety logic is cautious:** Depth alerts require several temporal samples, plausible closing motion, range limits and a cooldown. This is a heuristic and remains off by default; it is not a validated collision predictor.
5. **Personal memory is local and explicit:** User notes are written to SQLite only when requested, searchable, and deletable. Face recognition is limited to consented local enrollment; no stranger face-search service is called.
6. **Hand control is opt-in:** Air mouse and air keyboard are explicit interaction modes. The unified virtual keyboard is integrated with the desktop control workflow. Focus preservation and safe interaction with arbitrary third-party applications remain validation requirements.
7. **Sign-language claims are constrained:** The current code provides a Swin3D-based training/inference pipeline for a limited isolated ISL vocabulary. It requires the dataset and model assets to be available locally. MediaPipe hand landmarks alone do not produce sign-language translation, and the current isolated-label classifier does not provide continuous sentence translation.

#### What still requires empirical research and validation

- Real-world distance error distributions over indoor/outdoor scenes and different camera lenses; comparison against a physical tape measure or calibrated range sensor.
- Motion prediction under camera motion, occlusion, track swaps and intersecting vs non-intersecting trajectories.
- Human-subject usability review with blind and low-vision users and orientation-and-mobility professionals.
- Signer-separated validation and review by fluent ISL users before sign predictions are used in conversation.
- Verification of the current Swin3D checkpoint's dataset provenance, training procedure, license and signer distribution.
- Native phone/Android/iOS/smart-glasses client, latency/power measurements and offline speech output suited to the eventual hardware.
- Privacy, consent, retention, security and regional legal review before any release that stores biometric or location-related data.

## Original file: `ROADMAP.md`

### Arthur Implementation Roadmap

This roadmap describes the engineering state of the integrated source and the next release gates. The core desktop integrations and API client/server path are present in source; the remaining work is chiefly field validation, robustness, deployment hardening, and completing the sentence-level ISL model path.

#### Track 1 — Semantic command router

**Implemented in source:** Whisper transcript input, Groq function calling through registered typed tool declarations, deterministic parser/pattern fallback, SentenceTransformers semantic similarity fallback, typed `RoutedCommand`, and direct text-only Groq fallback in both desktop and authenticated API clients; prior conversation context remains opt-in.

**Next engineering gates:** Grow a paraphrase/argument test corpus; test dates, time zones, named contacts, multi-clause commands and low-confidence utterances; add clear clarification turns for arguments the model cannot safely infer; record route source and final execution status without logging private content.

#### Track 2 — Windows, browser and OS controls

**Implemented in source:** YouTube/browser shortcuts via PyAutoGUI/PyGetWindow; screen brightness via `screen-brightness-control`; Windows master audio/mute via Pycaw; named network adapter status/state through `netsh`; and UI/API confirmation for adapter changes.

**Next engineering gates:** Test on the target laptop and external monitors; validate supported Windows builds and permission failures; confirm playback focus and shortcut results; add post-action value checks where the driver exposes them; evaluate adapter names on non-English Windows installations. A play/pause keyboard toggle must not be described as a guaranteed playback-state read.

#### Track 3 — Desktop workflow execution

**Implemented in source:** Allowlisted window activation; paste/keyboard primitives; Gmail draft creation through a GUI workflow; Word document creation with unsaved review; WhatsApp Web draft entry; explicit separate send commands; and GUI target confirmation prompts.

**Additional implementation:** Word active-document save/save-as, find-and-replace, and selection deletion are exposed as separate confirmed actions; Drive file-content/metadata update and Docs range deletion are available through the allowlisted Workspace executor.

**Next engineering gates:** Verify the active target window and form-field focus after every step; add execution checkpoints with rollback/retry boundaries; improve screen/OCR verification across browser versions and accessibility settings; and test that interrupted workflows never continue in a newly focused window. Keep sends as a separately confirmed terminal action.

#### Track 4 — Gmail and Google Calendar

**Implemented in source:** OAuth 2.0 desktop flow; Gmail unread/search/read/API draft/send adapters; Calendar upcoming/search/create adapters; input bounds; date-time and time-zone validation; FastAPI endpoints; and confirmations for sends and Calendar writes.

**Next engineering gates:** Complete account-based integration tests with a dedicated test mailbox/calendar; test OAuth revocation, refresh and changed scopes; test quotas and transient network errors; refine attendees/recurrence/time-zone support without weakening confirmation; provide a clear disconnect/revoke control; and evaluate token protection for packaged deployments.

#### Track 5 — Timers and reminders

**Implemented in source:** Bounded, cancellable background countdown timers, monotonic timekeeping, desktop async-queue notifications, REST timer endpoints and WebSocket expiry events.

**Next engineering gates:** Stress-test concurrent timers, verify alert delivery under minimized/background conditions, document shutdown behavior, and add durable scheduler storage if reminders must survive a reboot. Never describe an in-process countdown as a persistent calendar event.

#### Track 6 — FastAPI, mobile and wearable clients

**Implemented in source:** FastAPI JSON command endpoint; one-use device-bound confirmation tokens; local Whisper upload endpoint; timers and Workspace endpoints; authenticated WebSocket notification route; Python client; and Flutter command client starter with speech, recording/upload, confirmation and event UI.

**Next engineering gates:** Generate and build the Android/iOS platform shells using the Flutter SDK; test physical-device microphone permissions and local network connectivity; add a formal device pairing/capability registry; add rate limits and audit IDs; configure TLS for remote use; implement client-native camera and wearable sensors with consent; and test reconnect, token expiry and offline conditions. Validate Android and iOS builds separately if both platforms are intended for release. The API executes on its host device, not remotely on a phone's operating system.

#### Track 7 — Air gestures

**Implemented in source:** MediaPipe hand landmarks, index-fingertip system pointer movement, pinch-click debounce/cooldown, right-edge vertical scrolling, horizontal browser-tab swipes, pointer smoothing, two-point calibration, PyAutoGUI fail-safe, explicit enable/disable, and a unified system-wide air virtual keyboard controllable by mouse and the gesture pointer. Voice literal typing pastes into the currently focused target after confirmation.

**Next engineering gates:** Test camera placement, hand sizes, lighting and fatigue; tune gesture thresholds on the target webcam; verify loss-of-hand and emergency-disable behaviour. Validate focus-preservation on Windows 10/11 and across browsers/custom widgets; generic Python GUI automation cannot guarantee every field's focus. The legacy prompt-only keyboard module remains in the source tree for compatibility but is no longer instantiated by the main UI.

#### Track 8 — ISL

**Implemented in source:** An isolated-sign Indian Sign Language training/inference path using Torchvision Swin3D-S, with a 76-class classifier and a local checkpoint at `models/isl/swin3d_s/ISL_best_model.pt`. Inference uses a 32-frame video clip. The current architecture and documentation distinguish isolated-sign recognition from continuous sentence translation.

**Next engineering gates:** Build or integrate a licensed continuous-sign sequence model; include non-manual cues and temporal context; create signer-consented evaluation splits; report held-out-signer metrics and confidence/reject states; and build a separate ISL text-to-sign output pipeline. The current isolated-label classifier should not be presented as continuous sentence translation. Independent classifier evaluation does not, by itself, establish live-camera integration or generalization to unseen signers.

#### Track 9 — Google Cloud assistive services, face profiles and navigation

**Implemented in source:** Cached and application-capped Google Geocoding, Weather, Routes and Cloud Vision Web Detection REST adapters; local product/image research workflow with explicit upload approval; persistent per-profile preferences and bounded action/result history; LBPH recognition with optional DeepFace embedding fusion; Windows location polling, spoken route steps and best-effort off-route rerouting.

**Next engineering gates:** Validate each enabled Google API/key restriction and current SKU pricing; test budget alerts against the user's actual project/account consumption; verify camera upload consent flow and cache privacy; evaluate face recognition with consenting enrolled users and held-out lighting/pose samples; test location permission, GPS accuracy, rerouting and maneuver timing in real Windows field trials. These modules are prototypes and must not be treated as certified identity or mobility safety systems.

#### Release gates

1. Automated tests and Python compilation pass.
2. Provider tests run against an isolated Gmail/Calendar test account with explicit consent.
3. Windows system controls and GUI workflows are exercised on the actual supported laptop/display/browser combination.
4. Mobile client builds are generated and exercised on physical devices for each platform included in the release.
5. Security checks cover API binding, authentication, confirmation replay, OAuth token storage, logging and file permissions.
6. Release notes distinguish automated checks from provider/device testing and make no unsupported mobility-safety or delivery claims.

## Original file: `CHANGES_SUMMARY.md`

### Arthur — Unified Implementation Summary

**Release preparation date:** 2026-10-28

#### Integrated features

- Expanded semantic voice routing for literal typing, safe arithmetic, Calculator workflows, focus targets, action-result follow-ups, keyboard/gesture controls, weather, routing, live navigation, visual/product research and per-profile preferences.
- Unified the visible input keyboard into one system-wide air virtual keyboard. Mouse clicks, camera gesture pointer/pinch-click and confirmed voice typing share the focused Windows application workflow.
- Added smoothed and calibratable camera hand-pointer control, pinch click, right-edge scroll gestures and left/right browser-tab switching.
- Preserved local LBPH face recognition and added an optional local DeepFace embedding backend. Conflicting recognizer results are rejected as unknown. Per-enrolled-user preferences persist locally.
- Added bounded action/result history to support follow-up questions about prior operations.
- Added Google Geocoding, current Weather, Routes and Cloud Vision Web Detection adapters, response caching and local daily request caps.
- Expanded Google Workspace / Generative Language support to 197 typed operations across 146 OAuth feature profiles; 118 extended writes are confirmation-gated and all operation names are exposed to semantic routing.
- Expanded the browser-launch allowlist for Google Cloud Console, Neon, Google Classroom, Google Contacts, LeetCode, LinkedIn Learning, Coursera, SWAYAM and NPTEL, including voice-recognition spelling aliases.
- Added best-effort Windows live-location navigation with spoken maneuvers and off-route recalculation where the Windows location provider and Google Routes API are available.
- Added focused tests and updated architecture, command catalogue, security, integration, roadmap and validation documentation.

These features describe the integrated project scope. Their presence in the source code or documentation does not by itself establish successful operation on every Windows device, Google account or external service.

#### Verification

The reported offline validation run for this build passed:

- `python -m pytest -q`: **93 passed, 4 warnings**.
- `python -m py_compile main.py visionguide/*.py visionguide/integrations/*.py`: passed.
- `python -m compileall -q main.py visionguide tools tests clients/python`: passed.
- `python main.py --help`: passed.
- Desktop and API module imports: passed.

The tests use mocked Google provider responses and do not constitute Windows hardware or live-cloud acceptance testing.

The expanded Google Workspace registry is tested for schema coverage and pre-OAuth write confirmation. Live Google authentication, API approval, account eligibility and resource-level permissions still require your own Cloud project and account.

The four warnings are existing FastAPI `@app.on_event` deprecation warnings.

##### Validation boundaries

The reported checks establish offline test, compilation, CLI and import results for the tested environment. They do not establish:

- Successful operation of camera, microphone, gestures or global keyboard focus on every Windows device.
- Correct face recognition for every enrolled user or reliable recognition under changing lighting and camera conditions.
- Successful live navigation or safe obstacle avoidance.
- Successful authentication and execution of every Google Workspace operation.
- Live API billing, quota availability, account eligibility or administrator approval.
- Successful Flutter builds and physical-device integration.
- Generalization of visual or sign-language models to unseen users and environments.

The test count is a build-specific result and should be regenerated after source changes.

#### Important setup and limitations

- Copy `.env.example` to `.env`, then configure local API keys and paths. The delivered archives do not contain `.env`, credentials, tokens, face samples, caches or personal data. If an existing `.env` is populated, merge required variables manually instead of replacing it.
- The custom `Hello Arthur` wake-word model is not bundled; follow `WAKE_WORD_SETUP.md` to provide a compatible model. The model's actual trained trigger phrase must match the configured wake phrase.
- DeepFace is optional and heavyweight; LBPH remains available without it. Install `requirements-face.txt` only if you choose the enhanced model.
- Live navigation and global keyboard focus/gesture behaviour require real Windows testing. Navigation is a best-effort prototype, not a certified mobility or road-safety system.
- Local Google API daily caps are accidental-usage safeguards, not a replacement for Google Cloud project quotas, budget alerts, API restrictions, billing controls or review of current SKU pricing.
- Local face recognition is an opt-in preference/recognition feature, not secure identity verification or authentication.
- The current ISL runtime supports isolated-sign classification only. Continuous sentence-level translation and text-to-sign remain separate development requirements.

#### Release acceptance checklist

Before treating this build as release-ready:

1. Run the test suite again on the intended release source revision and record the exact result.
2. Verify the Python 3.11 Windows environment and required dependencies.
3. Test microphone, camera, wake-word activation and shutdown behaviour on the target machine.
4. Test gesture pointer, pinch-click, scrolling, tab switching and virtual keyboard focus across supported applications.
5. Verify local face enrollment, recognition conflicts and unknown-result handling.
6. Test representative Google Workspace read and write operations with the intended account, including confirmation before state-changing actions.
7. Verify Maps/Weather/Routes and Cloud Vision API configuration, restrictions, quotas and billing.
8. Test live navigation with Windows location enabled and verify that stopping navigation stops location polling.
9. Confirm that `.env`, OAuth tokens, face samples and personal data are excluded from release archives and source control.
10. Update the release documentation if the source revision, test count, registry counts or supported capabilities change.

## Original file: `VALIDATION_REPORT.md`

### Arthur Validation Report

**Validation date:** 2026-11-13  
**Project location:** `Arthur`  
**Environment:** Linux build/test container; Python 3.13 runtime for this verification pass. The project runtime baseline remains Python 3.11 x64 on Windows for the reference desktop application.


#### Direct Groq fallback and confirmed document CRUD follow-up (2026-11-13)

The latest overlay validation completed with **225 passed, 4 warnings** after adding tests for direct text-only Groq fallback (desktop and authenticated API), Microsoft Word save/save-as, find-and-replace, selection deletion, Google Docs content-range deletion and Google Drive file-content update. The direct fallback sends the current text request without a second consent dialog; conversation context remains opt-in. State-changing operations retain their confirmation gates.

The test environment is the Linux build container using Python 3.13. The Windows Word COM automation, live Google OAuth/API operations, browser UI and real Groq service still require testing on the target Windows laptop.

#### Automated checks performed

| Check | Result |
|---|---|
| `python -m pytest -q` | **149 passed, 4 warnings** (existing FastAPI `@app.on_event` deprecation warnings) |
| `python -m py_compile main.py visionguide/*.py visionguide/integrations/*.py` | Passed |
| `python -m compileall -q main.py visionguide tools tests clients/python` | Passed |
| `python main.py --help` | Passed |
| Import desktop and FastAPI modules | Passed |
| Google Workspace scope/operation allowlist consistency | Passed (197 extended operations; all present in router schema) |
| Extended state-changing operations confirmation gate | Passed (all 118 extended write operations reject missing confirmation before OAuth/API setup) |

The tests cover existing command/API/memory and integration behavior plus new action history and profile preferences, deterministic voice intents, safe arithmetic, mocked Weather/Routes requests, route-mode parsing, Cloud Vision cache and quota behavior, encoded-polyline helpers, gesture calibration mapping, expanded web aliases, semantic-router operation coverage, scope profiles and confirmation guards.

External providers are mocked in automated tests; they do not prove access to the user's Google Cloud project or account.

#### Important code paths in this release

- Groq function-call routing with automatic tool execution disabled, deterministic command patterns, typed action registry and local safety validation.
- Literal typing versus safe arithmetic; Calculator launch/type workflow with an explicit caveat that its displayed result is not visually verified.
- One system-wide air virtual keyboard, mouse input, camera gesture pointer/pinch-click, vertical scroll and browser-tab swipes; keyboard and gestures are explicit opt-in.
- Consent-based local LBPH face profiles with optional DeepFace embedding fusion; conflicting matches resolve to unknown; per-profile preferences persist locally.
- Product research using OCR, Google Cloud Vision Web Detection and Groq where configured, after explicit confirmation before camera image upload. Similar images/pages are leads, not identity verification.
- Capped/cached Google Geocoding, Weather and Routes calls plus Cloud Vision Web Detection; caps are local per-install safeguards and do not protect against other apps or project-wide costs.
- Best-effort Windows live-location route guidance with spoken maneuvers and off-route rerouting, subject to live provider/location availability.
- Bounded local action/result history for follow-up requests.
- Indian Sign Language (ISL) isolated-sign recognition using Torchvision Swin3D-S with a 76-class classifier. The checkpoint is loaded from `models/isl/swin3d_s/ISL_best_model.pt`. The recognizer processes 32 video frames and performs local inference. It supports isolated signs only, not continuous sentence translation.

#### ISL model evaluation

The Swin3D-S model was independently evaluated using the available ISL dataset.

| Metric | Result |
|---|---:|
| Number of classes | 76 |
| Test samples | 187 |
| Top-1 accuracy | 80.75% (151/187) |
| Top-5 accuracy | 99.47% |
| Macro F1-score | 0.8150 |
| Weighted F1-score | 0.7854 |
| Approximate inference time | 400–410 ms |
| Approximate peak GPU memory | 925 MB |

Evaluation used a stratified random split. It was not signer-independent, so these results do not establish generalization to unseen signers. Some classes have limited test samples. Performance may vary with camera position, lighting, signing speed and individual signing style.

These metrics describe the independent model evaluation and should not be interpreted as proof of end-to-end live-camera recognition accuracy.

#### Windows ISL runtime verification

The Windows Python 3.11 virtual environment was separately checked.

| Component | Installed version / result |
|---|---|
| PyTorch | 2.14.1+cu130 |
| Torchvision | 0.29.1+cu130 |
| CUDA availability | True |
| NumPy | 2.2.6 |
| OpenCV package (`opencv-contrib-python`) | 4.14.0.94 |
| Pillow | 13.0.0 |
| Scikit-learn | 1.9.1 |
| `pip check` | No broken requirements found |
| Required ISL package imports | Successful |

The environment satisfies the updated `requirements-signs.txt` dependency constraints. The CUDA-enabled PyTorch installation was retained.

These checks verify dependency availability and import compatibility, not complete live-camera integration or end-to-end recognition.

#### Integration checks not run in this container

- Actual Windows GUI focus/paste, non-activating keyboard overlay behaviour, mouse injection, display/audio/network controls, camera gesture operation, webcam calibration and browser tab switching.
- Live location permission and GPS accuracy, real navigation, off-route rerouting and maneuver timing on the target Windows device.
- Actual Google API requests against the user's project, API enablement, key restrictions, billing status, and current account-level quotas/pricing. Tests use mocks; Google free allowances and pricing can change.
- Real Groq/Cloud Vision image search with a user-approved image; live product pages/manual accuracy.
- Actual recognition metrics with consenting users on the target laptop; DeepFace is an optional heavy dependency and requires first-run model weights.
- Live Google OAuth and Workspace API calls, actual mobile build generation, and continuous sentence-level ISL translation. The current test container does not authenticate to a Google account and does not establish that all external APIs/scopes are enabled or approved.
- End-to-end live-camera Swin3D ISL recognition through Arthur's camera activation, recognition and spoken-output workflow.

These are field/provider acceptance checks, not automated tests. Do not treat passing unit tests as proof of end-to-end desktop operation, identity certainty, route safety, ISL recognition reliability or message delivery.

Before relying on navigation while moving, validate it on-device and keep a safe independent navigation method available.

## Original file: `THIRD_PARTY_NOTICES.md`

### Third-Party Notices

Arthur combines separately licensed packages, services, datasets and model files. Each component retains its own licence and use conditions. This inventory is a pointer list, not legal advice; review exact versions, checkpoint licences, dataset consent, attribution requirements and provider terms before redistribution or commercial deployment.

A component being listed here does not necessarily mean that it is bundled with Arthur or enabled at runtime. Research references and potential future integrations are identified separately from active dependencies.

#### Runtime packages, tools and services

| Component | Use in Arthur | Licence / terms pointer |
|---|---|---|
| Ultralytics YOLO26 package and supplied `yolo26n.pt` model | Local object detection and tracking | Ultralytics documents AGPL-3.0 and a separate enterprise licence: <https://github.com/ultralytics/ultralytics> |
| Depth Anything V2 Metric Hypersim Small checkpoint | Indoor metric-depth estimates; downloaded separately | Model card lists Apache-2.0: <https://huggingface.co/depth-anything/Depth-Anything-V2-Metric-Hypersim-Small> |
| Depth Anything V2 upstream source | Depth inference source downloaded by `tools/setup_depth_model.py` | Upstream repository/licence: <https://github.com/DepthAnything/Depth-Anything-V2> |
| MediaPipe | Hand landmarks and gesture control | Google AI Edge / MediaPipe source and licence: <https://github.com/google-ai-edge/mediapipe> |
| OpenCV | Camera capture, image processing and OCR preprocessing | OpenCV licence and Python package notices: <https://github.com/opencv/opencv-python> |
| Tesseract OCR | Local OCR engine; installed separately | <https://github.com/tesseract-ocr/tesseract> |
| OpenAI Whisper | Local speech-to-text | <https://github.com/openai/whisper> |
| PyAutoGUI | Explicit desktop cursor, click and keyboard control | <https://github.com/asweigart/pyautogui> |
| pygetwindow | Enumerating and activating desktop windows | <https://github.com/asweigart/PyGetWindow> |
| screen-brightness-control | Windows display brightness access | <https://pypi.org/project/screen-brightness-control/> |
| Pycaw and comtypes | Windows Core Audio volume/mute control | <https://github.com/AndreMiras/pycaw> and <https://github.com/enthought/comtypes> |
| pyperclip | Clipboard paste for multilingual GUI text | <https://pypi.org/project/pyperclip/> |
| FastAPI / Uvicorn | REST/WebSocket service layer | <https://fastapi.tiangolo.com/> |
| Groq Python SDK | Groq text, tool calling and vision API access | <https://github.com/groq/groq-python> |
| SentenceTransformers / all-MiniLM-L6-v2 | Local semantic similarity fallback; model-card licensing applies separately | <https://www.sbert.net/> and <https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2> |
| Pydantic | API request schema validation | <https://docs.pydantic.dev/> |
| Python multipart parser | FastAPI multipart audio uploads | <https://github.com/Kludex/python-multipart> |
| Flutter `http`, `web_socket_channel`, `speech_to_text`, `record`, `path_provider` | Mobile API, notification, speech capture and temporary audio file flows | <https://pub.dev/>; review each pinned package's current licence and platform permission requirements |
| Google API Python client and OAuth libraries | Gmail and Calendar account integrations | <https://github.com/googleapis/google-api-python-client> |
| openWakeWord | Local wake-word runtime; model files have independent terms | <https://github.com/dscripka/openWakeWord> |
| Groq API | Hosted function calling, text response and visual Q&A | Provider API terms, privacy and quotas apply: <https://groq.com/> |

#### Indian Sign Language (ISL) recognition

Arthur's current isolated-sign recognition pipeline uses Torchvision Swin3D-S rather than the previous MediaPipe Holistic + TensorFlow LSTM architecture.

| Component | Use in Arthur | Licence / terms pointer |
|---|---|---|
| PyTorch | Deep-learning inference for the Swin3D ISL recognizer | <https://github.com/pytorch/pytorch> |
| Torchvision | Swin3D-S video classification architecture and model operations | <https://github.com/pytorch/vision> |
| `ISL_best_model.pt` | Trained 76-class Swin3D-S checkpoint at `models/isl/swin3d_s/ISL_best_model.pt` | Record the checkpoint's training provenance, creator, source, dataset terms and redistribution permission in the model manifest. Do not assume that the framework licence automatically covers the checkpoint. |
| Pillow | Image processing used by the ISL preprocessing pipeline | <https://github.com/python-pillow/Pillow> |
| NumPy | Frame and tensor preprocessing support | <https://github.com/numpy/numpy> |
| scikit-learn | Dataset evaluation and classification metrics | <https://github.com/scikit-learn/scikit-learn> |

The current ISL recognizer uses a 76-class isolated-sign classifier. It does not provide continuous sentence-level ISL translation.

The previous MediaPipe Holistic + TensorFlow LSTM pipeline is not the active Swin3D inference architecture. MediaPipe remains listed above for gesture-control functionality.

##### Dataset and research references

The following references concern ISL datasets or research implementations. Their presence in this document does not mean that they are bundled with Arthur or used by the current runtime.

| Resource | Purpose / status | Licence / terms pointer |
|---|---|---|
| Amrita SLR dataset | Isolated-sign ISL training data reference. Verify that this is the actual source of the data used to train the current Swin3D checkpoint before attributing it to the model. | Dataset record lists CC BY 4.0; provide attribution and follow its terms: <https://data.mendeley.com/datasets/dtg9s785v8/1> |
| Sid-V5/isl-translator | Continuous ISL research implementation candidate; not a bundled runtime dependency. | Upstream README identifies MIT; verify the obtained commit, checkpoints and dependencies: <https://github.com/Sid-V5/isl-translator> |
| ISLTranslate | Research dataset for continuous ISL translation; not identified as a current runtime dependency. | <https://aclanthology.org/2023.findings-acl.665/>; verify release terms on the actual dataset |
| ISH-NEWS research | Sentence-level ISL research reference; not identified as a current runtime dependency. | <https://www.nature.com/articles/s41598-026-60893-0>; follow the article's data availability statement |

Before redistributing the Swin3D checkpoint, document:
- The original dataset and dataset version.
- The dataset's licence, attribution and consent requirements.
- Any preprocessing, filtering or augmentation applied.
- The checkpoint creator and training provenance.
- Whether redistribution or commercial use of the trained weights is permitted.
- The checkpoint checksum and model evaluation details.

#### Downloaded and separately installed assets

The following assets are not necessarily included in the project archive:

- `vendor/Depth-Anything-V2/` is downloaded by the depth-model setup script.
- `models/depth_anything_v2_metric_hypersim_vits.pth` is downloaded separately.
- Tesseract OCR is installed as a separate system dependency.
- Other model weights may be downloaded or generated during setup.

The supplied `yolo26n.pt` is retained in the archive.

No trained continuous-ISL sentence checkpoint or custom wake-word ONNX file is bundled.

#### Licence and redistribution considerations

- Review the exact licence for every pinned package version and downloaded model checkpoint.
- Some packages and models may impose obligations beyond those of the Python package that loads them.
- Hosted services such as Groq and Google APIs are governed by provider terms, privacy policies, quotas and billing conditions.
- Dataset licences may require attribution, impose restrictions on redistribution or require additional consent for derived model weights.
- Do not assume that a publicly accessible repository or model download automatically permits commercial use or redistribution.
- Keep third-party notices, licence texts and required attribution with redistributed builds where applicable.

Record any later-added model's checksum, source, licence, dataset, creator and evaluation details in its model manifest.

## Original file: `QUICK_START_COMMANDS.md`

### ARTHUR — Quick Start Voice Commands

Commands are examples, not exact required scripts. ARTHUR normalizes common wake-word prefixes such as “Hey Arthur” and “Arthur”. Some features require Windows integrations, external API access, or downloaded model files.

#### Browser and desktop applications

- “Open YouTube” / “Arthur, open YouTube”
- “Search YouTube for Python tutorials”
- “Search Google for binary trees”
- “Open Word” / “Open Excel” / “Open PowerPoint”
- “Open Calculator” / “Open Notepad” / “Open File Explorer”
- “Close Excel” / “Close Word” / “Close Chrome” — ARTHUR asks before sending a normal close request. Save prompts are still handled by the application.

Word and Excel must be installed as desktop applications. If ARTHUR cannot locate one, use the Windows Start menu to confirm it is installed and repair Microsoft 365/Office if necessary. Store/web-only editions may not expose a local executable.

#### YouTube search and video selection

- “Search YouTube for Taylor Swift songs” opens the results and stores that search for follow-up commands during the current ARTHUR session.
- “Play the first video” / “Play the second video” / “Open result number 3” selects that numbered result from ARTHUR’s most recent YouTube search.
- “Play a video” selects the first result when a recent ARTHUR YouTube search exists.
- “Pause it” / “Play it” / “Skip forward 30 seconds” controls the current browser video using YouTube keyboard shortcuts.

Result selection retrieves YouTube’s public search-result page and opens the selected watch page with autoplay requested. YouTube or browser autoplay policies may still require a click. The numbered selection applies to the most recent search issued by ARTHUR in the current session; it does not use a search performed manually in another browser tab or a search from before ARTHUR was restarted.

#### Volume, brightness and media

- “Reduce system volume” / “Reduce volume by 20 percent”
- “Increase volume” / “Set volume to 35 percent” / “What is the current volume?”
- “Mute audio” / “Unmute audio”
- “Dim the screen” / “Set brightness to 60 percent”
- “Pause the video” / “Skip forward 30 seconds”

Volume control requires the Windows audio endpoint and the `pycaw` / `comtypes` integrations. Brightness control depends on the laptop display exposing a controllable brightness endpoint.

#### Typing and calculations are different

- “Type exactly 2+2” means paste the literal characters `2+2` into the window that was foreground when you issued the command. Arthur asks for confirmation, restores that same window, and pastes immediately; there is no four-second countdown. Use wake-word conversation while the intended destination is in the foreground. If the Arthur window itself was foreground (for example, after clicking Push to Talk), use an explicit target such as “Type hello in Microsoft Word”.
- “Calculate 2+2” computes the result locally and displays/speaks `4`; it does not type into another app.
- “Open Calculator and calculate 2+2” launches Calculator and sends the calculation through ARTHUR's local arithmetic path.

The command transcript can also appear in ARTHUR's output panel; that is the transcript/result log, not proof that text was pasted into another app.

#### Camera, scene description and OCR

- “Turn on camera” / “Turn off camera”
- “Describe the scene” / “What is in front of me?” / “Is there a television?”
- “Read the text on this page” / “Scan the page”
- “Read the text on my screen” — local desktop OCR
- “Explain what is on my screen” — screenshot sharing requires a separate confirmation

The camera and YOLO model must both start successfully. The provided ZIP currently contains a Git LFS pointer in place of `models/yolo26n.pt`; the full model weights are required before camera-based features can operate. Check the output panel for the exact error.

##### Use a phone camera

On Android, a local IP-camera app can expose an MJPEG stream. Start the stream on the phone, keep the phone and laptop on the same Wi-Fi network, then use the exact stream URL shown by the app. A common IP Webcam endpoint is:

```powershell
python main.py --camera "http://PHONE_IP:8080/video"
```

Or set this in `.env`:

```env
VISIONGUIDE_CAMERA_SOURCE=http://PHONE_IP:8080/video
```

Then run `python main.py`. Use `VISIONGUIDE_CAMERA_SOURCE=0` for the laptop's default webcam. Do not expose the phone stream port to the public internet. A better camera helps only when the page is well lit, in focus, held steady, and fills much of the image.

#### Hand / finger tracking and virtual keyboard

First download the separate MediaPipe model:

```powershell
python tools/download_hand_model.py
```

Then use:

- “Enable finger tracking” / “Disable finger tracking”
- “Calibrate finger tracking”
- “Open virtual keyboard” / “Close virtual keyboard”

The index fingertip moves the system pointer. A thumb-index pinch clicks. Move to the right edge of the camera view and move vertically to scroll. A quick left/right swipe changes browser tabs. The same pointer and pinch can select keys on ARTHUR's virtual keyboard. Keep the whole hand in view, avoid sensitive windows, and disable gestures before entering passwords.

Gesture control also needs the real camera/YOLO runtime, MediaPipe, and PyAutoGUI. The missing hand model file is a separate requirement from the YOLO weights.

#### Local memory and face enrollment

- “Remember that I left my keys in the bag” — ARTHUR asks before saving a local SQLite note.
- “Where did I leave my keys?” / “What do you remember about my keys?” — searches local notes.
- “Enroll my face” / “Remember my face” — asks for a name and consent before locally collecting face samples.
- “Enable face recognition” / “Disable face recognition”
- “Arthur, I prefer you to call me Chiraangshu” — saves the preferred form of address against the active enrolled face profile.

After enrollment, the just-enrolled profile becomes active for the current session. A preferred name is loaded immediately when the user sets it and is applied to short spoken assistant replies (including replacing direct-address “sir” salutations). The preference is stored locally in `data/action_history.sqlite3`. After a restart, enable face recognition so ARTHUR can identify the enrolled profile and reload its preference. If only one face profile is enrolled, a preference command can target it without asking you to choose; with multiple profiles, ARTHUR identifies the active face or asks which profile to use.

Face recognition requires `opencv-contrib-python`, a working camera/model pipeline, and explicit consent. Face samples and preferences are stored locally; they are not automatically sent to Groq. Enrolling a face does not happen silently.

#### Navigation

- “Get directions from Salt Lake to Howrah”
- “Get directions from Salt Lake to Howrah by motorcycle”
- “Stop navigation”

ARTHUR asks whether to start live guidance. Live guidance needs Windows Location permission, a working location provider, a valid `GOOGLE_MAPS_API_KEY`, Routes API enabled, Geocoding API where needed, and Google Maps Platform billing/quota configured. Choose No to live guidance to calculate/open a static route from the specified origin. When the Routes API is unavailable but the origin and destination are known, ARTHUR attempts to open Google Maps directions in the browser instead; that fallback does not provide an ARTHUR ETA or live spoken turns.

#### Indian Sign Language

- “Start sign language translation” / “Start ISL translation”
- “Stop sign language translation”

This build recognizes a limited set of isolated ISL signs; it does **not** translate continuous signed sentences. It requires the full Swin3D-S checkpoint at `models/isl/swin3d_s/ISL_best_model.pt`, the matching 76-class labels (or training dataset used to reconstruct them), and the PyTorch/Torchvision dependencies in `requirements-signs.txt`. The uploaded ZIP contains only an LFS pointer for the checkpoint, not the approximately 228 MB trained weights.

#### AI and Groq

Set `GROQ_API_KEY` to your GroqCloud API key. The default text/function-calling model is `openai/gpt-oss-120b`; the default vision model is `qwen/qwen3.8-27b`. Both model availability and free-tier rate limits are account-dependent; check the GroqCloud Models and Limits pages. Groq is separate from `GOOGLE_MAPS_API_KEY`. Do not send credentials, private documents, or confidential camera images to any hosted model.

#### Listening

- Press **Listening: OFF/ON** to arm/disarm the wake-word listener.
- Say the configured wake phrase, then speak a command.
- Push-to-talk records for up to 10 seconds.
- Voice confirmations also listen for up to 10 seconds.
- Silence for 30 seconds returns ARTHUR to its waiting/wake state. “Go to sleep”, “Stop listening”, or “Goodbye” ends the current conversation.


#### Targeted typing and browser tabs

- `Type hello` — confirm; Arthur restores and types into the window that was in the foreground when you spoke. No four-second countdown.
- `Type hello in Microsoft Word` — confirm; Arthur activates Word and inserts at the current selection/cursor, creating a blank document only when none is open.
- `Type Taylor Swift in YouTube search box` — confirm; Arthur focuses the YouTube search field and pastes without submitting the search.
- `Type example.com in Chrome address bar` — confirm; Arthur focuses the browser address bar and pastes without navigating.
- `Close YouTube` / `Close the Gmail tab` — confirm; Arthur closes the matching currently active browser tab with Ctrl+W. It does not terminate the browser process. Background tabs are not selected automatically.

Direct Word insertion requires `pywin32`; install it through the updated `requirements-integrations.txt`.

## Original file: `WAKE_WORD_SETUP.md`

### “Hey Arthur” Wake-Word Setup

Wake-word activation is a standard speech-input mode. It is disarmed at startup to preserve privacy and is only armed after the user explicitly enables it. After the phrase is detected, the system captures a bounded command clip and transcribes it with local Whisper.

#### Configure

1. Create and activate the project's Python 3.11 environment.
2. Install the integration dependencies:

   ```powershell
   pip install -r requirements-integrations.txt
   ```

   Or install the runtime-only packages in a prepared environment:

   ```powershell
   pip install -r requirements-wakeword.txt
   ```

3. Provide an ONNX model trained for the exact phrase **“Hey Arthur”** at `models/wakeword/hey_arthur.onnx`, or set `WAKE_WORD_MODEL` in `.env` to its absolute path.
4. Review the model's source, licence, training data and intended use. Do not use a model trained for a different phrase and label it as “Hello Arthur.”
5. Set `WAKE_WORD_THRESHOLD` from `0.10` to `0.99` as required by local evaluation. A low threshold may increase false activations; a high threshold may miss the phrase.
6. Start Arthur and use **Wake word mode…** to arm the listener. Say the phrase and then issue a command. The listener pauses while Whisper records/transcribes that command and re-arms after handling it.
7. Use **Wake word mode…** again or say “disable wake word” to stop listening.

#### Privacy and reliability

- The local wake detector processes the listening stream locally. The detector itself does not upload the audio.
- After phrase detection, command audio is separately captured for Whisper; the capture duration is bounded.
- Show a microphone indicator while armed. Provide a direct UI stop control and respect the user's stop command.
- Evaluate false accepts/rejects at realistic distance, background noise and speaking volume before daily use. Wake-word recognition is not guaranteed to be error-free.

## Original file: `AEC_AUDIO_FIX_GUIDE.md`

### ARTHUR AEC audio and confirmation guide

#### Why this patch is different

The earlier interruption patch opened short Whisper microphone windows while
SAPI was speaking and relied on the word "Arthur" as a filter. That is not echo
cancellation. This patch uses Echoff's separate WASAPI speaker-loopback reference
and physical microphone stream, aligned before WebRTC acoustic echo cancellation.

#### Important behaviour

- Active-playback interruption is enabled only after Echoff reports its measured
echo path ready. This is a quality gate, not a guarantee of zero echo.
- In the paused state, SAPI has been purged, so ARTHUR can safely use a raw
microphone window to hear "continue" or a new addressed command.
- If AEC cannot start or readiness is not reached, raw microphone audio is never
transcribed while TTS is playing. Use the Pause speech button or Escape.
- A confirmation is strictly half-duplex: ARTHUR stops all previous speech, speaks a
short prompt, waits for SAPI to finish, closes the AEC microphone stream, allows
the output buffer to drain, plays a tone, and then opens one six-second raw
microphone recording. There is one retry. The complete action details remain on
screen, rather than being read aloud before the answer is captured.

#### Optional .env settings

```dotenv
VISIONGUIDE_AEC_REFERENCE_DEVICE=0
VISIONGUIDE_AEC_MICROPHONE_DEVICE=1
VISIONGUIDE_AEC_STREAM_DELAY_MS=50
VISIONGUIDE_AEC_WARMUP_SECONDS=7.5
VISIONGUIDE_TTS_MIC_GUARD_SECONDS=1.35
```

Do not copy example device indexes without checking `python -m echoff devices`.
The `.env` settings are optional; the default Windows audio endpoints are used
when device settings are omitted.

#### Hardware diagnostic

```powershell
python -m echoff devices
python -m echoff record --duration 20
```

During the recording, play sound through the same output endpoint and speak into
the microphone. Compare `microphone_raw.wav` with `microphone_aec.wav`. The AEC
track should reduce the speaker playback while preserving your voice. The
recordings can contain private audio; do not share the WAV files.


#### Confirmation microphone selection and diagnostics

Voice confirmation uses the Windows default input device unless
`VISIONGUIDE_CONFIRMATION_MIC_DEVICE` is set in `.env`. The value may be a
numeric input-device index or an unambiguous device-name fragment. Inspect the
available devices and default input with:

```powershell
python -c "import sounddevice as sd; print(sd.query_devices()); print('Default devices:', sd.default.device)"
```

The confirmation path checks that the selected endpoint has input channels and
supports mono 16 kHz capture. It prints the selected device, captured RMS/peak
levels, and Whisper transcript to the local terminal; it does not save the
recording. A near-zero signal or device error is reported and the action remains
unconfirmed. If the Windows default endpoint changes, restart ARTHUR and verify
the device index again before setting an override. Do not select a virtual input
that reports zero-level audio.

## Original file: `AEC_READINESS_CALIBRATION.md`

### ARTHUR AEC readiness calibration

#### Findings from the uploaded hardware recordings

The controlled playback-only recording showed a very low but measurable
speaker leak at the microphone: raw microphone RMS was around `-74.3 dBFS`
(about `0.00019` linear RMS). Echoff's built-in default minimum raw RMS was
`0.003`, approximately 16 times higher than the measured signal. The same run
reported about `6.1 dB` of rolling suppression, while the offline far-end-only
comparison was about `8.6 dB`. This made the stock `0.003 RMS` / `10 dB` gate
unattainable even though listening tests suggested useful suppression and voice
preservation.

#### New gate

| Parameter | Previous default | New ARTHUR default |
|---|---:|---:|
| Active-reference warm-up | 7.5 s | 7.5 s |
| Minimum raw microphone RMS | 0.003 | 0.0001 |
| Minimum raw-to-clean suppression | 10 dB | 5 dB |

These are calibrated acceptance thresholds, not a claim of perfect echo
cancellation. The device still must deliver aligned reference/microphone pairs
and satisfy Echoff's sustained quality check. The lower values reflect this
laptop's unusually quiet acoustic echo rather than lowering the gate to zero.

#### Double-talk handling

The Echoff readiness value is a rolling energy heuristic. During double-talk,
the user's voice is intentionally preserved in `microphone_clean`, which can
reduce the apparent whole-microphone attenuation. ARTHUR now latches readiness
only after the initial Echoff gate passes, then keeps consuming cleaned frames
for that capture session. This stops a valid user utterance from being discarded
just because the rolling diagnostic changes while the user speaks.

A capture failure still propagates through `check_health()`. There is no raw
microphone fallback during active TTS. If output devices are changed, restart
ARTHUR so a new AEC capture must pass its startup gate again.

## Original file: `SPEECH_INTERRUPTION_GUIDE.md`

### ARTHUR speech interruption and natural rendering

#### Voice commands

During spoken output in wake-word conversation mode:

- **Pause:** “Arthur, stop” / “Arthur, stop speaking” / “Arthur, pause.”
- **Resume:** “Continue” / “Okay, now continue” while paused; or “Arthur, continue.”
- **Discard:** “Arthur, cancel that response.”
- **New request:** “Arthur, [new question or command].”

During playback, the address phrase is required to reduce the chance that ARTHUR
hears its own TTS as an instruction. The listener uses short Whisper capture
windows; response time includes that window and transcription time. This patch
does not provide true acoustic echo cancellation.

#### Speech rendering

The output panel receives the original response. Only the TTS input is converted
from common Markdown/LaTeX notation to plain language. The renderer supports common
fractions, powers, roots, integrals, inequalities and common math functions. It
is deliberately not a full LaTeX engine. Fenced code blocks are referred to as
being displayed in the output panel rather than read as source code.

## Original file: `ASSISTANT_INTELLIGENCE_UPGRADE.md`

### Arthur Conversational Intelligence Upgrade

This patch adds session-scoped conversational context and a more consistent spoken response style while preserving Arthur's existing typed command router and permissioned action executors.

#### Files

##### Replace
- `visionguide/app.py`
- `visionguide/semantic_router.py`
- `visionguide/cloud_ai.py`
- `visionguide/speech.py` (replaces the failing pyttsx3 playback path with native SAPI5; `comtypes` is already listed in the integration requirements)
- `.env.example` (merge the new setting into your existing `.env`; do not overwrite your real secrets)

##### Add
- `visionguide/conversation.py`
- `visionguide/voice_responses.py`
- `tests/test_conversation.py`

No dependency changes are required.

#### Context privacy

Arthur keeps the latest eight voice turns in memory only. They are discarded when the application exits and are not written to SQLite.

In `.env.example`, this setting defaults to disabled:

```dotenv
VISIONGUIDE_SHARE_CONVERSATION_CONTEXT=0
```

Keep it at `0` to retain context locally without sending it to Groq. Set it to `1` only when you want recent conversation turns included in Groq function-call routing and text-only responses. Ordinary text-only questions and tasks are sent directly to Groq without a second confirmation prompt. The current command text is sent; prior conversation context remains local unless this setting is enabled. Do not put API keys or other secrets in conversation commands.

#### Behaviour

- Existing deterministic command patterns still take priority over Groq.
- Groq receives recent context only when the explicit setting above is enabled.
- The router can use context to resolve clear follow-ups such as “open it”; ambiguous references should result in a clarification rather than a guessed action.
- Context does not grant permission for external messages, calendar changes, image uploads, or other sensitive operations.
- Ordinary text-only requests are sent directly to Groq; no “send to Groq?” dialog or “local command not found” narration is shown.
- Tool actions that save, update, delete, submit, send, publish, change network settings, or upload camera/screen content retain their separate confirmation gates.
- General Groq answers use a calm, concise assistant voice and may use approved recent context.
- Browser/app launch confirmations are shorter and more conversational. The complete operation result remains in the UI.
- Existing local memory, action history, tool allowlists, and confirmation gates are retained.

#### Apply

1. Back up the current project folder.
2. Copy the replacement files into the matching paths and add the new files.
3. Merge the new `VISIONGUIDE_SHARE_CONVERSATION_CONTEXT` setting into your real `.env`; do not replace `.env` with `.env.example`.
4. Restart Arthur.
5. Test: “Open YouTube” → “Open it” (the second command can use context only when sharing is enabled), then ask a follow-up question.
6. Run the test suite with `python -m unittest discover -s tests -v`.

The speech replacement uses native Windows SAPI5 from a single COM-initialized worker thread. It retains the existing `say()`, priority queue, `wait_until_idle()`, and `close()` interface. It does not require a new dependency; `comtypes` is already present in `requirements-integrations.txt`.

## Original file: `DIRECT_GROQ_AND_WORD_CUD_UPGRADE.md`

### ARTHUR — Direct Groq fallback and confirmed Save/Update/Delete upgrade

#### What changes

##### 1. No repeated confirmation for ordinary text requests

- Local deterministic commands continue to run locally.
- If Groq function calling identifies a registered tool, ARTHUR validates and dispatches that typed action through the existing executor.
- If the request is not a local command and does not resolve to a registered operation, ARTHUR sends the current text request directly to Groq.
- The desktop no longer asks “Would you like to send this to Groq?” and no longer announces “local command not found; sending to Groq”. It responds with the result or a provider error.
- The authenticated FastAPI `/api/v1/command` text-only fallback follows the same policy. The API still requires its configured bearer token when authentication is enabled.
- Prior conversation context is not sent by default. Keep `VISIONGUIDE_SHARE_CONVERSATION_CONTEXT=0`; set it to `1` only if you intentionally want recent turns included in Groq routing and text prompts.

**Privacy consequence:** the current non-local text request/transcript is automatically transmitted to Groq. Do not speak passwords, API keys, private credentials, or text you do not want sent to the provider. This change does not upload camera frames or screenshots as part of ordinary text Q&A.

##### 2. Confirmations that remain

ARTHUR still asks before actions that change data or affect other people/services, including:

- Sending email or WhatsApp messages.
- Creating/updating/deleting Google Workspace data (Docs, Drive, Calendar, Gmail, Sheets, Tasks, Contacts and other exposed operations).
- Saving a Word document, replacing its text, or deleting selected text.
- Submitting a form, publishing/uploading content, or changing network adapter state.
- Pasting dictated/generated content into a target application.
- Uploading a camera image or screenshot to Groq/Cloud Vision.
- Saving or deleting local memory where the existing workflow requests confirmation.

Text-only AI questions are the exception; those no longer prompt for provider consent.

##### 3. New Microsoft Word operations

Speak these with Word open and a document active:

- `Arthur, save it.` — saves the active document. If it has never been saved, ARTHUR creates `Documents/ARTHUR/ARTHUR-Document-YYYYMMDD-HHMMSS.docx`.
- `Arthur, save the Word document as report.docx.` — saves under `Documents/ARTHUR/report.docx`.
- `Arthur, replace old phrase with new phrase in Word.` — previews and asks for confirmation, replaces all matching occurrences in the active document, and leaves it modified but unsaved.
- `Arthur, delete selected text in Word.` — previews the current selection, asks for confirmation, and checks that the selection has not changed before deletion. The document remains modified but unsaved.

Save As is restricted to `Documents/ARTHUR`; an existing destination file is not overwritten. These operations require Windows desktop Microsoft Word and `pywin32`.

##### 4. Google Drive and Docs update/delete coverage

The extended Workspace registry now exposes:

- `drive_file_update`: metadata update via `payload_json`, or UTF-8 text content replacement via `content` (maximum 1,000,000 characters). A confirmation is required.
- `docs_delete_range`: delete a specified content range using `start_index` and `end_index`. A confirmation is required.

Existing Drive file deletion, Docs insert/replace/batch update, Gmail draft update/delete/send, Calendar update/delete, Sheets updates, Tasks update/delete, Contacts updates/deletes and other allowlisted CRUD operations remain behind their central confirmation gate. Each operation still requires the appropriate Google OAuth scopes, resource ID and API enablement.

Google Docs API updates are saved automatically by Google. Local Word replace/delete actions remain unsaved until you say `save it` and confirm.

#### Installation

1. Close ARTHUR completely.
2. Back up `E:\Chiraangshu\MyWorkspace\ARTHUR`.
3. Extract `ARTHUR_Direct_Groq_and_Word_CUD_Upgrade_Patch.zip`.
4. Open the extracted `ARTHUR-main` folder and copy its contents into the existing ARTHUR project root, preserving the folder structure and allowing replacements.
5. Preserve your real `.env`, `.venv`, `data`, `models`, and `credentials` folders. Do not replace them.
6. No dependency-manifest changes are required by this overlay. If Word COM reports that `win32com` is missing, install `pywin32` inside the existing virtual environment:

```powershell
python -m pip install pywin32
```

#### Validate and launch

From PowerShell in the project root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m compileall -q visionguide tests
python -m pytest -q
python main.py
```

The merged source was verified in the build container with **149 passed, 4 existing FastAPI lifecycle deprecation warnings**. This automated run does not validate Windows COM, actual Word UI focus, live Groq availability, or real Google OAuth/API account permissions.

#### Suggested acceptance tests

1. `Arthur, explain recursion with an example.` — should go to Groq without a consent dialog.
2. `Arthur, what is 25 multiplied by 48?` — should use the local arithmetic route.
3. `Arthur, save it.` — should show a save confirmation and save the active Word document only after approval.
4. `Arthur, replace draft with final in Word.` — should preview and ask before replacement.
5. Select a disposable phrase in Word, then say `Arthur, delete selected text in Word.` — should preview and confirm; the selection must still match before deletion.
6. Use a disposable Google Drive text file to test `drive_file_update`, and a disposable Google Doc to test `docs_delete_range`. Inspect the preview carefully before confirming.
7. Test Gmail/WhatsApp sends only with your own test account/contact and verify the recipient and entire message before confirming.

If Groq is unavailable, ARTHUR should report the provider failure; direct routing removes the extra consent prompt, not the provider's service limits or outages.

## Original file: `FIELD_SUBMISSION_CONTEXT_UPGRADE.md`

### ARTHUR — Cross-application typing and Enter follow-up

This cumulative overlay extends the Direct Groq + Word/Workspace Save-Update-Delete patch.

#### Behaviour

1. ARTHUR accepts a targeted typing command for a supported application or website, opens/activates that allowlisted target, focuses a known field or a uniquely identifiable Windows UI Automation field, and pastes the exact dictated text. It does not submit the text at this stage.
2. After a successful paste, ARTHUR stores the target top-level window, target type, field type, focused UI Automation runtime ID, and timestamp in memory for up to 120 seconds.
3. The next command can be `search it`, `submit it`, `press Enter`, or `hit the Enter key`. ARTHUR presses Enter only when the same window is still foreground and the same UI Automation control still has focus. The pending context is one-shot and is cleared by an unrelated command.
4. If the window or focused control changes, the target expires, or Windows cannot provide a stable focus identity, ARTHUR refuses to press Enter. The user can return to the field and repeat the typing command or press Enter manually.

#### Known shortcuts and generic field access

- YouTube search: `/` focuses YouTube search.
- File Explorer / Recycle Bin search: `Ctrl+E`; address/location bar: `Ctrl+L`.
- Chrome / Edge / browser address bar: `Ctrl+L`. A page search field is treated separately and is located through UI Automation.
- Word, Excel, Notepad, Google Docs, Google Sheets, VS Code, WPS Writer/Spreadsheets, Windows Settings and selected Windows tools: `Ctrl+F` for their supported Find/Search box.
- Gmail and GitHub: `/` focuses search. Gmail's keyboard shortcuts must be enabled in Gmail settings.
- WhatsApp Web: `Ctrl+F` focuses search.
- Other allowlisted applications/websites: ARTHUR uses Windows UI Automation (`pywinauto`) to locate a visible, enabled Edit/ComboBox control by its accessible name (for example, `Search`). It accepts a unique matching control, or a sole editable control when the label is unavailable. It refuses ambiguous matches rather than guessing coordinates.

#### Example commands

##### YouTube

1. `Arthur, type Taylor Swift in YouTube search field.`
2. `Arthur, search it.`

Equivalent second commands: `press Enter`, `hit the Enter key`, or `submit it`.

##### File Explorer

1. `Arthur, type quarterly report in File Explorer search field.`
2. `Arthur, press Enter.`

For navigation, use `File Explorer address bar` instead of `search field`.

##### Excel

1. `Arthur, type Q4 revenue in Excel search field.` — opens Find with `Ctrl+F`.
2. `Arthur, press Enter.` — runs the Find query.

To enter a value in a cell, target the active cell (or focus the cell yourself and use `type exactly ...`); Enter commits the cell edit.

##### Word

1. `Arthur, type recursion in Word search field.` — opens Find with `Ctrl+F`.
2. `Arthur, search it.` — runs the Find query.

To insert text into the document, say `type ... in Word document`; Enter then creates a new paragraph at the insertion point. Typing into a Word document uses Word COM and does not save the document automatically.

##### Other websites and text fields

Use the site/app name and the field type, for example:

- `Arthur, type machine learning in Google search field.`
- `Arthur, type Python course in LinkedIn Learning search field.`
- `Arthur, type my question in ChatGPT text box.`
- `Arthur, type a command in VS Code editor.`

A follow-up Enter on an ordinary search field runs the search. Enter in a chat/message composer or an ambiguous form field asks for confirmation first because it may send a message or submit data.

#### Supported targets

The target allowlist includes File Explorer; Microsoft Word, Excel and PowerPoint; Notepad; VS Code; WPS apps; Calculator; Task Manager; Windows Settings pages; Paint; Snipping Tool; Terminal, PowerShell and Command Prompt; Control Panel; Device Manager; Resource Monitor; Recycle Bin; AutoCAD; Arduino IDE; Python IDLE; Picasa; Photos; Media Player; Clock; and supported websites including YouTube, Google, GitHub, ChatGPT, Gemini, Claude, LeetCode, Netlify, Render, Gmail, Drive, Docs, Sheets, Maps, Meet, Classroom, Contacts, Google Cloud Console, Stack Overflow, Wikipedia, Reddit, LinkedIn, Instagram, WhatsApp Web, Coursera, SWAYAM, NPTEL, LinkedIn Learning and Neon.

Only built-in allowlisted targets can be launched by name. ARTHUR does not execute arbitrary spoken executable paths.

#### Safety and limitations

- The initial dictated paste still asks for confirmation.
- Search/address fields can be submitted without another confirmation. Typing into Gmail/WhatsApp message composers, ChatGPT-like message boxes, or an ambiguous website form keeps a confirmation gate before Enter.
- Saving, deleting, updating, sending, publishing and other data-changing actions keep their existing confirmation gates.
- ARTHUR does not inspect arbitrary website DOMs. Generic field targeting depends on Windows accessibility metadata being exposed by the application/browser. If the control is not exposed or more than one candidate matches, ARTHUR refuses and asks the user to click the intended field and use `type exactly ...`.
- The remembered target is session-only, expires after 120 seconds, and is invalidated by any unrelated command.
- Actual Windows UIA, Office COM, browser behavior and live website layouts must be verified on the user's Windows machine. The automated build tests mock these Windows-specific controls.

#### Added dependency

`requirements-integrations.txt` now includes the Windows-only dependency `pywinauto>=0.6.9,<0.7.0`. Install the updated integration requirements in the existing virtual environment.

## Original file: `PERSONALIZATION_UPGRADE.md`

### ARTHUR — Live preferred-name personalization

This update connects the preferred-name value stored against an enrolled face profile to ARTHUR's live response pipeline.

#### Behaviour

1. When face enrollment completes, that profile becomes the active profile for the current session.
2. Say: `Arthur, I prefer you to call me Chiraangshu.` The local semantic router now recognizes this exact phrase and routes it to `profile_preference_set`.
3. ARTHUR stores the preference in the existing local SQLite preferences table in `data/action_history.sqlite3`, keyed by the enrolled profile's stable slug.
4. ARTHUR immediately refreshes its in-memory active preferred name. No restart is required.
5. All application speech is routed through the personalization layer. Direct-address uses of `sir` are replaced with the stored preferred name; short assistant replies are naturally addressed to that name. Long read-aloud content such as OCR/document/memory text is not prefixed.
6. When face recognition later identifies that enrolled profile, ARTHUR reloads the preference from SQLite. Face recognition is privacy-controlled and must be enabled after restart for automatic profile recognition.

#### Multiple profiles

If exactly one face profile is enrolled, ARTHUR uses that profile for the preference command. If multiple profiles exist and no face is active, ARTHUR asks which profile should receive the preference (by voice during an active voice conversation, otherwise through a dialog).

#### Privacy and scope

- The preferred name and face profile link are stored locally.
- This feature does not send face images or saved preferences to Groq.
- It does not hardcode any person's name in application source.
- The helper only replaces `sir` when it appears as a direct salutation (for example, `Yes, sir?`); it does not rewrite titles such as `Sir Isaac Newton`.
- Automated tests verify the exact natural-language preference phrase, salutation replacement, duplicate-name avoidance, and preservation of raw content.

#### Test

From the project root, in the active virtual environment:

```powershell
python -m compileall -q visionguide tests
python -m pytest -q
```

## Original file: `GOOGLE_APIS_PATCH_NOTES.md`

### Arthur Google API Integration Patch

#### Applying this patch

Copy the files and folders in the archive into the root of your existing `Arthur` project, preserving relative paths and replacing only the listed source/documentation files.

**This patch intentionally excludes `.env`, OAuth client JSON, OAuth token files, local caches and user data.**

Back up your project before replacing files. Keep a copy of the current source files so that you can restore them if the updated build fails.

Merge any required variables from `.env.example` into your existing `.env` manually. Do not replace a populated `.env` with `.env.example` and do not copy secret values into source files.

Keep the Desktop OAuth client JSON at your configured `GOOGLE_OAUTH_CLIENT_FILE` path and generated tokens under `data/google_tokens/`.

After applying the patch, verify that the existing Python environment and installed dependencies satisfy the updated requirements before launching Arthur.

#### Configuration groups

- `GROQ_API_KEY`: primary assistant text, tool-routing, and vision inference. Keep this key private and do not confuse it with Google Cloud keys. Google Workspace and Maps integrations continue to use their configured Google OAuth / Maps credentials.
- `GOOGLE_MAPS_API_KEY`: Maps Platform REST services used by this Python application: Geocoding, Routes, Weather, Places API (New), Air Quality, Pollen, Time Zone, Roads and explicitly consented Geolocation.
- `GOOGLE_CLOUD_API_KEY` or `GOOGLE_VISION_API_KEY`: optional Cloud Vision Web Detection key. Enable Cloud Vision API and restrict this separate key to Cloud Vision if visual web search is needed.
- OAuth desktop client: Gmail and Calendar plus feature-specific profiles for Drive metadata search, Docs, Sheets, Slides, Tasks, People/Contacts, Classroom read operations, Meet-space creation, YouTube search, Forms, Cloud Translation and Cloud Natural Language.

Cloud Translation and Natural Language use Google OAuth profiles in this build; they do not use the Groq key or a Maps-only key. Enable each relevant API in the Cloud project, configure the scopes required by the profile in Google Auth Platform, then approve its first-run OAuth flow.

A profile may request consent separately from Gmail/Calendar because its token is isolated by feature group. Existing token files should not be copied from another machine or shared between users.

#### Scope and API boundaries

The expanded adapter uses per-feature OAuth profiles and exposes 197 explicit extended operation handlers in the current build. The exact registered operation and scope-profile lists are generated by `google_scope_capability_report()` and described in `GOOGLE_SCOPE_FEATURE_MATRIX.md`.

Current supported families include Calendar events/calendars/free-busy/ACLs, Gmail messages/drafts/labels/settings/forwarding/delegation/notification watches, Drive file metadata/sharing/app data/Apps Script/activity query, Docs, Sheets, Slides, Tasks, People/Contacts and selected profile attributes, Classroom courses/rosters/classwork/submissions/guardians/registrations, Meet REST records and artifacts, YouTube channel/video/playlist operations, Forms responses/watches, and OAuth-backed Generative Language tuning/retriever operations.

This remains an API-backed desktop integration, not a promise that every visible OAuth scope can be exercised by the desktop app.

- Gmail add-on current-message/action scopes need a Gmail add-on runtime.
- Meet live audio/video capture and Meet hardware administration are not implemented in this client.
- Classroom add-on attachment operations and practice sets are not exposed by this adapter.
- Drive Activity query is implemented but there is no activity-write API operation.
- The Drive photo scope is not treated as Google Photos Library support.
- `drive.install` has no ordinary file CRUD handler.
- The `calendar.settings` scope does not add a Calendar API settings-write method.
- Generative per-user quota has no standalone quota-query endpoint in this adapter.
- YouTube raw-media downloading and partner/content-owner features are not implemented as general-purpose operations.

`GOOGLE_SCOPE_FEATURE_MATRIX.md` lists these boundaries explicitly.

The website launcher has fixed destinations for Google Cloud Console, Neon DB, Google Classroom, Google Contacts, LeetCode, LinkedIn Learning, Coursera, SWAYAM and NPTEL (including the voice aliases `linkedln learning` and `swaym`). That allowlist opens browser destinations; it does not grant API access to those third-party services.

Maps JavaScript, Maps Embed, Android/iOS Maps SDKs and Map Tiles are not rendered inside the Python desktop client. The app opens web map previews and calls the Maps REST services.

Geolocation requires caller-supplied Wi-Fi access-point records and an explicit consent flag; the adapter does not collect nearby Wi-Fi identifiers automatically.

Every create/update/delete/send/share/publish operation exposed through the extended Workspace dispatcher is checked against the central confirmation gate before OAuth token acquisition or provider calls. Core integrations use their existing confirmation paths.

Local confirmation and API quotas are guardrails, not replacements for project-level Cloud quotas, billing alerts, verification, administrator policy or account eligibility.

#### Validation

The current offline validation run passed **97 tests**, with 4 existing FastAPI lifecycle deprecation warnings.

The registry snapshot contains:

| Registry item | Reported count |
|---|---:|
| Extended API operations | 197 |
| Extended state-changing operations | 118 |
| Feature-specific OAuth profiles | 146 |
| Offline tests passed | 97 |
| Existing FastAPI lifecycle deprecation warnings | 4 |

All extended operation names appear in the semantic-router schema.

The offline test suite covers routing, scope isolation, write-confirmation gates and mocked API requests. These results establish local test coverage for the tested code paths; they do not establish successful authentication against a live Google account.

The offline tests do not validate:

- Live Google OAuth consent and token acquisition.
- Cloud API enablement or billing configuration.
- Signed-in account eligibility.
- Workspace administrator restrictions.
- Live API quotas or rate limits.
- Actual permissions on the user's documents, calendars, courses or other resources.
- Successful execution of every registered operation against a real provider account.

The operation counts and test results are build-specific snapshots. Regenerate the capability report and rerun the test suite after subsequent changes.

#### Post-install verification

1. Confirm that the patch files were copied to the correct relative paths.
2. Confirm that the existing `.env` and OAuth client JSON remain intact.
3. Verify that the configured OAuth client path resolves correctly.
4. Start Arthur and invoke a read-only Google Workspace operation.
5. Complete the feature-specific OAuth consent flow when prompted.
6. Verify the returned data against the corresponding resource in Google's own interface.
7. Test a state-changing operation separately. Confirm that Arthur displays the intended action details and requests confirmation before executing it.
8. Check the application logs for authentication, scope, API enablement and permission errors.
9. Verify that no credentials, token files or user data were added to source control.

Do not treat successful local tests or a successful OAuth login as proof that every operation in the registry is available to the signed-in account.

#### Security and backup reminders

- Never commit `.env`, `credentials/`, `data/google_tokens/` or other credential-bearing files.
- Do not share OAuth refresh tokens, client secrets or API keys in screenshots, issues or archives.
- Keep Groq credentials separate from Maps Platform and Cloud Vision API keys; Google OAuth credentials remain scoped to the Google Workspace and Cloud services they authorize.
- Do not disable confirmation gates to work around provider permission errors.
- Retain a backup of the previous working source files until the updated integration has passed local and live-account acceptance tests.

## Original file: `ARTHUR_Reliability_Fixes_Patch_Notes_2026-11-16.md`

### ARTHUR reliability fixes — 16 November 2026

This ZIP is an overlay patch for the `ARTHUR-main(3).zip` source archive reviewed for this work. Extract it into the existing ARTHUR project root and allow the listed files to be overwritten. It does not replace the project or its `.env`, local data, face enrollments, camera configuration, or model files.

#### Included fixes

- **Camera scene description:** captures a fresh camera frame and sends that frame to the configured Groq vision model after explicit upload consent. Local YOLO detections and optional depth estimates are included as context. When Groq is not configured or upload is declined, Arthur gives the local detection/depth summary.
- **Visible product research:** takes a fresh camera frame, gathers local YOLO detections and available depth estimates, and passes those alongside the image and the user's specific question to the visual-research workflow. OCR and optional Google Cloud Vision Web Detection remain part of the research path. Image upload is confirmation-gated.
- **Speech controls:** corrects SAPI completion-state handling (`RunningState == 0` is waiting, not completion), uses SAPI's asynchronous purge flag, and sends pause/cancel signals before waiting for the audio-interruption listener. Resume retains the queued remainder.
- **Calendar:** verifies a newly inserted event by reading it back by event ID. Arthur now distinguishes an inserted event from a read-back-verified event. Calendar listing defaults to 30 future days plus a 7-day lookback, so recently created events are not silently omitted by a short default window.
- **Wi-Fi and Bluetooth:** adds Windows WinRT Radio status and state-change operations for voice commands and the device API. The app asks for confirmation before changing either radio and verifies the resulting state.
- **Navigation diagnostics:** exposes Google's geocoding provider status and error message instead of returning only a generic failure, with guidance for common API-key, billing, quota, and no-result cases.
- **Virtual keyboard voice routing:** adds common variants including “open the on-screen keyboard” and “bring up the virtual keyboard.”
- **Face identification:** adds a one-shot local identification intent for “do you recognize me?” It only identifies a single visible face when it confidently matches a locally enrolled profile; it will not guess when zero or multiple faces are detected.
- **Desktop typing and Enter:** improves Google Drive and Google Contacts search focus and permits Enter fallback for allowlisted search/address fields when Chromium UI Automation does not expose a Runtime ID. Message composers and ambiguous form submissions remain confirmation-gated. WhatsApp's message field may still need to be clicked manually when its accessibility control cannot be reliably identified.
- **PyCAW volume endpoint:** uses the installed PyCAW `AudioDevice.EndpointVolume` property rather than calling a missing public `AudioDevice.Activate()` method.
- **ISL Swin3D checkpoint compatibility:** strips common `module.` and `base_model.` wrappers and maps the fine-tuned classifier key to torchvision's `head.` naming, with duplicate-key protection. Strict model loading remains enabled.

#### Installation (Windows PowerShell)

From the existing ARTHUR project root:

```powershell
Expand-Archive .\ARTHUR_Reliability_Fixes_Patch.zip -DestinationPath . -Force
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-navigation.txt
python -m compileall -q visionguide
python -m pytest -q
```

Then restart ARTHUR:

```powershell
python main.py
```

The added `requirements-navigation.txt` dependency provides the Windows Radio API projection used for Wi-Fi/Bluetooth control. Windows may still deny a change because of permission, driver, hardware-switch, airplane-mode, or policy restrictions; Arthur will report the resulting state or provider error.

#### Required external configuration and assets

- **Groq vision:** `GROQ_API_KEY` must be set in the local `.env`; `GROQ_VISION_MODEL` must identify an image-capable model enabled for the account. This patch requests consent before uploading a camera image. Without a key, scene description falls back to local detections/depth.
- **Google Calendar:** valid OAuth credentials/scopes and the intended Google account must be configured. The patch verifies a create operation by reading the inserted event from that account's primary calendar; it does not bypass Google authorization.
- **Google Maps navigation:** `GOOGLE_MAPS_API_KEY` (or the key variable used in the existing project configuration) must have the Geocoding API enabled, with billing and key restrictions configured. The improved error text helps diagnose configuration but cannot activate a disabled API or repair an invalid key.
- **Actual model files are not included in this patch.** In the uploaded source archive, `models/yolo26n.pt` is a 132-byte Git LFS pointer whose declared binary size is 5,544,453 bytes. `models/isl/swin3d_s/ISL_best_model.pt` is a 134-byte Git LFS pointer whose declared binary size is 227,921,863 bytes. Obtain the real model artifacts from the repository's Git LFS objects or the project maintainer. For an actual Git clone with Git LFS installed, run `git lfs pull` from the repository root. Extracting a source ZIP does not create a Git clone, so `git lfs pull` cannot be used directly in that extracted directory.
- **ISL:** the checkpoint-prefix correction only helps when a real checkpoint for the expected Swin3D-S architecture is present. A Git LFS pointer is not usable weights.
- **Face recognition:** local LBPH recognition is lighting- and pose-sensitive and is not suitable for security/access-control decisions. Enroll only consenting people.

#### Validation boundary

The source was compiled and tested in the patch-building environment: `225 passed, 4 warnings, 38 subtests passed`. The four warnings are FastAPI `on_event` deprecation warnings. This environment did not have the user's Windows desktop, phone camera, SAPI5 audio device, Windows Radio stack, Google OAuth account, or Groq key. Therefore actual hardware, account, and live-provider behavior must be checked on the target Windows machine after installation.

## Original file: `YOUTUBE_CONTEXT_PLAYBACK_PATCH.md`

### ARTHUR — YouTube Context Playback Add-on

This add-on is designed for the ARTHUR source after applying `ARTHUR_Complete_Repair_Patch_v2.zip`.

#### Install

1. Close ARTHUR.
2. Back up your current ARTHUR project folder.
3. Extract this ZIP.
4. Copy the extracted files into the existing ARTHUR project root, preserving the folder structure and allowing the included source files to be replaced.
5. Do not replace `.env`, `.venv`, `data/`, `models/`, `credentials/`, or downloaded model files.

No dependency-manifest changes are required. The feature uses the existing `requests` dependency already declared by the project.

#### Use

1. Say: `Search YouTube for Taylor Swift songs`.
2. Then say: `Play the first video` or `Play the second video`.
3. Other supported selection forms include `Open result number 3`, `Watch video number 2`, and `Play a video` (which selects result 1).
4. After a video opens, say `Pause it`, `Play it`, `Skip forward 30 seconds`, or `Go back 10 seconds`.

ARTHUR remembers only the most recent YouTube search it launched during the current running session. A manually typed search or a search from before ARTHUR was restarted is not used for result selection.

The feature retrieves the public YouTube search-result page, extracts the ordered video IDs/titles, and opens the selected watch page with `autoplay=1`. YouTube/browser autoplay policy can still block automatic playback; in that case, click the player once. ARTHUR does not attempt to bypass autoplay policy.

#### Validation

From the ARTHUR project root in its activated virtual environment:

```powershell
python -m compileall -q visionguide tests
python -m pytest -q
```

The merged source tree was validated with 127 passing tests and four existing FastAPI lifecycle deprecation warnings. Live YouTube responses and autoplay behavior still need to be validated on the target browser/network.

## Original file: `README.md`

### ARTHUR — Confirmation Audio Reliability Patch

This is a focused patch for the voice-confirmation failure where ARTHUR reports that it could not transcribe a clear yes/no answer after two attempts.

#### What changes

- Confirmation capture explicitly resolves and validates the selected microphone. By default it uses the current Windows default input. It can be pinned with `VISIONGUIDE_CONFIRMATION_MIC_DEVICE` in `.env` using a device index or an unambiguous device-name fragment.
- The selected device, input RMS/peak levels, and Whisper transcript are printed to the local terminal. The recording is not saved.
- A digitally silent input stream is detected before transcription. A missing, invalid, or silent microphone does not cause a switch to an arbitrary device; the confirmation remains unaccepted.
- Confirmation Whisper decoding uses deterministic settings (`temperature=0`) and does not condition the answer on previous text.
- The answer parser accepts clear forms such as `Arthur, yes`, `Yes, go ahead`, `The answer is yes`, `I said no`, and `Absolutely not`, while ambiguous phrases such as `I think yes` remain unconfirmed.
- A microphone/PortAudio error on the first attempt is recorded and the existing single retry is still attempted. Actions remain fail-closed: no clear yes means no action.
- Existing half-duplex protection is preserved: ARTHUR stops speech, waits for SAPI/output drain, closes Echoff/AEC, plays the cue, and only then opens the raw microphone.

No new Python dependencies are introduced. The patch does not change regular voice-command capture behaviour.

#### Install

1. Extract this ZIP into the ARTHUR project root, the folder that contains `main.py` and `visionguide\`.
2. Open PowerShell in that project root and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\arthur_confirmation_reliability_patch\install_patch.ps1
```

The installer backs up every file it replaces into `backups\confirmation_reliability_<timestamp>`. It does not overwrite `.env`.

#### Microphone setting for the tested laptop

The diagnostic previously showed that input device **1** (`Microphone Array (AMD Audio Device)`) recorded and transcribed speech, while device **19** returned a zero-level signal. The Windows default input was also device 1.

To pin confirmation capture to the known-working endpoint, add this line to your existing `.env`:

```dotenv
VISIONGUIDE_CONFIRMATION_MIC_DEVICE=1
```

This is specific to the current device enumeration on that laptop. If audio drivers or devices change, inspect the current indexes first:

```powershell
python -c "import sounddevice as sd; print(sd.query_devices()); print('Default devices:', sd.default.device)"
```

Do not set the variable to device 19. Leave it blank or set it to `default` to use the current Windows default input.

#### Validate and run

Activate the project virtual environment, then run the targeted regression tests:

```powershell
python -m pytest -q tests\test_confirmation_audio.py tests\test_speech_interruptions.py tests\test_assistant_state_helpers.py
```

Start ARTHUR normally:

```powershell
python main.py
```

When a protected action asks for confirmation, wait for the tone and say a short, clear `yes` or `no`. The console should show the selected input device, measured input levels, and the transcription. If the levels are effectively zero or the device cannot open, ARTHUR reports the capture error, retries once, and cancels the action if it still cannot obtain a clear answer.

#### Validation performed while preparing this patch

- `python -m compileall -q visionguide tests` — passed.
- Non-timer suite — 205 passed, 4 existing FastAPI deprecation warnings, 38 subtests passed.
- Timer suite, run separately — 6 passed.
- Focused confirmation suite — 28 passed, 33 subtests passed.

The full test suite was validated in two groups because a combined run intermittently stalled in an existing timer test in this Linux validation environment; that timer test suite passed separately. This environment cannot validate the actual Windows microphone, Realtek driver, SAPI playback, or Echoff device timing. After installation, the first live confirmation on the laptop is the required hardware check.

## Original file: `README_INSTALL.txt`

ARTHUR — AEC Readiness Calibration Patch
========================================

PURPOSE
-------
This is a small overlay for the existing ARTHUR Echoff AEC integration. It
updates the startup quality thresholds to match the measured acoustic level of
your Realtek speaker-loopback / AMD microphone setup, and prevents the rolling
readiness diagnostic from discarding your speech during double-talk.

WHAT CHANGES
------------
1. Echoff minimum raw microphone RMS is calibrated from 0.003 to 0.0001.
   Your far-end-only microphone recording was approximately 0.00019 RMS, so
   the old threshold was about 16 times higher than the signal your hardware
   actually produces.
2. Minimum measured suppression is calibrated from 10 dB to 5 dB. Your clean
   playback-only test measured about 6.1 dB on Echoff's rolling diagnostic and
   about 8.6 dB in the offline far-end-only analysis.
3. The 7.5-second active-reference warm-up remains in place. The suppression
   requirement must still pass Echoff's rolling quality window and stable-time
   check before ARTHUR accepts barge-in audio.
4. Once Echoff first reports its path ready, ARTHUR latches readiness for that
   AEC capture session. Echoff's rolling metric can dip when you speak because
   your preserved voice raises the clean microphone energy. Such a dip must not
   cause ARTHUR to throw away the user's cleaned speech frames.
5. Status now distinguishes the live Echoff readiness value from ARTHUR's
   latched session readiness.

This does NOT bypass the startup gate. If the speaker reference is not active,
AEC does not pass its quality check, no paired frames arrive, or the capture
fails, ARTHUR continues to fail closed: raw microphone audio is not sent to
Whisper during active SAPI playback. Once ready, only Echoff's microphone_clean
frames are used for speech interruption.

INSTALLATION
------------
1. Close ARTHUR completely.
2. Extract this ZIP into the ARTHUR project root (the folder containing main.py).
   The archive creates the folder arthur_aec_readiness_patch.
3. Open PowerShell in the ARTHUR project root and run:

   powershell -ExecutionPolicy Bypass -File .\arthur_aec_readiness_patch\install_patch.ps1

4. Activate the existing environment:

   .\.venv\Scripts\Activate.ps1

5. Validate:

   python -m compileall -q visionguide tests
   python -m pytest -q

6. Start ARTHUR:

   python main.py

The installer creates timestamped .bak backups of the two replaced files. It
does not modify .env, .venv, requirements files, credentials, models, databases,
or any other project files. Echoff dependencies are unchanged; this patch
assumes the earlier requirements-aec.txt installation is already complete.

OPTIONAL .ENV OVERRIDES
-----------------------
The calibrated defaults are already applied. You normally do not need to add
these variables. They are available for later tuning:

   VISIONGUIDE_AEC_MIN_SUPPRESSION_DB=5.0
   VISIONGUIDE_AEC_MIN_RAW_RMS=0.0001
   VISIONGUIDE_AEC_WARMUP_SECONDS=7.5

Values are bounded by the integration. Minimum suppression cannot be configured
below 3 dB, raw RMS cannot be configured below 0.00001, and warm-up cannot be
configured below 1 second or above 7.5 seconds.

TESTING AFTER INSTALL
---------------------
A. Start ARTHUR and ask it to speak a long answer (at least 10–15 seconds).
B. Wait for the AEC startup period, then say: "Arthur, stop speaking."
C. While paused, say: "Continue."
D. While speaking, try a new addressed command: "Arthur, what is 25 multiplied
   by 48?"
E. Confirm a yes/no action. ARTHUR should finish its short prompt and tone
   before opening the microphone answer window.

If readiness is not reached, the app should still fail safely. Pause speech or
press Escape rather than expecting raw-microphone barge-in during TTS.

VALIDATION
----------
Built against the ARTHUR source archive available in this session.
Results:
   python -m compileall -q visionguide tests  -> passed
   python -m pytest -q                         -> 205 passed, 20 subtests passed
   4 existing FastAPI on_event deprecation warnings

Automated tests cannot prove the behaviour of your specific speakers, room,
Windows audio endpoints, or Whisper transcription. Continue with the hardware
and manual tests above.

## Original file: `README_PATCH.md`

### ARTHUR persistent timers and scheduled reminders

This patch replaces the in-memory timer store with a SQLite-backed scheduler while keeping the existing `TimerManager.schedule()`, `cancel()`, `list_timers()` and `close()` interface.

#### Files in this patch

- `visionguide/integrations/timers.py` — persistent countdowns, one-time reminders, daily/weekly recurrence, restart recovery, and separate desktop/API notification deliveries.
- `visionguide/api_server.py` — API timer manager uses the `api` delivery channel and exposes reminder endpoints plus internal reminder route handlers.
- `tests/test_timers.py` — persistence, cancellation, recurrence, timezone validation, and cross-channel notification tests.

`api_server.py` was prepared against the complete version you pasted in this conversation. Back up the current file before replacing it.

#### Install

From the ARTHUR project root in the activated `.venv`:

```powershell
python -m pip install tzdata
```

`tzdata` supplies IANA time-zone definitions on Windows for `zoneinfo`, including `Asia/Kolkata`.

Copy the files into the matching paths, preserving the existing project folders. The new scheduler creates `data\arthur_schedule.sqlite3` automatically. Both the desktop app and API resolve the same default database path from the package location.

To use a custom location, set `ARTHUR_SCHEDULE_DB` in `.env`. The desktop and API processes must use the same path.

#### Verify

```powershell
python -m pytest tests\test_timers.py -q
python -m py_compile visionguide\integrations\timers.py visionguide\api_server.py
```

The five scheduler tests included here passed in the patch-building environment. This is not a run of the full ARTHUR test suite.

#### API usage

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

#### Remaining voice-router integration

The timer engine, desktop delivery callback contract, and API endpoints are implemented here. Natural-language voice routing for phrases such as “remind me tomorrow at nine” still needs targeted edits to `semantic_router.py` and the desktop command dispatcher. Those source sections were not included in the code you pasted, so I have not guessed their surrounding implementation. The next source-extraction command is included in the chat response.

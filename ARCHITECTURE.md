# Arthur Technical Architecture

## 1. Runtime components

Arthur uses a local-first Windows desktop application plus a FastAPI device-agent service. A small Python REST client and a Flutter client starter communicate with the service. The design keeps tools close to the resources they control: Windows input, brightness, audio, network interfaces, active application windows, and local files execute on the Windows device agent.

Camera frames, microphone recordings, screenshots, face profiles, and local notes are intended to remain on-device unless a workflow explicitly requires an external service and the user approves the relevant upload or transmission. The desktop application is the reference implementation; the Flutter client is a mobile interface starter, not a replacement for Windows device-level integrations.

### Source map

| Source | Responsibility |
|---|---|
| `main.py` | Desktop entry point or `--serve-api` entry point |
| `visionguide/app.py` | Tk desktop UI, camera/status controls, speech routing, permission prompts and result display |
| `visionguide/voice_commands.py` | On-demand microphone recording and Whisper transcription; file-based transcription |
| `visionguide/semantic_router.py` | Gemini function calling, rule/parser fallback, local intent patterns, embedding similarity, typed `RoutedCommand` |
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

## 2. Command lifecycle

1. **Capture.** The desktop records audio only after an explicit voice-command action or after the locally armed wake-word flow activates. The Flutter starter supports short device-native speech recognition and recorded audio sent to the service for Whisper transcription.
2. **Transcribe.** Whisper returns text. It does not execute tools and is not given a shell or application-control interface.
3. **Route.** `SemanticCommandRouter.route()` attempts Gemini function calling when a Gemini API key is configured. If routing is unavailable, it checks the existing local parser, deterministic high-value patterns, and a SentenceTransformers cosine-similarity matcher. The local similarity model loads on first use and uses `VISIONGUIDE_SEMANTIC_THRESHOLD`.
4. **Validate.** The router returns a `RoutedCommand` with an action name, primitive typed arguments, source, and confidence. Tool names are registered in `_FUNCTIONS`; execution is a separate layer. The executor checks allowed website/app/window names, argument ranges and OS/provider prerequisites.
5. **Confirm.** Network disconnection, sending messages, calendar writes, and sensitive GUI workflows require a confirmation checkpoint. The API returns a random one-use confirmation ID bound to the `device_id`; the token expires after five minutes and is consumed after approval or cancellation.
6. **Execute.** Local desktop actions execute on Windows. Gmail/Calendar API requests run with the authenticated Google account. A GUI workflow types into a selected known window and leaves a draft open unless a separately confirmed send command is issued.
7. **Verify and respond.** Result text and status are returned to the desktop, HTTP client, or timer WebSocket. A keyboard shortcut being issued is not proof of final delivery; the user/application status must be checked.

### Semantic function calling

`visionguide/semantic_router.py` declares functions for websites, apps, vision/document intents, media playback, display/audio/network controls, timers, Gmail, Calendar, GUI drafting and text-only general queries. `automatic_function_calling` is disabled for the router request: Gemini proposes a function and the local code decides what happens next. No model-generated Python or shell string is evaluated.

Calendar routing receives the configured local date/time and `VISIONGUIDE_TIMEZONE` (defaults to `Asia/Kolkata`) so phrases such as “tomorrow at 10” can be resolved. The router should ask for clarification when a required event detail or recipient is ambiguous.

Fallback order when the Gemini API is unavailable: legacy local parser → high-value deterministic patterns → local SentenceTransformers similarity → unmatched intent. The API may then route an unmatched textual query to text-only Gemini; the desktop asks before sending the transcription to Gemini.

The text-only Gemini fallback does not automatically include camera frames or screenshots. Visual requests that require an external vision service follow a separate image-selection and permission path.

## 3. Client-server design

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

### API routes

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

## 4. Windows system and browser controls

- **Media:** `media_playback()` targets a browser window title (prefers YouTube) through PyGetWindow and uses YouTube keyboard shortcuts (`K`, `J`, `L`, `Shift+N`, `Shift+P`). The browser player must be focused. Stop maps to pause; `K` is a toggle rather than an idempotent play/pause state query.
- **Brightness:** `screen-brightness-control` queries/sets percentage values. Hardware and external monitor support depends on the display/driver.
- **Audio:** Pycaw reads and adjusts Windows master output level and mute state through the Core Audio endpoint API.
- **Wi-Fi:** `netsh interface show interface` enumerates Windows interfaces; `netsh interface set interface` changes only a named adapter that was found. The UI/API confirmation must precede this action. Windows policy or adapter privileges may deny the operation.
- **GUI:** PyAutoGUI injects keys/pastes and PyGetWindow activates allowlisted windows. The executor never starts arbitrary shell commands from transcribed text. PyAutoGUI fail-safe remains enabled.

GUI automation depends on the target application being available and correctly focused. Clipboard paste and keyboard injection are best-effort input operations; they do not guarantee that the intended application accepted, saved, or delivered the content.

## 5. Timers, threads and event handling

`TimerManager` creates `threading.Timer` workers, maintains a lock-protected ID registry, uses monotonic deadlines, supports cancellation and stops its callbacks during shutdown. Timer callbacks run away from the Tk UI loop; `app.py` passes events through its async queue. The FastAPI timer callback publishes a `timer_expired` WebSocket event when connected clients are present. Countdown timers are in-process and are cleared when the process stops; persistent calendar scheduling is a separate Google Calendar write.

These timers are not persistent reminders: they do not survive process termination, a machine restart, or an API service restart.

## 6. Workspace services

`google_workspace.py` uses `InstalledAppFlow` for desktop OAuth and the Google API client libraries. Access/refresh tokens are stored under `data/google_tokens/`, outside version control. Supported operations:

- Gmail unread metadata and body text when requested, inbox query search, read one message, create API draft, send a named draft after explicit confirmation.
- Calendar list upcoming primary-calendar events, search event summaries/descriptions, create a validated event after confirmation.

Scopes are defined in the module. OAuth consent and test-user configuration must be completed in Google Cloud Console. API quota, revoked grants, scope changes and account policy errors are returned through the provider adapter; remove the local token file to force re-consent after changing scopes.

The desktop's GUI path is separate: it uses Gmail's compose keyboard shortcut, pastes the user-approved recipient/subject and Gemini-generated body, then leaves the draft for review. The send action activates Gmail and issues Ctrl+Enter only after explicit confirmation.

The API and GUI paths have different execution and verification characteristics. An API draft operation is not the same as typing into Gmail's graphical interface, and neither should be reported as successfully sent until the relevant provider or application confirms the result.

## 7. Air mouse and ISL

### Air mouse

`GestureMouse` consumes the current camera frame through MediaPipe Hand Landmarker. The index fingertip maps to the cursor; thumb-index pinch produces a debounced left click; the rightmost 18% of the mirrored camera frame is reserved for vertical scrolling. The user must enable it and can disable it in the desktop UI; camera loss and PyAutoGUI fail-safe stop control.

The unified system-wide virtual keyboard is controlled through mouse interaction and the gesture pointer's pinch-click path. Literal voice typing can paste into the currently focused target after confirmation. The older prompt-only `air_keyboard.py` module remains in the source tree for compatibility but is not a second visible/active keyboard in the desktop UI.

### Indian Sign Language

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

## 8. Failure handling and invariants

- A failed provider call does not become a success response.
- The camera remains silent until requested; screen/camera upload requires explicit UI permission.
- A route cannot broaden the registered tool allowlist.
- Recipient, contact, target window and full message body must be verified before sending.
- Confirmation tokens are one-use, device-bound and time-limited.
- Wi-Fi, Calendar and send actions report failure when the operating system/provider rejects the call.
- The project does not claim that inferred distance, detection absence or a single image proves a path safe.
- Local inference does not imply that every feature in the wider application is offline; Gemini, Google Workspace and Google Cloud adapters require their respective credentials and network access.
- Face recognition is limited to locally enrolled profiles. It is not a general-purpose stranger-identification or internet face-search feature.
- Optional DeepFace embedding fusion does not establish biometric identity accuracy or suitability for security-critical authentication.

## Newly integrated assistive workflows

- **Action/result memory:** executed commands are recorded to bounded local SQLite history; follow-up questions retrieve the last action without overwriting the result being queried.
- **Unified keyboard/gesture path:** one system-wide virtual keyboard is controlled by mouse clicks and hand-pointer pinch clicks; literal voice typing can paste into the currently focused target after confirmation. The older prompt-only `air_keyboard.py` module remains in the source tree for compatibility but is not a second visible/active keyboard in the desktop UI.
- **Local profile preferences:** enrolled-user preferences persist across restarts and are cleared when the profile is deleted. Unknown/multiple-face views do not inherit preferences. Optional DeepFace embeddings are fused with LBPH when available, and mismatched predictions are treated as unknown.
- **Maps and route guidance:** REST adapters cache responses and apply per-device request caps. `NavigationSession` uses Windows geolocation when installed and available, speaks route instructions, and recalculates after repeated off-route readings. This is a prototype, not a certified navigation SDK or safety service; live acceptance testing on the target machine is required.
- **Visual search and cloud vision:** Google Cloud Vision Web Detection and other external visual services require their configured credentials and an explicitly approved image payload. Local object detection and external image research are separate workflows; local detection does not itself require uploading an image.
- **Privacy and storage:** user notes are stored locally in SQLite when requested and can be searched or deleted. Face profiles and preferences are local profile data; their persistence and deletion behavior should be verified against the actual storage implementation before release.
# Arthur — Assistive Multimodal Agent Platform

Arthur is a local-first assistive AI vision, voice, productivity, and hands-free control system. The Windows desktop client is the reference implementation; a FastAPI device-agent service and Flutter client starter extend the same typed command model to mobile and wearable front ends.

The project includes implementation modules for semantic/LLM command routing, Whisper transcription, camera object detection, user-requested scene Q&A, OCR, local document search, timers, Windows audio/display/network controls, browser playback shortcuts, GUI drafting workflows, Google Workspace OAuth adapters, a FastAPI API, and hand-gesture controls.

The current Indian Sign Language (ISL) implementation uses a Swin3D-S video classifier for a defined vocabulary of 76 isolated signs. Continuous sentence-level sign-to-text and text-to-sign are separate development components described in `CONTINUOUS_ISL.md`; they should not be treated as completed capabilities of the current isolated-sign recognizer.

## Arthur listening and camera privacy

- The desktop UI starts with the microphone wake detector disabled and the camera off.
- Use the **Listening: OFF/ON** master toggle to permit local wake-word detection. Set `WAKE_WORD_MODEL` in `.env` to a compatible downloaded openWakeWord ONNX model. The example path is `models/wakeword/hey_arthur.onnx`; ensure the configured filename matches the actual model file.
- After the configured wake phrase is detected, Arthur can enter its active voice-interaction mode. The intended conversation flow uses short audio chunks for transcription and returns to wake-word mode after its configured inactivity period. The exact chunk duration, timeout, and supported exit phrases must match the current implementation and configuration; verify them against the running application before relying on them.
- The camera is off at startup. A requested camera task opens it temporarily; use “turn on the camera” to keep it running, and “turn off the camera” to release it. Face enrollment and enabled camera-based features may use the camera while active. If the master listening toggle is configured to stop the camera as well, switching it off releases both resources.
- Voice confirmation prompts for sensitive or external actions remain in place. Review the recipient, target, and content before authorizing any send or account-changing action.

## Core behaviour

- **Silent camera by default.** Camera capture and object detection do not trigger unsolicited scene narration. The user must request a scene description or OCR operation; proactive safety alerts remain disabled until explicitly enabled.
- **Semantic intent routing.** A command is transcribed by local Whisper on the desktop (or by the selected mobile speech/Whisper path), then routed by Gemini function calling, the local command parser, high-value local intent patterns, and a SentenceTransformers similarity matcher. Routed calls select only tools in the typed registry. Unmatched requests can fall back to a text-only Gemini request after consent in the desktop client or a confirmation screen in the API client.
- **Permissioned tool execution.** The model proposes an intent; a local executor validates arguments, allowlisted targets, device scope, and confirmation rules. Model-generated shell commands and arbitrary `eval` are never executed.
- **Local-first processing.** Camera frames, audio recordings, screenshots, face templates, and local notes stay on-device unless a user-authorized operation explicitly sends selected content to a configured provider. The API's audio upload endpoint runs Whisper on the server machine and deletes its temporary upload afterward.
- **Review before external actions.** Gmail/WhatsApp sends and Calendar writes require an explicit confirmation checkpoint. GUI workflows prepare editable drafts by default; they do not silently send or save them.
- **Device-aware architecture.** Windows-specific actions execute on the machine running the Windows device agent. The mobile client sends commands and receives results; it does not automatically acquire control of another device's camera, display, cursor, or network adapter.

## Architecture

```text
Windows desktop / mobile client / wearable client
     speech, text, camera and gesture input
                       |
          Whisper / client-native speech
                       |
             Semantic command router
    Gemini function calling → local parser/patterns
              → local embedding matcher
                       |
              typed allowlisted intent
                       |
         executor + confirmation policy
     ┌─────────────────┬──────────────────┐
     │                 │                  │
 Local perception  Productivity    Windows device tools
 YOLO / OCR / ISL   Gmail / Calendar media / brightness
 documents/memory  timer manager   Pycaw / netsh / GUI
     └─────────────────┴──────────────────┘
                       |
           REST response / WebSocket event
              text, UI and speech output
```

The implementation entry points are:

| Module | Implemented responsibility |
|---|---|
| `visionguide/semantic_router.py` | Gemini function-calling router, local parser/pattern fallback, SentenceTransformers semantic similarity, typed `RoutedCommand` results |
| `visionguide/voice_commands.py` | Explicit microphone recording and local Whisper transcription, plus audio-file transcription for API uploads |
| `visionguide/integrations/system_controls.py` | Browser playback shortcuts, display brightness, Windows master volume/mute, Windows adapter list/enable/disable |
| `visionguide/integrations/timers.py` | Thread-safe countdown manager with cancellation and background expiry callbacks |
| `visionguide/integrations/google_workspace.py` | Feature-isolated Google OAuth 2.0 scope profiles, core Gmail/Calendar helpers, and dispatch to the extended Workspace operation registry |
| `visionguide/integrations/google_workspace_extended.py` | 197 allowlisted Calendar, Gmail, Drive/Apps Script, Docs/Sheets/Slides/Tasks, People/Contacts, Classroom, Meet REST, YouTube, Forms, and Generative Language operations with explicit write confirmation |
| `visionguide/integrations/gui_automation.py` | Window targeting; Gmail draft entry; Word document typing; WhatsApp Web draft/send; safe text paste into allowlisted windows |
| `visionguide/api_server.py` | FastAPI command, confirmation, timer, Workspace, transcription and WebSocket notification endpoints |
| `visionguide/gesture_mouse.py` | MediaPipe hand tracking, cursor control, thumb-index pinch clicks and a dedicated vertical-scroll strip |
| `visionguide/system_virtual_keyboard.py` | Custom always-on-top Windows keyboard overlay; mouse clicks send keys to the currently focused application without intentionally activating the overlay |
| `clients/python/visionguide_client.py` | Small Python REST client for API commands, confirmations, timers and Workspace reads |
| `clients/flutter/` | Flutter mobile client starter with server connection, command text, device speech recognition, recorded-audio upload to local Whisper, confirmation UI and timer notifications |
| `visionguide/sign_language.py` | Current isolated-sign ISL Swin3D-S classification/inference path |

See `ARCHITECTURE.md`, `INTEGRATIONS.md`, `COMMAND_CATALOGUE.md`, and `GOOGLE_SCOPE_FEATURE_MATRIX.md` for implementation details and scope-specific limitations.

## Requirements

- Windows 10/11 x64 for the reference desktop client and Windows-specific integrations.
- Python 3.11 x64 is the project runtime baseline.
- Webcam and microphone for camera and voice features; keyboard/mouse and display for system automation.
- `GEMINI_API_KEY` for Gemini function calling, visual Q&A, and text-only fallback.
- A Google Cloud project with Gmail API and Google Calendar API enabled plus a Desktop OAuth client JSON for Workspace operations.
- Tesseract OCR installed separately if using the Tesseract-backed local OCR path.
- FFmpeg available on `PATH` for Whisper audio decoding.
- For hand control, the MediaPipe hand-landmarker model downloaded into `models/hand_landmarker.task`.
- For ISL inference, the Swin3D-S checkpoint at `models/isl/swin3d_s/ISL_best_model.pt`, plus the PyTorch/Torchvision dependencies listed in `requirements-signs.txt`.

## Install — PowerShell

Open PowerShell in the extracted `Arthur` project directory.

If you already have the project's Python 3.11 virtual environment, activate and reuse it. Create a new environment only if one does not already exist:

```powershell
if (-not (Test-Path .venv)) {
    py -3.11 -m venv .venv
}

.\.venv\Scripts\Activate.ps1
python --version
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-integrations.txt

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
```

If `.env` already exists, keep it and merge any new variables from `.env.example` manually; do not overwrite configured secrets.

If the current PowerShell session blocks activation, use:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Edit `.env` and set `GEMINI_API_KEY`. `VISIONGUIDE_TIMEZONE` defaults to `Asia/Kolkata` and is used when routing natural-language calendar dates. The local semantic fallback uses `sentence-transformers/all-MiniLM-L6-v2`; its weights are downloaded by SentenceTransformers when first needed unless already cached. Configure `VISIONGUIDE_SEMANTIC_MODEL` and `VISIONGUIDE_SEMANTIC_THRESHOLD` to tune it.

### Optional feature dependencies

Install additional dependencies only when you need the corresponding feature and its required model or external service:

```powershell
# ISL Swin3D-S inference and evaluation
pip install -r requirements-signs.txt

# Face-recognition extras
pip install -r requirements-face.txt

# Windows location/navigation extras
pip install -r requirements-navigation.txt
```

The ISL requirements include PyTorch and Torchvision. The current recognizer uses the Swin3D-S checkpoint and does not use the previous TensorFlow LSTM model for ISL inference. MediaPipe remains part of the hand-gesture control implementation.

Start the Windows desktop client:

```powershell
python main.py
```

Common launch options:

```powershell
python main.py --camera 1
python main.py --camera "http://192.168.1.20:8080/video"
python main.py --confidence 0.40 --fps 6
python main.py --cpu
python main.py --no-speech
python main.py --model "E:\path\to\another-model.pt"
```

## Windows and browser controls

The command router can invoke browser playback shortcuts, screen-brightness adjustment, Windows master volume and mute, adapter status, and adapter enable/disable. Brightness uses `screen-brightness-control`; audio uses Pycaw; Wi-Fi uses `netsh interface`. The Wi-Fi operation identifies the named adapter and asks before changing its state. Depending on Windows policy, adapter changes may need elevated privileges.

Browser playback targets an existing browser window, preferring a YouTube title, then sends the YouTube keyboard shortcuts. The player must have focus; `K` is a play/pause toggle and stop maps to pause because browser playback does not provide a universal stop shortcut. Skip-forward/back uses repeated `L`/`J` key presses in approximate ten-second increments.

GUI automation uses PyAutoGUI and PyGetWindow with allowlisted application/window targets. It can prepare Gmail drafts, open a new Word document and paste content, prepare a WhatsApp Web message, or paste text into supported windows. These are keyboard-driven workflows, not browser-DOM automation: check the active window, selected contact, recipient, subject and full text before continuing. Enable Gmail keyboard shortcuts in Gmail settings for the `C` compose shortcut. Email and WhatsApp sends have separate confirmation actions.

The **Air virtual keyboard…** button opens the unified system-wide virtual keyboard. It is a single on-screen keyboard controlled by mouse clicks or by the same enabled hand-gesture controller. Voice commands such as “type exactly hello world” can paste literal text into the currently focused Windows application after an explicit confirmation and a short focus-selection delay. It supports letters, numbers, common symbols, Space, Tab, Enter, Backspace, navigation/function keys, Caps Lock, and modifier combinations. On Windows, the overlay attempts to use a non-activating window style so key clicks do not steal focus from the target app.

Verify the target field before typing: generic desktop automation cannot reliably identify every browser or custom application control. The keyboard is Windows 10/11-only and requires the integrations dependencies, including `pyautogui`.

### System-wide gestures

Run `python tools/download_hand_model.py` to install the MediaPipe Hand Landmarker model at `models/hand_landmarker.task`, then use **Hand gestures…** to enable or disable camera-based control.

The index finger moves the pointer, a thumb-index pinch clicks, vertical movement in the rightmost 18% of the camera view scrolls, and a quick horizontal swipe changes browser tabs (left = previous, right = next). The same pointer/pinch gestures can click keys on the unified Air virtual keyboard. The mapping is intentionally opt-in and has motion smoothing and cooldowns. Avoid it while entering passwords or handling sensitive screens; the PyAutoGUI emergency corner failsafe remains active.

### Google Cloud weather, visual search and navigation

Set `GOOGLE_MAPS_API_KEY` in your local `.env` and restrict it to the Maps Platform REST APIs you use: Geocoding, Routes, Weather, Places API (New), Air Quality, Pollen, Time Zone, Roads and (only with explicit consent) Geolocation. Cloud Vision Web Detection uses a **separate** `GOOGLE_CLOUD_API_KEY` or `GOOGLE_VISION_API_KEY`, restricted to Cloud Vision API; a Maps-only key will not work if its API restrictions exclude Cloud Vision. Cloud Translation and Cloud Natural Language use separate OAuth scope profiles rather than either API key. Enable billing and set project-level quotas/budget alerts. The `.env.example` caps each adapter's daily requests locally and response caches reduce repeat calls; these are guardrails, not a replacement for Google Cloud quotas/billing controls. Current pricing and availability vary by service, account and region. Cache and usage counters are stored under `data/cache/`.

Weather commands retrieve current conditions for a named place or, with permission, the device's current Windows location. Route commands can calculate a route and show Google Maps, including traffic-aware ETA for supported drive/two-wheeler requests. When you opt into live navigation, Arthur uses Windows location updates to speak maneuver steps and request a new route after repeated off-route readings.

This is a best-effort Python navigation prototype, not a certified navigation/safety system. Location, route coverage, GPS accuracy, live rerouting and step timing require real Windows/device testing. Google Maps is opened as a visual route preview, while live spoken guidance runs in Arthur.

### Local face preferences and visual product search

Face recognition remains local and opt-in. OpenCV LBPH is preserved; when the optional DeepFace extra is installed and embeddings can be created for enrolled samples, the local embedding match is combined with LBPH, and conflicting predictions remain unknown. Install the optional extras only when needed with `pip install -r requirements-face.txt`. Enrol only consenting users; embeddings and samples stay in `data/faces/`.

Use local profile preferences to remember a name of address. Public visual search is separate from enrolled-face recognition; it can return similar images/pages but does not prove a person's identity or an exact product model. Product research asks before sending a compressed camera image to Gemini and Google Cloud Vision.

For live Windows location support, run `pip install -r requirements-navigation.txt`, enable Windows Location services, and grant the desktop app permission when prompted. The Maps/Weather/Routes REST adapters work only when a valid key, enabled APIs and applicable billing/quotas are configured.

## Google Workspace OAuth setup

The Google Workspace adapter exposes the expanded scope-aware operation set described in `GOOGLE_SCOPE_FEATURE_MATRIX.md`. Features include Calendar event/calendar management, Gmail messages/drafts/labels/settings/forwarding/delegates/notifications, Drive files/metadata/permissions/app-data/Apps Script/activity, Docs/Sheets/Slides edits, Tasks, People/Contacts and selected user-profile fields, Classroom courses/rosters/classwork/submissions/guardians, Meet REST records and artifacts, YouTube channel/video/playlist operations, Forms responses and watches, and OAuth-backed Gemini tuning/retriever operations.

Create a Desktop OAuth client and store its JSON at `credentials/google_oauth_client.json` (or set `GOOGLE_OAUTH_CLIENT_FILE`). OAuth tokens are stored separately per feature profile under `data/google_tokens/`. **Merge** needed variables from `.env.example` into your existing `.env`; do not replace an existing `.env` with the template. Each feature requests its own scope profile at first use; the app does not ask for the whole Google Auth Platform catalogue on every login. The associated API must also be enabled in Cloud Console, and sensitive/restricted scope verification, account role, API quotas, Workspace-admin policy and product eligibility can affect availability.

Writes, sends, deletes, publication, sharing changes and other externally visible mutations require explicit confirmation. The Meet Media API real-time audio/video capture, Gmail add-on contextual scopes, Classroom add-on attachment runtime/practice sets, Meet hardware management, Drive Activity writes, Google Photos Library media management, and YouTube partner/download features are listed as gated or not implemented; details and scope-to-operation mappings are in `GOOGLE_SCOPE_FEATURE_MATRIX.md`. Enabling a scope does not make those product-level APIs available.

## Run the FastAPI device service

From the project root, set `VISIONGUIDE_API_HOST` and `VISIONGUIDE_API_PORT` in `.env` and run:

```powershell
python main.py --serve-api
```

The default host is `127.0.0.1`. Visit `http://127.0.0.1:8000/docs` for the OpenAPI UI. Important routes:

| Route | Purpose |
|---|---|
| `GET /health` | Agent health |
| `GET /api/v1/tools` | Device/API tool manifest |
| `POST /api/v1/command` | Route and execute a typed natural-language command |
| `POST /api/v1/confirm` | Approve/reject the exact stored high-impact intent; token is one-use, device-bound and expires after five minutes |
| `POST /api/v1/transcribe` | Receive a bounded audio clip and transcribe it locally with Whisper |
| `/api/v1/timers` | Create/list/cancel timers and publish expiry events |
| `/api/v1/workspace/gmail/*` | Gmail reads, search, draft, and a preview-first draft-send challenge; approve the returned one-use token via `/api/v1/confirm` |
| `/api/v1/workspace/calendar/*` | Calendar upcoming/search and a one-use confirmation challenge for event creation |
| `WS /ws/notifications` | Timer-expiry/event stream |

### Connect a phone on the same trusted network

Set a strong unique `VISIONGUIDE_API_TOKEN` in `.env`, set `VISIONGUIDE_API_HOST=0.0.0.0`, configure Windows Firewall for the chosen port on the private network only, and restart the API. The Flutter client should use the laptop's LAN IP (for example `http://192.168.1.20:8000`) and the same bearer token. Do not expose this unaudited development service to the public internet. For remote access, use a properly configured TLS reverse proxy, strong authentication, firewall restrictions, and least-privilege networking.

The Python client supports direct Gmail draft creation and preview-first send requests, Calendar search/event previews, local-audio transcription, and direct token confirmation. The API runs actions on the machine hosting it. It does not stream phone camera frames or remotely change phone settings; those capabilities need the relevant client-native permission and a device-agent implementation for that OS.

## Flutter mobile client starter

The `clients/flutter` directory contains the Dart UI and dependency manifest for connecting to the device API, typing/speaking a short command, recording audio and sending it to server-side Whisper, showing a confirmation dialog for protected actions, and receiving timer notifications.

A Flutter SDK is required to generate the native Android/iOS scaffolding and compile the app. From `clients/flutter`, run:

```powershell
flutter create --platforms=android,ios .
```

Review any files Flutter reports as retained or generated, then restore the provided `pubspec.yaml` and `lib/main.dart` if they were rewritten. Run `flutter pub get` and configure Android microphone/Internet permissions plus iOS microphone and speech-recognition usage descriptions. This repository contains the client starter rather than generated platform projects or a signed mobile release. Build and test on a physical phone before daily use.

## Air mouse and gestures

Run `python tools/download_hand_model.py` to place the MediaPipe Hand Landmarker task file at the expected location. In the desktop UI, explicitly enable Hand gestures. The index fingertip controls the pointer, thumb-index pinch clicks, the rightmost 18% of the camera frame acts as a vertical-scroll strip, and quick left/right swipes switch browser tabs. The gestures can operate the unified Air virtual keyboard. PyAutoGUI's top-left failsafe remains active. Disable gesture control before handling passwords, payments, or other sensitive screens.

## Indian Sign Language

The current ISL inference path uses **Torchvision Swin3D-S** with a 76-class isolated-sign vocabulary.

- **Checkpoint:** `models/isl/swin3d_s/ISL_best_model.pt`
- **Dataset directory used by the current project workflow:** `data/isl_dataset/ProcessedData_vivit`
- **Input:** a temporal clip of 32 video frames, rather than a single still image.
- **Output:** a predicted class label and confidence score for one isolated sign.
- **Processing:** local model inference; the model requires the dependencies in `requirements-signs.txt`.

The current classifier does not translate continuous signing into complete sentences. A sequence-level system needs temporal segmentation, sequence decoding, linguistic context, and validation with signers. The separate `CONTINUOUS_ISL.md` document describes that development direction and its integration boundary; its presence does not mean a complete continuous translation model is currently integrated.

Previously used MediaPipe/TensorFlow LSTM ISL inference is not the current Swin3D-S inference path. MediaPipe remains used for hand-gesture control.

Reported offline classifier evaluation is not equivalent to live-camera validation or signer-independent generalization. Evaluation should report held-out signer performance, per-class metrics, sequence metrics where applicable, non-manual cues, and confidence/reject behaviour. Dataset and checkpoint provenance, licensing, and permission to redistribute must be documented separately.

## Tests and diagnostics

```powershell
python -m unittest discover -s tests -v
python -m compileall -q main.py visionguide tools tests clients/python
python main.py --help
```

The unit suite covers command routing, timers, local memory, document search, depth-motion logic, API confirmation gates, and selected integration input validation. It does not emulate a real Windows GUI, Google account/OAuth consent, local mic/webcam, installed external browser player, or a physical Android/iOS build. See `VALIDATION_REPORT.md` for the exact checks run.

## Reliability and safety

Arthur is not a certified mobility aid, a guarantee of path safety, or an emergency system. Object detections can be missed; monocular distance estimates are approximate. Face memory is for consent-based enrolled people and is not used for public-web identification of strangers. Screen/image uploads require a separate user action. The system must not claim a GUI click, message send, API write, or reminder delivery succeeded unless the execution result supports that claim.

## Documentation

- `ARCHITECTURE.md` — source modules, router flow, API and device boundary.
- `INTEGRATIONS.md` — setup and execution for each connected provider and device tool.
- `GOOGLE_SCOPE_FEATURE_MATRIX.md` — Google OAuth scope, API operation and product-limit matrix.
- `COMMAND_CATALOGUE.md` — spoken command examples.
- `ROADMAP.md` — implementation status and next engineering gates.
- `SECURITY_AND_PERMISSIONS.md` — authentication, privacy and confirmation policy.
- `CONTINUOUS_ISL.md` — isolated-sign and continuous ISL architecture.
- `WAKE_WORD_SETUP.md` — local wake-word model setup.
- `THIRD_PARTY_NOTICES.md` — third-party packages/models and licensing reminders.
- `VALIDATION_REPORT.md` — automated validation results and environment boundaries.

## Expanded desktop, website, and Windows Settings allowlists

The launcher and voice-command parser include LeetCode, Gemini, Netlify, Render, Claude, Google Classroom, Google Contacts, Google Cloud Console, Neon, LinkedIn Learning, Coursera, SWAYAM, NPTEL, Google Docs/Sheets/Meet, and other existing destinations. The `linkedln learning` and `swaym` aliases also normalize to their intended sites.

Additional desktop launch aliases include WhatsApp, Microsoft Edge, Microsoft PowerPoint, Microsoft Excel, WPS Office (Docs/Writer, Sheets, Slides, and PDF), Arduino IDE, AutoCAD 2026, Python IDLE for Python 3.14, Picasa 3, Photos, Media Player, Clock, and Recycle Bin. Third-party application launch depends on the app being installed and discoverable through its executable or a supported common install path.

The Windows Settings shortcuts include Airplane mode, Eye comfort/Night light, and Energy saver/Battery saver. These commands **open the corresponding Settings page**; they do not silently toggle those settings. Windows app URI registrations and Settings-page availability can vary by Windows version.

The website and app names are mirrored in the semantic-router tool schema, and the GUI-focus allowlist is separately defined. Being allowlisted for launch does not guarantee that every application supports automated typing or in-app actions; GUI typing/focus is restricted to its own supported target list.
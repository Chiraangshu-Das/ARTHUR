# Arthur Security, Privacy and Permission Policy

This policy applies to the Windows client, FastAPI device agent, Google Workspace adapters, and remote client starters.

## 1. Camera, microphone and screen privacy

- Camera capture may run locally for the active view but it does not produce spontaneous scene narration. Narration and OCR/read-aloud happen after a user request.
- Microphone recording starts only after a voice-command action or explicitly armed wake-word flow. Keep a visible listening/recording state and a stop control.
- Camera frames and screenshots are not sent to Gemini or Cloud Vision as a side effect of routine command transcription. Product/visual search and screen-description upload must be a distinct user-approved action because the frame may contain people or private information.
- API audio uploads are bounded to 20 MB, saved to a temporary file for local Whisper, and removed in a `finally` cleanup path. The transcript is returned to the client; the audio is not passed to Gemini by that endpoint.
- Local memory, face templates, screenshots, voice recordings and Google OAuth tokens are data with different retention needs. Store each only in its intended local directory; do not commit `data/`, `.env`, credentials or tokens.

## 2. Semantic routing and tool execution

- The LLM receives a registered function catalogue, not a Python interpreter, terminal, shell, arbitrary URL launcher or unrestricted file-system tool.
- Function calling is returned as data with automatic execution disabled. The executor chooses from a finite action registry, validates arguments and checks device/provider capability.
- Local parser/pattern and embedding routes must use the same typed tool executor and policy checks as LLM-selected intents.
- General text-only Gemini fallback is subject to consent in the desktop client and confirmation in the API client. Camera/screen bytes do not accompany this fallback.
- Tool responses must distinguish a requested action from an observed result. A keyboard shortcut or provider submission is not proof of email delivery, playback state, meeting attendance or network connectivity.

## 3. Confirmation policy

Require an explicit user review/confirmation step before:

- Sending Gmail messages or WhatsApp messages.
- Creating or modifying Google Calendar events.
- Disabling/enabling a network adapter.
- Sending text to Gemini when a text-only fallback is triggered by an unknown request.
- Executing GUI workflows that paste sensitive text into a known application.
- Other irreversible or externally visible actions added to the tool registry.

Gmail and WhatsApp compose workflows create drafts and stop before sending. The send step must be a separate action. A UI confirmation should show recipients/contacts, subject, complete message, or calendar title/time/timezone in enough detail to review. Never accept a vague “yes” as confirmation for an action whose target or content is not displayed.

## 4. FastAPI network boundary

- Development default: bind `VISIONGUIDE_API_HOST=127.0.0.1`.
- Binding to a non-loopback host requires `VISIONGUIDE_API_TOKEN`; the app fails startup if it is absent.
- Supply the token as `Authorization: Bearer <token>` over HTTP and authenticate WebSocket connections with the first frame `auth:<token>` rather than a URL query parameter.
- Confirmation IDs are high-entropy, one-use, expire after five minutes and are bound to the requesting `device_id`. IDs expire from the bounded in-memory store; only the exact stored intent can be executed after approval.
- Apply firewall restrictions to private networks. Do not expose the device API directly to the public internet. Remote deployment requires TLS/WSS, strong authentication, rate limiting, audit identifiers, request budgets, revocation and per-device authorization.
- `/api/v1/transcribe` limits body size and allowed audio extensions. Add reverse-proxy limits, request timeouts and rate limits in a deployed gateway.

The development bearer token is one shared secret; it is not a production identity or per-user authorization system. The current service does not implement a full device-pairing lifecycle or production audit database.

## 5. OAuth and Google data

- Use the installed-app OAuth flow with the per-feature scope profiles in `visionguide/integrations/google_workspace.py`. Cloud Translation and Natural Language use dedicated OAuth profiles too; Gemini uses `GEMINI_API_KEY` and does not need Gemini OAuth scopes for normal text/image generation.
- Store `credentials/google_oauth_client.json` and every `data/google_tokens/google_*.json` file locally and outside source control. Restrict machine account access and back up neither file to a public repository.
- Request only the scopes needed by enabled workflows. Gmail reading, sending, Contacts, Drive, Classroom, and Cloud scopes can expose private data. Do not select every scope in the Data Access catalogue simply because it is listed; add-on-only, admin, media-capture, deletion, and broad Drive permissions are not needed by this desktop integration.
- The Maps API key and Cloud Vision API key use API-key restrictions. Cloud Translation and Natural Language use OAuth scopes. API enablement, OAuth scope configuration, and API-key restrictions are separate settings and all must match the intended integration.
- Never print access/refresh tokens or full email bodies in debug logs. Responses may include private email content; show and speak only what the user requested.
- Provide a revoke/disconnect workflow for deployed builds; to force a fresh local consent in the current package, revoke the app grant in the Google account and delete the local token file.

## 6. GUI and operating-system controls

- `pygetwindow` identifies active target windows by title keyword; title matching is not identity proof. Verify the window and current field focus before pasting sensitive content.
- `PyAutoGUI.FAILSAFE` remains enabled. Stop a workflow if a window cannot be located, the title changes unexpectedly, or a checkpoint fails.
- Website and application launch use allowlists. Never call `subprocess(..., shell=True)` with user/model text, and do not add a generic “execute code” tool to the semantic registry.
- `netsh` changes a specific adapter only after checking its name and obtaining confirmation; this may interrupt API connectivity.
- Brightness and audio values are validated and bounded. Hardware/driver results are surfaced without claiming every external display supports brightness control.
- System-wide hand gestures are explicitly armed. They move the pointer, click keys in the unified air virtual keyboard, scroll and switch tabs. Do not enable them while entering credentials, editing sensitive records or approving transactions. The top-left PyAutoGUI failsafe remains active. The keyboard overlay attempts to use Windows `WS_EX_NOACTIVATE` so key clicks do not take focus away from the target app; test this with each target program.

## 7. Face and ISL data

### Face data

Face memory must be opt-in and limited to people who have consented to be enrolled. OpenCV LBPH is retained and optional DeepFace embeddings can improve local enrolled-user comparison; if models conflict, return Unknown rather than forcing a personalized match.

Samples and embedding vectors stay locally under `data/faces/` and must not be included in project ZIPs. Use the local enrolled-person workflow; do not identify a stranger from a face or run public-web reverse face identification.

Visual Web Detection is a separate public-page/similar-image search and its matches are not identity verification. Visible text on a badge can be read when explicitly requested, but it is separate from face identity.

### Indian Sign Language data

Arthur's current ISL recognition pipeline uses a Torchvision Swin3D-S video classifier with 76 isolated-sign classes.

- The recognizer processes a sequence of 32 video frames rather than classifying a single still image.
- Inference is performed locally using the checkpoint at `models/isl/swin3d_s/ISL_best_model.pt`.
- The current pipeline supports isolated-sign recognition only. It does not provide continuous sentence-level ISL translation or general-purpose sign-language conversation.
- MediaPipe Holistic and the previous TensorFlow LSTM architecture are not the active Swin3D ISL inference pipeline. MediaPipe remains relevant to gesture-control functionality.
- ISL samples, trained checkpoints, class labels and sign-recognition outputs may contain biometric and linguistic information. Protect them accordingly.

Use signer consent, dataset/model manifests, provenance and explicit retention policies. Do not include private signer samples or trained model assets in public project archives unless their licences and consent conditions permit redistribution.

ISL validation must be separate from other sign languages and should evaluate unseen signers, natural sequence context, signing speed, camera position and lighting. A classifier prediction is not guaranteed to be correct and should not be presented as a definitive translation without appropriate context.

## 8. Logs, retention and reporting

Log command IDs, route/action names, timing and success/failure categories—not credentials, full email bodies, raw audio, camera frames or personal notes.

The timer service is in-process and the current API has no durable audit database; do not promise persistent delivery after a process exit.

The mobile starter does not persist API credentials in secure device storage yet; use it as a development client until a platform-native secure storage and pairing lifecycle is added.

## 9. Location, navigation and cloud API budget guardrails

- Live navigation uses Windows Location services only after the user opts in. Enable/allow location in Windows Settings; live position is used for route progress and is not stored as a user profile. Disable navigation to stop polling.
- Maps Platform calls use `GOOGLE_MAPS_API_KEY`; optional Cloud Vision uses a separately restricted `GOOGLE_CLOUD_API_KEY`/`GOOGLE_VISION_API_KEY`; Cloud Translation and Natural Language use OAuth profile tokens. The application maintains per-device daily counters and local cache for Maps data, but this is not a replacement for project-level quotas, API restrictions, Cloud Billing budget alerts or monitoring other apps that share the billing account.
- Place names/coordinates and derived weather/air-quality/pollen/time-zone data may be cached locally. User-supplied text for translation/natural-language analysis is not cached by those adapters, but is sent to Google when the request is executed. Wi-Fi access-point identifiers are never collected locally by this code; any provided identifiers are sent only after explicit consent.
- Traffic-aware Routes and two-wheeler routing can use higher-priced SKUs. Check current country-specific prices/SKUs before enabling them; a Google Cloud key does not guarantee free usage.
- A route result, GPS poll, or off-route trigger can fail due to missing permission, unavailable position, poor coverage, quota, billing or network issues. Arthur must state these failures clearly and is not a certified navigation or mobility-safety aid.
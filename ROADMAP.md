# Arthur Implementation Roadmap

This roadmap describes the engineering state of the integrated source and the next release gates. The core desktop integrations and API client/server path are present in source; the remaining work is chiefly field validation, robustness, deployment hardening, and completing the sentence-level ISL model path.

## Track 1 — Semantic command router

**Implemented in source:** Whisper transcript input, Gemini function calling through registered typed tool declarations, deterministic parser/pattern fallback, SentenceTransformers semantic similarity fallback, typed `RoutedCommand`, and text-only Gemini fallback with a consent gate in the desktop client or a confirmation path in the API.

**Next engineering gates:** Grow a paraphrase/argument test corpus; test dates, time zones, named contacts, multi-clause commands and low-confidence utterances; add clear clarification turns for arguments the model cannot safely infer; record route source and final execution status without logging private content.

## Track 2 — Windows, browser and OS controls

**Implemented in source:** YouTube/browser shortcuts via PyAutoGUI/PyGetWindow; screen brightness via `screen-brightness-control`; Windows master audio/mute via Pycaw; named network adapter status/state through `netsh`; and UI/API confirmation for adapter changes.

**Next engineering gates:** Test on the target laptop and external monitors; validate supported Windows builds and permission failures; confirm playback focus and shortcut results; add post-action value checks where the driver exposes them; evaluate adapter names on non-English Windows installations. A play/pause keyboard toggle must not be described as a guaranteed playback-state read.

## Track 3 — Desktop workflow execution

**Implemented in source:** Allowlisted window activation; paste/keyboard primitives; Gmail draft creation through a GUI workflow; Word document creation with unsaved review; WhatsApp Web draft entry; explicit separate send commands; and GUI target confirmation prompts.

**Next engineering gates:** Verify the active target window and form-field focus after every step; add execution checkpoints with rollback/retry boundaries; improve screen/OCR verification across browser versions and accessibility settings; and test that interrupted workflows never continue in a newly focused window. Keep sends as a separately confirmed terminal action.

## Track 4 — Gmail and Google Calendar

**Implemented in source:** OAuth 2.0 desktop flow; Gmail unread/search/read/API draft/send adapters; Calendar upcoming/search/create adapters; input bounds; date-time and time-zone validation; FastAPI endpoints; and confirmations for sends and Calendar writes.

**Next engineering gates:** Complete account-based integration tests with a dedicated test mailbox/calendar; test OAuth revocation, refresh and changed scopes; test quotas and transient network errors; refine attendees/recurrence/time-zone support without weakening confirmation; provide a clear disconnect/revoke control; and evaluate token protection for packaged deployments.

## Track 5 — Timers and reminders

**Implemented in source:** Bounded, cancellable background countdown timers, monotonic timekeeping, desktop async-queue notifications, REST timer endpoints and WebSocket expiry events.

**Next engineering gates:** Stress-test concurrent timers, verify alert delivery under minimized/background conditions, document shutdown behavior, and add durable scheduler storage if reminders must survive a reboot. Never describe an in-process countdown as a persistent calendar event.

## Track 6 — FastAPI, mobile and wearable clients

**Implemented in source:** FastAPI JSON command endpoint; one-use device-bound confirmation tokens; local Whisper upload endpoint; timers and Workspace endpoints; authenticated WebSocket notification route; Python client; and Flutter command client starter with speech, recording/upload, confirmation and event UI.

**Next engineering gates:** Generate and build the Android/iOS platform shells using the Flutter SDK; test physical-device microphone permissions and local network connectivity; add a formal device pairing/capability registry; add rate limits and audit IDs; configure TLS for remote use; implement client-native camera and wearable sensors with consent; and test reconnect, token expiry and offline conditions. Validate Android and iOS builds separately if both platforms are intended for release. The API executes on its host device, not remotely on a phone's operating system.

## Track 7 — Air gestures

**Implemented in source:** MediaPipe hand landmarks, index-fingertip system pointer movement, pinch-click debounce/cooldown, right-edge vertical scrolling, horizontal browser-tab swipes, pointer smoothing, two-point calibration, PyAutoGUI fail-safe, explicit enable/disable, and a unified system-wide air virtual keyboard controllable by mouse and the gesture pointer. Voice literal typing pastes into the currently focused target after confirmation.

**Next engineering gates:** Test camera placement, hand sizes, lighting and fatigue; tune gesture thresholds on the target webcam; verify loss-of-hand and emergency-disable behaviour. Validate focus-preservation on Windows 10/11 and across browsers/custom widgets; generic Python GUI automation cannot guarantee every field's focus. The legacy prompt-only keyboard module remains in the source tree for compatibility but is no longer instantiated by the main UI.

## Track 8 — ISL

**Implemented in source:** An isolated-sign Indian Sign Language training/inference path using Torchvision Swin3D-S, with a 76-class classifier and a local checkpoint at `models/isl/swin3d_s/ISL_best_model.pt`. Inference uses a 32-frame video clip. The current architecture and documentation distinguish isolated-sign recognition from continuous sentence translation.

**Next engineering gates:** Build or integrate a licensed continuous-sign sequence model; include non-manual cues and temporal context; create signer-consented evaluation splits; report held-out-signer metrics and confidence/reject states; and build a separate ISL text-to-sign output pipeline. The current isolated-label classifier should not be presented as continuous sentence translation. Independent classifier evaluation does not, by itself, establish live-camera integration or generalization to unseen signers.

## Track 9 — Google Cloud assistive services, face profiles and navigation

**Implemented in source:** Cached and application-capped Google Geocoding, Weather, Routes and Cloud Vision Web Detection REST adapters; local product/image research workflow with explicit upload approval; persistent per-profile preferences and bounded action/result history; LBPH recognition with optional DeepFace embedding fusion; Windows location polling, spoken route steps and best-effort off-route rerouting.

**Next engineering gates:** Validate each enabled Google API/key restriction and current SKU pricing; test budget alerts against the user's actual project/account consumption; verify camera upload consent flow and cache privacy; evaluate face recognition with consenting enrolled users and held-out lighting/pose samples; test location permission, GPS accuracy, rerouting and maneuver timing in real Windows field trials. These modules are prototypes and must not be treated as certified identity or mobility safety systems.

## Release gates

1. Automated tests and Python compilation pass.
2. Provider tests run against an isolated Gmail/Calendar test account with explicit consent.
3. Windows system controls and GUI workflows are exercised on the actual supported laptop/display/browser combination.
4. Mobile client builds are generated and exercised on physical devices for each platform included in the release.
5. Security checks cover API binding, authentication, confirmation replay, OAuth token storage, logging and file permissions.
6. Release notes distinguish automated checks from provider/device testing and make no unsupported mobility-safety or delivery claims.
# Arthur Spoken Command Catalogue

Commands are natural-language intents, not magic exact strings. Gemini function calling routes common paraphrases to the same typed tool when configured. Local parsing/patterns and SentenceTransformers similarity provide fallback routing. If an argument cannot be safely inferred, ask for clarification rather than guessing.

A recognized command is not proof that the requested action succeeded. Arthur must report execution results accurately and distinguish a completed action from an attempted action, an unavailable capability or a provider error.

## 1. Websites, search and applications

- “Open YouTube.” / “Take me to YouTube.” / “Put YouTube on screen.”
- “Open Gmail.” / “Take me to Google Drive.” / “Open WhatsApp Web.”
- “Search YouTube for binary search trees.”
- “Search the web for the Python datetime documentation.”
- “Open Calculator.” / “Open Notepad.” / “Open Settings.” / “Open VS Code.”
- “Open the Documents folder.” / “Open my latest PDF.”

Website and app targets use allowlists; arbitrary transcribed strings are never passed to a shell. Available app names depend on the installed Windows application and PATH configuration.

If a file reference such as “my latest PDF” matches multiple possible files or cannot be resolved reliably, Arthur should ask the user to select the intended file rather than opening an arbitrary result.

## 2. Browser media controls

- “Pause the YouTube video.” / “Play the video.” / “Stop the video.”
- “Skip ahead 30 seconds.” / “Go back ten seconds.”
- “Play the next video.” / “Go to the previous video.”

The playback adapter activates a matching browser window and sends YouTube keyboard shortcuts. `K` toggles playback and stop maps to pause; player focus matters. Skip durations are approximate in ten-second increments.

These are keyboard-shortcut actions, not guaranteed playback-state detection. Arthur should not claim that playback changed unless the action can be verified.

## 3. Display, audio and network

- “Set brightness to 45 percent.” / “Make the screen brighter.” / “Dim the display.”
- “What is the current brightness?”
- “Set volume to 25 percent.” / “Turn the volume up.” / “Make it quieter.”
- “What is the system volume?” / “Mute system audio.” / “Unmute sound.”
- “Show Wi-Fi adapter status.” / “Turn the Wi-Fi adapter off.” / “Enable the Wi-Fi adapter named Wi-Fi.”

Brightness and volume percentages are bounded. Wi-Fi changes identify the requested adapter and require a user confirmation; this may interrupt the network and may require elevated Windows permissions.

## 4. Timers and reminders

- “Set a timer for five minutes.”
- “Start a 30-second countdown.”
- “Remind me in two hours to check the build.”
- “List my active timers.”
- “Cancel timer 2.”

Countdowns run in background threads and return a timer ID. These timers are in-process; they do not persist after app/server shutdown.

A timer reminder is not automatically a persistent Calendar event or a scheduled notification that survives an application restart. Calendar events are a separate integration.

## 5. Camera and local vision

- “What is in front of me?” / “Describe the camera view.”
- “Is there a chair?” / “Can you see a television?”
- “Read the text on this page.” / “Scan this label.”
- “Take a snapshot.”
- “Start the camera.” / “Stop the camera.”
- “Enable proactive safety alerts.” / “Disable safety alerts.”

The camera remains silent until asked. A detected object may be missed; not detecting an object is not proof that it is absent.

Camera upload to Gemini requires a separate prompt/consent gate. Distance and hazard analysis are not certified mobility guidance. Proactive safety alerts should not be treated as a replacement for environmental awareness or mobility assistance.

## 6. Screen, OCR and documents

- “Take a screenshot.”
- “Read the text on my screen.” (local OCR)
- “Explain what is on my screen.” (asks before screenshot upload)
- “Open a document.”
- “Search this document for recursion.”
- “Find the word stack on the last scanned page.”
- “Open my latest PDF.”

Screenshots are saved locally unless the user separately requests AI screen description and confirms upload. Document operations may open a file picker so the user can choose a source explicitly.

Local OCR and AI screen description are separate operations. AI screen description requires its own upload approval; a request to read screen text locally does not authorize sending the screenshot to an external service.

## 7. Gmail — OAuth API and GUI workflow

After configuring Google Cloud OAuth and authenticating:

- “Read my unread emails.” / “Check unread Gmail.”
- “Search Gmail for messages from my professor this month.”
- “Read the email with subject about the lab report.” (choose/read a specific result as supported by current client context)
- “Draft an email to student@example.com with subject Project update about the latest build.”
- “Prepare a Gmail draft to team@example.com with subject Meeting notes; say that the test run passed and ask for review.”
- “Send email.”

Gmail API operations support unread metadata/body, inbox search, reading by message ID, API draft creation and explicit draft send.

The desktop GUI workflow opens Gmail, uses its compose shortcut, pastes the recipient, subject and Gemini-generated body, and leaves the draft open for review. To send from the active GUI draft, the user must separately say “send email” and confirm the displayed recipient/subject/body. Enable Gmail keyboard shortcuts for GUI compose.

Never infer an email address from a person's name when no uniquely known address is supplied. Review the full message before sending. A send shortcut is not proof of delivery; verify Gmail's Sent state.

## 8. Google Calendar — OAuth API

- “What meetings do I have this week?”
- “Show upcoming calendar events.”
- “Search calendar for the design review.”
- “Schedule a meeting called project review tomorrow at 10 AM for 30 minutes.”

The router uses current date/time and `VISIONGUIDE_TIMEZONE`. The app must confirm title, start, end and timezone before creating an event.

If the time, date or duration is unclear, clarify before writing. Current adapter supports upcoming event listing, metadata search and single-event creation; attendees and recurrence are not part of the current event form.

## 9. Word, WhatsApp Web and window typing

- “Open Word and write this draft: [dictated text].”
- “Paste this text into Notepad: [dictated text].”
- “Prepare a WhatsApp Web message to Alex: [message].”
- “Send WhatsApp message.”
- “Type this text in the Gmail window: [text].”

Word documents remain unsaved. WhatsApp drafts remain unsent. Text paste targets are allowlisted.

Before sending a WhatsApp message, confirm the visible chat title and complete message body; before email send, confirm recipient, subject and body. A GUI workflow stops on a missing window or error.

GUI typing depends on the intended window and input field being active. Arthur should not assume that text was entered into the correct application merely because a paste operation was attempted.

## 10. Unified system-wide air virtual keyboard and hand gestures

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

## 11. Weather, routes and live navigation

- “Tell me today's weather in Kolkata.”
- “Get directions from Salt Lake to Howrah by motorcycle.”
- “Navigate to Howrah.” (asks permission to use live Windows location and start turn-by-turn guidance when configured)
- “Stop navigation.”

Weather returns provider-sourced current conditions. Routes support driving, two-wheeler where enabled, walking, cycling and transit where available; traffic-aware ETA is requested for driving/two-wheeler routes.

Live navigation polls location, speaks maneuver updates and recalculates after repeated off-route readings. It requires Windows location permission, enabled Google APIs and a valid key.

This is best-effort prototype guidance, not a certified mobility/navigation safety service. Location availability, route quality, provider responses and GPS accuracy can affect guidance.

## 12. Product/object lookup and public visual search

- “Tell me about this air fryer.”
- “What product is this?”
- “Search this object online.”

Arthur asks for consent before uploading the compressed camera frame to Gemini and/or Google Cloud Vision. It can combine OCR, visual inference, public page matches and similar-image leads, with uncertainty called out.

A visual match never proves a person's identity or an exact model number. Similar-image results should be treated as research leads, not definitive identification.

## 13. ISL

- “Start ISL isolated-sign recognition.”
- “Stop ISL recognition.”

The current runtime path is isolated-label ISL classification. Continuous sentence-level translation and text-to-sign have separate model, output and evaluation requirements documented in `CONTINUOUS_ISL.md`.

The current classifier recognizes only its supported isolated-sign vocabulary. It does not provide continuous sentence-level translation or general sign-language conversation.

## 14. API / mobile examples

Once `python main.py --serve-api` is running:

- Python: `python clients/python/visionguide_client.py "open YouTube" --server http://127.0.0.1:8000`
- Flutter: connect to the server URL, enter its bearer token when enabled, and use text, short speech, or recorded-audio Whisper transcription.
- High-impact API commands return a confirmation ID and a preview. The client must post that exact token and device ID to `/api/v1/confirm`; IDs expire after five minutes and can be used once.

The FastAPI service executes device operations on the machine hosting the service. A connected Flutter client does not automatically gain direct control over the phone's operating system, camera, cursor or network adapter.

## 15. Additional Google APIs (OAuth or Maps key as noted)

The following examples use the installed-app OAuth flow for Workspace/Cloud services and `GOOGLE_MAPS_API_KEY` for Maps Platform lookups. The first use of a feature may open a separate consent flow for that feature's narrow token profile.

### Maps Platform (Maps API key)

- “Find nearby pharmacies in Kolkata.” / “Search cafes near Park Street, Kolkata.”
- “Tell me the air quality in Kolkata.”
- “Check the pollen forecast in Kolkata.”
- “What is the time zone in Tokyo?”

Road snapping is exposed to typed tool/API clients because it requires a JSON path of latitude/longitude pairs.

Geolocation is also an API-level operation: it needs caller-supplied Wi-Fi access-point data and an explicit consent flag; Arthur does not collect nearby Wi-Fi MAC addresses automatically.

Maps JavaScript, Embed, mobile SDK and Map Tiles restrictions do not add an in-app Python renderer.

### Google Cloud language services (OAuth)

- “Translate hello world to Hindi.”
- “Analyze the sentiment of this text: The product is excellent and useful.”
- “Find entities in this text: Ada Lovelace worked in London.”
- “Analyze the grammar of this sentence: The quick fox jumps.”
- “Classify this text: [provide a paragraph of at least 20 characters].”

Text is sent to Google Cloud for the explicitly requested operation and is not cached by the integration. Translation and Natural Language APIs must be enabled in the same Cloud project as the OAuth client.

### Workspace and productivity (OAuth)

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

## General AI fallback

- “Explain binary search trees with an example.”
- “Help me draft a project report outline.”
- “What is the difference between threads and async tasks?”

The desktop asks before sending unmatched transcript text to Gemini. The API's text-only fallback shows a confirmation screen.

General Gemini Q&A is text-only unless an image-specific action was explicitly requested and confirmed separately.

## 16. Extended website launcher allowlist

The `open_website` tool and local voice parser support Google Cloud Console, Neon DB, Google Classroom, Google Contacts/Contacts, LeetCode, LinkedIn Learning, Coursera, SWAYAM and NPTEL. Common typo/voice aliases `linkedln learning` and `swaym` are normalized to LinkedIn Learning and SWAYAM.

Opening one of these sites is browser navigation only; it does not automate a login or bypass the site provider's permissions.
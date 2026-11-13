# ARTHUR — Quick Start Voice Commands

Commands are examples, not exact required scripts. ARTHUR normalizes common wake-word prefixes such as “Hey Arthur” and “Arthur”. Some features require Windows integrations, external API access, or downloaded model files.

## Browser and desktop applications

- “Open YouTube” / “Arthur, open YouTube”
- “Search YouTube for Python tutorials”
- “Search Google for binary trees”
- “Open Word” / “Open Excel” / “Open PowerPoint”
- “Open Calculator” / “Open Notepad” / “Open File Explorer”
- “Close Excel” / “Close Word” / “Close Chrome” — ARTHUR asks before sending a normal close request. Save prompts are still handled by the application.

Word and Excel must be installed as desktop applications. If ARTHUR cannot locate one, use the Windows Start menu to confirm it is installed and repair Microsoft 365/Office if necessary. Store/web-only editions may not expose a local executable.

## YouTube search and video selection

- “Search YouTube for Taylor Swift songs” opens the results and stores that search for follow-up commands during the current ARTHUR session.
- “Play the first video” / “Play the second video” / “Open result number 3” selects that numbered result from ARTHUR’s most recent YouTube search.
- “Play a video” selects the first result when a recent ARTHUR YouTube search exists.
- “Pause it” / “Play it” / “Skip forward 30 seconds” controls the current browser video using YouTube keyboard shortcuts.

Result selection retrieves YouTube’s public search-result page and opens the selected watch page with autoplay requested. YouTube or browser autoplay policies may still require a click. The numbered selection applies to the most recent search issued by ARTHUR in the current session; it does not use a search performed manually in another browser tab or a search from before ARTHUR was restarted.

## Volume, brightness and media

- “Reduce system volume” / “Reduce volume by 20 percent”
- “Increase volume” / “Set volume to 35 percent” / “What is the current volume?”
- “Mute audio” / “Unmute audio”
- “Dim the screen” / “Set brightness to 60 percent”
- “Pause the video” / “Skip forward 30 seconds”

Volume control requires the Windows audio endpoint and the `pycaw` / `comtypes` integrations. Brightness control depends on the laptop display exposing a controllable brightness endpoint.

## Typing and calculations are different

- “Type exactly 2+2” means paste the literal characters `2+2` into the window that was foreground when you issued the command. Arthur asks for confirmation, restores that same window, and pastes immediately; there is no four-second countdown. Use wake-word conversation while the intended destination is in the foreground. If the Arthur window itself was foreground (for example, after clicking Push to Talk), use an explicit target such as “Type hello in Microsoft Word”.
- “Calculate 2+2” computes the result locally and displays/speaks `4`; it does not type into another app.
- “Open Calculator and calculate 2+2” launches Calculator and sends the calculation through ARTHUR's local arithmetic path.

The command transcript can also appear in ARTHUR's output panel; that is the transcript/result log, not proof that text was pasted into another app.

## Camera, scene description and OCR

- “Turn on camera” / “Turn off camera”
- “Describe the scene” / “What is in front of me?” / “Is there a television?”
- “Read the text on this page” / “Scan the page”
- “Read the text on my screen” — local desktop OCR
- “Explain what is on my screen” — screenshot sharing requires a separate confirmation

The camera and YOLO model must both start successfully. The provided ZIP currently contains a Git LFS pointer in place of `models/yolo26n.pt`; the full model weights are required before camera-based features can operate. Check the output panel for the exact error.

### Use a phone camera

On Android, a local IP-camera app can expose an MJPEG stream. Start the stream on the phone, keep the phone and laptop on the same Wi-Fi network, then use the exact stream URL shown by the app. A common IP Webcam endpoint is:

```powershell
python main.py --camera "http://PHONE_IP:8080/video"
```

Or set this in `.env`:

```env
VISIONGUIDE_CAMERA_SOURCE=http://PHONE_IP:8080/video
```

Then run `python main.py`. Use `VISIONGUIDE_CAMERA_SOURCE=0` for the laptop's default webcam. Do not expose the phone stream port to the public internet. A better camera helps only when the page is well lit, in focus, held steady, and fills much of the image.

## Hand / finger tracking and virtual keyboard

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

## Local memory and face enrollment

- “Remember that I left my keys in the bag” — ARTHUR asks before saving a local SQLite note.
- “Where did I leave my keys?” / “What do you remember about my keys?” — searches local notes.
- “Enroll my face” / “Remember my face” — asks for a name and consent before locally collecting face samples.
- “Enable face recognition” / “Disable face recognition”
- “Arthur, I prefer you to call me Chiraangshu” — saves the preferred form of address against the active enrolled face profile.

After enrollment, the just-enrolled profile becomes active for the current session. A preferred name is loaded immediately when the user sets it and is applied to short spoken assistant replies (including replacing direct-address “sir” salutations). The preference is stored locally in `data/action_history.sqlite3`. After a restart, enable face recognition so ARTHUR can identify the enrolled profile and reload its preference. If only one face profile is enrolled, a preference command can target it without asking you to choose; with multiple profiles, ARTHUR identifies the active face or asks which profile to use.

Face recognition requires `opencv-contrib-python`, a working camera/model pipeline, and explicit consent. Face samples and preferences are stored locally; they are not automatically sent to Groq. Enrolling a face does not happen silently.

## Navigation

- “Get directions from Salt Lake to Howrah”
- “Get directions from Salt Lake to Howrah by motorcycle”
- “Stop navigation”

ARTHUR asks whether to start live guidance. Live guidance needs Windows Location permission, a working location provider, a valid `GOOGLE_MAPS_API_KEY`, Routes API enabled, Geocoding API where needed, and Google Maps Platform billing/quota configured. Choose No to live guidance to calculate/open a static route from the specified origin. When the Routes API is unavailable but the origin and destination are known, ARTHUR attempts to open Google Maps directions in the browser instead; that fallback does not provide an ARTHUR ETA or live spoken turns.

## Indian Sign Language

- “Start sign language translation” / “Start ISL translation”
- “Stop sign language translation”

This build recognizes a limited set of isolated ISL signs; it does **not** translate continuous signed sentences. It requires the full Swin3D-S checkpoint at `models/isl/swin3d_s/ISL_best_model.pt`, the matching 76-class labels (or training dataset used to reconstruct them), and the PyTorch/Torchvision dependencies in `requirements-signs.txt`. The uploaded ZIP contains only an LFS pointer for the checkpoint, not the approximately 228 MB trained weights.

## AI and Groq

Set `GROQ_API_KEY` to your GroqCloud API key. The default text/function-calling model is `openai/gpt-oss-120b`; the default vision model is `qwen/qwen3.8-27b`. Both model availability and free-tier rate limits are account-dependent; check the GroqCloud Models and Limits pages. Groq is separate from `GOOGLE_MAPS_API_KEY`. Do not send credentials, private documents, or confidential camera images to any hosted model.

## Listening

- Press **Listening: OFF/ON** to arm/disarm the wake-word listener.
- Say the configured wake phrase, then speak a command.
- Push-to-talk records for up to 10 seconds.
- Voice confirmations also listen for up to 10 seconds.
- Silence for 30 seconds returns ARTHUR to its waiting/wake state. “Go to sleep”, “Stop listening”, or “Goodbye” ends the current conversation.


## Targeted typing and browser tabs

- `Type hello` — confirm; Arthur restores and types into the window that was in the foreground when you spoke. No four-second countdown.
- `Type hello in Microsoft Word` — confirm; Arthur activates Word and inserts at the current selection/cursor, creating a blank document only when none is open.
- `Type Taylor Swift in YouTube search box` — confirm; Arthur focuses the YouTube search field and pastes without submitting the search.
- `Type example.com in Chrome address bar` — confirm; Arthur focuses the browser address bar and pastes without navigating.
- `Close YouTube` / `Close the Gmail tab` — confirm; Arthur closes the matching currently active browser tab with Ctrl+W. It does not terminate the browser process. Background tabs are not selected automatically.

Direct Word insertion requires `pywin32`; install it through the updated `requirements-integrations.txt`.

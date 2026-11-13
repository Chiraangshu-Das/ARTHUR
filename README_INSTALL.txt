ARTHUR — Acoustic Echo Cancellation and Voice Confirmation Fix
================================================================

This is a focused overlay for the previous ARTHUR speech-interruption and
natural-rendering patch. It replaces the earlier wake-phrase-only echo guard
with an actual speaker-loopback + microphone acoustic echo-cancellation path.
It also makes the yes/no confirmation path strictly half-duplex.

WHAT CHANGED
------------

1. During active SAPI playback, Whisper receives only Echoff's echo-reduced
   microphone frames, and only after Echoff reports its echo path ready.
2. A raw microphone recorder is never opened while ARTHUR is actively speaking.
3. When the user pauses speech, SAPI is purged first. ARTHUR then releases the
   AEC capture and opens a raw microphone window while the speaker is silent.
   This supports saying "continue" or a new "Arthur, ..." command while paused.
4. Resuming speech starts a fresh AEC stream alongside the resumed SAPI output.
5. Normal conversation recording waits for SAPI to finish, then applies a
   configurable output-drain interval before opening a microphone capture.
6. Yes/no confirmation stops the previous response, speaks a short prompt,
   checks that playback has finished, waits for the output endpoint to drain,
   plays a brief tone, and only then records the answer. The full action preview
   remains visible in the ARTHUR output panel. One retry is provided.
7. The previous natural-language speech renderer remains in place.

INSTALLATION
------------

1. Close ARTHUR completely.
2. Extract this ZIP into the ARTHUR project root (the folder containing main.py).
3. Run from PowerShell in that root:

   powershell -ExecutionPolicy Bypass -File .\arthur_aec_audio_fix\install_patch.ps1

4. Activate the existing virtual environment and install the AEC package:

   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements-aec.txt

5. Check that Windows audio endpoints are visible:

   python -m echoff devices

6. Validate the code and tests:

   python -m compileall -q visionguide tests
   python -m pytest -q

7. Launch:

   python main.py

The installer backs up every replaced file with a timestamped
.before_aec_audio_fix_*.bak suffix. It does not overwrite .env, .venv, data,
models, credentials, or the main requirements manifests. It adds only the
separate requirements-aec.txt file; install it explicitly as shown above.

DEVICE CONFIGURATION
--------------------

Echoff uses the default Windows WASAPI render endpoint as its speaker reference
and the default Windows microphone. To inspect device indexes:

   python -m echoff devices

If the defaults are wrong, add the selected device index or exact device name to
your existing .env (do not replace that file):

   VISIONGUIDE_AEC_REFERENCE_DEVICE=0
   VISIONGUIDE_AEC_MICROPHONE_DEVICE=1
   VISIONGUIDE_AEC_STREAM_DELAY_MS=50
   VISIONGUIDE_AEC_WARMUP_SECONDS=7.5
   VISIONGUIDE_TTS_MIC_GUARD_SECONDS=1.35

Replace the example indexes with those shown on your laptop. The reference is
the playback/render device; the microphone setting is the physical mic that
should receive your voice.

SAFE FALLBACK
-------------

If Echoff is missing, cannot open the selected devices, or never produces a
paired stream, ARTHUR falls back to half-duplex operation. It will not send raw
microphone audio to Whisper during active TTS playback. During a spoken response,
use the Pause speech button or press Escape while the ARTHUR window is focused.
Once paused, say "continue" or "Arthur, <your new command>". Voice barge-in during
active playback is disabled until the AEC stream is available and its readiness
gate has passed.

HARDWARE TEST
-------------

Run the official raw-versus-AEC capture probe before judging barge-in quality:

   python -m echoff record --duration 20

While it runs, play continuous speech through the same output device for at least
10 seconds, then speak briefly yourself during a separate part of the capture.
Listen to microphone_raw.wav and microphone_aec.wav in the output folder. Speaker
playback should be quieter in microphone_aec.wav while your own speech remains
intelligible. These recordings may contain private room speech and computer audio;
do not upload or share the WAV files. Share only the CLI diagnostic summary if
troubleshooting is needed.

MANUAL ACCEPTANCE
-----------------

A. Enable wake-word listening and say the configured wake phrase.
B. Ask ARTHUR for a long explanation. During playback, say:
      "Arthur, stop speaking."
   Expected: with AEC readiness active, playback pauses and the remainder is kept.
C. While paused, say:
      "Continue."
   Expected: playback resumes. The AEC stream is recreated alongside resumed SAPI.
D. Repeat, but while paused say:
      "Arthur, what is 25 multiplied by 48?"
   Expected: the old response is discarded and the new request is routed.
E. Trigger an action that requires confirmation. Wait for ARTHUR's short prompt
   and tone, then say "yes" or "no".
   Expected: ARTHUR transcribes the answer only after its own output has stopped.
F. Repeat with the AEC package disabled/unavailable. Expected: no raw microphone
   capture while TTS is playing; use Escape/Pause as the interruption fallback.

VALIDATION STATUS
-----------------

The source used to build this patch passed:
   - 203 tests passed
   - 20 subtests passed
   - 4 existing FastAPI lifecycle deprecation warnings

Automated tests do not validate the user's actual Windows audio-device selection,
room acoustics, WASAPI loopback availability, or Whisper's recognition quality.
Run the hardware probe and the manual acceptance tests on the target laptop.

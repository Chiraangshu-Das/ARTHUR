# ARTHUR — Confirmation Audio Reliability Patch

This is a focused patch for the voice-confirmation failure where ARTHUR reports that it could not transcribe a clear yes/no answer after two attempts.

## What changes

- Confirmation capture explicitly resolves and validates the selected microphone. By default it uses the current Windows default input. It can be pinned with `VISIONGUIDE_CONFIRMATION_MIC_DEVICE` in `.env` using a device index or an unambiguous device-name fragment.
- The selected device, input RMS/peak levels, and Whisper transcript are printed to the local terminal. The recording is not saved.
- A digitally silent input stream is detected before transcription. A missing, invalid, or silent microphone does not cause a switch to an arbitrary device; the confirmation remains unaccepted.
- Confirmation Whisper decoding uses deterministic settings (`temperature=0`) and does not condition the answer on previous text.
- The answer parser accepts clear forms such as `Arthur, yes`, `Yes, go ahead`, `The answer is yes`, `I said no`, and `Absolutely not`, while ambiguous phrases such as `I think yes` remain unconfirmed.
- A microphone/PortAudio error on the first attempt is recorded and the existing single retry is still attempted. Actions remain fail-closed: no clear yes means no action.
- Existing half-duplex protection is preserved: ARTHUR stops speech, waits for SAPI/output drain, closes Echoff/AEC, plays the cue, and only then opens the raw microphone.

No new Python dependencies are introduced. The patch does not change regular voice-command capture behaviour.

## Install

1. Extract this ZIP into the ARTHUR project root, the folder that contains `main.py` and `visionguide\`.
2. Open PowerShell in that project root and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\arthur_confirmation_reliability_patch\install_patch.ps1
```

The installer backs up every file it replaces into `backups\confirmation_reliability_<timestamp>`. It does not overwrite `.env`.

## Microphone setting for the tested laptop

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

## Validate and run

Activate the project virtual environment, then run the targeted regression tests:

```powershell
python -m pytest -q tests\test_confirmation_audio.py tests\test_speech_interruptions.py tests\test_assistant_state_helpers.py
```

Start ARTHUR normally:

```powershell
python main.py
```

When a protected action asks for confirmation, wait for the tone and say a short, clear `yes` or `no`. The console should show the selected input device, measured input levels, and the transcription. If the levels are effectively zero or the device cannot open, ARTHUR reports the capture error, retries once, and cancels the action if it still cannot obtain a clear answer.

## Validation performed while preparing this patch

- `python -m compileall -q visionguide tests` — passed.
- Non-timer suite — 205 passed, 4 existing FastAPI deprecation warnings, 38 subtests passed.
- Timer suite, run separately — 6 passed.
- Focused confirmation suite — 28 passed, 33 subtests passed.

The full test suite was validated in two groups because a combined run intermittently stalled in an existing timer test in this Linux validation environment; that timer test suite passed separately. This environment cannot validate the actual Windows microphone, Realtek driver, SAPI playback, or Echoff device timing. After installation, the first live confirmation on the laptop is the required hardware check.

# ARTHUR AEC audio and confirmation guide

## Why this patch is different

The earlier interruption patch opened short Whisper microphone windows while
SAPI was speaking and relied on the word "Arthur" as a filter. That is not echo
cancellation. This patch uses Echoff's separate WASAPI speaker-loopback reference
and physical microphone stream, aligned before WebRTC acoustic echo cancellation.

## Important behaviour

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

## Optional .env settings

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

## Hardware diagnostic

```powershell
python -m echoff devices
python -m echoff record --duration 20
```

During the recording, play sound through the same output endpoint and speak into
the microphone. Compare `microphone_raw.wav` with `microphone_aec.wav`. The AEC
track should reduce the speaker playback while preserving your voice. The
recordings can contain private audio; do not share the WAV files.

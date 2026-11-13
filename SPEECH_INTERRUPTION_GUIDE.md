# ARTHUR speech interruption and natural rendering

## Voice commands

During spoken output in wake-word conversation mode:

- **Pause:** “Arthur, stop” / “Arthur, stop speaking” / “Arthur, pause.”
- **Resume:** “Continue” / “Okay, now continue” while paused; or “Arthur, continue.”
- **Discard:** “Arthur, cancel that response.”
- **New request:** “Arthur, [new question or command].”

During playback, the address phrase is required to reduce the chance that ARTHUR
hears its own TTS as an instruction. The listener uses short Whisper capture
windows; response time includes that window and transcription time. This patch
does not provide true acoustic echo cancellation.

## Speech rendering

The output panel receives the original response. Only the TTS input is converted
from common Markdown/LaTeX notation to plain language. The renderer supports common
fractions, powers, roots, integrals, inequalities and common math functions. It
is deliberately not a full LaTeX engine. Fenced code blocks are referred to as
being displayed in the output panel rather than read as source code.

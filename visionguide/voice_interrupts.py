from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SpeechInterrupt:
    kind: str
    command: str = ""


def parse_speech_interrupt(
    transcript: object, *, allow_unaddressed_resume: bool = False
) -> SpeechInterrupt | None:
    """Accept barge-in only when addressed to Arthur, with a paused-state resume shortcut.

    Requiring the assistant name is a lightweight echo-rejection guard: the live
    TTS audio may be audible to the microphone, but ordinary assistant sentences
    are not interpreted as commands unless they contain the address phrase.
    """
    original = str(transcript or "").casefold().strip()
    normalized = re.sub(r"[^a-z0-9' ]+", " ", original)
    normalized = " ".join(normalized.split())
    match = re.match(r"^(?:(?:hey|hi|hello)\s+)?arthur\b[,:\s-]*(.*)$", normalized)
    if not match:
        if allow_unaddressed_resume and re.fullmatch(
            r"(?:ok(?:ay)?\s+)?(?:now\s+)?(?:continue|resume|go on|carry on)(?:\s+(?:speaking|it|that|your response|from where you stopped|from where you left off))?",
            normalized,
        ):
            return SpeechInterrupt("resume")
        return None
    text = match.group(1).strip()
    if not text:
        return None

    if re.fullmatch(r"(?:please\s+)?(?:stop|pause)(?:\s+(?:speaking|talking|your response|the response))?", text):
        return SpeechInterrupt("pause")
    if re.fullmatch(r"(?:please\s+)?(?:hold on|wait)(?:\s+a second)?", text):
        return SpeechInterrupt("pause")
    if re.fullmatch(r"(?:please\s+)?(?:continue|resume|go on|carry on)(?:\s+(?:speaking|it|that|your response|from where you stopped|from where you left off))?", text):
        return SpeechInterrupt("resume")
    if re.fullmatch(r"(?:please\s+)?(?:cancel|discard)(?:\s+(?:that|this|the current|your))?\s*(?:response)?", text):
        return SpeechInterrupt("cancel")
    return SpeechInterrupt("command", text)

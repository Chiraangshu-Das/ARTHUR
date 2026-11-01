from __future__ import annotations

import re


_WEBSITES = {
    "youtube": "youtube",
    "google": "google",
    "github": "github",
    "chatgpt": "chatgpt",
    "gemini": "gemini",
    "claude": "claude",
    "leetcode": "leetcode",
    "netlify": "netlify",
    "render": "render",
    "gmail": "gmail",
    "google drive": "google drive",
    "google docs": "google docs",
    "google sheets": "google sheets",
    "google meet": "google meet",
    "google classroom": "google classroom",
    "google maps": "google maps",
    "stackoverflow": "stackoverflow",
    "stack overflow": "stackoverflow",
    "wikipedia": "wikipedia",
    "reddit": "reddit",
    "linkedin": "linkedin",
    "instagram": "instagram",
    "whatsapp web": "whatsapp web",
    "google cloud console": "google cloud console",
    "google cloud": "google cloud console",
    "cloud console": "google cloud console",
    "cloud console": "google cloud console",
    "neon db": "neon db",
    "neon": "neon db",
    "neon database": "neon db",
    "neon database": "neon db",
    "google contacts": "google contacts",
    "contacts": "google contacts",
    "linkedin learning": "linkedin learning",
    "linkedln learning": "linkedin learning",
    "linkedin learning courses": "linkedin learning",
    "coursera": "coursera",
    "swayam": "swayam",
    "swaym": "swayam",
    "swayam courses": "swayam",
    "nptel": "nptel",
    "nptel courses": "nptel",
}

_APPS = {
    "calculator": "calculator", "calc": "calculator", "windows calculator": "calculator",
    "notepad": "notepad", "text editor": "notepad",
    "file explorer": "file explorer", "explorer": "file explorer", "files": "file explorer",
    "task manager": "task manager", "settings": "settings", "windows settings": "settings",
    "bluetooth settings": "bluetooth settings", "wi-fi settings": "wi-fi settings",
    "wifi settings": "wi-fi settings", "network settings": "network settings",
    "vscode": "vscode", "vs code": "vscode", "visual studio code": "vscode",
    "paint": "paint", "snipping tool": "snipping tool", "command prompt": "command prompt",
    "terminal": "terminal", "powershell": "powershell", "control panel": "control panel",
    "device manager": "device manager", "resource monitor": "resource monitor",
    "magnifier": "magnifier", "on-screen keyboard": "on-screen keyboard",
    "word": "word", "microsoft word": "microsoft word",
    "powerpoint": "powerpoint", "microsoft powerpoint": "microsoft powerpoint",
    "excel": "excel", "microsoft excel": "microsoft excel",
    "wps office": "wps office", "wps docs": "wps docs", "wps writer": "wps writer",
    "wps sheets": "wps sheets", "wps spreadsheets": "wps spreadsheets",
    "wps slides": "wps slides", "wps presentation": "wps presentation", "wps pdf": "wps pdf",
    "whatsapp": "whatsapp", "arduino": "arduino", "arduino ide": "arduino ide",
    "autocad": "autocad", "autocad 2026": "autocad 2026",
    "python idle": "python idle", "idle python 3.14": "idle python 3.14",
    "picasa": "picasa", "picasa 3": "picasa 3", "media player": "media player",
    "windows media player": "windows media player", "photos": "photos", "clock": "clock",
    "recycle bin": "recycle bin", "airplane mode": "airplane mode",
    "eye comfort": "eye comfort", "night light": "night light",
    "energy saver": "energy saver", "battery saver": "battery saver",
    "edge": "edge", "microsoft edge": "microsoft edge",
}


def _clean(value: str) -> str:
    return " ".join(value.lower().strip().split()).strip(" \t\r\n\"'“”‘’")


def parse_voice_command(text: str) -> tuple[str, str]:
    """Map a natural-language command to an explicit, allowlisted action.

    This parser never executes an action. The GUI/action layer applies its own
    confirmation gates before file, screen-sharing, memory, or other sensitive work.
    """
    raw = (text or "").strip()
    normalized = _clean(raw)
    if not normalized:
        return "unknown", ""

    # Screen-oriented requests must precede generic scene questions.
    if any(p in normalized for p in (
        "explain what is on my screen", "explain what's on my screen", "describe my screen",
        "what is on my screen", "what's on my screen", "explain this screen",
        "describe the current screen", "what am i looking at on my computer",
    )):
        return "screen_describe", "Describe the visible screen, distinguish readable text from visual inference, and state uncertainty."
    if any(p in normalized for p in (
        "read the text on my screen", "read my screen", "read text on screen",
        "read what is on screen", "read what's on screen", "ocr my screen",
    )):
        return "screen_ocr", ""

    # Online search commands. Search queries are passed as data, never shell text.
    match = re.match(r"^(?:search youtube(?: for)?|search on youtube(?: for)?|find youtube videos?(?: about| for)?|youtube search(?: for)?)\s+(.+)$", normalized)
    if match:
        return "youtube_search", match.group(1).strip(" ?.!\"")
    match = re.match(r"^(?:search google(?: for)?|search the web(?: for)?|search online(?: for)?|look up|find online|search for)\s+(.+)$", normalized)
    if match and not normalized.startswith(("search this page", "search memory", "search the document")):
        return "web_search", match.group(1).strip(" ?.!\"")

    # Camera/scene commands.
    if any(p in normalized for p in (
        "describe the scene", "describe scene", "what can you see", "what is in front",
        "what's in front", "what do you see", "what is present in front of me",
        "what is around me", "what is in front of me", "describe the camera view",
        "describe current camera view",
    )):
        return "describe", ""
    for prefix in (
        "is there any ", "are there any ", "can you see any ", "do you see any ",
        "is there a ", "is there an ", "can you see a ", "can you see an ",
        "do you see a ", "do you see an ", "is a ", "is an ",
    ):
        if normalized.startswith(prefix):
            target = normalized[len(prefix):].strip().rstrip("?.! ")
            for suffix in (
                " in front of me", " in front", " around me", " near me", " nearby",
                " visible", " here", " on my left", " on my right", " in the centre",
                " in the center", " to my left", " to my right",
            ):
                if target.endswith(suffix):
                    target = target[:-len(suffix)].strip()
                    break
            if target:
                return "check_object", target
    if any(p in normalized for p in (
        "read the text", "read text", "read this page", "scan the page", "read the document",
        "scan this page", "read the sign", "read this label",
    )):
        return "ocr", ""

    # Screen capture and document browsing/search.
    if any(p in normalized for p in ("take a screenshot", "take screenshot", "capture the screen", "capture screen", "screenshot my screen", "screenshot")):
        return "screenshot", ""
    # Support both word orders: "find algorithm in this PDF" and
    # "open my document and find the word algorithm".
    match = re.search(r"\bfind (?:the )?word\s+(.+?)\s+(?:in|inside|within)\s+(?:my |this |the )?(?:document|file|pdf|docx)\b", normalized)
    if match:
        return "document_search", match.group(1).strip(" ?.!\"")
    match = re.search(r"\bfind\s+(?!the word\b)(.+?)\s+(?:in|inside|within)\s+(?:my |this |the )?(?:document|file|pdf|docx)\b", normalized)
    if match:
        return "document_search", match.group(1).strip(" ?.!\"")
    if any(token in normalized for token in ("document", "pdf", "docx", "file")):
        trailing_word = re.search(r"\bfind (?:the )?word\s+(.+?)\s*$", normalized)
        if trailing_word:
            term = trailing_word.group(1).strip(" ?.!\"")
            if term:
                return "document_search", term
    match = re.search(r"\bfind (?:the )?word\s+(.+?)\s+(?:on|in) (?:this )?(?:page|scanned page)\b", normalized)
    if match:
        return "find_word", match.group(1).strip(" ?.!\"")
    if normalized.startswith("find the word "):
        return "find_word", normalized.removeprefix("find the word ").strip()
    if normalized.startswith("search this page for "):
        return "find_word", normalized.removeprefix("search this page for ").strip()
    if normalized in {"open my latest pdf", "open latest pdf", "open my most recent pdf", "open the latest pdf"}:
        return "open_latest_pdf", ""
    if any(p in normalized for p in ("open my document", "open a document", "open my pdf", "open a pdf", "choose a document")):
        return "open_document", ""

    # Safety-alert opt-in remains explicit.
    if any(p in normalized for p in ("turn on safety alerts", "enable safety alerts", "start safety alerts")):
        return "safety_on", ""
    if any(p in normalized for p in ("turn off safety alerts", "disable safety alerts", "stop safety alerts")):
        return "safety_off", ""

    # Wake-word input requires an explicitly configured model and remains disarmed until enabled.
    if any(p in normalized for p in ("enable wake word", "turn on wake word", "start wake word mode", "arm hello Arthur")):
        return "wake_on", ""
    if any(p in normalized for p in ("disable wake word", "turn off wake word", "stop wake word mode", "disarm hello Arthur")):
        return "wake_off", ""

    # Allowlisted application launch. No arbitrary executable names are accepted.
    open_prefixes = ("open ", "launch ", "start ", "run ", "show me ", "take me to ", "go to ")
    for prefix in open_prefixes:
        if normalized.startswith(prefix):
            target = normalized[len(prefix):].strip().rstrip("?.! ")
            if target in _WEBSITES:
                return "open_website", _WEBSITES[target]
            if target in _APPS:
                return "open_app", _APPS[target]
            folder_aliases = {
                "downloads folder": "downloads", "my downloads": "downloads", "downloads": "downloads",
                "documents folder": "documents", "my documents": "documents", "documents": "documents",
                "desktop": "desktop", "desktop folder": "desktop", "pictures folder": "pictures",
                "pictures": "pictures", "visionguideai folder": "project",
            }
            if target in folder_aliases:
                return "open_folder", folder_aliases[target]
            if target in {"browser", "web browser", "internet"}:
                return "open_website", "browser"

    if normalized in {"send this email", "send email", "send the email", "send it"}:
        return "email_send", ""
    if any(p in normalized for p in ("start sign language translation", "start isl translation", "translate sign language", "enable sign language translation")):
        return "sign_start", ""
    if any(p in normalized for p in ("stop sign language translation", "stop isl translation", "disable sign language translation")):
        return "sign_stop", ""

    if any(p in normalized for p in ("is my internet connected", "check my internet connection", "test internet connection", "is the internet working")):
        return "internet_status", ""
    if any(p in normalized for p in ("how much ram", "memory usage", "how much disk space", "available disk space", "system status", "computer status", "battery level", "how much battery")):
        return "system_status", ""

    if "stop listening" in normalized or normalized in {"cancel", "cancel that", "cancel the current operation", "stop the current task"}:
        return "cancel", ""

    if normalized in {"stop camera analysis", "turn off the camera", "stop the camera", "pause camera"}:
        return "camera_stop", ""
    if normalized in {"resume camera", "restart camera", "turn the camera back on", "start camera again"}:
        return "camera_start", ""

    if "capture photo" in normalized or "take a picture" in normalized or "take a photo" in normalized:
        return "snapshot", ""

    for prefix in ("remember that ", "remember this: ", "remember: ", "save this memory: "):
        if normalized.startswith(prefix):
            note = raw[len(prefix):].strip()
            return ("memory_save", note) if note else ("unknown", raw)
    for prefix in ("what do you remember about ", "search memory for ", "find in memory "):
        if normalized.startswith(prefix):
            query = normalized[len(prefix):].strip().rstrip("?.! ")
            return ("memory_search", query) if query else ("memory_search", "")
    for prefix in ("forget memory about ", "forget that ", "delete memory about "):
        if normalized.startswith(prefix):
            query = normalized[len(prefix):].strip().rstrip("?.! ")
            return ("memory_delete", query) if query else ("unknown", raw)

    if normalized.startswith("ask ai "):
        return "ask_ai", raw[len("ask ai "):].strip()
    if any(normalized.startswith(prefix) for prefix in (
        "write an email", "write email", "draft an email", "draft email", "compose an email",
        "compose email", "write a letter", "draft a letter", "summarize this text",
        "summarise this text", "explain this topic", "explain this concept", "translate this text",
        "translate this sentence", "ask general ai", "solve ", "differentiate ", "integrate ",
        "explain this error", "explain this code", "write a program", "generate code",
        "research this topic", "compare ", "make revision notes", "create flashcards",
    )):
        return "text_ai", raw

    if normalized in {"help", "what commands are available", "show commands", "list commands", "command catalogue"}:
        return "help", ""
    return "unknown", raw

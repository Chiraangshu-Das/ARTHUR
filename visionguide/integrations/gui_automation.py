from __future__ import annotations

import re
import time
import webbrowser
from typing import Callable

from visionguide.desktop_actions import open_website


def _validate_recipient(recipient: str) -> str:
    recipient = str(recipient).strip()
    if not re.fullmatch(r"[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+", recipient) or len(recipient) > 254:
        raise ValueError("A single valid recipient email address is required.")
    return recipient


def _clipboard_paste(text: str) -> None:
    try:
        import pyperclip
        pyperclip.copy(text)
        import pyautogui
        pyautogui.hotkey("ctrl", "v")
    except ImportError:
        import pyautogui
        # pyautogui.write is ASCII-oriented; non-ASCII mail content needs clipboard support.
        if any(ord(char) > 127 for char in text):
            raise RuntimeError("Install pyperclip to paste non-ASCII text into desktop apps.")
        pyautogui.write(text, interval=0.001)


def activate_window(title_keyword: str, timeout: float = 20.0) -> str:
    try:
        import pygetwindow
    except ImportError as exc:
        raise RuntimeError("Window targeting requires pygetwindow. Install requirements-integrations.txt.") from exc
    deadline = time.monotonic() + max(1, min(float(timeout), 60))
    while time.monotonic() < deadline:
        matches = [window for window in pygetwindow.getAllWindows()
                   if window.title and title_keyword.casefold() in window.title.casefold()]
        if matches:
            window = matches[0]
            if window.isMinimized:
                window.restore()
            window.activate()
            time.sleep(0.25)
            return window.title
        time.sleep(0.25)
    raise RuntimeError(f"No window containing {title_keyword!r} appeared within {timeout:g} seconds.")


def compose_gmail_gui(
    recipient: str,
    subject: str,
    body: str,
    *,
    send: bool = False,
    confirmed_send: bool = False,
    on_status: Callable[[str], None] | None = None,
) -> str:
    """GUI compose helper. It leaves a reviewed draft open unless sending is explicitly confirmed.

    Gmail keyboard shortcuts (Settings -> General -> Keyboard shortcuts) must be enabled.
    The workflow uses window activation and keyboard input; browser DOM or pixel coordinates
    are deliberately not assumed. User review is required before Ctrl+Enter.
    """
    recipient = _validate_recipient(recipient)
    subject = " ".join(str(subject).split()).strip()
    body = str(body).strip()
    if not subject or not body:
        raise ValueError("Email subject and body are both required.")
    if len(subject) > 250 or len(body) > 100_000:
        raise ValueError("Email subject/body exceeds supported length.")
    if send and not confirmed_send:
        raise PermissionError("Email send blocked. Review the message and set confirmed_send=True after explicit confirmation.")
    try:
        import pyautogui
    except ImportError as exc:
        raise RuntimeError("GUI automation requires pyautogui. Install requirements-integrations.txt.") from exc
    pyautogui.FAILSAFE = True
    (on_status or (lambda _message: None))("Opening Gmail in the default browser.")
    open_website("gmail")
    title = activate_window("gmail", timeout=30)
    # Gmail's 'c' shortcut opens a new message when keyboard shortcuts are enabled.
    pyautogui.press("c")
    time.sleep(1.0)
    _clipboard_paste(recipient)
    pyautogui.press("enter")
    time.sleep(0.25)
    # After committing the recipient, Tab normally advances to Subject; after subject it
    # advances to message body. If Gmail layout/shortcuts differ, the user can correct the draft.
    pyautogui.press("tab")
    _clipboard_paste(subject)
    pyautogui.press("tab")
    _clipboard_paste(body)
    time.sleep(0.35)
    if not send:
        return f"Prepared a draft in the active Gmail window {title!r}. Review the recipient, subject, and body before sending."
    # This is a high-impact external action and is impossible without the caller's confirmation.
    pyautogui.hotkey("ctrl", "enter")
    return f"Issued Gmail's Ctrl+Enter send shortcut in {title!r} after explicit confirmation. Verify Gmail's sent-state indicator."


def play_youtube_search(query: str) -> str:
    query = " ".join(str(query).split()).strip()
    if not query:
        raise ValueError("Provide a video search query.")
    # Search opens a results page; automatic selection/playback is intentionally separate so
    # a voice command cannot silently choose the wrong video.
    import urllib.parse
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
    if not webbrowser.open(url, new=2):
        raise RuntimeError("Could not open YouTube search results.")
    return f"Opened YouTube results for {query!r}. Select the intended video, then say play or pause."


_TARGET_WINDOWS = {
    "gmail": ("gmail",),
    "word": ("word",),
    "microsoft word": ("word",),
    "powerpoint": ("powerpoint",),
    "microsoft powerpoint": ("powerpoint",),
    "excel": ("excel",),
    "microsoft excel": ("excel",),
    "microsoft excel": ("excel",),
    "whatsapp": ("whatsapp",),
    "whatsapp web": ("whatsapp",),
    "google docs": ("docs",),
    "google sheets": ("sheets",),
    "google meet": ("meet",),
    "google classroom": ("classroom",),
    "notepad": ("notepad",),
    "vscode": ("visual studio code", "vs code", "code"),
    "wps docs": ("wps writer", "writer", "wps office"),
    "wps sheets": ("wps spreadsheet", "spreadsheet", "wps office"),
    "wps slides": ("wps presentation", "presentation", "wps office"),
    "wps pdf": ("wps pdf",),
    "arduino ide": ("arduino ide", "arduino"),
    "autocad": ("autocad",),
    "python idle": ("idle shell", "idle"),
    "picasa": ("picasa",),
    "photos": ("photos",),
    "media player": ("media player", "windows media player"),
    "clock": ("clock",),
    "instagram": ("instagram",),
}


def _normalise_target(target: str) -> tuple[str, tuple[str, ...]]:
    key = " ".join(str(target).casefold().split()).strip()
    if key not in _TARGET_WINDOWS:
        raise ValueError(f"Window target {target!r} is not in the GUI automation allowlist.")
    return key, _TARGET_WINDOWS[key]


def type_into_window(target: str, text: str) -> str:
    """Paste dictated or generated text into a known application window; do not submit it."""
    key, keywords = _normalise_target(target)
    text = str(text)
    if not text.strip():
        raise ValueError("Text to paste cannot be empty.")
    if len(text) > 100_000:
        raise ValueError("Text to paste exceeds 100,000 characters.")
    title = None
    last_error = None
    for keyword in keywords:
        try:
            title = activate_window(keyword, timeout=1.5)
            break
        except RuntimeError as exc:
            last_error = exc
    if title is None:
        raise RuntimeError(f"The requested {key} window is not open. {last_error or ''}")
    _clipboard_paste(text)
    return f"Pasted text into the {key} window {title!r}. The text was not submitted or sent. Review the target before the next action."


def word_write_document(text: str) -> str:
    """Open a new Word document and insert text, leaving it unsaved for the user's review."""
    from visionguide.desktop_actions import open_app
    open_app("word")
    title = activate_window("word", timeout=20)
    import pyautogui
    pyautogui.hotkey("ctrl", "n")
    time.sleep(0.7)
    _clipboard_paste(text)
    return f"Created a new document in {title!r} and inserted the text. It has not been saved or shared; review it before saving."


def compose_whatsapp_gui(contact: str, message: str, *, send: bool = False, confirmed_send: bool = False) -> str:
    """Open a WhatsApp Web chat and prepare, but do not send, a message by default.

    The user must verify the selected contact/chat title and complete text. Search result
    selection is UI-dependent, so a recipient is never assumed to be verified by this helper.
    """
    contact = " ".join(str(contact).split()).strip()
    message = str(message).strip()
    if not contact or len(contact) > 150:
        raise ValueError("WhatsApp contact name is required and must be 150 characters or fewer.")
    if not message or len(message) > 20_000:
        raise ValueError("WhatsApp message is required and must be 20,000 characters or fewer.")
    if send and not confirmed_send:
        raise PermissionError("Sending a WhatsApp message requires explicit confirmation after reviewing the current chat and message.")
    try:
        import pyautogui
    except ImportError as exc:
        raise RuntimeError("WhatsApp GUI automation requires pyautogui. Install requirements-integrations.txt.") from exc
    open_website("whatsapp web")
    title = activate_window("whatsapp", timeout=30)
    # Official WhatsApp Web shortcut on Windows: Ctrl+Alt+N for New Chat.
    pyautogui.hotkey("ctrl", "alt", "n")
    time.sleep(0.4)
    _clipboard_paste(contact)
    time.sleep(0.8)
    pyautogui.press("enter")
    time.sleep(0.7)
    _clipboard_paste(message)
    if not send:
        return (f"Prepared message text in WhatsApp Web window {title!r} without sending. "
                f"Verify the visible chat title is exactly the intended contact and inspect the full message before saying 'send WhatsApp message'.")
    pyautogui.press("enter")
    return f"Issued Enter in WhatsApp Web window {title!r} after explicit confirmation. Verify the message appears in the intended chat."


def send_current_whatsapp(*, confirmed_send: bool = False) -> str:
    if not confirmed_send:
        raise PermissionError("WhatsApp send blocked until the user confirms the recipient and complete message text.")
    import pyautogui
    title = activate_window("whatsapp", timeout=8)
    pyautogui.press("enter")
    return f"Issued Enter in {title!r} after explicit confirmation. Verify the message appears in the intended chat."


def type_text_to_focused_window(text: str) -> str:
    """Paste literal text into the current Windows keyboard-focus target without submitting it.

    This deliberately does not activate a window: it sends text only to the field that is
    already focused. Clipboard paste supports Unicode and avoids PyAutoGUI's ASCII limits.
    """
    text = str(text)
    if not text:
        raise ValueError("Text to type cannot be empty.")
    if len(text) > 100_000:
        raise ValueError("Text to type exceeds 100,000 characters.")
    try:
        import pyautogui
    except ImportError as exc:
        raise RuntimeError("Typing into desktop applications requires PyAutoGUI. Install requirements-integrations.txt.") from exc
    pyautogui.FAILSAFE = True
    _clipboard_paste(text)
    return f"Pasted {len(text)} characters into the currently focused application. The text was not submitted or sent."


def focus_application_target(target: str, element: str = "") -> str:
    """Focus an allowlisted application and only use safe, known keyboard focus shortcuts."""
    import pyautogui
    target = " ".join(str(target).casefold().split()).strip()
    element = " ".join(str(element).casefold().split()).strip()
    aliases = {
        "youtube": "youtube", "browser": "browser", "chrome": "chrome", "edge": "edge",
        "whatsapp": "whatsapp", "whatsapp web": "whatsapp", "gmail": "gmail",
        "google docs": "docs", "google sheets": "sheets", "google meet": "meet",
        "google classroom": "classroom", "docs": "docs", "calculator": "calculator",
        "notepad": "notepad", "word": "word", "microsoft word": "word",
        "powerpoint": "powerpoint", "microsoft powerpoint": "powerpoint",
        "excel": "excel", "microsoft excel": "excel", "wps docs": "wps writer",
        "wps sheets": "wps spreadsheet", "wps slides": "wps presentation", "wps pdf": "wps pdf",
        "vscode": "visual studio code", "vs code": "visual studio code",
        "arduino ide": "arduino", "autocad": "autocad", "autocad 2026": "autocad",
        "python idle": "idle", "picasa": "picasa", "picasa 3": "picasa",
        "photos": "photos", "media player": "media player", "clock": "clock", "instagram": "instagram",
    }
    if target not in aliases:
        raise ValueError("The requested application is not in the focus allowlist.")
    keyword = aliases[target]
    title = activate_window(keyword, timeout=5)
    if not element:
        return f"Focused the {target} window ({title}). No text was entered."
    if element in {"address bar", "url bar", "browser address bar"} and target in {"browser", "chrome", "edge", "youtube"}:
        pyautogui.hotkey("ctrl", "l")
        return f"Focused the browser address bar in {title}."
    if element in {"search bar", "search box", "youtube search bar"} and target == "youtube":
        # YouTube's slash shortcut normally moves focus to its search box. Report the
        # shortcut action, not a guarantee about browser extensions or custom layouts.
        pyautogui.press("/")
        return f"Sent YouTube's search-focus shortcut to {title}. Verify that its search box has focus before typing."
    if element in {"message box", "chat box", "message field"} and target in {"whatsapp", "whatsapp web"}:
        raise RuntimeError("The WhatsApp window is focused, but the message field cannot be reliably verified through generic desktop automation. Click the intended chat's message box before asking Arthur to type.")
    if element in {"search bar", "search box"} and target in {"whatsapp", "whatsapp web", "gmail", "google docs"}:
        raise RuntimeError(f"The {target} window is focused, but this application's {element} cannot be verified safely. Click the intended field before typing.")
    raise ValueError(f"The target element {element!r} is not supported for {target!r}.")

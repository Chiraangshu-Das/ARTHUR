from __future__ import annotations

import re
import os
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
    "youtube": ("youtube",),
    "file explorer": ("file explorer", "explorer"),
    "google": ("google",),
    "github": ("github",),
    "chatgpt": ("chatgpt",),
    "gemini": ("gemini",),
    "claude": ("claude",),
    "leetcode": ("leetcode",),
    "netlify": ("netlify",),
    "render": ("render",),
    "google drive": ("google drive", "drive"),
    "google maps": ("google maps", "maps"),
    "google contacts": ("google contacts", "contacts"),
    "google cloud console": ("google cloud", "cloud console"),
    "coursera": ("coursera",),
    "swayam": ("swayam",),
    "nptel": ("nptel",),
    "stackoverflow": ("stackoverflow",),
    "wikipedia": ("wikipedia",),
    "reddit": ("reddit",),
    "linkedin": ("linkedin",),
    "browser": ("google chrome", "microsoft edge", "chrome", "edge"),
    "chrome": ("google chrome", "chrome"),
    "edge": ("microsoft edge", "edge"),
    "word": ("word",),
    "microsoft word": ("word",),
    "powerpoint": ("powerpoint",),
    "microsoft powerpoint": ("powerpoint",),
    "excel": ("excel",),
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
    "calculator": ("calculator",),
    "task manager": ("task manager",),
    "settings": ("settings",),
    "bluetooth settings": ("settings",),
    "wi-fi settings": ("settings",),
    "network settings": ("settings",),
    "paint": ("paint",),
    "snipping tool": ("snipping tool",),
    "terminal": ("terminal",),
    "powershell": ("powershell",),
    "command prompt": ("command prompt",),
    "control panel": ("control panel",),
    "device manager": ("device manager",),
    "magnifier": ("magnifier",),
    "on-screen keyboard": ("on-screen keyboard",),
    "resource monitor": ("resource monitor",),
    "recycle bin": ("recycle bin",),
    "airplane mode": ("settings",),
    "night light": ("settings",),
    "eye comfort": ("settings",),
    "energy saver": ("settings",),
    "battery saver": ("settings",),
    "microsoft edge": ("microsoft edge", "edge"),
    "windows media player": ("windows media player", "media player"),
    "autocad 2026": ("autocad",),
    "arduino": ("arduino",),
    "picasa 3": ("picasa",),
    "idle python 3.14": ("idle shell", "idle"),
    "google cloud": ("google cloud", "cloud console"),
    "neon": ("neon",),
    "neon db": ("neon",),
    "neon database": ("neon",),
    "linkedln learning": ("linkedin learning", "linkedin"),
    "linkedin learning": ("linkedin learning", "linkedin"),
    "swaym": ("swayam",),
    "swāyam": ("swayam",),
}


def _normalise_target(target: str) -> tuple[str, tuple[str, ...]]:
    key = " ".join(str(target).casefold().split()).strip()
    aliases = {
        "explorer": "file explorer", "microsoft excel": "excel", "microsoft powerpoint": "powerpoint",
        "microsoft edge": "edge", "visual studio code": "vscode", "vs code": "vscode",
        "linkedln learning": "linkedin learning", "swaym": "swayam",
    }
    key = aliases.get(key, key)
    if key not in _TARGET_WINDOWS:
        raise ValueError(f"Window target {target!r} is not in the GUI automation allowlist.")
    return key, _TARGET_WINDOWS[key]


def _validated_text(text: str) -> str:
    text = str(text)
    if not text.strip():
        raise ValueError("Text to paste cannot be empty.")
    if len(text) > 100_000:
        raise ValueError("Text to paste exceeds 100,000 characters.")
    return text


def _focus_accessible_field(element: str) -> str:
    """Focus a named Windows UI Automation edit control without guessing coordinates.

    This is a fallback for apps/sites without a known keyboard shortcut. It accepts
    only a uniquely identifiable visible, enabled Edit/ComboBox control.
    """
    if os.name != "nt":
        raise RuntimeError("Accessible field targeting requires Windows UI Automation.")
    try:
        import ctypes
        from pywinauto import Desktop
    except ImportError as exc:
        raise RuntimeError(
            "Generic search/text-field targeting needs pywinauto. Install the updated "
            "requirements-integrations.txt and restart Arthur."
        ) from exc

    hwnd = int(ctypes.windll.user32.GetForegroundWindow() or 0)
    if not hwnd:
        raise RuntimeError("Windows did not report an active application window.")
    window = Desktop(backend="uia").window(handle=hwnd)
    field = " ".join(str(element).casefold().replace("field", "box").split()).strip()
    if field in {"search", "search box", "search bar", "search field", "find box", "find bar"}:
        terms = ("search", "find")
    elif field in {"address bar", "url bar", "location bar"}:
        terms = ("address", "url", "location")
    else:
        terms = tuple(x for x in re.findall(r"[a-z0-9]+", field) if x not in {"text", "box", "field"})

    controls = []
    matched = []
    for control in window.descendants():
        try:
            info = control.element_info
            if info.control_type not in {"Edit", "ComboBox"}:
                continue
            if not control.is_visible() or not control.is_enabled():
                continue
            name = str(info.name or "").casefold()
            auto_id = str(info.automation_id or "").casefold()
            metadata = f"{name} {auto_id}".strip()
            controls.append(control)
            if terms and any(term in metadata for term in terms):
                matched.append((control, metadata))
        except Exception:
            continue

    # Prefer one semantically named match; otherwise accept only a sole editable control.
    if len(matched) == 1:
        chosen = matched[0][0]
    elif len(matched) > 1:
        exact = [item for item in matched if any(item[1].strip() == term for term in terms)]
        if len(exact) == 1:
            chosen = exact[0][0]
        else:
            raise RuntimeError(
                f"More than one accessible {field or 'text'} control was found. Click the intended field manually."
            )
    elif len(controls) == 1:
        # A single editable control is an unambiguous fallback even if its label is blank.
        chosen = controls[0]
    else:
        raise RuntimeError(
            f"Could not identify one accessible {field or 'text'} field in the active window. "
            "Click the intended field and use 'type exactly ...' to enter text there."
        )

    try:
        chosen.set_focus()
        return str(chosen.element_info.name or field or "editable field")
    except Exception as exc:
        raise RuntimeError(f"Windows could not focus the identified {field or 'text'} field: {exc}") from exc


def _word_insert_text(text: str, *, create_new_document: bool = False) -> str:
    """Use Word's COM object model so the user does not need to click the document canvas."""
    text = _validated_text(text)
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise RuntimeError(
            "Direct Microsoft Word insertion requires pywin32. Run `python -m pip install pywin32`, then restart Arthur."
        ) from exc

    from visionguide.desktop_actions import open_app
    pythoncom.CoInitialize()
    try:
        try:
            title = activate_window("word", timeout=1.0)
        except RuntimeError:
            open_app("word")
            title = activate_window("word", timeout=25.0)

        try:
            word = win32com.client.GetActiveObject("Word.Application")
        except Exception:
            word = win32com.client.Dispatch("Word.Application")
        word.Visible = True
        if create_new_document or int(word.Documents.Count) == 0:
            document = word.Documents.Add()
        else:
            document = word.ActiveDocument
            document.Activate()
        word.Activate()
        word.Selection.TypeText(Text=text)
        return f"Inserted {len(text)} characters into Microsoft Word ({title!r}). The document was not saved or shared."
    finally:
        pythoncom.CoUninitialize()


def type_into_window(target: str, text: str, element: str = "") -> str:
    """Activate a named target, focus a supported field, and insert text without submitting it.

    The function deliberately uses keyboard shortcuts only for well-known fields. It does
    not guess mouse coordinates for arbitrary website controls or dialog widgets.
    """
    key, keywords = _normalise_target(target)
    text = _validated_text(text)
    element_key = " ".join(str(element).casefold().replace("field", "box").split()).strip()
    search_elements = {"search box", "search bar", "search", "find box", "find bar"}
    address_elements = {"address bar", "url bar", "browser address box", "location bar"}

    # Word document body insertion is handled through COM. Its Find box is a separate
    # workflow and must receive focus before the clipboard paste.
    if key in {"word", "microsoft word"} and element_key not in search_elements | {"find box", "find bar"}:
        return _word_insert_text(text, create_new_document=False)

    title = None
    last_error = None
    for keyword in keywords:
        try:
            title = activate_window(keyword, timeout=1.5)
            break
        except RuntimeError as exc:
            last_error = exc
    if title is None:
        # If a supported app/site is not already open, launch it through the existing
        # allowlisted launcher, then reacquire its actual foreground window.
        try:
            from visionguide.desktop_actions import WEBSITE_URLS, open_app
            if key in WEBSITE_URLS:
                from visionguide.desktop_actions import open_website
                open_website(key)
            else:
                open_app(key)
            title = activate_window(keywords[0], timeout=20.0)
        except Exception as exc:
            raise RuntimeError(f"Could not open or activate the requested {key} target. {exc}") from exc

    if key == "file explorer" and element_key in {"document", "text box", "text field", "message box", "chat box"}:
        raise RuntimeError("File Explorer supports its search box and address bar here. Specify one of those fields.")

    import pyautogui
    pyautogui.FAILSAFE = True

    if key == "youtube" and element_key in search_elements:
        pyautogui.press("/")  # YouTube's search-focus shortcut.
        time.sleep(0.2)
    elif key in {"browser", "chrome", "edge"} and element_key in address_elements:
        pyautogui.hotkey("ctrl", "l")  # Browser omnibox / address bar.
        time.sleep(0.1)
    elif key in {"browser", "chrome", "edge"} and element_key in search_elements:
        # A browser search field means the page's accessible search control; the
        # address bar is a separate explicit target.
        _focus_accessible_field(element_key)
        time.sleep(0.1)
    elif key in {"file explorer", "recycle bin"} and element_key in search_elements:
        pyautogui.hotkey("ctrl", "e")  # File Explorer search box.
        time.sleep(0.15)
        pyautogui.hotkey("ctrl", "a")
    elif key in {"file explorer", "recycle bin"} and element_key in address_elements:
        pyautogui.hotkey("ctrl", "l")  # File Explorer location bar.
        time.sleep(0.1)
    elif key in {"word", "microsoft word", "excel", "microsoft excel", "notepad", "google docs", "google sheets", "vscode", "wps docs", "wps sheets", "settings", "bluetooth settings", "wi-fi settings", "network settings", "task manager", "control panel"} and element_key in search_elements:
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.2)
    elif key == "google drive" and element_key in search_elements:
        # Google Drive uses '/' to focus its global Search in Drive box.
        pyautogui.press("/")
        time.sleep(0.2)
    elif key in {"gmail", "github"} and element_key in search_elements:
        pyautogui.press("/")  # Gmail shortcuts must be enabled; GitHub uses / to focus search.
        time.sleep(0.15)
    elif key in {"whatsapp", "whatsapp web"} and element_key in search_elements:
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.15)
    elif element_key in search_elements | address_elements:
        # Try Windows UI Automation for the page/app's real search or address field.
        # This handles many sites and desktop apps without site-specific shortcuts.
        try:
            _focus_accessible_field(element_key)
            time.sleep(0.1)
        except RuntimeError as exc:
            raise RuntimeError(
                f"Could not safely focus the {element_key} in {key!r}. {exc}"
            ) from exc
    elif element_key in {"document", "text box", "text field", "cell", "active cell", "message box", "chat box"}:
        # For generic app text controls, use UI Automation when the target is not a
        # known document/cell editor. Otherwise preserve the app's current insertion point.
        if key not in {"word", "microsoft word", "excel", "microsoft excel", "notepad", "vscode", "google docs", "google sheets", "wps docs", "wps sheets"}:
            try:
                _focus_accessible_field(element_key)
            except RuntimeError as exc:
                raise RuntimeError(
                    f"Could not safely focus the {element_key} in {key!r}. {exc}"
                ) from exc
        pyautogui.sleep(0.05)
    elif element_key:
        raise RuntimeError(
            f"Arthur cannot reliably identify {element!r} in {key!r}. Click the intended control first, "
            "then use 'type exactly ...' or specify a supported search field."
        )
    elif key == "youtube":
        raise RuntimeError("Specify 'YouTube search box' or click the intended field before typing.")
    elif key == "file explorer":
        raise RuntimeError("Specify 'File Explorer search box' or 'File Explorer address bar'. Arthur will not type into the file list by guessing.")
    _clipboard_paste(text)
    destination = f"{key} {element_key}".strip() if element_key else key
    return f"Pasted text into {destination} in window {title!r}. It was not submitted or sent."


def field_submission_requires_confirmation(target: str, element: str = "") -> bool:
    """Return whether Enter may send a message or submit an ambiguous/high-impact field."""
    key = " ".join(str(target).casefold().split()).strip()
    key = {"microsoft word": "word", "microsoft excel": "excel", "whatsapp web": "whatsapp"}.get(key, key)
    field = " ".join(str(element).casefold().split()).strip()
    if field in {"search box", "search bar", "search field", "address bar", "url bar"}:
        return False
    if key in {"gmail", "whatsapp"}:
        return True
    if key == "word" and field in {"", "document", "text box", "text field"}:
        return False
    if key == "excel" and field in {"", "cell", "active cell"}:
        return False
    if key == "notepad" and field in {"", "document", "editor", "text box", "text field"}:
        return False
    if key == "vscode" and field in {"", "editor"}:
        return False
    if key == "google docs" and field == "document":
        return False
    if key in {"google sheets", "wps sheets"} and field in {"", "cell", "active cell"}:
        return False
    return True


def capture_focused_control_identity() -> tuple[int, ...] | None:
    """Capture the current Windows UIA runtime ID for the focused control."""
    if os.name != "nt":
        return None
    try:
        from pywinauto.windows.uia_defines import IUIA
        focused = IUIA().get_focused_element()
        if focused is None:
            return None
        runtime_id = focused.GetRuntimeId()
        return tuple(int(value) for value in runtime_id)
    except Exception:
        # A field may still accept text even when its accessibility provider does not
        # expose a stable runtime ID. In that case ARTHUR will not issue a follow-up Enter.
        return None


def submit_typed_field(
    target_hwnd: int, target_title: str, target: str, element: str = "",
    expected_focus_identity: tuple[int, ...] | list[int] | None = None,
    confirmed_submission: bool = False,
) -> str:
    """Press Enter in the exact window that received the last successful targeted paste.

    Callers must obtain confirmation for message composers and ambiguous form fields.
    This helper never switches to a different app based on a stale window title.
    """
    if os.name != "nt":
        raise RuntimeError("Submitting a remembered desktop field is supported only on Windows.")
    import ctypes
    hwnd = int(target_hwnd or 0)
    if not hwnd or not ctypes.windll.user32.IsWindow(hwnd):
        raise RuntimeError("The window that received the last text no longer exists. Nothing was submitted.")
    user32 = ctypes.windll.user32
    current = int(user32.GetForegroundWindow() or 0)
    if current != hwnd:
        raise RuntimeError(
            f"The last text was entered in {target_title!r}, but that window is no longer active. "
            "Bring it back to the foreground and repeat 'press Enter'."
        )
    if not expected_focus_identity:
        # A number of Chromium/Google custom controls expose no stable UIA RuntimeId.
        # Permit a follow-up Enter only for explicit search/address fields, where Enter
        # is non-destructive. Never apply this fallback to composers or generic forms.
        safe_search_targets = {
            "youtube", "browser", "chrome", "edge", "microsoft edge", "gmail", "github",
            "google drive", "google docs", "google sheets", "google contacts", "file explorer",
            "explorer", "whatsapp", "whatsapp web",
        }
        normalized_target = " ".join(str(target).casefold().split())
        normalized_field = " ".join(str(element).casefold().split())
        safe_field = normalized_field in {
            "search box", "search bar", "search field", "search", "address bar", "url bar",
        }
        safe_target = normalized_target in safe_search_targets
        safe_editor = (
            (normalized_target in {"google docs", "word", "microsoft word", "notepad"}
             and normalized_field in {"document", "editor", "text box", "text field"})
            or (normalized_target in {"google sheets", "excel", "microsoft excel"}
                and normalized_field in {"cell", "active cell"})
        )
        confirmed_composer = (
            confirmed_submission
            and normalized_target in {"gmail", "whatsapp", "whatsapp web"}
            and normalized_field in {"message box", "chat box", "message field", "text box", "text field", "composer"}
        )
        if not ((safe_field and safe_target) or safe_editor or confirmed_composer):
            raise RuntimeError(
                "Windows did not provide a stable identity for this field. "
                "For safety, Arthur will not press Enter in an unverified form or message composer without confirmation."
            )
    else:
        current_focus_identity = capture_focused_control_identity()
        if tuple(current_focus_identity or ()) != tuple(expected_focus_identity):
            raise RuntimeError(
                "The focused control has changed since Arthur entered the text. Nothing was submitted. "
                "Return to the original field and repeat the typing command before asking for Enter."
            )
    length = int(user32.GetWindowTextLengthW(hwnd))
    buffer = ctypes.create_unicode_buffer(max(1, length + 1))
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    active_title = buffer.value
    if target_title and active_title.casefold() != str(target_title).casefold():
        raise RuntimeError(
            f"The active window title changed from {target_title!r} to {active_title!r}. "
            "Nothing was submitted; repeat the typing command in the intended window."
        )
    if any(marker in active_title.casefold() for marker in ("arthur", "visionguide")):
        raise RuntimeError("Arthur is the foreground window. Nothing was submitted; activate the target app and repeat.")
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.press("enter")
    destination = f"{target} {element}".strip()
    return f"Pressed Enter in {destination} in {active_title!r}. Check the application to verify the result."


def word_write_document(text: str) -> str:
    """Create a new Word document via COM and insert text, leaving it unsaved for review."""
    return _word_insert_text(text, create_new_document=True)


def _get_active_word_for_operation():
    """Return an already-running Word application and active document in the current COM apartment."""
    try:
        import win32com.client
    except ImportError as exc:
        raise RuntimeError("Microsoft Word operations require pywin32. Run `python -m pip install pywin32`.") from exc
    try:
        title = activate_window("word", timeout=1.5)
    except RuntimeError as exc:
        raise RuntimeError("Microsoft Word is not currently open. Open the document first, then repeat the command.") from exc
    try:
        word = win32com.client.GetActiveObject("Word.Application")
    except Exception as exc:
        raise RuntimeError("Could not connect to the running Microsoft Word instance.") from exc
    if int(word.Documents.Count) < 1:
        raise RuntimeError("Microsoft Word is open, but no document is available.")
    document = word.ActiveDocument
    return word, document, title


def save_active_word_document(file_name: str = "") -> str:
    """Save the active Word document; never overwrite a different file by filename collision."""
    try:
        import pythoncom
    except ImportError as exc:
        raise RuntimeError("Word save requires pywin32. Run `python -m pip install pywin32`.") from exc

    pythoncom.CoInitialize()
    try:
        word, document, title = _get_active_word_for_operation()
        requested_name = str(file_name or "").strip().strip('\"“”')
        if requested_name:
            # Save-as is deliberately confined to Documents/ARTHUR. It does not accept
            # arbitrary paths or silently overwrite an existing document.
            safe_name = requested_name.replace("\\", "/").split("/")[-1]
            safe_name = re.sub(r'[<>:"/\\|?*]+', "_", safe_name).strip(" .")
            if not safe_name:
                raise ValueError("Provide a valid document filename.")
            if not safe_name.casefold().endswith(".docx"):
                safe_name += ".docx"
            destination_dir = os.path.join(os.path.expanduser("~"), "Documents", "ARTHUR")
            os.makedirs(destination_dir, exist_ok=True)
            destination = os.path.join(destination_dir, safe_name)
            if os.path.exists(destination):
                raise FileExistsError(f"{destination} already exists. Choose another filename; Arthur will not overwrite it.")
            document.SaveAs2(FileName=destination, FileFormat=16)
            return f"Saved the active Microsoft Word document to {destination}."

        current_name = str(getattr(document, "Name", "") or "")
        current_path = str(getattr(document, "Path", "") or "")
        if not current_path or re.fullmatch(r"Document\d*", current_name, re.I):
            destination_dir = os.path.join(os.path.expanduser("~"), "Documents", "ARTHUR")
            os.makedirs(destination_dir, exist_ok=True)
            from datetime import datetime
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            destination = os.path.join(destination_dir, f"ARTHUR-Document-{stamp}.docx")
            if os.path.exists(destination):
                raise FileExistsError(f"{destination} already exists. Try Save As with a different filename.")
            document.SaveAs2(FileName=destination, FileFormat=16)
            return f"Saved the previously unsaved Word document to {destination}."
        document.Save()
        full_name = str(getattr(document, "FullName", "") or current_name)
        return f"Saved the active Microsoft Word document: {full_name}."
    finally:
        pythoncom.CoUninitialize()


def replace_text_in_active_word_document(find_text: str, replace_text: str, *, confirmed: bool = False) -> str:
    """Replace all occurrences in the active Word document after explicit confirmation."""
    find_text = str(find_text or "")
    replace_text = str(replace_text or "")
    if not find_text.strip():
        raise ValueError("The text to find cannot be empty.")
    if len(find_text) > 5000 or len(replace_text) > 20_000:
        raise ValueError("Word find/replace text exceeds the supported length.")
    if not confirmed:
        raise PermissionError("Replacing Word document text requires explicit confirmation.")
    try:
        import pythoncom
    except ImportError as exc:
        raise RuntimeError("Word editing requires pywin32. Run `python -m pip install pywin32`.") from exc
    pythoncom.CoInitialize()
    try:
        word, document, title = _get_active_word_for_operation()
        document_text = str(document.Content.Text)
        match_count = len(re.findall(re.escape(find_text), document_text, flags=re.IGNORECASE))
        if match_count == 0:
            return f"No occurrence of {find_text!r} was found in {document.Name!r}; nothing was changed."
        find = document.Content.Find
        find.ClearFormatting()
        find.Replacement.ClearFormatting()
        find.Execute(
            FindText=find_text,
            ReplaceWith=replace_text,
            Replace=2,  # wdReplaceAll
            Forward=True,
            Wrap=1,  # wdFindContinue
            MatchCase=False,
        )
        return f"Replaced {match_count} occurrence(s) of {find_text!r} in {document.Name!r} ({title}). The document is modified but not saved."
    finally:
        pythoncom.CoUninitialize()


def get_active_word_selection_text() -> str:
    """Read the current Word selection so Arthur can show it before a deletion confirmation."""
    try:
        import pythoncom
    except ImportError as exc:
        raise RuntimeError("Word selection access requires pywin32.") from exc
    pythoncom.CoInitialize()
    try:
        word, _document, _title = _get_active_word_for_operation()
        return str(word.Selection.Text or "")
    finally:
        pythoncom.CoUninitialize()


def delete_active_word_selection(expected_text: str, *, confirmed: bool = False) -> str:
    """Delete only the selection Arthur previewed; abort if the selection changed."""
    expected_text = str(expected_text or "")
    if not expected_text:
        raise ValueError("There is no selected text to delete.")
    if not confirmed:
        raise PermissionError("Deleting selected Word text requires explicit confirmation.")
    try:
        import pythoncom
    except ImportError as exc:
        raise RuntimeError("Word editing requires pywin32.") from exc
    pythoncom.CoInitialize()
    try:
        word, document, _title = _get_active_word_for_operation()
        selection = word.Selection
        current_text = str(selection.Text or "")
        if current_text != expected_text:
            raise RuntimeError("The Word selection changed after the preview. Nothing was deleted; select the text again and retry.")
        selection.Delete()
        return f"Deleted the confirmed {len(expected_text)}-character selection from {document.Name!r}. The document is modified but not saved."
    finally:
        pythoncom.CoUninitialize()


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



def close_website_tab(name: str) -> str:
    """Close a matching, currently active browser tab; never terminate the browser process."""
    key = " ".join(str(name).casefold().split()).strip()
    aliases = {
        "youtube": ("youtube",), "google": ("google",), "github": ("github",),
        "chatgpt": ("chatgpt",), "gemini": ("gemini",), "claude": ("claude",),
        "leetcode": ("leetcode",), "netlify": ("netlify",), "render": ("render",),
        "gmail": ("gmail",), "google drive": ("google drive",),
        "google docs": ("google docs",), "google sheets": ("google sheets",),
        "google maps": ("google maps",), "google meet": ("google meet",),
        "google classroom": ("google classroom",), "stackoverflow": ("stack overflow", "stackoverflow"),
        "wikipedia": ("wikipedia",), "reddit": ("reddit",), "linkedin": ("linkedin",),
        "instagram": ("instagram",), "whatsapp web": ("whatsapp",),
        "google cloud console": ("google cloud console",), "neon": ("neon",),
        "coursera": ("coursera",), "swayam": ("swayam",), "nptel": ("nptel",),
    }
    keywords = aliases.get(key)
    if not keywords:
        raise ValueError(f"Website {name!r} is not in Arthur's website-close allowlist.")
    try:
        import pygetwindow
        import pyautogui
    except ImportError as exc:
        raise RuntimeError("Closing a website tab requires pygetwindow and pyautogui from requirements-integrations.txt.") from exc
    windows = [window for window in pygetwindow.getAllWindows() if window.title and window.title.strip()]
    browser_markers = ("google chrome", "microsoft edge", "mozilla firefox", "firefox", "brave", "vivaldi", "opera")
    matches = [
        window for window in windows
        if any(term in window.title.casefold() for term in keywords)
        and any(marker in window.title.casefold() for marker in browser_markers)
    ]
    if not matches:
        raise RuntimeError(
            f"No browser window with an active {key} tab was found. Arthur can close a matching active tab; "
            "it cannot identify a background tab unless browser remote debugging is enabled."
        )
    if len(matches) > 1:
        titles = "; ".join(window.title.strip() for window in matches[:4])
        raise RuntimeError(f"More than one active {key} tab matches: {titles}. Close the intended one manually or specify a browser window.")
    window = matches[0]
    title = window.title.strip()
    handle = getattr(window, "_hWnd", None)
    if getattr(window, "isMinimized", False):
        window.restore()
    if handle and os.name == "nt":
        import ctypes
        user32 = ctypes.windll.user32
        # If the matched browser is already foreground, do not needlessly request
        # foreground rights again (Windows may deny redundant activation requests).
        if int(user32.GetForegroundWindow() or 0) != int(handle):
            window.activate()
            time.sleep(0.25)
        if int(user32.GetForegroundWindow() or 0) != int(handle):
            raise RuntimeError("Windows did not activate the matching browser window. Nothing was closed.")
    else:
        window.activate()
        time.sleep(0.25)
    pyautogui.hotkey("ctrl", "w")
    return f"Sent Ctrl+W to close the active {key} browser tab in {title!r}. The browser itself was not force-closed."

def send_current_whatsapp(*, confirmed_send: bool = False) -> str:
    if not confirmed_send:
        raise PermissionError("WhatsApp send blocked until the user confirms the recipient and complete message text.")
    import pyautogui
    title = activate_window("whatsapp", timeout=8)
    pyautogui.press("enter")
    return f"Issued Enter in {title!r} after explicit confirmation. Verify the message appears in the intended chat."


def capture_foreground_window() -> tuple[int, str]:
    """Capture the foreground HWND/title before a confirmation dialog changes focus."""
    if os.name != "nt":
        return 0, ""
    import ctypes
    user32 = ctypes.windll.user32
    hwnd = int(user32.GetForegroundWindow() or 0)
    if not hwnd:
        return 0, ""
    length = int(user32.GetWindowTextLengthW(hwnd))
    buffer = ctypes.create_unicode_buffer(max(1, length + 1))
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return hwnd, buffer.value


def type_text_to_focused_window(text: str, target_hwnd: int | None = None) -> str:
    """Paste literal text into the field that was focused when the request was issued."""
    text = _validated_text(text)
    if not target_hwnd:
        raise RuntimeError("Arthur could not capture the foreground application. Say 'type [text] in Word' or another named target instead.")
    if target_hwnd:
        if os.name != "nt":
            raise RuntimeError("Restoring a captured foreground window is currently supported only on Windows.")
        import ctypes
        user32 = ctypes.windll.user32
        if not user32.IsWindow(int(target_hwnd)):
            raise RuntimeError("The original target window no longer exists. Nothing was pasted.")
        # A voice command can be issued while another app remains foreground.
        # Keep that focus if it is still current; only request activation if it changed.
        if int(user32.GetForegroundWindow() or 0) != int(target_hwnd):
            user32.ShowWindow(int(target_hwnd), 9)  # SW_RESTORE
            user32.SetForegroundWindow(int(target_hwnd))
            time.sleep(0.25)
        if int(user32.GetForegroundWindow() or 0) != int(target_hwnd):
            raise RuntimeError(
                "Windows did not restore the original target window to the foreground. Nothing was pasted. "
                "Repeat the command while the intended app is active, or name the target explicitly."
            )
        _length = int(user32.GetWindowTextLengthW(int(target_hwnd)))
        _buffer = ctypes.create_unicode_buffer(max(1, _length + 1))
        user32.GetWindowTextW(int(target_hwnd), _buffer, len(_buffer))
        if any(marker in _buffer.value.casefold() for marker in ("arthur", "visionguide")):
            raise RuntimeError("Arthur was the foreground window when you spoke. Say 'type [text] in Word' or another named target instead.")
    try:
        import pyautogui
    except ImportError as exc:
        raise RuntimeError("Typing into desktop applications requires PyAutoGUI. Install requirements-integrations.txt.") from exc
    pyautogui.FAILSAFE = True
    _clipboard_paste(text)
    return f"Pasted {len(text)} characters into the captured foreground window. The text was not submitted or sent."


def focus_application_target(target: str, element: str = "") -> str:
    """Focus an allowlisted application and only use safe, known keyboard focus shortcuts."""
    import pyautogui
    target = " ".join(str(target).casefold().split()).strip()
    element = " ".join(str(element).casefold().split()).strip()
    aliases = {
        "file explorer": "file explorer", "explorer": "file explorer",
        "youtube": "youtube", "browser": "browser", "chrome": "chrome", "edge": "edge",
        "whatsapp": "whatsapp", "whatsapp web": "whatsapp", "gmail": "gmail",
        "google docs": "docs", "google sheets": "sheets", "google drive": "drive",
        "google contacts": "contacts", "google meet": "meet",
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
    if target in aliases:
        keyword = aliases[target]
    else:
        try:
            _normalised, keywords = _normalise_target(target)
        except ValueError as exc:
            raise ValueError("The requested application is not in the focus allowlist.") from exc
        keyword = keywords[0]
    title = activate_window(keyword, timeout=5)
    if not element:
        return f"Focused the {target} window ({title}). No text was entered."
    if element in {"search bar", "search box"} and target in {"file explorer", "explorer"}:
        pyautogui.hotkey("ctrl", "e")
        return f"Focused the File Explorer search box in {title}."
    if element in {"address bar", "url bar", "browser address bar"} and target in {"file explorer", "explorer"}:
        pyautogui.hotkey("ctrl", "l")
        return f"Focused the File Explorer address bar in {title}."
    if element in {"search bar", "search box"} and target in {"google drive"}:
        pyautogui.press("/")
        return f"Sent Google Drive's search-focus shortcut to {title}. Verify that its search box has focus before typing."
    if element in {"search bar", "search box"} and target in {"google contacts"}:
        _focus_accessible_field(element)
        return f"Focused the uniquely identified Google Contacts search field in {title}."
    if element in {"search bar", "search box"} and target in {"word", "microsoft word", "excel", "microsoft excel", "notepad", "google docs", "google sheets", "vscode", "wps docs", "wps sheets", "settings", "bluetooth settings", "wi-fi settings", "network settings", "task manager", "control panel"}:
        pyautogui.hotkey("ctrl", "f")
        return f"Opened the {target} Find field in {title}. Verify its focus before typing."
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
    if element in {"search bar", "search box"} and target in {"whatsapp", "whatsapp web", "gmail"}:
        raise RuntimeError(f"The {target} window is focused, but this application's {element} cannot be verified safely. Click the intended field before typing.")
    raise ValueError(f"The target element {element!r} is not supported for {target!r}.")

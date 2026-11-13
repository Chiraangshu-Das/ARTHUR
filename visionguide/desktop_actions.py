from __future__ import annotations

import os
import platform
import glob
import json
import re
import shutil
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus


_LAST_YOUTUBE_SEARCH_QUERY: str | None = None


WEBSITE_URLS = {
    "youtube": "https://www.youtube.com/",
    "google": "https://www.google.com/",
    "github": "https://github.com/",
    "chatgpt": "https://chatgpt.com/",
    "gemini": "https://gemini.google.com/",
    "claude": "https://claude.ai/",
    "leetcode": "https://leetcode.com/",
    "netlify": "https://app.netlify.com/",
    "render": "https://dashboard.render.com/",
    "gmail": "https://mail.google.com/",
    "google drive": "https://drive.google.com/",
    "google docs": "https://docs.google.com/",
    "google sheets": "https://sheets.google.com/",
    "google maps": "https://maps.google.com/",
    "google meet": "https://meet.google.com/",
    "google classroom": "https://classroom.google.com/",
    "stackoverflow": "https://stackoverflow.com/",
    "wikipedia": "https://www.wikipedia.org/",
    "reddit": "https://www.reddit.com/",
    "linkedin": "https://www.linkedin.com/",
    "instagram": "https://www.instagram.com/",
    "whatsapp web": "https://web.whatsapp.com/",
    "browser": "about:blank",
    "google cloud console": "https://console.cloud.google.com/",
    "google cloud": "https://console.cloud.google.com/",
    "cloud console": "https://console.cloud.google.com/",
    "neon db": "https://console.neon.tech/",
    "neon": "https://console.neon.tech/",
    "neon database": "https://console.neon.tech/",
    "google contacts": "https://contacts.google.com/",
    "contacts": "https://contacts.google.com/",
    "linkedin learning": "https://www.linkedin.com/learning/",
    "linkedln learning": "https://www.linkedin.com/learning/",
    "coursera": "https://www.coursera.org/",
    "swayam": "https://swayam.gov.in/",
    "swaym": "https://swayam.gov.in/",
    "swāyam": "https://swayam.gov.in/",
    "nptel": "https://nptel.ac.in/",
}

# Only fixed, known executable names are accepted. Never pass user speech to a shell.
WINDOWS_APPS = {
    "calculator": ["calc.exe"],
    "notepad": ["notepad.exe"],
    "file explorer": ["explorer.exe"],
    "task manager": ["taskmgr.exe"],
    "paint": ["mspaint.exe"],
    "snipping tool": ["snippingtool.exe"],
    "command prompt": ["cmd.exe"],
    "terminal": ["wt.exe"],
    "powershell": ["powershell.exe"],
    "control panel": ["control.exe"],
    "device manager": ["devmgmt.msc"],
    "resource monitor": ["resmon.exe"],
    "magnifier": ["magnify.exe"],
    "on-screen keyboard": ["osk.exe"],
    "vscode": ["code"],
    "edge": ["msedge.exe"],
    "microsoft edge": ["msedge.exe"],
    "word": ["winword.exe"],
    "microsoft word": ["winword.exe"],
    "powerpoint": ["powerpnt.exe"],
    "microsoft powerpoint": ["powerpnt.exe"],
    "excel": ["excel.exe"],
    "microsoft excel": ["excel.exe"],
    "wps office": ["wps.exe"],
    "wps docs": ["wps.exe"],
    "wps writer": ["wps.exe"],
    "wps sheets": ["et.exe"],
    "wps spreadsheets": ["et.exe"],
    "wps slides": ["wpp.exe"],
    "wps presentation": ["wpp.exe"],
    "wps pdf": ["wpspdf.exe"],
    "arduino": ["arduino-ide.exe"],
    "arduino ide": ["arduino-ide.exe"],
    "autocad": ["acad.exe"],
    "autocad 2026": ["acad.exe"],
    "python idle": ["py", "-3.14", "-m", "idlelib"],
    "idle python 3.14": ["py", "-3.14", "-m", "idlelib"],
    "picasa": ["picasa3.exe"],
    "picasa 3": ["picasa3.exe"],
    "media player": ["wmplayer.exe"],
    "windows media player": ["wmplayer.exe"],
    "recycle bin": ["explorer.exe", "shell:RecycleBinFolder"],
}

# URI handlers cover packaged Windows apps and Settings pages whose executables are
# not stable across Windows versions. These open the page/app; they do not toggle settings.
WINDOWS_URIS = {
    "whatsapp": "whatsapp:",
    "photos": "ms-photos:",
    "clock": "ms-clock:",
    "airplane mode": "ms-settings:network-airplanemode",
    "eye comfort": "ms-settings:nightlight",
    "night light": "ms-settings:nightlight",
    "energy saver": "ms-settings:batterysaver",
    "battery saver": "ms-settings:batterysaver",
}

SETTINGS_URIS = {
    "settings": "ms-settings:",
    "bluetooth settings": "ms-settings:bluetooth",
    "wi-fi settings": "ms-settings:network-wifi",
    "network settings": "ms-settings:network-status",
    "airplane mode": "ms-settings:network-airplanemode",
    "eye comfort": "ms-settings:nightlight",
    "night light": "ms-settings:nightlight",
    "energy saver": "ms-settings:batterysaver",
    "battery saver": "ms-settings:batterysaver",
}


def open_website(name: str) -> str:
    key = " ".join(str(name).lower().split())
    if key not in WEBSITE_URLS:
        raise ValueError(f"Website is not in the built-in allowlist: {name!r}.")
    url = WEBSITE_URLS[key]
    if not webbrowser.open(url, new=2):
        raise RuntimeError("The default browser did not report that it opened the page.")
    return f"Opened {key} in the default browser."


def search_youtube(query: str) -> str:
    """Open YouTube search results and retain the query for follow-up selection commands."""
    global _LAST_YOUTUBE_SEARCH_QUERY
    query = str(query).strip()
    if not query:
        raise ValueError("A YouTube search query is required.")
    url = "https://www.youtube.com/results?search_query=" + quote_plus(query)
    if not webbrowser.open(url, new=2):
        raise RuntimeError("The default browser did not report that it opened YouTube search.")
    _LAST_YOUTUBE_SEARCH_QUERY = query
    return f"Opened YouTube search results for {query}."


def _youtube_video_results_from_html(html: str) -> list[dict[str, str]]:
    """Extract ordered video results from YouTube's embedded ytInitialData JSON."""
    decoder = json.JSONDecoder()
    initial_data = None
    for marker in re.finditer(r"ytInitialData\s*=\s*", str(html)):
        try:
            initial_data, _end = decoder.raw_decode(str(html)[marker.end():])
            break
        except json.JSONDecodeError:
            continue
    if initial_data is None:
        raise RuntimeError("YouTube did not return a readable search-results payload. Open the results page and try again.")

    results: list[dict[str, str]] = []
    seen: set[str] = set()

    def visit(node):
        if isinstance(node, dict):
            renderer = node.get("videoRenderer")
            if isinstance(renderer, dict):
                video_id = str(renderer.get("videoId", "")).strip()
                title_node = renderer.get("title") or {}
                if isinstance(title_node, dict):
                    runs = title_node.get("runs") or []
                    title = "".join(str(item.get("text", "")) for item in runs if isinstance(item, dict))
                    if not title:
                        title = str(title_node.get("simpleText", ""))
                else:
                    title = ""
                if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) and video_id not in seen:
                    seen.add(video_id)
                    results.append({"video_id": video_id, "title": title.strip() or "Untitled video"})
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(initial_data)
    if not results:
        raise RuntimeError("No standard YouTube videos were found in those search results. Try a different search phrase.")
    return results


def play_youtube_result(index: int = 1) -> str:
    """Open a numbered result from the last YouTube search, requesting autoplay."""
    index = int(index)
    if not 1 <= index <= 20:
        raise ValueError("YouTube result number must be between 1 and 20.")
    query = _LAST_YOUTUBE_SEARCH_QUERY
    if not query:
        raise RuntimeError("I do not have an active YouTube search. First say 'search YouTube for ...', then ask me to play a result.")

    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("Selecting a YouTube result requires the existing requests dependency. Install the project requirements.") from exc

    search_url = "https://www.youtube.com/results?search_query=" + quote_plus(query)
    try:
        response = requests.get(
            search_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"},
            timeout=15,
        )
        response.raise_for_status()
        results = _youtube_video_results_from_html(response.text)
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError(f"Could not retrieve YouTube results for {query!r}: {exc}") from exc

    if index > len(results):
        raise RuntimeError(f"YouTube returned only {len(results)} video result(s); there is no result number {index}.")
    selected = results[index - 1]
    watch_url = f"https://www.youtube.com/watch?v={selected['video_id']}&autoplay=1"
    if not webbrowser.open(watch_url, new=2):
        raise RuntimeError("The default browser did not report that it opened the selected YouTube video.")
    title = selected["title"]
    return f"Opened YouTube video {index}: {title}. Autoplay was requested; browser autoplay settings may still require a click."


def search_web(query: str) -> str:
    query = str(query).strip()
    if not query:
        raise ValueError("A web search query is required.")
    url = "https://www.google.com/search?q=" + quote_plus(query)
    if not webbrowser.open(url, new=2):
        raise RuntimeError("The default browser did not report that it opened web search.")
    return f"Opened web search results for {query}."


def _office_registry_path(executable: str) -> str | None:
    """Find Click-to-Run Office executables through Windows App Paths/Office registry."""
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None
    subkeys = [
        fr"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{executable}",
        fr"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\{executable}",
    ]
    office_app = {"winword.exe": "Word", "excel.exe": "Excel", "powerpnt.exe": "PowerPoint"}.get(executable.casefold())
    if office_app:
        for version in ("16.0", "15.0", "14.0"):
            subkeys.extend([
                fr"SOFTWARE\Microsoft\Office\{version}\{office_app}\InstallRoot",
                fr"SOFTWARE\WOW6432Node\Microsoft\Office\{version}\{office_app}\InstallRoot",
            ])
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for subkey in subkeys:
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    for value_name in (None, "Path"):
                        try:
                            value, _kind = winreg.QueryValueEx(key, value_name)
                        except OSError:
                            continue
                        candidate = str(value).strip().strip('"')
                        if candidate and os.path.isdir(candidate) and office_app:
                            candidate = str(Path(candidate) / executable)
                        if candidate and os.path.isfile(candidate):
                            return candidate
            except OSError:
                continue
    return None


def _office_start_menu_shortcut(app_label: str) -> str | None:
    """Return a matching Office Start Menu shortcut, if present."""
    if os.name != "nt":
        return None
    roots = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    matches = []
    wanted = app_label.casefold()
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for shortcut in root.rglob("*.lnk"):
                name = shortcut.stem.casefold()
                if wanted in name and ("office" in str(shortcut.parent).casefold() or "microsoft" in name or name in {"word", "excel", "powerpoint"}):
                    matches.append(shortcut)
        except OSError:
            continue
    return str(sorted(matches, key=lambda item: len(str(item)))[0]) if matches else None


def open_app(name: str) -> str:
    key = " ".join(str(name).lower().split())
    if key in SETTINGS_URIS or key in WINDOWS_URIS:
        if os.name != "nt":
            raise RuntimeError("Windows app and Settings shortcuts are only available on Windows.")
        os.startfile(SETTINGS_URIS.get(key, WINDOWS_URIS.get(key)))  # type: ignore[attr-defined]
        return f"Opened {key}."
    # Instagram is an allowlisted service, so the app alias opens its official website.
    if key == "instagram":
        return open_website("instagram")
    if key not in WINDOWS_APPS:
        raise ValueError(f"Application is not in the built-in allowlist: {name!r}.")
    if os.name != "nt":
        raise RuntimeError("This application launcher is configured for Windows. Use the matching platform launcher to port it.")
    command = list(WINDOWS_APPS[key])
    # Resolve common third-party apps from PATH and known default install locations.
    executable = command[0]
    candidates = []
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    exe_key = executable.lower()
    if exe_key == "acad.exe":
        candidates += [fr"{program_files}\Autodesk\AutoCAD 2026\acad.exe", fr"{program_files_x86}\Autodesk\AutoCAD 2026\acad.exe"]
    elif exe_key == "picasa3.exe":
        candidates += [fr"{program_files}\Google\Picasa3\Picasa3.exe", fr"{program_files_x86}\Google\Picasa3\Picasa3.exe"]
    elif exe_key == "arduino-ide.exe":
        candidates += [fr"{program_files}\Arduino IDE\Arduino IDE.exe", fr"{local_app_data}\Programs\Arduino IDE\Arduino IDE.exe", fr"{program_files}\Arduino IDE\arduino-ide.exe"]
    elif exe_key in {"wps.exe", "et.exe", "wpp.exe", "wpspdf.exe"}:
        candidates += [
            *glob.glob(fr"{program_files}\Kingsoft\WPS Office\*\office6\{executable}"),
            *glob.glob(fr"{program_files_x86}\Kingsoft\WPS Office\*\office6\{executable}"),
            fr"{program_files}\Kingsoft\WPS Office\office6\{executable}",
            fr"{program_files_x86}\Kingsoft\WPS Office\office6\{executable}",
        ]
    elif exe_key in {"winword.exe", "powerpnt.exe", "excel.exe"}:
        for office_version in ("Office16", "Office15", "Office14"):
            candidates += [
                fr"{program_files}\Microsoft Office\root\{office_version}\{executable}",
                fr"{program_files_x86}\Microsoft Office\root\{office_version}\{executable}",
                fr"{program_files}\Microsoft Office\{office_version}\{executable}",
                fr"{program_files_x86}\Microsoft Office\{office_version}\{executable}",
            ]
    elif exe_key == "msedge.exe":
        candidates += [fr"{program_files}\Microsoft\Edge\Application\msedge.exe", fr"{program_files_x86}\Microsoft\Edge\Application\msedge.exe"]
    found = next((candidate for candidate in candidates if os.path.isfile(candidate)), None)
    if not found and exe_key in {"winword.exe", "powerpnt.exe", "excel.exe"}:
        found = _office_registry_path(executable)
        if not found:
            label = {"winword.exe": "Word", "powerpnt.exe": "PowerPoint", "excel.exe": "Excel"}[exe_key]
            found = _office_start_menu_shortcut(label)
    if found:
        if found.lower().endswith(".lnk"):
            os.startfile(found)  # type: ignore[attr-defined]
            return f"Opened {key} using its Start Menu shortcut."
        command[0] = found
    elif shutil.which(executable) is None and not os.path.isfile(executable):
        # Keep the Python launcher command intact; py.exe is the supported version selector.
        if executable.lower() == "py" and shutil.which("py"):
            pass
        elif executable.lower() in {"acad.exe", "picasa3.exe", "arduino-ide.exe", "wps.exe", "et.exe", "wpp.exe", "wpspdf.exe", "winword.exe", "powerpnt.exe", "excel.exe"}:
            raise RuntimeError(
                f"{key} was not found. Arthur checked PATH, common install folders, Office registry entries, "
                "and the Start Menu. Confirm that the desktop application is installed; Store/web-only editions may need to be opened manually."
            )
    try:
        subprocess.Popen(command, shell=False, close_fds=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"{key} was not found. It may not be installed or may not be on PATH.") from exc
    return f"Launched {key}."


def close_application(name: str) -> str:
    """Send a graceful close request to an explicitly allowlisted window; never kill a process."""
    aliases = {
        "word": ("word", "winword"), "excel": ("excel",),
        "powerpoint": ("powerpoint",), "notepad": ("notepad",),
        "calculator": ("calculator",), "file explorer": ("file explorer", "explorer"),
        "chrome": ("chrome", "google chrome"), "edge": ("edge", "microsoft edge"),
        "firefox": ("firefox",), "vscode": ("visual studio code", "vscode"),
        "whatsapp": ("whatsapp",), "autocad": ("autocad",),
        "arduino": ("arduino ide", "arduino"), "terminal": ("terminal", "windows terminal"),
        "powershell": ("powershell",), "command prompt": ("command prompt", "cmd"),
        "paint": ("paint",), "snipping tool": ("snipping tool",),
    }
    key = " ".join(str(name).casefold().split())
    keywords = aliases.get(key)
    if not keywords:
        raise ValueError(f"Closing {name!r} is not supported. Choose a named application from Arthur's close-app allowlist.")
    if os.name != "nt":
        raise RuntimeError("Graceful application-window closing is currently supported only on Windows.")
    try:
        import pygetwindow
    except ImportError as exc:
        raise RuntimeError("Closing application windows requires pygetwindow. Install requirements-integrations.txt.") from exc
    windows = [window for window in pygetwindow.getAllWindows() if window.title and window.title.strip()]
    matches = [window for window in windows if any(term in window.title.casefold() for term in keywords)]
    if not matches:
        raise RuntimeError(f"No open {key} window was found. It may already be closed or have a different window title.")
    # Prefer a visible, non-minimized matching window, then the shortest title.
    matches.sort(key=lambda window: (bool(getattr(window, "isMinimized", False)), len(window.title)))
    window = matches[0]
    title = window.title.strip()
    try:
        closed = window.close()
    except Exception as exc:
        raise RuntimeError(f"Windows refused the close request for {title!r}: {exc}") from exc
    if closed is False:
        raise RuntimeError(f"Windows did not accept the close request for {title!r}.")
    return f"Sent a normal close request to {title!r}. If the app has unsaved work, complete its save prompt."


def open_folder(name: str, project_dir: Path) -> str:
    home = Path.home()
    locations = {
        "downloads": home / "Downloads",
        "documents": home / "Documents",
        "desktop": home / "Desktop",
        "pictures": home / "Pictures",
        "project": Path(project_dir).resolve(),
    }
    key = str(name).lower().strip()
    if key not in locations:
        raise ValueError("Folder is not in the built-in folder allowlist.")
    path = locations[key]
    if not path.exists():
        raise FileNotFoundError(f"Folder does not exist: {path}")
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        webbrowser.open(path.as_uri(), new=2)
    return f"Opened {key} folder."


def open_document(path: Path) -> str:
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"File does not exist: {path}")
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        webbrowser.open(path.as_uri(), new=2)
    return f"Opened {path.name}."


def capture_screen(snapshots_dir: Path) -> Path:
    """Capture all visible monitors. Does not upload the image anywhere."""
    try:
        from PIL import ImageGrab
    except ImportError as exc:
        raise RuntimeError("Screen capture requires Pillow. Install the project requirements.") from exc
    snapshots_dir = Path(snapshots_dir)
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = snapshots_dir / f"screenshot_{stamp}.png"
    try:
        image = ImageGrab.grab(all_screens=True)
        image.save(path)
    except Exception as exc:
        raise RuntimeError(f"Screen capture failed: {exc}") from exc
    return path


def image_file_to_bgr(path: Path):
    """Load a screenshot as OpenCV BGR pixels for the existing visual-Q&A adapter."""
    try:
        import cv2
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Screen-image conversion requires OpenCV, NumPy, and Pillow.") from exc
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)



def find_latest_pdf() -> Path:
    """Find the most recently modified PDF in common user folders (top level only)."""
    home = Path.home()
    roots = [home / "Downloads", home / "Documents", home / "Desktop"]
    candidates: list[Path] = []
    for root in roots:
        if root.is_dir():
            try:
                candidates.extend(p for p in root.glob("*.pdf") if p.is_file())
            except OSError:
                continue
    if not candidates:
        raise FileNotFoundError("No PDF was found directly in Downloads, Documents, or Desktop.")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def check_internet_connectivity() -> str:
    """Do a lightweight connectivity probe without sending user content."""
    import socket
    errors: list[str] = []
    for host in ("1.1.1.1", "8.8.8.8"):
        try:
            with socket.create_connection((host, 53), timeout=1.8):
                return "A connection to an external DNS service succeeded. Internet connectivity is reachable."
        except OSError as exc:
            errors.append(f"{host}: {exc.__class__.__name__}")
    return "The connectivity probe could not reach the tested DNS endpoints. This does not prove there is no internet; a firewall or network policy may block the probe. " + "; ".join(errors)

def system_status() -> str:
    parts = [f"Operating system: {platform.platform()}."]
    try:
        import psutil
        memory = psutil.virtual_memory()
        parts.append(f"RAM usage is {memory.percent:.0f} percent ({memory.used / (1024**3):.1f} of {memory.total / (1024**3):.1f} GB).")
        try:
            battery = psutil.sensors_battery()
            if battery is not None:
                parts.append(f"Battery is at {battery.percent:.0f} percent.")
        except Exception:
            pass
    except ImportError:
        parts.append("Install psutil for RAM and battery details.")
    usage = shutil.disk_usage(Path.home())
    parts.append(f"The drive containing your home folder has {usage.free / (1024**3):.1f} GB free of {usage.total / (1024**3):.1f} GB.")
    return " ".join(parts)


def calculate_expression(expression: str) -> tuple[str, int | float]:
    """Safely calculate a basic arithmetic expression without eval/exec or shell access."""
    import ast
    import operator

    expression = str(expression).strip()
    if not expression or len(expression) > 120:
        raise ValueError("Enter a short arithmetic expression.")
    # Reject anything outside the arithmetic character set before parsing.
    if not re.fullmatch(r"[0-9\s.+\-*/()%]+", expression):
        raise ValueError("Only numbers, parentheses, and + - * / % operators are supported.")
    tree = ast.parse(expression, mode="eval")
    operators = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod, ast.Pow: operator.pow, ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }
    def visit(node):
        if isinstance(node, ast.Expression): return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            if abs(node.value) > 10**12: raise ValueError("Numbers must be at most 1 trillion in magnitude.")
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in operators:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 12:
                raise ValueError("Exponent magnitude is limited to 12.")
            result = operators[type(node.op)](left, right)
            if isinstance(result, complex) or not isinstance(result, (int, float)) or abs(result) > 10**18:
                raise ValueError("The result is outside the supported range.")
            return result
        if isinstance(node, ast.UnaryOp) and type(node.op) in operators:
            return operators[type(node.op)](visit(node.operand))
        raise ValueError("Unsupported arithmetic expression.")
    try:
        result = visit(tree)
    except (ZeroDivisionError, OverflowError) as exc:
        raise ValueError(f"Could not calculate this expression: {exc}") from exc
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return expression, result


def calculator_calculate(expression: str) -> str:
    """Open Windows Calculator, enter an allowlisted expression, and report local calculation."""
    original, result = calculate_expression(expression)
    if os.name == "nt":
        open_app("calculator")
        try:
            from visionguide.integrations.gui_automation import activate_window
            import pyautogui
            import time
            title = activate_window("calculator", timeout=12)
            pyautogui.hotkey("ctrl", "a")
            pyautogui.write(original, interval=0.025)
            pyautogui.press("enter")
            time.sleep(0.2)
            return f"Opened Calculator and entered {original}. The locally calculated result is {result}; verify the displayed Calculator result on screen."
        except Exception as exc:
            return f"Calculated {original} = {result}, but Calculator input could not be verified ({exc})."
    return f"Calculated {original} = {result}. Opening Windows Calculator is only supported on Windows."

from __future__ import annotations

import os
import platform
import re
import subprocess
import time
from typing import Literal


def _require_windows(feature: str) -> None:
    if os.name != "nt":
        raise RuntimeError(f"{feature} is currently implemented for Windows desktop clients.")


def _pyautogui():
    try:
        import pyautogui
        import pygetwindow
    except ImportError as exc:
        raise RuntimeError("Desktop controls require pyautogui and pygetwindow. Install requirements-integrations.txt.") from exc
    pyautogui.FAILSAFE = True
    return pyautogui, pygetwindow


def _activate_target_window(keywords: tuple[str, ...] = ("youtube", "chrome", "edge", "firefox")) -> str:
    """Activate an existing browser window rather than injecting into an arbitrary app."""
    pyautogui, pygetwindow = _pyautogui()
    titles = [w for w in pygetwindow.getAllWindows() if w.title and w.title.strip()]
    preferred = [w for w in titles if any(k in w.title.casefold() for k in keywords)]
    if not preferred:
        raise RuntimeError("No matching browser window is open. Open YouTube in a browser first.")
    # Prefer a YouTube tab/window, then any known browser window.
    preferred.sort(key=lambda w: ("youtube" not in w.title.casefold(), len(w.title)))
    window = preferred[0]
    try:
        if window.isMinimized:
            window.restore()
        window.activate()
        time.sleep(0.15)
    except Exception as exc:
        raise RuntimeError(f"Could not activate browser window {window.title!r}: {exc}") from exc
    return window.title


def media_playback(action: str, seconds: int = 10) -> str:
    """Control YouTube/browser playback using YouTube keyboard shortcuts.

    Stop maps to pause because browser video elements do not expose a universal stop key.
    """
    key = str(action).lower().strip().replace(" ", "_")
    if key not in {"play", "pause", "stop", "toggle", "next", "previous", "forward", "back"}:
        raise ValueError("Playback action must be play, pause, stop, toggle, next, previous, forward, or back.")
    if not 1 <= int(seconds) <= 600:
        raise ValueError("Skip amount must be between 1 and 600 seconds.")
    pyautogui, _ = _pyautogui()
    title = _activate_target_window(("youtube", "chrome", "edge", "firefox", "browser"))
    # The YouTube K/J/L keys require the player to have focus. Space may scroll a page,
    # so click focus remains the user's responsibility if the page/player is not focused.
    if key in {"play", "pause", "stop", "toggle"}:
        pyautogui.press("k")  # toggle: when already playing, pause; when paused, play
        label = "Paused or resumed"
    elif key == "next":
        pyautogui.hotkey("shift", "n")
        label = "Skipped to the next video"
    elif key == "previous":
        pyautogui.hotkey("shift", "p")
        label = "Requested the previous video"
    else:
        # YouTube has fixed 10-second J/L shortcuts; repeat for larger requests.
        key_name = "l" if key == "forward" else "j"
        count = max(1, min(60, round(int(seconds) / 10)))
        for _ in range(count):
            pyautogui.press(key_name)
            time.sleep(0.035)
        label = f"Skipped {'forward' if key == 'forward' else 'back'} approximately {count * 10} seconds"
    return f"{label} in browser window {title!r}. If playback did not change, focus the YouTube player and retry."


def get_brightness() -> int:
    try:
        import screen_brightness_control as sbc
    except ImportError as exc:
        raise RuntimeError("Brightness control requires screen-brightness-control. Install requirements-integrations.txt.") from exc
    values = sbc.get_brightness()
    if not values:
        raise RuntimeError("No controllable display brightness value was reported.")
    return int(values[0])


def set_brightness(level: int) -> str:
    level = int(level)
    if not 0 <= level <= 100:
        raise ValueError("Brightness must be between 0 and 100.")
    try:
        import screen_brightness_control as sbc
    except ImportError as exc:
        raise RuntimeError("Brightness control requires screen-brightness-control. Install requirements-integrations.txt.") from exc
    result = sbc.set_brightness(level)
    return f"Requested display brightness {level} percent. Provider result: {result!s}."


def get_volume() -> dict[str, int | bool]:
    _require_windows("OS audio control")
    try:
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    except ImportError as exc:
        raise RuntimeError("Audio controls require pycaw and comtypes. Install requirements-integrations.txt.") from exc
    device = AudioUtilities.GetSpeakers()
    interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    endpoint = cast(interface, POINTER(IAudioEndpointVolume))
    return {"volume": int(round(endpoint.GetMasterVolumeLevelScalar() * 100)), "muted": bool(endpoint.GetMute())}


def set_volume(level: int) -> str:
    _require_windows("OS audio control")
    level = int(level)
    if not 0 <= level <= 100:
        raise ValueError("Volume must be between 0 and 100.")
    try:
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    except ImportError as exc:
        raise RuntimeError("Audio controls require pycaw and comtypes. Install requirements-integrations.txt.") from exc
    device = AudioUtilities.GetSpeakers()
    interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    endpoint = cast(interface, POINTER(IAudioEndpointVolume))
    endpoint.SetMasterVolumeLevelScalar(level / 100.0, None)
    return f"System volume set to {level} percent."


def set_mute(muted: bool) -> str:
    _require_windows("OS audio control")
    try:
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    except ImportError as exc:
        raise RuntimeError("Audio controls require pycaw and comtypes. Install requirements-integrations.txt.") from exc
    device = AudioUtilities.GetSpeakers()
    interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    endpoint = cast(interface, POINTER(IAudioEndpointVolume))
    endpoint.SetMute(1 if muted else 0, None)
    return "System audio muted." if muted else "System audio unmuted."


def list_wifi_adapters() -> list[dict[str, str]]:
    _require_windows("Wi-Fi adapter management")
    result = subprocess.run(
        ["netsh", "interface", "show", "interface"], capture_output=True, text=True,
        timeout=8, check=False, shell=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"netsh could not list network interfaces: {(result.stderr or result.stdout).strip()}")
    adapters: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        # Output columns are Admin State, State, Type, Interface Name; the name may contain spaces.
        match = re.match(r"^\s*(Enabled|Disabled)\s+(Connected|Disconnected|Connecting|Media disconnected|Disabled|Not connected)\s+(.+?)\s{2,}(.+?)\s*$", line, re.I)
        if match:
            adapters.append({"admin_state": match.group(1), "state": match.group(2), "type": match.group(3), "name": match.group(4)})
    return adapters


def set_wifi(enabled: bool, adapter: str | None = None) -> str:
    """Enable/disable one specifically named Wi-Fi adapter; requires elevated privileges on Windows."""
    _require_windows("Wi-Fi adapter management")
    wanted = (adapter or os.getenv("VISIONGUIDE_WIFI_ADAPTER", "Wi-Fi")).strip()
    if not wanted or len(wanted) > 80:
        raise ValueError("A valid Wi-Fi adapter name is required.")
    if '"' in wanted or "\n" in wanted or "\r" in wanted:
        raise ValueError("Invalid Wi-Fi adapter name.")
    # Confirm that the requested name exists before issuing the state-changing command.
    adapters = list_wifi_adapters()
    if not any(a["name"].casefold() == wanted.casefold() for a in adapters):
        names = ", ".join(a["name"] for a in adapters) or "none detected"
        raise ValueError(f"Adapter {wanted!r} was not found. Detected interfaces: {names}.")
    admin_state = "enabled" if enabled else "disabled"
    result = subprocess.run(
        ["netsh", "interface", "set", "interface", f"name={wanted}", f"admin={admin_state}"],
        capture_output=True, text=True, timeout=10, check=False, shell=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Could not {admin_state} {wanted!r}. Administrator permission may be required. {detail}")
    return f"Requested that Wi-Fi adapter {wanted!r} be {admin_state}. Verify connectivity after the change."


def adjust_brightness(delta: int) -> str:
    delta = int(delta)
    if not -50 <= delta <= 50 or delta == 0:
        raise ValueError("Brightness adjustment must be between -50 and 50 percentage points, excluding zero.")
    current = get_brightness()
    target = max(0, min(100, current + delta))
    set_brightness(target)
    return f"Display brightness adjusted from {current} to {target} percent."


def adjust_volume(delta: int) -> str:
    delta = int(delta)
    if not -50 <= delta <= 50 or delta == 0:
        raise ValueError("Volume adjustment must be between -50 and 50 percentage points, excluding zero.")
    state = get_volume()
    target = max(0, min(100, int(state["volume"]) + delta))
    set_volume(target)
    return f"System volume adjusted from {state['volume']} to {target} percent."

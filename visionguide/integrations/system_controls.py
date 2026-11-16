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



def _with_audio_endpoint(operation):
    """Run a pycaw endpoint-volume operation with balanced COM initialization."""
    _require_windows("OS audio control")

    try:
        from comtypes import CoInitialize, CoUninitialize
        from pycaw.pycaw import AudioUtilities
    except ImportError as exc:
        raise RuntimeError(
            "Audio controls require pycaw and comtypes. "
            "Install requirements-integrations.txt."
        ) from exc

    initialized = False
    try:
        CoInitialize()
        initialized = True

        device = AudioUtilities.GetSpeakers()
        endpoint = device.EndpointVolume

        return operation(endpoint)

    except Exception as exc:
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError(
            f"Windows audio endpoint operation failed: {exc}"
        ) from exc

    finally:
        if initialized:
            try:
                CoUninitialize()
            except Exception:
                pass


def get_volume() -> dict[str, int | bool]:
    return _with_audio_endpoint(
        lambda endpoint: {
            "volume": int(round(endpoint.GetMasterVolumeLevelScalar() * 100)),
            "muted": bool(endpoint.GetMute()),
        }
    )


def set_volume(level: int) -> str:
    level = int(level)
    if not 0 <= level <= 100:
        raise ValueError("Volume must be between 0 and 100.")
    _with_audio_endpoint(lambda endpoint: endpoint.SetMasterVolumeLevelScalar(level / 100.0, None))
    return f"System volume set to {level} percent."


def set_mute(muted: bool) -> str:
    _with_audio_endpoint(lambda endpoint: endpoint.SetMute(1 if muted else 0, None))
    return "System audio muted." if muted else "System audio unmuted."


def _run_winrt_radio_coroutine(coroutine):
    """Run a WinRT coroutine safely from either a plain thread or an active asyncio loop."""
    import asyncio
    import threading

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    result: dict[str, object] = {}
    finished = threading.Event()

    def runner():
        try:
            result["value"] = asyncio.run(coroutine)
        except BaseException as exc:
            result["error"] = exc
        finally:
            finished.set()

    thread = threading.Thread(target=runner, name="arthur-winrt-radio", daemon=True)
    thread.start()
    if not finished.wait(15.0):
        raise TimeoutError("Windows radio operation timed out after 15 seconds.")
    if "error" in result:
        raise result["error"]  # type: ignore[misc]
    return result.get("value")


def _radio_name(radio) -> str:
    kind = getattr(radio, "kind", None)
    name = str(getattr(kind, "name", kind)).casefold().replace("_", "")
    if "bluetooth" in name:
        return "bluetooth"
    if "wifi" in name or "wi-fi" in name:
        return "wifi"
    return ""


def _radio_state_name(radio) -> str:
    state = getattr(radio, "state", None)
    return str(getattr(state, "name", state)).split(".")[-1].replace("_", " ").title()


async def _get_winrt_radios():
    try:
        from winrt.windows.devices.radios import Radio
    except ImportError as exc:
        raise RuntimeError(
            "Windows Wi-Fi/Bluetooth radio control requires WinRT Radio support. "
            "Run `python -m pip install -r requirements-navigation.txt` and restart Arthur."
        ) from exc
    return await Radio.get_radios_async()


def get_radio_states() -> dict[str, str]:
    """Read the Windows Wi-Fi and Bluetooth radio states, without changing them."""
    _require_windows("Wi-Fi/Bluetooth radio status")

    async def read_states():
        radios = await _get_winrt_radios()
        states: dict[str, str] = {}
        for radio in radios:
            key = _radio_name(radio)
            if key:
                states[key] = _radio_state_name(radio)
        return states

    states = _run_winrt_radio_coroutine(read_states())
    return {"wifi": states.get("wifi", "not detected"), "bluetooth": states.get("bluetooth", "not detected")}


def _set_windows_radio(kind: str, enabled: bool) -> str:
    _require_windows(f"{kind.title()} radio control")

    async def change_state():
        from winrt.windows.devices.radios import Radio, RadioAccessStatus, RadioState

        radios = await _get_winrt_radios()
        matches = [radio for radio in radios if _radio_name(radio) == kind]
        if not matches:
            raise RuntimeError(f"Windows did not report a {kind.title()} radio. Check the device driver and hardware switch.")

        access = await Radio.request_access_async()
        if access != RadioAccessStatus.ALLOWED:
            raise PermissionError(
                f"Windows denied permission to change the {kind.title()} radio (access status: {access}). "
                "Check Windows privacy/device policy and try again."
            )

        desired = RadioState.ON if enabled else RadioState.OFF
        target = matches[0]
        result = await target.set_state_async(desired)
        if result != RadioAccessStatus.ALLOWED:
            raise PermissionError(
                f"Windows did not allow the {kind.title()} radio change (status: {result}). "
                "A hardware switch, airplane mode, device policy, or driver may be overriding it."
            )

        # Re-enumerate after the operation. Do not report success based only on a
        # command being accepted: the actual radio state must match the request.
        import asyncio
        expected = "On" if enabled else "Off"
        for _ in range(5):
            await asyncio.sleep(0.25)
            refreshed = await _get_winrt_radios()
            current = next((radio for radio in refreshed if _radio_name(radio) == kind), None)
            if current is not None and _radio_state_name(current) == expected:
                return expected
        actual = _radio_state_name(current) if current is not None else "not detected"
        raise RuntimeError(
            f"Windows accepted the {kind.title()} radio request but its reported state is {actual!r}, not {expected!r}. "
            "Check airplane mode, hardware controls, and the device driver."
        )

    state = _run_winrt_radio_coroutine(change_state())
    return f"Windows {kind.title()} radio is now verified {str(state).lower()}."


def set_bluetooth(enabled: bool) -> str:
    return _set_windows_radio("bluetooth", bool(enabled))


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
    """Turn the Windows Wi-Fi radio on/off (not the underlying NIC admin state).

    ``adapter`` is retained for backwards compatibility with older callers but is
    no longer used: Windows Radio controls the platform radio rather than disabling
    an arbitrary network interface.
    """
    return _set_windows_radio("wifi", bool(enabled))


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

from __future__ import annotations

import os
import tkinter as tk
from typing import Callable


class SystemVirtualKeyboard:
    """Mouse-operated keyboard overlay for the currently focused Windows app.

    The window uses WS_EX_NOACTIVATE so clicking its buttons should not take
    keyboard focus away from the target application.
    """

    KEY_ROWS = (
        ("Esc", "esc"), ("F1", "f1"), ("F2", "f2"), ("F3", "f3"),
        ("F4", "f4"), ("F5", "f5"), ("F6", "f6"), ("F7", "f7"),
        ("F8", "f8"), ("F9", "f9"), ("F10", "f10"), ("F11", "f11"),
        ("F12", "f12"),
    )

    # Labels show the normal key and its Shift output. The internal key value
    # remains the unshifted key; _press() applies Shift when appropriate.
    CHAR_ROWS = (
        (
            ("` ~", "`"), ("1 !", "1"), ("2 @", "2"), ("3 #", "3"),
            ("4 $", "4"), ("5 %", "5"), ("6 ^", "6"), ("7 &", "7"),
            ("8 *", "8"), ("9 (", "9"), ("0 )", "0"), ("- _", "-"),
            ("= +", "="), ("Backspace", "backspace"),
        ),
        (
            ("Tab", "tab"), ("Q", "q"), ("W", "w"), ("E", "e"),
            ("R", "r"), ("T", "t"), ("Y", "y"), ("U", "u"),
            ("I", "i"), ("O", "o"), ("P", "p"), ("[ {", "["),
            ("] }", "]"), ("\\ |", "\\"),
        ),
        (
            ("Caps Lock", "caps"), ("A", "a"), ("S", "s"), ("D", "d"),
            ("F", "f"), ("G", "g"), ("H", "h"), ("J", "j"),
            ("K", "k"), ("L", "l"), ("; :", ";"), ("' \"", "'"),
            ("Enter", "enter"),
        ),
        (
            ("Shift", "shift"), ("Z", "z"), ("X", "x"), ("C", "c"),
            ("V", "v"), ("B", "b"), ("N", "n"), ("M", "m"),
            (", <", ","), (". >", "."), ("/ ?", "/"), ("Shift", "shift"),
        ),
    )

    NAV_KEYS = (
        ("Ctrl", "ctrl"), ("Win", "win"), ("Alt", "alt"), ("Space", "space"),
        ("AltGr", "altgr"), ("←", "left"), ("↑", "up"), ("↓", "down"),
        ("→", "right"), ("Insert", "insert"), ("Delete", "delete"),
        ("Home", "home"), ("End", "end"), ("PgUp", "pageup"),
        ("PgDn", "pagedown"),
    )

    # Shifted punctuation is sent as Shift + its physical/base key. This is
    # more reliable with PyAutoGUI than trying to press punctuation directly.
    SHIFTED_KEYS = {
        "`": "~",
        "1": "!",
        "2": "@",
        "3": "#",
        "4": "$",
        "5": "%",
        "6": "^",
        "7": "&",
        "8": "*",
        "9": "(",
        "0": ")",
        "-": "_",
        "=": "+",
        "[": "{",
        "]": "}",
        "\\": "|",
        ";": ":",
        "'": '"',
        ",": "<",
        ".": ">",
        "/": "?",
    }

    def __init__(
        self,
        root: tk.Misc,
        on_status: Callable[[str], None] | None = None,
    ):
        self.root = root
        self.on_status = on_status or (lambda _message: None)
        self.window: tk.Toplevel | None = None
        self.status_label: tk.Label | None = None
        self._buttons: dict[str, tk.Button] = {}
        self._modifiers: set[str] = set()
        self._caps_lock = False

    @property
    def is_open(self) -> bool:
        return self.window is not None and bool(self.window.winfo_exists())

    def toggle(self) -> str:
        if self.is_open:
            self.close()
            return "System virtual keyboard closed."
        self.open()
        return (
            "System virtual keyboard opened. Click a target application first, "
            "then use the keyboard."
        )

    def open(self) -> None:
        if self.is_open:
            self.window.deiconify()
            self.window.lift()
            return

        if os.name != "nt":
            raise RuntimeError(
                "The system-wide virtual keyboard currently supports "
                "Windows 10/11 only."
            )

        try:
            import pyautogui  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "The system virtual keyboard requires PyAutoGUI. "
                "Install requirements-integrations.txt."
            ) from exc

        self._caps_lock = self._read_windows_caps_lock()

        window = tk.Toplevel(self.root)
        self.window = window
        window.title("Arthur — System Virtual Keyboard")
        window.configure(bg="#101820")
        window.attributes("-topmost", True)
        window.resizable(True, False)
        window.geometry("1120x365+120+480")
        window.protocol("WM_DELETE_WINDOW", self.close)

        header = tk.Frame(window, bg="#17232d", padx=10, pady=6)
        header.pack(fill="x")

        tk.Label(
            header,
            text="ARTHUR SYSTEM KEYBOARD",
            bg="#17232d",
            fg="#edf3f5",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        tk.Label(
            header,
            text=(
                "Select a target app outside this keyboard; key clicks "
                "should not activate this window."
            ),
            bg="#17232d",
            fg="#9eb0ba",
            font=("Segoe UI", 8),
        ).pack(side="left", padx=12)

        self.status_label = tk.Label(
            window,
            text="Ready — target is whichever Windows app currently has keyboard focus.",
            bg="#101820",
            fg="#4fd1a5",
            anchor="w",
            padx=8,
        )
        self.status_label.pack(fill="x")

        body = tk.Frame(window, bg="#101820", padx=6, pady=3)
        body.pack(fill="both", expand=True)

        function_row = tk.Frame(body, bg="#101820")
        function_row.pack(fill="x", pady=2)
        for label, key in self.KEY_ROWS:
            self._add_key(function_row, label, key, width=5)

        for row in self.CHAR_ROWS:
            row_frame = tk.Frame(body, bg="#101820")
            row_frame.pack(fill="x", pady=2)
            for label, key in row:
                if key in {"backspace", "enter", "caps"}:
                    width = 11 if key != "enter" else 9
                elif key in {"tab", "shift"}:
                    width = 8
                else:
                    width = 5
                self._add_key(row_frame, label, key, width=width)

        bottom = tk.Frame(body, bg="#101820")
        bottom.pack(fill="x", pady=2)
        for label, key in self.NAV_KEYS:
            width = 13 if key == "space" else 6
            self._add_key(bottom, label, key, width=width)
        self._add_key(bottom, "Close", "close", width=7, accent=False)

        window.update_idletasks()
        self._set_button_state("caps", self._caps_lock)
        self._set_windows_no_activate(window)
        self.on_status(
            "System virtual keyboard opened. Select a target app outside "
            "the keyboard, then click keys here."
        )

    def _set_windows_no_activate(self, window: tk.Toplevel) -> None:
        """Apply WS_EX_NOACTIVATE while keeping the keyboard topmost."""
        if os.name != "nt":
            return

        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            client_hwnd = wintypes.HWND(window.winfo_id())
            root_hwnd = user32.GetAncestor(client_hwnd, 2) or client_hwnd
            hwnd = wintypes.HWND(root_hwnd)

            get_long = user32.GetWindowLongPtrW
            set_long = user32.SetWindowLongPtrW
            get_long.argtypes = (wintypes.HWND, ctypes.c_int)
            get_long.restype = ctypes.c_ssize_t
            set_long.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t)
            set_long.restype = ctypes.c_ssize_t

            gwl_exstyle = -20
            ws_ex_noactivate = 0x08000000
            ws_ex_toolwindow = 0x00000080
            style = get_long(hwnd, gwl_exstyle)
            set_long(
                hwnd,
                gwl_exstyle,
                style | ws_ex_noactivate | ws_ex_toolwindow,
            )

            hwnd_topmost = wintypes.HWND(-1)
            swp_nosize = 0x0001
            swp_nomove = 0x0002
            swp_noactivate = 0x0010
            user32.SetWindowPos(
                hwnd,
                hwnd_topmost,
                0,
                0,
                0,
                0,
                swp_nosize | swp_nomove | swp_noactivate,
            )
        except Exception as exc:
            self.on_status(
                "Keyboard opened, but Windows could not apply "
                f"non-activating mode: {exc}"
            )

    def _add_key(
        self,
        parent: tk.Misc,
        label: str,
        key: str,
        *,
        width: int,
        accent: bool = True,
    ) -> None:
        button = tk.Button(
            parent,
            text=label,
            width=width,
            height=1,
            padx=2,
            pady=5,
            bg="#2a3d49" if accent else "#6b3a3a",
            fg="#edf3f5",
            activebackground="#4fd1a5",
            activeforeground="#101820",
            relief="flat",
            bd=0,
            font=("Segoe UI", 8),
            command=lambda value=key: self._press(value),
        )
        button.pack(side="left", fill="x", expand=(key == "space"), padx=2)
        # Shift appears twice, so retain both buttons for visual state updates.
        self._buttons.setdefault(key, button)

    def _press(self, key: str) -> None:
        if key == "close":
            self.close()
            return

        if key in {"shift", "ctrl", "alt", "win", "altgr"}:
            self._toggle_modifier(key)
            return

        try:
            import pyautogui

            pyautogui.FAILSAFE = True

            if key == "caps":
                # Toggle the real Windows Caps Lock state, not just a local flag.
                pyautogui.press("capslock")
                self._caps_lock = self._read_windows_caps_lock()
                self._set_button_state("caps", self._caps_lock)
                self._set_status(
                    f"Caps Lock {'on' if self._caps_lock else 'off'}."
                )
                return

            if key == "space":
                self._send_key(pyautogui, "space")
            elif len(key) == 1 and key.isalpha():
                # Windows' real Caps Lock state is authoritative, so physical
                # Caps Lock changes are reflected even while this overlay is open.
                self._caps_lock = self._read_windows_caps_lock()
                self._set_button_state("caps", self._caps_lock)
                want_shift = self._caps_lock ^ ("shift" in self._modifiers)
                self._send_key(
                    pyautogui,
                    key.lower(),
                    force_shift=want_shift,
                    ignore_shift_modifier=True,
                )
            elif len(key) == 1 and key in self.SHIFTED_KEYS:
                # A manually armed Shift or Caps Lock does not alter punctuation;
                # punctuation uses Shift only when the Shift modifier is armed.
                self._send_key(
                    pyautogui,
                    key,
                    force_shift=("shift" in self._modifiers),
                )
            else:
                self._send_key(pyautogui, key)

            self._set_status(f"Sent {key!r} to the focused application.")
        except Exception as exc:
            self._set_status(f"Could not send key: {exc}")

    def _toggle_modifier(self, modifier: str) -> None:
        if modifier in self._modifiers:
            self._modifiers.remove(modifier)
        else:
            self._modifiers.add(modifier)

        self._set_button_state(
            modifier,
            modifier in self._modifiers,
        )
        self._set_status(
            f"Modifier {modifier.upper()} "
            f"{'armed' if modifier in self._modifiers else 'disarmed'} "
            "for the next key."
        )

    def _send_key(
        self,
        pyautogui,
        key: str,
        *,
        force_shift: bool = False,
        ignore_shift_modifier: bool = False,
    ) -> None:
        modifiers: list[str] = []

        for modifier in ("ctrl", "alt", "shift", "win"):
            if modifier in self._modifiers:
                if modifier == "shift" and ignore_shift_modifier:
                    continue
                modifiers.append(modifier)

        if "altgr" in self._modifiers:
            if "ctrl" not in modifiers:
                modifiers.append("ctrl")
            if "alt" not in modifiers:
                modifiers.append("alt")

        if force_shift and "shift" not in modifiers:
            modifiers.append("shift")

        if modifiers:
            pyautogui.hotkey(*modifiers, key)
        else:
            pyautogui.press(key)

        # Modifiers are one-shot: consume them after the next ordinary key.
        # This also consumes Shift when Caps Lock + Shift cancel each other.
        if self._modifiers:
            self._modifiers.clear()
            for modifier in ("ctrl", "alt", "shift", "win", "altgr"):
                self._set_button_state(modifier, False)

    @staticmethod
    def _read_windows_caps_lock() -> bool:
        """Read the actual Windows Caps Lock toggle state."""
        if os.name != "nt":
            return False
        try:
            import ctypes

            return bool(ctypes.windll.user32.GetKeyState(0x14) & 1)
        except Exception:
            return False

    def _set_button_state(self, key: str, active: bool) -> None:
        button = self._buttons.get(key)
        if button is not None:
            button.configure(
                bg="#4fd1a5" if active else "#2a3d49",
                fg="#101820" if active else "#edf3f5",
            )

    def _set_status(self, message: str) -> None:
        if self.window is not None and self.window.winfo_exists():
            if self.status_label is not None:
                self.status_label.configure(text=message)
        self.on_status(message)

    def close(self) -> None:
        self._modifiers.clear()
        self._buttons.clear()
        window, self.window = self.window, None
        self.status_label = None

        if window is not None:
            try:
                window.destroy()
            except tk.TclError:
                pass

        self.on_status("System virtual keyboard closed.")

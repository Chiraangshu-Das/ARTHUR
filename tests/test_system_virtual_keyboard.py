import unittest
from unittest.mock import Mock, patch

from visionguide.system_virtual_keyboard import SystemVirtualKeyboard


class SystemVirtualKeyboardLayoutTests(unittest.TestCase):
    def test_contains_common_text_and_navigation_keys(self):
        keys = {key for row in SystemVirtualKeyboard.CHAR_ROWS for _, key in row}
        keys.update(key for _, key in SystemVirtualKeyboard.KEY_ROWS)
        keys.update(key for _, key in SystemVirtualKeyboard.NAV_KEYS)
        self.assertTrue({"a", "z", "1", "0", "space", "enter", "backspace", "tab", "left", "right", "ctrl", "shift"}.issubset(keys))

    def test_key_layout_has_no_empty_labels_or_actions(self):
        rows = list(SystemVirtualKeyboard.CHAR_ROWS) + [SystemVirtualKeyboard.KEY_ROWS, SystemVirtualKeyboard.NAV_KEYS]
        for row in rows:
            for label, key in row:
                self.assertTrue(label)
                self.assertTrue(key)


class SystemVirtualKeyboardInputTests(unittest.TestCase):
    def _make_keyboard(self, caps_lock, modifiers=None):
        keyboard = object.__new__(SystemVirtualKeyboard)
        keyboard._modifiers = set(modifiers or ())
        keyboard._read_windows_caps_lock = Mock(return_value=caps_lock)
        keyboard._set_button_state = Mock()
        keyboard._set_status = Mock()
        return keyboard

    def test_send_key_uses_armed_shift_without_caps_compensation(self):
        keyboard = self._make_keyboard(caps_lock=True, modifiers={"shift"})
        pyautogui = Mock()

        keyboard._send_key(pyautogui, "a")

        pyautogui.hotkey.assert_called_once_with("shift", "a")
        self.assertEqual(keyboard._modifiers, set())

    def test_send_key_without_armed_shift_does_not_add_shift(self):
        keyboard = self._make_keyboard(caps_lock=True)
        pyautogui = Mock()

        keyboard._send_key(pyautogui, "a")

        pyautogui.press.assert_called_once_with("a")
        pyautogui.hotkey.assert_not_called()

    @patch.dict("sys.modules", {"pyautogui": Mock()})
    def test_caps_lock_does_not_add_shift_to_letter(self):
        import sys

        pyautogui = sys.modules["pyautogui"]
        keyboard = self._make_keyboard(caps_lock=True)
        keyboard._send_key = Mock()

        keyboard._press("a")

        keyboard._send_key.assert_called_once_with(pyautogui, "a")

    @patch.dict("sys.modules", {"pyautogui": Mock()})
    def test_armed_shift_is_preserved_with_caps_lock(self):
        import sys

        pyautogui = sys.modules["pyautogui"]
        keyboard = self._make_keyboard(caps_lock=True, modifiers={"shift"})
        keyboard._send_key = Mock()

        keyboard._press("a")

        keyboard._send_key.assert_called_once_with(pyautogui, "a")
        self.assertIn("shift", keyboard._modifiers)


if __name__ == "__main__":
    unittest.main()

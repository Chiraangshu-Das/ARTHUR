import unittest

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


if __name__ == "__main__":
    unittest.main()

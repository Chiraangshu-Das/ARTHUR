import sys
import types
import unittest
from unittest.mock import patch

from visionguide.semantic_router import SemanticCommandRouter


class TargetedTypingRoutingTests(unittest.TestCase):
    def setUp(self):
        self.router = SemanticCommandRouter(None, enable_local_semantic=False)

    def test_type_in_word_routes_to_targeted_word_insertion(self):
        result = self.router.route("Type hello in Microsoft Word")
        self.assertEqual(result.action, "type_into_window")
        self.assertEqual(result.arguments, {"target": "microsoft word", "text": "hello", "element": ""})

    def test_type_inside_word_document_routes_to_word_com_insertion(self):
        result = self.router.route("Type hello inside the Word document")
        self.assertEqual(result.action, "type_into_window")
        self.assertEqual(result.arguments["target"], "word")
        self.assertEqual(result.arguments["element"], "document")
        self.assertEqual(result.arguments["text"], "hello")

    def test_type_in_youtube_search_box_routes_to_known_field(self):
        result = self.router.route("Type Taylor Swift in YouTube search box")
        self.assertEqual(result.action, "type_into_window")
        self.assertEqual(result.arguments["target"], "youtube")
        self.assertEqual(result.arguments["element"], "search box")
        self.assertEqual(result.arguments["text"], "Taylor Swift")

    def test_type_in_browser_address_bar_routes_to_known_field(self):
        result = self.router.route("Type example.com in Chrome address bar")
        self.assertEqual(result.arguments["target"], "chrome")
        self.assertEqual(result.arguments["element"], "address bar")
        self.assertEqual(result.arguments["text"], "example.com")

    def test_type_in_chrome_search_box_routes_to_omnibox(self):
        result = self.router.route("Type Python tutorials in Chrome search box")
        self.assertEqual(result.action, "type_into_window")
        self.assertEqual(result.arguments["target"], "chrome")
        self.assertEqual(result.arguments["element"], "search box")
        self.assertEqual(result.arguments["text"], "Python tutorials")


    def test_file_explorer_search_field_routes_to_targeted_typing(self):
        result = self.router.route("Type quarterly report in File Explorer search field")
        self.assertEqual(result.action, "type_into_window")
        self.assertEqual(result.arguments["target"], "file explorer")
        self.assertEqual(result.arguments["element"], "search box")
        self.assertEqual(result.arguments["text"], "quarterly report")

    def test_follow_up_press_enter_routes_to_remembered_field_submission(self):
        for utterance in ("Press Enter", "Hit the Enter key", "Search it", "Submit it", "Submit now"):
            with self.subTest(utterance=utterance):
                result = self.router.route(utterance)
                self.assertEqual(result.action, "submit_typed_field")

    def test_excel_search_field_routes_to_targeted_typing(self):
        result = self.router.route("Type quarterly results in Excel search field")
        self.assertEqual(result.action, "type_into_window")
        self.assertEqual(result.arguments["target"], "excel")
        self.assertEqual(result.arguments["element"], "search box")

    def test_word_search_field_routes_separately_from_document_body(self):
        result = self.router.route("Type recursion in Word search field")
        self.assertEqual(result.action, "type_into_window")
        self.assertEqual(result.arguments["element"], "search box")

    def test_current_focus_typing_remains_distinct(self):
        result = self.router.route("Type exactly hello world")
        self.assertEqual(result.action, "type_text")
        self.assertEqual(result.arguments["text"], "hello world")

    def test_close_youtube_is_a_website_tab_action(self):
        result = self.router.route("Close YouTube")
        self.assertEqual(result.action, "close_website")
        self.assertEqual(result.arguments["name"], "youtube")

    def test_close_chrome_is_still_a_desktop_app_action(self):
        result = self.router.route("Close Chrome")
        self.assertEqual(result.action, "close_app")
        self.assertEqual(result.arguments["name"], "chrome")


class BrowserTabCloseTests(unittest.TestCase):
    def test_matching_active_site_tab_receives_ctrl_w(self):
        from visionguide.integrations.gui_automation import close_website_tab

        calls = []
        window = types.SimpleNamespace(
            title="Taylor Swift songs - YouTube - Google Chrome",
            isMinimized=False,
            activate=lambda: calls.append("activate"),
            restore=lambda: calls.append("restore"),
        )
        pygetwindow = types.ModuleType("pygetwindow")
        pygetwindow.getAllWindows = lambda: [window]
        pyautogui = types.ModuleType("pyautogui")
        pyautogui.hotkey = lambda *args: calls.append(args)
        with patch.dict(sys.modules, {"pygetwindow": pygetwindow, "pyautogui": pyautogui}):
            response = close_website_tab("youtube")
        self.assertIn("active youtube browser tab", response)
        self.assertIn(("ctrl", "w"), calls)

    def test_background_tab_is_not_claimed_as_found(self):
        from visionguide.integrations.gui_automation import close_website_tab

        pygetwindow = types.ModuleType("pygetwindow")
        pygetwindow.getAllWindows = lambda: [types.SimpleNamespace(title="Google Chrome", isMinimized=False)]
        pyautogui = types.ModuleType("pyautogui")
        pyautogui.hotkey = lambda *_args: None
        with patch.dict(sys.modules, {"pygetwindow": pygetwindow, "pyautogui": pyautogui}):
            with self.assertRaisesRegex(RuntimeError, "background tab"):
                close_website_tab("youtube")


class WordComTypingTests(unittest.TestCase):
    def test_word_insertion_uses_active_selection_without_mouse_focus(self):
        from visionguide.integrations import gui_automation

        entered = []
        calls = []
        selection = types.SimpleNamespace(TypeText=lambda Text: entered.append(Text))
        document = types.SimpleNamespace(Activate=lambda: calls.append("document_activate"))
        word = types.SimpleNamespace(
            Visible=False,
            Documents=types.SimpleNamespace(Count=1, Add=lambda: calls.append("new_document")),
            ActiveDocument=document,
            Selection=selection,
            Activate=lambda: calls.append("word_activate"),
        )
        client_module = types.ModuleType("win32com.client")
        client_module.GetActiveObject = lambda _name: word
        client_module.Dispatch = lambda _name: word
        win32com_module = types.ModuleType("win32com")
        win32com_module.client = client_module
        pythoncom_module = types.ModuleType("pythoncom")
        pythoncom_module.CoInitialize = lambda: calls.append("co_init")
        pythoncom_module.CoUninitialize = lambda: calls.append("co_uninit")
        with patch.dict(sys.modules, {
            "pythoncom": pythoncom_module,
            "win32com": win32com_module,
            "win32com.client": client_module,
        }), patch.object(gui_automation, "activate_window", return_value="Document1 - Word"):
            result = gui_automation.type_into_window("microsoft word", "Hello")
        self.assertEqual(entered, ["Hello"])
        self.assertIn("Inserted 5 characters", result)
        self.assertIn("co_init", calls)
        self.assertIn("co_uninit", calls)
        self.assertNotIn("new_document", calls)

    def test_word_creates_document_when_none_exists(self):
        from visionguide.integrations import gui_automation

        entered = []
        calls = []
        document = types.SimpleNamespace(Activate=lambda: None)
        selection = types.SimpleNamespace(TypeText=lambda Text: entered.append(Text))
        documents = types.SimpleNamespace(Count=0, Add=lambda: calls.append("new_document") or document)
        word = types.SimpleNamespace(
            Visible=False, Documents=documents, ActiveDocument=document, Selection=selection,
            Activate=lambda: None,
        )
        client_module = types.ModuleType("win32com.client")
        client_module.GetActiveObject = lambda _name: word
        client_module.Dispatch = lambda _name: word
        win32com_module = types.ModuleType("win32com")
        win32com_module.client = client_module
        pythoncom_module = types.ModuleType("pythoncom")
        pythoncom_module.CoInitialize = lambda: None
        pythoncom_module.CoUninitialize = lambda: None
        with patch.dict(sys.modules, {
            "pythoncom": pythoncom_module,
            "win32com": win32com_module,
            "win32com.client": client_module,
        }), patch.object(gui_automation, "activate_window", return_value="Document1 - Word"):
            gui_automation.type_into_window("word", "Hello")
        self.assertIn("new_document", calls)
        self.assertEqual(entered, ["Hello"])


if __name__ == "__main__":
    unittest.main()


class SearchFieldFocusTests(unittest.TestCase):
    def _run_type(self, target, element, text):
        from visionguide.integrations import gui_automation
        calls = []
        pyautogui = types.ModuleType("pyautogui")
        pyautogui.FAILSAFE = False
        pyautogui.hotkey = lambda *args: calls.append(("hotkey", *args))
        pyautogui.press = lambda *args: calls.append(("press", *args))
        pyautogui.sleep = lambda *_args: None
        with patch.dict(sys.modules, {"pyautogui": pyautogui}), \
             patch.object(gui_automation, "activate_window", return_value=f"{target.title()} Window"), \
             patch.object(gui_automation, "_clipboard_paste", side_effect=lambda value: calls.append(("paste", value))):
            message = gui_automation.type_into_window(target, text, element)
        return message, calls

    def test_file_explorer_search_uses_ctrl_e_and_replaces_old_query(self):
        message, calls = self._run_type("file explorer", "search box", "quarterly report")
        self.assertIn("file explorer search box", message)
        self.assertIn(("hotkey", "ctrl", "e"), calls)
        self.assertIn(("hotkey", "ctrl", "a"), calls)
        self.assertIn(("paste", "quarterly report"), calls)

    def test_excel_find_box_uses_ctrl_f(self):
        _, calls = self._run_type("excel", "search box", "revenue")
        self.assertIn(("hotkey", "ctrl", "f"), calls)
        self.assertIn(("paste", "revenue"), calls)

    def test_word_find_box_uses_ctrl_f_instead_of_document_com_insertion(self):
        _, calls = self._run_type("word", "search box", "recursion")
        self.assertIn(("hotkey", "ctrl", "f"), calls)
        self.assertIn(("paste", "recursion"), calls)

    def test_browser_page_field_uses_accessibility_fallback(self):
        from visionguide.integrations import gui_automation
        calls = []
        pyautogui = types.ModuleType("pyautogui")
        pyautogui.FAILSAFE = False
        pyautogui.sleep = lambda *_args: None
        with patch.dict(sys.modules, {"pyautogui": pyautogui}), \
             patch.object(gui_automation, "activate_window", return_value="Chrome"), \
             patch.object(gui_automation, "_focus_accessible_field", side_effect=lambda field: calls.append(("focus", field))), \
             patch.object(gui_automation, "_clipboard_paste", side_effect=lambda text: calls.append(("paste", text))):
            gui_automation.type_into_window("chrome", "hello", "text box")
        self.assertEqual(calls, [("focus", "text box"), ("paste", "hello")])


class RememberedFieldSubmissionTests(unittest.TestCase):
    def test_enter_is_low_risk_for_search_and_document_editing(self):
        from visionguide.integrations.gui_automation import field_submission_requires_confirmation
        self.assertFalse(field_submission_requires_confirmation("youtube", "search box"))
        self.assertFalse(field_submission_requires_confirmation("file explorer", "search box"))
        self.assertFalse(field_submission_requires_confirmation("word", "document"))
        self.assertFalse(field_submission_requires_confirmation("excel", "cell"))
        self.assertFalse(field_submission_requires_confirmation("notepad", "editor"))

    def test_enter_requires_confirmation_for_message_or_ambiguous_forms(self):
        from visionguide.integrations.gui_automation import field_submission_requires_confirmation
        self.assertTrue(field_submission_requires_confirmation("whatsapp", "text box"))
        self.assertTrue(field_submission_requires_confirmation("gmail", "text box"))
        self.assertTrue(field_submission_requires_confirmation("chatgpt", "text box"))
        self.assertTrue(field_submission_requires_confirmation("browser", "text box"))
        self.assertFalse(field_submission_requires_confirmation("gmail", "search box"))

    def test_enter_is_sent_only_to_the_same_foreground_window(self):
        import ctypes
        from visionguide.integrations import gui_automation
        calls = []
        user32 = types.SimpleNamespace(
            IsWindow=lambda hwnd: hwnd == 123,
            GetForegroundWindow=lambda: 123,
            GetWindowTextLengthW=lambda hwnd: len("YouTube"),
            GetWindowTextW=lambda hwnd, buffer, size: setattr(buffer, "value", "YouTube"),
        )
        pyautogui = types.ModuleType("pyautogui")
        pyautogui.FAILSAFE = False
        pyautogui.press = lambda key: calls.append(key)
        with patch.object(gui_automation.os, "name", "nt"), \
             patch.object(ctypes, "windll", types.SimpleNamespace(user32=user32), create=True), \
             patch.object(gui_automation, "capture_focused_control_identity", return_value=(11, 22, 33)), \
             patch.dict(sys.modules, {"pyautogui": pyautogui}):
            result = gui_automation.submit_typed_field(123, "YouTube", "youtube", "search box", (11, 22, 33))
        self.assertIn("Pressed Enter", result)
        self.assertEqual(calls, ["enter"])

    def test_enter_refuses_if_user_changed_windows(self):
        import ctypes
        from visionguide.integrations import gui_automation
        calls = []
        user32 = types.SimpleNamespace(
            IsWindow=lambda hwnd: True,
            GetForegroundWindow=lambda: 456,
            GetWindowTextLengthW=lambda hwnd: 7,
            GetWindowTextW=lambda hwnd, buffer, size: setattr(buffer, "value", "Chrome"),
        )
        pyautogui = types.ModuleType("pyautogui")
        pyautogui.FAILSAFE = False
        pyautogui.press = lambda key: calls.append(key)
        with patch.object(gui_automation.os, "name", "nt"), \
             patch.object(ctypes, "windll", types.SimpleNamespace(user32=user32), create=True), \
             patch.object(gui_automation, "capture_focused_control_identity", return_value=(11, 22, 33)), \
             patch.dict(sys.modules, {"pyautogui": pyautogui}):
            with self.assertRaisesRegex(RuntimeError, "no longer active"):
                gui_automation.submit_typed_field(123, "YouTube", "youtube", "search box", (11, 22, 33))
        self.assertEqual(calls, [])

    def test_enter_refuses_if_focus_changed_inside_same_window(self):
        import ctypes
        from visionguide.integrations import gui_automation
        calls = []
        user32 = types.SimpleNamespace(
            IsWindow=lambda hwnd: True,
            GetForegroundWindow=lambda: 123,
            GetWindowTextLengthW=lambda hwnd: len("YouTube"),
            GetWindowTextW=lambda hwnd, buffer, size: setattr(buffer, "value", "YouTube"),
        )
        pyautogui = types.ModuleType("pyautogui")
        pyautogui.FAILSAFE = False
        pyautogui.press = lambda key: calls.append(key)
        with patch.object(gui_automation.os, "name", "nt"), \
             patch.object(ctypes, "windll", types.SimpleNamespace(user32=user32), create=True), \
             patch.object(gui_automation, "capture_focused_control_identity", return_value=(99, 88, 77)), \
             patch.dict(sys.modules, {"pyautogui": pyautogui}):
            with self.assertRaisesRegex(RuntimeError, "focused control has changed"):
                gui_automation.submit_typed_field(123, "YouTube", "youtube", "search box", (11, 22, 33))
        self.assertEqual(calls, [])


class AccessibleFieldFocusTests(unittest.TestCase):
    def _control(self, name, automation_id=""):
        calls = []
        info = types.SimpleNamespace(control_type="Edit", name=name, automation_id=automation_id)
        control = types.SimpleNamespace(
            element_info=info,
            is_visible=lambda: True,
            is_enabled=lambda: True,
            set_focus=lambda: calls.append("focus"),
        )
        return control, calls

    def test_search_field_uses_unique_accessible_name(self):
        import ctypes
        from visionguide.integrations import gui_automation
        search, calls = self._control("Search courses")
        email, _ = self._control("Email address")
        window = types.SimpleNamespace(descendants=lambda: [email, search])
        pywinauto = types.ModuleType("pywinauto")
        pywinauto.Desktop = lambda backend: types.SimpleNamespace(window=lambda handle: window)
        with patch.object(gui_automation.os, "name", "nt"), \
             patch.object(ctypes, "windll", types.SimpleNamespace(user32=types.SimpleNamespace(GetForegroundWindow=lambda: 321)), create=True), \
             patch.dict(sys.modules, {"pywinauto": pywinauto}):
            result = gui_automation._focus_accessible_field("search box")
        self.assertEqual(result, "Search courses")
        self.assertEqual(calls, ["focus"])

    def test_search_field_refuses_ambiguous_controls(self):
        import ctypes
        from visionguide.integrations import gui_automation
        first, first_calls = self._control("Search files")
        second, second_calls = self._control("Search folders")
        window = types.SimpleNamespace(descendants=lambda: [first, second])
        pywinauto = types.ModuleType("pywinauto")
        pywinauto.Desktop = lambda backend: types.SimpleNamespace(window=lambda handle: window)
        with patch.object(gui_automation.os, "name", "nt"), \
             patch.object(ctypes, "windll", types.SimpleNamespace(user32=types.SimpleNamespace(GetForegroundWindow=lambda: 321)), create=True), \
             patch.dict(sys.modules, {"pywinauto": pywinauto}):
            with self.assertRaisesRegex(RuntimeError, "More than one"):
                gui_automation._focus_accessible_field("search box")
        self.assertEqual(first_calls + second_calls, [])


class GenericApplicationTypingTests(unittest.TestCase):
    def setUp(self):
        self.router = SemanticCommandRouter(None, enable_local_semantic=False)

    def test_other_website_search_field_routes_to_accessible_field_fallback(self):
        result = self.router.route("Type machine learning in Google search field")
        self.assertEqual(result.action, "type_into_window")
        self.assertEqual(result.arguments["target"], "google")
        self.assertEqual(result.arguments["element"], "search box")

    def test_linkedin_learning_and_neon_are_supported_targets(self):
        linked_in = self.router.route("Type Python course in LinkedIn Learning search field")
        neon = self.router.route("Type project database in Neon search field")
        self.assertEqual(linked_in.arguments["target"], "linkedin learning")
        self.assertEqual(neon.arguments["target"], "neon")

    def test_non_shortcut_website_uses_accessibility_field_focus(self):
        from visionguide.integrations import gui_automation
        calls = []
        pyautogui = types.ModuleType("pyautogui")
        pyautogui.FAILSAFE = False
        pyautogui.sleep = lambda *_args: None
        with patch.dict(sys.modules, {"pyautogui": pyautogui}), \
             patch.object(gui_automation, "activate_window", return_value="Google - Chrome"), \
             patch.object(gui_automation, "_focus_accessible_field", side_effect=lambda field: calls.append(field) or "Search"), \
             patch.object(gui_automation, "_clipboard_paste", side_effect=lambda text: calls.append(text)):
            gui_automation.type_into_window("google", "machine learning", "search box")
        self.assertEqual(calls, ["search box", "machine learning"])

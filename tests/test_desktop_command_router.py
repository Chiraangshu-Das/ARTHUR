import unittest
from visionguide.scene_commands import parse_voice_command


class DesktopCommandRouterTests(unittest.TestCase):
    def test_youtube_search(self):
        self.assertEqual(
            parse_voice_command("Search YouTube for Python tutorials"),
            ("youtube_search", "python tutorials"),
        )

    def test_web_search(self):
        self.assertEqual(
            parse_voice_command("Search Google for binary trees"),
            ("web_search", "binary trees"),
        )

    def test_open_allowlisted_site(self):
        self.assertEqual(parse_voice_command("Open YouTube"), ("open_website", "youtube"))
        self.assertEqual(parse_voice_command("Take me to GitHub"), ("open_website", "github"))

    def test_open_calculator(self):
        self.assertEqual(parse_voice_command("Launch Calculator"), ("open_app", "calculator"))

    def test_screenshot(self):
        self.assertEqual(parse_voice_command("Take a screenshot"), ("screenshot", ""))

    def test_screen_explanation(self):
        action, _ = parse_voice_command("Explain what is on my screen")
        self.assertEqual(action, "screen_describe")

    def test_screen_ocr(self):
        self.assertEqual(parse_voice_command("Read the text on my screen"), ("screen_ocr", ""))

    def test_document_search(self):
        self.assertEqual(
            parse_voice_command("Open my document and find the word algorithm"),
            ("document_search", "algorithm"),
        )

    def test_document_search_reverse_word_order(self):
        self.assertEqual(
            parse_voice_command("Find algorithm in this PDF"),
            ("document_search", "algorithm"),
        )

    def test_email_send_is_separate_high_risk_action(self):
        self.assertEqual(parse_voice_command("Send this email"), ("email_send", ""))

    def test_isl_language_commands_are_explicit(self):
        self.assertEqual(parse_voice_command("Start sign language translation"), ("sign_start", ""))
        self.assertEqual(parse_voice_command("Start ISL translation"), ("sign_start", ""))
        self.assertEqual(parse_voice_command("Stop sign language translation"), ("sign_stop", ""))

    def test_stop_camera(self):
        self.assertEqual(parse_voice_command("stop camera analysis"), ("camera_stop", ""))

    def test_system_status(self):
        self.assertEqual(parse_voice_command("How much RAM is being used?"), ("system_status", ""))
        self.assertEqual(parse_voice_command("Is my internet connected?"), ("internet_status", ""))

    def test_latest_pdf_is_distinct_from_file_picker(self):
        self.assertEqual(parse_voice_command("Open my latest PDF"), ("open_latest_pdf", ""))

    def test_screen_question_is_not_misrouted_to_scene_description(self):
        self.assertEqual(parse_voice_command("What is on my screen?" )[0], "screen_describe")


if __name__ == "__main__":
    unittest.main()

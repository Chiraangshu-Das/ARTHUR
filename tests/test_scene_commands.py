import unittest
from visionguide.scene_commands import parse_voice_command
from visionguide.documents import find_word


class SceneCommandTests(unittest.TestCase):
    def test_scene_command(self):
        self.assertEqual(parse_voice_command("describe the scene"), ("describe", ""))

    def test_word_lookup_command(self):
        self.assertEqual(parse_voice_command("find the word address"), ("find_word", "address"))

    def test_safety_default_command_mapping(self):
        self.assertEqual(parse_voice_command("disable safety alerts"), ("safety_off", ""))

    def test_object_query(self):
        self.assertEqual(parse_voice_command("Is there a TV?"), ("check_object", "tv"))

    def test_object_query_with_any(self):
        self.assertEqual(parse_voice_command("Is there any TV in front of me?"),
                         ("check_object", "tv"))

    def test_remember_note(self):
        self.assertEqual(parse_voice_command("Remember that my keys are in the blue bowl"),
                         ("memory_save", "my keys are in the blue bowl"))

    def test_memory_query(self):
        self.assertEqual(parse_voice_command("What do you remember about my keys?"),
                         ("memory_search", "my keys"))

    def test_draft_email_routes_to_text_ai(self):
        action, argument = parse_voice_command("Draft an email to my professor asking for an extension")
        self.assertEqual(action, "text_ai")
        self.assertIn("professor", argument)

    def test_find_word_is_case_insensitive(self):
        self.assertEqual(find_word("Hello world\nAddress: Main Road", "address"), [(2, "Address: Main Road")])


if __name__ == "__main__":
    unittest.main()

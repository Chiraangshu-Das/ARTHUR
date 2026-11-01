import tempfile
import unittest
from pathlib import Path

from visionguide.document_search import search_document, extract_supported_text


class DocumentSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.file = Path(self.temp.name) / "lecture.md"
        self.file.write_text("Algorithm design\nA binary search algorithm runs in logarithmic time.\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_search_case_insensitive_and_lines(self):
        matches = search_document(self.file, "ALGORITHM")
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0].location, "line 1")
        self.assertEqual(matches[1].location, "line 2")

    def test_search_requires_nonempty_query(self):
        with self.assertRaises(ValueError):
            search_document(self.file, "  ")

    def test_rejects_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            extract_supported_text(Path(self.temp.name) / "missing.pdf")

    def test_rejects_unknown_file_type(self):
        unsupported = Path(self.temp.name) / "unknown.xyz"
        unsupported.write_text("data", encoding="utf-8")
        with self.assertRaises(ValueError):
            search_document(unsupported, "data")


if __name__ == "__main__":
    unittest.main()

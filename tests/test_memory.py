import tempfile
import unittest
from pathlib import Path

from visionguide.memory import LocalMemory


class LocalMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.memory = LocalMemory(Path(self.tempdir.name) / "memory.sqlite3")

    def tearDown(self):
        self.tempdir.cleanup()

    def test_add_search_delete(self):
        memory_id = self.memory.add("My preferred meeting time is 3 PM.")
        rows = self.memory.search("meeting time")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], memory_id)
        self.assertTrue(self.memory.delete(memory_id))
        self.assertEqual(self.memory.search("meeting time"), [])

    def test_does_not_accept_empty_memory(self):
        with self.assertRaises(ValueError):
            self.memory.add("   ")

    def test_delete_matching_only_deletes_matching_entries(self):
        self.memory.add("Remember the blue notebook.")
        self.memory.add("Remember the red bag.")
        self.assertEqual(self.memory.delete_matching("blue notebook"), 1)
        self.assertEqual(len(self.memory.search()), 1)
        self.assertIn("red bag", self.memory.search()[0]["content"])


if __name__ == "__main__":
    unittest.main()

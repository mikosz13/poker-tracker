import os
import tempfile
import time
import unittest
from pathlib import Path

from pokertracker.db import Database
from pokertracker.importer import changed_files, import_path
from tests.fixtures import HAND_3WAY, HISTORY, SUMMARY_BOUNTY


class FileImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.dir = Path(self.tmp.name)
        (self.dir / "hh.txt").write_text(HISTORY)
        (self.dir / "sum.txt").write_text(SUMMARY_BOUNTY)
        (self.dir / "notes.md").write_text("ignored: not an importable extension")
        self.db = Database("sqlite:///:memory:")
        self.addCleanup(self.db.close)
        self.db.init_schema()

    def tearDown(self):
        self.tmp.cleanup()

    def test_progress_and_only_new(self):
        seen = []
        s = import_path(self.db, self.dir, progress=lambda done, total, name: seen.append((done, total, name)),
                        skip_unchanged=True)
        self.assertEqual((s.hands_new, s.summary_files, s.unchanged), (3, 1, 0))
        self.assertEqual(seen, [(1, 2, "hh.txt"), (2, 2, "sum.txt")])
        self.assertEqual(changed_files(self.db, self.dir), [])
        again = import_path(self.db, self.dir, skip_unchanged=True)
        self.assertEqual((again.files, again.unchanged), (0, 2))          # nothing was even read

    def test_new_and_modified_files_are_picked_up(self):
        import_path(self.db, self.dir, skip_unchanged=True)
        (self.dir / "3way.txt").write_text(HAND_3WAY)
        later = time.time() + 5
        os.utime(self.dir / "sum.txt", (later, later))                   # e.g. exported again
        self.assertEqual({f.name for f in changed_files(self.db, self.dir)}, {"3way.txt", "sum.txt"})
        s = import_path(self.db, self.dir, skip_unchanged=True)
        self.assertEqual((s.hands_new, s.unchanged), (1, 1))

    def test_full_rescan_still_deduplicates(self):
        import_path(self.db, self.dir)
        s = import_path(self.db, self.dir)
        self.assertEqual((s.hands_new, s.hands_duplicate), (0, 3))


if __name__ == "__main__":
    unittest.main()

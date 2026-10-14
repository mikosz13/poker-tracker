"""Backup and restore of the SQLite database (pokertracker/backup.py)."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from pokertracker.backup import BackupError, check_backup, make_backup, restore
from pokertracker.db import Database
from pokertracker.importer import import_texts
from pokertracker.migrations import LATEST
from tests.fixtures import HISTORY, SUMMARY_BOUNTY


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.url = f"sqlite:///{self.dir / 'pokertracker.db'}"
        with Database(self.url) as db:
            db.init_schema()
            import_texts(db, [("h", HISTORY), ("b", SUMMARY_BOUNTY)], equity=False)
            db.commit()

    def count(self, url=None):
        with Database(url or self.url) as db:
            return db.scalar("SELECT COUNT(*) FROM hands")

    def test_round_trip_keeps_the_current_database_aside(self):
        path = make_backup(self.url, self.dir)
        self.assertTrue(Path(path).name.startswith("poker-tracker-") and path.endswith(".db"))
        self.assertNotEqual(make_backup(self.url, self.dir), path)            # a second one the same day: (2)
        info = check_backup(path)
        self.assertEqual((info["version"], info["tournaments"], info["hands"]), (LATEST, 1, 3))
        with Database(self.url) as db:                                         # the database changes after the backup
            db.execute("DELETE FROM hands WHERE hand_id = 'TM1000000003'")
            db.commit()
        info, saved = restore(self.url, path)
        self.assertEqual(self.count(), 3)                                      # the backup is back
        self.assertEqual(self.count(f"sqlite:///{saved}"), 2)                  # and what it replaced is kept

    def test_an_older_backup_is_upgraded(self):
        path = make_backup(self.url, self.dir)
        with sqlite3.connect(path) as c:
            c.execute("UPDATE schema_version SET version = 7")
            c.execute("DELETE FROM hand_facts")
        restore(self.url, path)
        with Database(self.url) as db:
            self.assertEqual((db.scalar("SELECT MAX(version) FROM schema_version"),
                              db.scalar("SELECT COUNT(*) FROM hand_facts")), (LATEST, 3))   # migration 8 ran again

    def test_foreign_files_are_refused_and_nothing_changes(self):
        text = self.dir / "notes.db"
        text.write_text("not a database")
        other = self.dir / "other.db"
        with sqlite3.connect(other) as c:
            c.execute("CREATE TABLE x (a)")
        newer = Path(make_backup(self.url, self.dir))
        with sqlite3.connect(newer) as c:
            c.execute(f"UPDATE schema_version SET version = {LATEST + 1}")
        for path, code in ((text, "unreadable"), (other, "not_ours"), (newer, "too_new"), (self.dir / "missing.db", "not_found")):
            with self.assertRaises(BackupError) as e:
                restore(self.url, str(path))
            self.assertEqual(e.exception.code, code)
        self.assertEqual(self.count(), 3)

    def test_postgresql_is_not_backed_up_here(self):
        with self.assertRaises(BackupError) as e:
            make_backup("postgresql://x@localhost/db", self.dir)
        self.assertEqual(e.exception.code, "not_sqlite")


if __name__ == "__main__":
    unittest.main()

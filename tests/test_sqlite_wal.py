"""SQLite in WAL mode: the app reads (e.g. the import's progress) while an import writes; copies stay one plain file."""
import sqlite3
import tempfile
import time
import unittest
from contextlib import closing
from pathlib import Path

from pokertracker.backup import make_backup
from pokertracker.db import Database


def journal_mode(path):
    with closing(sqlite3.connect(path)) as c:
        return c.execute("PRAGMA journal_mode").fetchone()[0]


class WalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.url = f"sqlite:///{self.dir / 'p.db'}"
        with Database(self.url) as db:
            db.init_schema()
            db.execute("INSERT INTO settings (name, value) VALUES ('watch', '1')")
            db.commit()

    def test_a_file_database_is_in_wal_mode(self):
        self.assertEqual(journal_mode(self.dir / "p.db"), "wal")
        with Database("sqlite:///:memory:") as db:                  # in memory: nothing to switch
            self.assertEqual(db.scalar("PRAGMA journal_mode"), "memory")

    def test_reading_does_not_wait_for_a_write(self):
        writer = Database(self.url)
        self.addCleanup(writer.close)
        writer.conn.execute("BEGIN EXCLUSIVE")                      # an import in the middle of its write
        writer.execute("UPDATE settings SET value = '0' WHERE name = 'watch'")
        with Database(self.url) as reader:
            t = time.time()
            self.assertEqual(reader.scalar("SELECT value FROM settings WHERE name = 'watch'"), "1")   # the last commit
            self.assertLess(time.time() - t, 1)
        writer.commit()
        with Database(self.url) as reader:
            self.assertEqual(reader.scalar("SELECT value FROM settings WHERE name = 'watch'"), "0")

    def test_copies_are_one_plain_file(self):
        backup = make_backup(self.url, self.dir)
        self.assertEqual(journal_mode(backup), "delete")
        with Database(self.url) as db:
            before_upgrade = db.backup("bak-test")
        self.assertEqual(journal_mode(before_upgrade), "delete")
        self.assertFalse(Path(backup + "-wal").exists())


if __name__ == "__main__":
    unittest.main()

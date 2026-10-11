import tempfile
import time
import unittest
from pathlib import Path

from pokertracker.db import Database
from pokertracker.importer import (excluded_list, excluded_tournaments, ignore_tournaments, import_files, list_files,
                                   preview_files, restore_tournament)
from pokertracker.scope import FREEROLL, USER
from pokertracker.server import ImportJob
from tests.fixtures import HAND_3WAY, HISTORY, SUMMARY_BOUNTY
from tests.test_scope_freeroll import FREEROLL_900001


def hands(db, tid):
    return db.scalar("SELECT COUNT(*) FROM hands WHERE tournament_id = ?", (tid,))


class ImportControlTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        (self.dir / "hh.txt").write_text(HISTORY)           # tournament 900001
        (self.dir / "3way.txt").write_text(HAND_3WAY)       # tournament 900003
        (self.dir / "sum.txt").write_text(SUMMARY_BOUNTY)   # 900001's summary
        self.url = f"sqlite:///{self.dir / 'test.db'}"
        self.db = Database(self.url)
        self.addCleanup(self.db.close)
        self.db.init_schema()

    def files(self):
        return [f for f in list_files(self.dir) if f.suffix == ".txt"]

    def test_preview_lists_tournaments_and_writes_nothing(self):
        (self.dir / "cd.txt").write_text(FREEROLL_900001.replace("900001", "900009"))
        p = preview_files(self.db, self.files())
        rows = {r["tournament_id"]: r for r in p["tournaments"]}
        self.assertEqual(set(rows), {900001, 900003, 900009})
        self.assertEqual((rows[900001]["hands"], rows[900001]["summary"], rows[900001]["buyin"]), (3, True, 10.0))
        self.assertEqual((rows[900003]["hands"], rows[900003]["summary"], rows[900003]["reason"]), (1, False, None))
        self.assertEqual(rows[900009]["reason"], FREEROLL)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM tournaments"), 0)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM imported_files"), 0)

    def test_unticked_tournament_never_comes_back(self):
        p = preview_files(self.db, self.files())
        t = next(r for r in p["tournaments"] if r["tournament_id"] == 900001)
        ignore_tournaments(self.db, [(900001, t["name"], t["files"])])
        import_files(self.db, self.files())
        self.assertEqual((hands(self.db, 900001), hands(self.db, 900003)), (0, 1))
        import_files(self.db, self.files())                       # "Re-read every file"
        self.assertEqual(hands(self.db, 900001), 0)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM tournaments WHERE tournament_id = 900001"), 0)
        self.assertEqual(excluded_tournaments(self.db), {900001: USER})

    def test_ignore_removes_everything_stored(self):
        import_files(self.db, self.files())
        self.assertEqual(hands(self.db, 900001), 3)
        ignore_tournaments(self.db, [900001])
        for table in ("hands", "entries", "tournaments", "tournament_tags"):
            self.assertEqual(self.db.scalar(f"SELECT COUNT(*) FROM {table} WHERE tournament_id = 900001"), 0, table)
        [row] = excluded_list(self.db)["ignored"]
        self.assertEqual((row["tournament_id"], row["files"], row["files_found"]), (900001, 2, 2))   # hh.txt, sum.txt

    def test_restored_tournament_comes_back_at_the_next_import(self):
        import_files(self.db, self.files(), skip_unchanged=True)
        ignore_tournaments(self.db, [900001])
        import_files(self.db, self.files(), skip_unchanged=True)
        self.assertEqual(hands(self.db, 900001), 0)
        self.assertEqual(restore_tournament(self.db, 900001), 2)  # both of its files are still there
        s = import_files(self.db, self.files(), skip_unchanged=True)   # a normal import, not "Re-read every file"
        self.assertEqual(s.unchanged, 1)                          # 3way.txt; hh.txt and sum.txt are read again
        self.assertEqual(hands(self.db, 900001), 3)
        self.assertEqual(excluded_tournaments(self.db), {})
        self.assertIsNone(restore_tournament(self.db, 900001))    # not on the list any more

    def test_automatic_import_skips_ignored_tournaments(self):
        ignore_tournaments(self.db, [900001])
        job = ImportJob(self.url)
        self.assertTrue(job.start(str(self.dir), skip_unchanged=True, source="auto"))
        end = time.time() + 30
        while job.state.get("running") and time.time() < end:
            time.sleep(0.05)
        self.assertIsNone(job.state["error"])
        self.assertEqual(job.state["result"]["tournament_ids"], [900003])
        self.assertEqual((hands(self.db, 900001), hands(self.db, 900003)), (0, 1))

    def test_import_job_ignores_what_the_preview_unticked(self):
        job = ImportJob(self.url)

        def run(**kw):
            self.assertTrue(job.start(str(self.dir), skip_unchanged=False, **kw))
            while job.state.get("running"):
                time.sleep(0.05)
            return job.state

        rows = run(preview=True)["preview"]["tournaments"]
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM hands"), 0)
        t = next(r for r in rows if r["tournament_id"] == 900003)
        run(ignore=[(900003, t["name"], t["files"])])
        self.assertEqual((hands(self.db, 900001), hands(self.db, 900003)), (3, 0))


if __name__ == "__main__":
    unittest.main()

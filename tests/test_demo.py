"""Demo data (pokertracker/demo.py): made-up GG files that import cleanly into a separate database."""
import json
import tempfile
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

from pokertracker.db import Database
from pokertracker.demo import DEMO_FIRST_ID, build_demo, demo_files, demo_url, ensure_demo
from pokertracker.server import serve_in_background

TODAY = datetime(2026, 10, 14)


class DemoFilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database("sqlite:///:memory:")
        cls.db.init_schema()
        cls.stats = build_demo(cls.db, n=12, equity=False)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_same_seed_and_day_give_the_same_files(self):
        self.assertEqual(demo_files(3, today=TODAY), demo_files(3, today=TODAY))
        self.assertNotEqual(demo_files(3, seed=1, today=TODAY), demo_files(3, today=TODAY))

    def test_every_file_imports_without_a_skip(self):
        self.assertEqual((self.stats.skipped, self.stats.to_check, self.stats.ignored_counts()), ([], [], {}))
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM tournaments"), 12)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM tournament_results WHERE summary_missing = 1"), 0)
        self.assertGreater(self.stats.hands_new, 300)
        self.assertGreater(self.db.scalar("SELECT COUNT(DISTINCT hand_id) FROM actions WHERE nick = 'Hero' AND all_in"), 10)
        self.assertGreaterEqual(self.db.scalar("SELECT MIN(tournament_id) FROM tournaments"), DEMO_FIRST_ID)
        self.assertTrue(all(r["name"].startswith("DEMO") for r in self.db.query("SELECT name FROM tournaments")))

    def test_chips_are_neither_made_nor_lost(self):
        bad = self.db.query("SELECT hand_id, SUM(net_won) AS s FROM hand_players GROUP BY hand_id HAVING ABS(SUM(net_won)) > 0.001")
        self.assertEqual(bad, [])

    def test_hero_is_in_every_hand(self):
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM hands h WHERE NOT EXISTS (SELECT 1 FROM hand_players p "
                                        "WHERE p.site = h.site AND p.hand_id = h.hand_id AND p.is_hero)"), 0)


class DemoCliTests(unittest.TestCase):
    def test_files_written_then_imported_twice(self):
        import contextlib, io
        from pokertracker.cli import main
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            out, url = Path(tmp) / "demo", f"sqlite:///{Path(tmp) / 'demo.db'}"
            counts = []
            for args in (["demo-files", str(out), "--count", "3"], ["--db", url, "import", str(out), "--no-equity"],
                         ["--db", url, "import", str(out), "--no-equity"]):
                with contextlib.redirect_stdout(io.StringIO()):
                    main(args)
                if args[0] == "--db":
                    with Database(url) as db:
                        counts.append((db.scalar("SELECT COUNT(*) FROM tournaments"), db.scalar("SELECT COUNT(*) FROM hands")))
            self.assertEqual(len(list(out.iterdir())), 6)                  # hands + summary per tournament
            self.assertEqual(counts[0][0], 3)
            self.assertEqual(counts[1], counts[0])                         # the second import adds nothing


class EnsureDemoTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.real = f"sqlite:///{Path(tmp.name) / 'poker.db'}"

    def test_built_next_to_the_real_database_reused_while_fresh_rebuilt_when_stale(self):
        url = demo_url(self.real)
        self.assertEqual(Path(url[len("sqlite:///"):]).name, "demo.db")
        self.assertEqual(ensure_demo(self.real, equity=False), url)
        with Database(url) as db:
            db.execute("DELETE FROM hands WHERE hand_id IN (SELECT hand_id FROM hands LIMIT 1)")
            db.commit()
            n = db.scalar("SELECT COUNT(*) FROM hands")
        ensure_demo(self.real, equity=False)                       # fresh: kept as it is
        with Database(url) as db:
            self.assertEqual(db.scalar("SELECT COUNT(*) FROM hands"), n)
        ensure_demo(self.real, now=datetime.now() + timedelta(days=60), equity=False)   # stale: built again
        with Database(url) as db:
            self.assertEqual(db.scalar("SELECT COUNT(*) FROM hands"), n + 1)
        self.assertFalse(Path(self.real[len("sqlite:///"):]).exists())   # the player's database is not created


class DemoServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        real = f"sqlite:///{Path(cls.tmp.name) / 'poker.db'}"
        ensure_demo(real, equity=False)                            # built ahead, so the switch does not wait for equity
        cls.server, cls.url = serve_in_background(real)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.url + path.lstrip("/")) as r:
            return json.loads(r.read())

    def post(self, path, body):
        req = urllib.request.Request(self.url + path.lstrip("/"), data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-Token": self.server.token})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read())

    def test_switching_to_the_demo_and_back(self):
        self.assertEqual(self.get("/api/dashboard")["dashboard"]["tournaments"], 0)
        self.assertEqual(self.post("/api/demo", {"on": True}), (200, {"demo": True}))
        try:
            self.assertTrue(self.get("/api/settings")["demo"])
            self.assertTrue(self.get("/api/status")["demo"])
            self.assertEqual(len(self.get("/api/tournaments")), 40)
            for path, body in (("/api/import", {"folder": self.tmp.name}), ("/api/backup", {}), ("/api/ignore", {"ids": [1]})):
                status, r = self.post(path, body)
                self.assertEqual((status, r["code"]), (409, "demo_mode"), path)
            self.assertEqual(self.post("/api/display", {"lang": "pl", "dashboard_period": "7d"})[0], 200)
        finally:
            self.assertEqual(self.post("/api/demo", {"on": False}), (200, {"demo": False}))
        st = self.get("/api/settings")
        self.assertEqual((st["demo"], st["lang"]), (False, "pl"))         # display settings belong to the player
        self.assertNotEqual(self.get("/api/dashboard")["dashboard"]["period"], "7d")   # the period stayed in the demo
        self.assertEqual(self.get("/api/tournaments"), [])


if __name__ == "__main__":
    unittest.main()

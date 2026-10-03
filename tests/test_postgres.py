"""Runs the core flow against a real PostgreSQL server.

Skipped unless POKERTRACKER_TEST_POSTGRES points at a database that may be wiped (CI provides one).
"""
import os
import unittest

URL = os.environ.get("POKERTRACKER_TEST_POSTGRES")


class PlaceholderTests(unittest.TestCase):
    """Runs everywhere: the SQL handed to psycopg must not contain a bare '%'."""

    def test_literal_percent_is_escaped_for_postgres(self):
        from pokertracker.db import Database
        db = Database.__new__(Database)
        db.kind = "postgres"
        self.assertEqual(db._q("SELECT ? WHERE tag LIKE 'entry:%'"), "SELECT %s WHERE tag LIKE 'entry:%%'")
        db.kind = "sqlite"
        self.assertEqual(db._q("SELECT ? WHERE tag LIKE 'entry:%'"), "SELECT ? WHERE tag LIKE 'entry:%'")


@unittest.skipUnless(URL, "set POKERTRACKER_TEST_POSTGRES to a throwaway PostgreSQL database to run these tests")
class PostgresTests(unittest.TestCase):
    def setUp(self):
        from pokertracker.db import Database
        self.db = Database(URL)
        self.db.script("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        self.db.init_schema()

    def tearDown(self):
        self.db.close()

    def import_all(self):
        from pokertracker.importer import import_texts
        from tests.fixtures import HAND_3WAY, HISTORY, SUMMARY_BOUNTY, SUMMARY_SATELLITE
        return import_texts(self.db, [("h", HISTORY), ("t", HAND_3WAY), ("b", SUMMARY_BOUNTY), ("s", SUMMARY_SATELLITE)])

    def test_import_is_idempotent(self):
        s = self.import_all()
        self.assertEqual((s.hands_new, s.allins), (4, 2))
        s = self.import_all()
        self.assertEqual((s.hands_new, s.hands_duplicate), (0, 4))
        for table, n in (("hands", 4), ("entries", 3), ("allin_ev", 5), ("tournaments", 3)):
            self.assertEqual(self.db.scalar(f"SELECT COUNT(*) FROM {table}"), n, table)

    def test_views_and_reports(self):
        from pokertracker.dashboard import dashboard_data
        from pokertracker.replay import hand_replay
        from pokertracker.server import last_session, tournaments_list
        from pokertracker.tournament_report import render_html, render_text, tournament_data
        self.import_all()
        roi = {r["tournament_id"]: r for r in self.db.query("SELECT * FROM tournament_results")}
        self.assertEqual(float(roi[900001]["roi_pct"]), 0.0)
        self.assertEqual(float(roi[900002]["roi_incl_tickets_pct"]), 900.0)
        d = tournament_data(self.db, 900003)
        self.assertEqual(d["knockouts"], {"sole": 2, "shared": 0})
        self.assertIn("knockouts: 2", render_text(d))
        self.assertIn("<svg", render_html(tournament_data(self.db, 900001)))
        self.assertEqual(dashboard_data(self.db)["tournaments"], 2)
        self.assertEqual(len(tournaments_list(self.db)), 3)
        self.assertIsNotNone(last_session(self.db))
        steps = hand_replay(self.db, "TM1000000010")["steps"]
        self.assertEqual(next(p for p in steps[-1]["players"] if p["nick"] == "Hero")["stack"], 7000)
        tags = {r["tag"] for r in self.db.query("SELECT tag FROM tournament_tags WHERE tournament_id = 900002")}
        self.assertIn("format:satellite", tags)


if __name__ == "__main__":
    unittest.main()

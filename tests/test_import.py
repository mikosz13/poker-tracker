import unittest

from pokertracker.db import Database
from pokertracker.importer import import_texts
from tests.fixtures import HISTORY, SUMMARY_BOUNTY, SUMMARY_SATELLITE


def fresh_db():
    db = Database("sqlite:///:memory:")
    db.init_schema()
    return db


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()
        self.addCleanup(self.db.close)
        self.items = [("history", HISTORY), ("bounty", SUMMARY_BOUNTY), ("sat", SUMMARY_SATELLITE)]

    def test_import_counts(self):
        s = import_texts(self.db, self.items)
        self.assertEqual((s.hands_new, s.hands_duplicate, s.summary_files, len(s.tournaments)), (3, 0, 2, 2))
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM hands"), 3)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM tournaments"), 2)

    def test_reimport_is_idempotent(self):
        import_texts(self.db, self.items)
        s = import_texts(self.db, self.items)
        self.assertEqual((s.hands_new, s.hands_duplicate), (0, 3))
        for table, n in (("hands", 3), ("hand_players", 7), ("entries", 2), ("tournaments", 2)):
            self.assertEqual(self.db.scalar(f"SELECT COUNT(*) FROM {table}"), n, table)

    def test_summary_can_arrive_before_or_after_hands(self):
        import_texts(self.db, [("bounty", SUMMARY_BOUNTY)])
        import_texts(self.db, [("history", HISTORY)])
        row = self.db.query("SELECT * FROM tournament_results WHERE tournament_id = 900001")[0]
        self.assertEqual(float(row["total_cost"]), 20.0)     # $10 x (1 + 1 re-entry)

    def test_entries_stored(self):
        import_texts(self.db, self.items)
        rows = self.db.query("SELECT entry_no, entry_level, starts_fresh FROM entries ORDER BY entry_no")
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["starts_fresh"] for r in rows))

    def test_roi_cash_vs_ticket(self):
        import_texts(self.db, self.items)
        by_id = {r["tournament_id"]: r for r in self.db.query("SELECT * FROM tournament_results")}
        b, s = by_id[900001], by_id[900002]
        self.assertEqual((float(b["profit"]), float(b["roi_pct"])), (0.0, 0.0))
        self.assertEqual((float(s["cash_won"]), float(s["ticket_value"]), float(s["roi_pct"])), (0.0, 50.0, -100.0))
        self.assertEqual(float(s["roi_incl_tickets_pct"]), 900.0)
        fr = {r["format"]: r for r in self.db.query("SELECT * FROM format_results")}
        self.assertEqual(set(fr), {"bounty", "satellite"})

    def test_hero_stats(self):
        import_texts(self.db, self.items)
        h = self.db.query("SELECT COUNT(*) AS n, SUM(vpip) AS vpip, SUM(pfr) AS pfr, SUM(net_won) AS net FROM hero_hands")[0]
        self.assertEqual((h["n"], h["vpip"], h["pfr"]), (3, 2, 0))       # called in hands 1 and 2
        self.assertEqual(float(h["net"]), -155 - 4845 + 30)
        pos = self.db.query("SELECT * FROM hero_position_stats")
        self.assertEqual([(p["position"], p["hands"]) for p in pos], [("BB", 3)])

    def test_junk_is_skipped_not_fatal(self):
        s = import_texts(self.db, [("notes.txt", "hello"), ("empty", "")])
        self.assertEqual(len(s.skipped), 2)


if __name__ == "__main__":
    unittest.main()


class ReimportHoleCardsTests(unittest.TestCase):
    def test_reimport_refreshes_hole_cards_of_stored_hands(self):
        from tests.fixtures import HAND_1
        db = Database("sqlite:///:memory:")
        self.addCleanup(db.close)
        db.init_schema()
        import_texts(db, [("h", HAND_1)])
        db.execute("UPDATE hand_players SET hole_cards = 'Kh' WHERE nick = 'Hero'")   # what 0.4.0 could store
        db.commit()
        import_texts(db, [("h", HAND_1)])
        self.assertEqual(db.scalar("SELECT hole_cards FROM hand_players WHERE nick = 'Hero'"), "Ah Kh")

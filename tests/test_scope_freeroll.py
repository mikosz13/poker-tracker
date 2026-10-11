import tempfile
import unittest
from pathlib import Path

from pokertracker.db import Database
from pokertracker.importer import excluded_tournaments, import_files, import_texts
from pokertracker.scope import FREEROLL, UNRECOGNISED, buyin_paid
from pokertracker.scope_review import review
from tests.fixtures import HAND_3WAY, HISTORY, SUMMARY_BOUNTY

# The real Cash Drop summary (tournament 317586476), moved onto the fixture's tournament id
FREEROLL_900001 = """Tournament #900001, $10,000 Bounty Hunters Series Cash Drop, Hold'em No Limit
Buy-in: $0
8554 Players
Total Prize Pool: $10,000
Tournament started 2026/01/01 09:00:00
1237th : Hero, $0
You finished the tournament in 1237th place.
You received a total of $0.
"""
# A satellite seat used to enter: GGPoker writes the full buy-in (as on Mik's #304781634)
TICKET_ENTRY = """Tournament #900005, #25: The BIG $500 Mystery Bounty NLH, Hold'em No Limit
Buy-in: $237.5+$25+$237.5
4016 Players
Total Prize Pool: $2,008,000
Tournament started 2026/01/05 18:00:00
2100th : Hero, $0
You finished the tournament in 2100th place.
You received a total of $0.
"""


def unreadable(tid):
    """A GGPoker header, then nothing the parser knows."""
    return f"Tournament #{tid}, Bounty Hunters $10, Hold'em No Limit\nEntry fee paid in some new way\n"


def count(db, table, tid):
    return db.scalar(f"SELECT COUNT(*) FROM {table} WHERE tournament_id = ?", (tid,))


class ScopeRuleTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.addCleanup(self.db.close)
        self.db.init_schema()

    def test_buyin_paid(self):
        self.assertEqual([buyin_paid(x) for x in ("Buy-in: $0", "Buy-in: $0+$0", "Buy-in: $4.50+$0.50+$5", "", "Buy-in:")],
                         [0, 0, 10.0, None, None])

    def test_freeroll_removes_hands_imported_before(self):
        import_texts(self.db, [("hh.txt", HISTORY)])
        self.assertEqual(count(self.db, "hands", 900001), 3)
        s = import_texts(self.db, [("cash drop.txt", FREEROLL_900001)])
        for table in ("hands", "entries", "tournaments", "actions"):
            self.assertEqual(count(self.db, table, 900001) if table != "actions" else self.db.scalar(
                "SELECT COUNT(*) FROM actions WHERE hand_id LIKE 'TM100000000%'"), 0, table)
        self.assertEqual(excluded_tournaments(self.db), {900001: FREEROLL})
        self.assertEqual(s.ignored_file_lists(), {FREEROLL: ["cash drop.txt"]})

    def test_hands_after_the_summary_stay_out(self):
        import_texts(self.db, [("cash drop.txt", FREEROLL_900001)])
        s = import_texts(self.db, [("hh.txt", HISTORY)])
        self.assertEqual(count(self.db, "hands", 900001), 0)
        self.assertEqual(s.ignored_counts(), {FREEROLL: 1})

    def test_ticket_entry_is_not_a_freeroll(self):
        import_texts(self.db, [("big500.txt", TICKET_ENTRY)])
        self.assertEqual(self.db.scalar("SELECT buyin_total FROM tournaments WHERE tournament_id = 900005"), 500)
        self.assertEqual(excluded_tournaments(self.db), {})

    def test_unreadable_summary_removes_hands_imported_before(self):
        import_texts(self.db, [("hh.txt", HISTORY), ("3way.txt", HAND_3WAY)])
        s = import_texts(self.db, [("odd.txt", unreadable(900001))])
        self.assertEqual(count(self.db, "hands", 900001), 0)
        self.assertEqual(count(self.db, "hands", 900003), 1)            # a tournament with only hands stays
        self.assertEqual(excluded_tournaments(self.db), {900001: UNRECOGNISED})
        self.assertEqual((s.ignored_file_lists(), s.to_check), ({UNRECOGNISED: ["odd.txt"]}, []))

    def test_hands_only_tournament_stays(self):
        import_texts(self.db, [("hh.txt", HISTORY)])
        import_texts(self.db, [("hh.txt", HISTORY)])
        self.assertEqual(count(self.db, "hands", 900001), 3)
        self.assertEqual(excluded_tournaments(self.db), {})

    def test_readable_again_comes_back_in_scope(self):
        import_texts(self.db, [("odd.txt", unreadable(900001))])
        import_texts(self.db, [("sum.txt", SUMMARY_BOUNTY)])            # e.g. after a parser update
        self.assertEqual(excluded_tournaments(self.db), {})
        self.assertEqual(count(self.db, "tournaments", 900001), 1)

    def test_safety_fuse_keeps_everything_when_many_summaries_are_unreadable(self):
        import_texts(self.db, [("hh.txt", HISTORY)])
        s = import_texts(self.db, [(f"odd{i}.txt", unreadable(tid)) for i, tid in
                                   enumerate((900001, 910001, 910002, 910003))])
        self.assertEqual(excluded_tournaments(self.db), {})
        self.assertEqual(count(self.db, "hands", 900001), 3)
        self.assertEqual(s.to_check, ["odd0.txt", "odd1.txt", "odd2.txt", "odd3.txt"])

    def test_safety_fuse_by_share(self):
        # 2 of 5 summaries unreadable (40 %): kept, flagged
        s = import_texts(self.db, [("a.txt", unreadable(910001)), ("b.txt", unreadable(910002)),
                                   ("ok.txt", SUMMARY_BOUNTY), ("big.txt", TICKET_ENTRY), ("cd.txt", FREEROLL_900001)])
        self.assertEqual(s.to_check, ["a.txt", "b.txt"])
        self.assertNotIn(910001, excluded_tournaments(self.db))


class ScopeReviewTests(unittest.TestCase):
    def test_review_changes_nothing_and_shows_the_amounts(self):
        db = Database("sqlite:///:memory:")
        self.addCleanup(db.close)
        db.init_schema()
        import_texts(db, [("hh.txt", HISTORY)])
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "cash drop.txt").write_text(FREEROLL_900001)
            (Path(d) / "big500.txt").write_text(TICKET_ENTRY)
            r = review(db, d)
            self.assertEqual(count(db, "hands", 900001), 3)              # read-only
            [x] = r["remove"]
            self.assertEqual((x["tournament_id"], x["reason"], x["buyin"], x["received"], x["hands"], x["in_database"]),
                             (900001, FREEROLL, "$0", "$0", 3, True))
            import_files(db, sorted(Path(d).iterdir()))
            self.assertEqual(count(db, "hands", 900001), 0)


if __name__ == "__main__":
    unittest.main()

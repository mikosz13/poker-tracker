import unittest

from pokertracker.db import Database
from pokertracker.importer import excluded_tournaments, import_texts
from pokertracker.migrations import migrate
from pokertracker.session import summary_sentence
from pokertracker.summary import parse_summary, prize_parts, stage_of
from tests.fixtures import HISTORY

# A real day-1 summary (PokerCraft, October 2026), tournament number changed: Hero re-entered once, won $7.02 in
# knockouts and went through to Day 2
STAGE1_ADVANCED = """Tournament #900101, $5 Ocean KO Opener, $1M GTD [Stage 1], Hold'em No Limit
Buy-in: $2.1+$0.4+$2.5
4660 Players
Total Prize Pool: $1,000,000
Tournament started 2026/10/05 10:30:00
446th : Hero, $0 Entry$7.02
You finished the tournament in 446th place.
You have re-entered 1 times, and have advanced to Day2 with 20,801 chips.
"""
# A real day-1 bust in the same series, tournament number changed
STAGE1_BUST = """Tournament #900102, $5 Ocean KO Opener, $1M GTD [Stage 1], Hold'em No Limit
Buy-in: $2.1+$0.4+$2.5
9361 Players
Total Prize Pool: $1,000,000
Tournament started 2026/10/04 14:30:00
1102th : Hero, 0 chips
You finished the tournament in 1102th place.
You made 1 re-entries and received a total of 0 chips.
"""
# No Day 2 summary exists in the data yet: this one is written after the day-1 format, with the $0 buy-in a later
# day can show (it was paid on day 1)
DAY2 = """Tournament #900103, $5 Ocean KO Opener, $1M GTD [Stage 2], Hold'em No Limit
Buy-in: $0
1500 Players
Total Prize Pool: $1,000,000
Tournament started 2026/10/12 18:00:00
120th : Hero, $45.10
You finished the tournament in 120th place.
You received a total of $45.10.
"""


def result(db, tid):
    rows = db.query("SELECT * FROM tournament_results WHERE tournament_id = ?", (tid,))
    return rows[0] if rows else None


class StageParserTests(unittest.TestCase):
    def test_day1_advance_with_knockout_cash_and_reentry(self):
        t = parse_summary(STAGE1_ADVANCED)
        self.assertEqual((t.prize_won, t.prize_ticket, t.prize_is_ticket, t.reentries), (7.02, 0.0, False, 1))
        self.assertEqual((t.stage, t.advanced_to, t.advanced_chips), (1, "Day 2", 20801.0))

    def test_day1_bust_in_chips(self):
        t = parse_summary(STAGE1_BUST)
        self.assertEqual((t.prize_won, t.reentries, t.advanced_to), (0.0, 1, None))

    def test_prize_parts_and_stages(self):
        self.assertEqual([prize_parts(x) for x in ("$20", "$500 Entry", "$0 Entry$7.02", "0 chips", "$1,234.50")],
                         [(20.0, 0), (0, 500.0), (7.02, 0.0), (0, 0), (1234.5, 0)])
        self.assertEqual([stage_of(x) for x in ("X [Stage 1]", "X [Stage 2]", "X Final Day", "$54 Sunday Mystery", "Day 1B")],
                         [1, 2, 99, 1, 1])


class StageImportTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.addCleanup(self.db.close)
        self.db.init_schema()

    def test_day1_cost_is_buyin_times_entries_and_return_is_knockout_cash(self):
        import_texts(self.db, [("s1.txt", STAGE1_ADVANCED), ("bust.txt", STAGE1_BUST)])
        r = result(self.db, 900101)
        self.assertEqual([round(float(r[k]), 2) for k in ("total_cost", "cash_won", "profit")], [10.0, 7.02, -2.98])
        self.assertEqual((r["cashed"], r["in_the_money"]), (0, None))  # going through to Day 2 is not cashing; bounty
        self.assertEqual((float(result(self.db, 900102)["total_cost"]), float(result(self.db, 900102)["cash_won"])),
                         (10.0, 0.0))

    def test_day2_with_zero_buyin_is_not_a_freeroll_and_joins_day1(self):
        import_texts(self.db, [("d2.txt", DAY2), ("s1.txt", STAGE1_ADVANCED)])     # any order
        self.assertEqual(excluded_tournaments(self.db), {})
        self.assertEqual(self.db.scalar("SELECT first_day_id FROM tournaments WHERE tournament_id = 900103"), 900101)
        self.assertIsNone(result(self.db, 900103))                  # counted under day 1
        r = result(self.db, 900101)
        self.assertEqual((float(r["total_cost"]), round(float(r["cash_won"]), 2), r["finish_place"], r["cashed"]),
                         (10.0, 52.12, 120, 1))                     # $7.02 + $45.10; ITM on the day that paid
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM tournament_results"), 1)

    def test_day2_without_day1_counts_on_its_own_at_no_cost(self):
        import_texts(self.db, [("d2.txt", DAY2)])
        r = result(self.db, 900103)
        self.assertEqual((float(r["total_cost"]), float(r["cash_won"])), (0.0, 45.1))

    def test_a_later_day_does_not_teach_the_starting_stack(self):
        day2_of_history = DAY2.replace("#900103", "#900001")       # HISTORY's hands become a Day 2
        import_texts(self.db, [("hh.txt", HISTORY), ("d2.txt", day2_of_history)])
        t = self.db.query("SELECT starting_stack FROM tournaments WHERE tournament_id = 900001")[0]
        self.assertIsNone(t["starting_stack"])
        tags = [r["tag"] for r in self.db.query("SELECT tag FROM tournament_tags WHERE tournament_id = 900001")]
        self.assertFalse([x for x in tags if x.startswith("entry:")])  # no late reg vs start for chips carried over

    def test_session_sentence_names_the_advance(self):
        import_texts(self.db, [("s1.txt", STAGE1_ADVANCED)])
        from pokertracker.server import tournaments_list
        rows = tournaments_list(self.db)
        text = summary_sentence(rows, {"luck": {"count": 0}, "busts": []}, "pl")
        self.assertIn("Awans do Day 2 w $5 Ocean KO Opener, $1M GTD [Stage 1].", text)
        self.assertIn("0 z gotówką", text)

    def test_migration_moves_ticket_value_out_of_cash(self):
        self.db.execute("INSERT INTO tournaments (site, tournament_id, name, buyin_total, prize_won, prize_is_ticket, "
                        "prize_ticket, has_summary) VALUES ('GGPoker', 1, 'Sat', 50, 500, TRUE, NULL, TRUE)")
        self.db.execute("UPDATE schema_version SET version = 3")
        migrate(self.db, fresh=False)
        r = self.db.query("SELECT prize_won, prize_ticket FROM tournaments WHERE tournament_id = 1")[0]
        self.assertEqual((float(r["prize_won"]), float(r["prize_ticket"])), (0.0, 500.0))


if __name__ == "__main__":
    unittest.main()

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

# Mik's real case (October 2026): PokerCraft offered the Day 2 hands but no Day 2 summary. The hands of HISTORY
# become that Day 2.
DAY2_HANDS = (HISTORY.replace("Tournament #900001, Bounty Hunters $10 Hold'em",
                              "Tournament #900103, $5 Ocean KO Opener, $1M GTD [Day 2] Hold'em")
              .replace("2026/01/0", "2026/10/1"))


def flight(tid, name, started, reentries, ko):
    """A day-1 flight that went through to Day 2, in the format of STAGE1_ADVANCED."""
    re_line = f"You have re-entered {reentries} times, and" if reentries else "You"
    return (f"Tournament #{tid}, {name}, Hold'em No Limit\nBuy-in: $2.1+$0.4+$2.5\n5000 Players\n"
            f"Total Prize Pool: $1,000,000\nTournament started {started} \n400th : Hero, $0 Entry${ko}\n"
            f"You finished the tournament in 400th place.\n{re_line} have advanced to Day2 with 30,000 chips.\n")


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
        self.assertEqual([self.db.scalar(f"SELECT event_id FROM tournaments WHERE tournament_id = {i}")
                          for i in (900101, 900103)], [900103, 900103])
        self.assertIsNone(result(self.db, 900101))                  # counted under the event's last day
        r = result(self.db, 900103)
        self.assertEqual((float(r["total_cost"]), round(float(r["cash_won"]), 2), r["finish_place"], r["cashed"], r["days"]),
                         (10.0, 52.12, 120, 1, 2))                  # $7.02 + $45.10; cashed on the day that paid
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM tournament_results"), 1)

    def test_every_flight_joins_the_one_day2(self):
        # Mik's case: several day-1 flights went through (the name changed from "$1M GTD" to "$1M"), one Day 2 stack
        flights = [flight(900111, "$5 Ocean KO Opener, $1M GTD [Stage 1]", "2026/10/05 10:30:00", reentries=1, ko="7.02"),
                   flight(900112, "$5 Ocean KO Opener, $1M GTD [Stage 1]", "2026/10/06 16:30:00", reentries=0, ko="4.46"),
                   flight(900113, "$5 Ocean KO Opener, $1M [Stage 1]", "2026/10/09 14:30:00", reentries=6, ko="0.67")]
        bust = STAGE1_BUST.replace("#900102", "#900114")              # a flight without an advance stays on its own
        import_texts(self.db, [(f"f{i}", t) for i, t in enumerate(flights)] + [("bust", bust), ("d2", DAY2)])
        r = result(self.db, 900103)
        self.assertEqual((float(r["total_cost"]), round(float(r["cash_won"]), 2), r["reentries"], r["days"]),
                         (50.0, 57.25, 7, 4))                       # 2 + 1 + 7 entries x $5; KO cash + Day 2 cash
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM tournament_results"), 2)    # the event and the bust
        self.assertIsNone(self.db.scalar("SELECT event_id FROM tournaments WHERE tournament_id = 900114"))

    def test_an_advance_waits_for_day2_then_shows_not_played(self):
        from datetime import datetime
        from pokertracker.server import day_status
        import_texts(self.db, [("s1.txt", STAGE1_ADVANCED)])
        row = self.db.query("SELECT * FROM tournaments WHERE tournament_id = 900101")[0]
        self.assertEqual(day_status(row, now=datetime(2026, 10, 7)), "waiting")
        self.assertEqual(day_status(row, now=datetime(2026, 10, 20)), "not_played")
        import_texts(self.db, [("d2.txt", DAY2)])
        row = self.db.query("SELECT * FROM tournaments WHERE tournament_id = 900101")[0]
        self.assertEqual(day_status(row, now=datetime(2026, 10, 20)), "event")

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
        self.assertNotIn("ITM", text)                                 # a bounty day 1: ITM is not in the files

    def test_day2_without_summary_joins_its_flights_from_the_hands(self):
        from pokertracker.server import tournaments_list
        import_texts(self.db, [("s1.txt", STAGE1_ADVANCED), ("d2.txt", DAY2_HANDS)], equity=False)
        self.assertEqual(self.db.scalar("SELECT event_id FROM tournaments WHERE tournament_id = 900101"), 900103)
        r = result(self.db, 900103)
        self.assertEqual((float(r["total_cost"]), round(float(r["cash_won"]), 2), r["days"], r["finish_place"],
                          r["place_pct"], r["summary_missing"], r["provisional"]),
                         (10.0, 7.02, 2, None, None, 1, 0))         # the Day 2 prize is unknown: not counted, flagged
        self.assertIsNone(result(self.db, 900101))
        tags = [x["tag"] for x in self.db.query("SELECT tag FROM tournament_tags WHERE tournament_id = 900103")]
        self.assertFalse([x for x in tags if x.startswith("entry:")])   # no late reg vs start for chips carried over
        flight1 = next(x for x in tournaments_list(self.db) if x["tournament_id"] == 900101)
        self.assertEqual(flight1["day_status"], "event")             # not "Day 2 not played" after 7 days

    def test_a_provisional_prize_counts_until_the_summary_comes(self):
        from pokertracker.importer import set_provisional_prize
        import_texts(self.db, [("s1.txt", STAGE1_ADVANCED), ("d2.txt", DAY2_HANDS)], equity=False)
        self.assertIn("$250.00 counted", set_provisional_prize(self.db, 900103, 250))
        r = result(self.db, 900103)
        self.assertEqual((round(float(r["cash_won"]), 2), round(float(r["profit"]), 2), r["cashed"], r["provisional"]),
                         (257.02, 247.02, 1, 1))
        self.assertIn("has its summary", set_provisional_prize(self.db, 900101, 5))   # only where a summary is missing
        import_texts(self.db, [("d2s.txt", DAY2)], equity=False)    # the summary replaces the amount typed in
        r = result(self.db, 900103)
        self.assertEqual((round(float(r["cash_won"]), 2), r["summary_missing"], r["provisional"], r["finish_place"]),
                         (52.12, 0, 0, 120))
        self.assertIsNone(self.db.scalar("SELECT provisional_prize FROM tournaments WHERE tournament_id = 900103"))
        # one record after the summary: the event once in the results, the Day 2 once in tournaments
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM tournament_results WHERE tournament_id IN (900101, 900103)"), 1)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM tournaments WHERE tournament_id = 900103"), 1)

    def test_the_provisional_command_saves_it(self):
        import tempfile
        from pathlib import Path
        from pokertracker.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            url = f"sqlite:///{Path(tmp) / 'p.db'}"
            with Database(url) as db:
                db.init_schema()
                import_texts(db, [("s1.txt", STAGE1_ADVANCED), ("d2.txt", DAY2_HANDS)], equity=False)
                db.commit()
            main(["--db", url, "provisional", "900103", "250"])
            with Database(url) as db:                                # a new connection sees it
                self.assertEqual(float(db.scalar("SELECT provisional_prize FROM tournaments WHERE tournament_id = 900103")), 250.0)

    def test_migration_links_a_day2_stored_without_its_stage(self):
        import_texts(self.db, [("s1.txt", STAGE1_ADVANCED), ("d2.txt", DAY2_HANDS)], equity=False)
        self.db.execute("UPDATE tournaments SET stage = NULL, event_id = NULL")       # as schema 6 stored them
        self.db.execute("UPDATE schema_version SET version = 6")
        migrate(self.db, fresh=False)
        self.assertEqual([self.db.scalar(f"SELECT stage FROM tournaments WHERE tournament_id = {i}") for i in (900101, 900103)],
                         [None, 2])                                   # day 1 keeps its summary's stage (NULL here)
        self.assertEqual(self.db.scalar("SELECT event_id FROM tournaments WHERE tournament_id = 900101"), 900103)

    def test_migration_moves_ticket_value_out_of_cash(self):
        self.db.execute("INSERT INTO tournaments (site, tournament_id, name, buyin_total, prize_won, prize_is_ticket, "
                        "prize_ticket, has_summary) VALUES ('GGPoker', 1, 'Sat', 50, 500, TRUE, NULL, TRUE)")
        self.db.execute("UPDATE schema_version SET version = 3")
        migrate(self.db, fresh=False)
        r = self.db.query("SELECT prize_won, prize_ticket FROM tournaments WHERE tournament_id = 1")[0]
        self.assertEqual((float(r["prize_won"]), float(r["prize_ticket"])), (0.0, 500.0))


if __name__ == "__main__":
    unittest.main()

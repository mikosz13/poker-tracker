import unittest

from pokertracker.db import Database
from pokertracker.importer import import_texts
from pokertracker.migrations import migrate
from pokertracker.summary import parse_summary
from pokertracker.tickets import tickets_summary
from tests.fixtures import SUMMARY_SATELLITE
from tests.test_stages import STAGE1_ADVANCED

# The tournament the satellite's $50 seat is for, played the next day with the ticket: GGPoker writes the full buy-in
BIG_EVENT = """Tournament #900010, #1: Big Event, Hold'em No Limit
Buy-in: $45+$5
2000 Players
Total Prize Pool: $90,000
Tournament started 2026/01/03 18:00:00
800th : Hero, $0
You finished the tournament in 800th place.
You received a total of $0.
"""
# A "MEGA" satellite (as on Mik's #313552054), with its $54 seat
MEGA = """Tournament #900020, $6 MEGA to WSOP: $54 Sunday Mystery Bounty, 300 Seats, Hold'em No Limit
Buy-in: $5.52+$0.48
4000 Players
Total Prize Pool: $22,080
Tournament started 2026/01/04 16:20:00
120th : Hero, $54 Entry
You finished the tournament in 120th place.
You received a total of $54 Entry.
"""


def result(db, tid):
    return db.query("SELECT * FROM tournament_results WHERE tournament_id = ?", (tid,))[0]


class TicketTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.addCleanup(self.db.close)
        self.db.init_schema()

    def test_satellite_returns_the_ticket_value(self):
        import_texts(self.db, [("sat.txt", SUMMARY_SATELLITE)])
        r = result(self.db, 900002)
        self.assertEqual([float(r[k]) for k in ("total_cost", "won_total", "profit", "roi_pct", "cash_profit", "roi_cash_pct")],
                         [5.0, 50.0, 45.0, 900.0, -5.0, -100.0])

    def test_satellite_and_target_together_match_the_cash_flow(self):
        import_texts(self.db, [("sat.txt", SUMMARY_SATELLITE), ("big.txt", BIG_EVENT)])
        total = sum(float(r["profit"]) for r in self.db.query("SELECT profit FROM tournament_results"))
        self.assertEqual(total, -5.0)                               # $5 paid for the satellite, nothing won
        k = tickets_summary(self.db)
        self.assertEqual((k["count"], k["value"], k["unused_value"]), (1, 50.0, 0))
        self.assertEqual(k["items"][0]["used_in"]["tournament_id"], 900010)    # the ticket entry, information only
        self.assertEqual(float(result(self.db, 900010)["total_cost"]), 50.0)    # the full buy-in all the same

    def test_an_unused_ticket_is_counted_apart(self):
        import_texts(self.db, [("sat.txt", SUMMARY_SATELLITE)])
        k = tickets_summary(self.db)
        self.assertEqual((k["unused_value"], k["items"][0]["used_in"], k["items"][0]["target"]), (50.0, None, "Big Event"))

    def test_mega_is_a_satellite_with_a_target(self):
        import_texts(self.db, [("mega.txt", MEGA)])
        self.assertEqual(self.db.scalar("SELECT format FROM tournaments WHERE tournament_id = 900020"), "satellite")
        tags = [r["tag"] for r in self.db.query("SELECT tag FROM tournament_tags WHERE tournament_id = 900020")]
        self.assertIn("target:WSOP: $54 Sunday Mystery Bounty", tags)

    def test_going_through_to_day_2_is_not_a_satellite(self):
        self.assertEqual(parse_summary(STAGE1_ADVANCED).format, "bounty")     # "$0 Entry" is the next day, not a seat

    def test_format_results_count_tickets(self):
        import_texts(self.db, [("sat.txt", SUMMARY_SATELLITE)])
        f = self.db.query("SELECT * FROM format_results WHERE format = 'satellite'")[0]
        self.assertEqual((float(f["roi_pct"]), float(f["roi_cash_pct"])), (900.0, -100.0))

    def test_migration_turns_stored_mega_into_a_satellite(self):
        self.db.execute("INSERT INTO tournaments (site, tournament_id, name, format, buyin_total, prize_won, prize_ticket, "
                        "prize_is_ticket, has_summary) VALUES ('GGPoker', 7, '$55 MEGA to $525 Super KICKOFF Bounty "
                        "Hunters, 40 Seats', 'regular', 55, 0, 0, FALSE, TRUE)")
        self.db.execute("UPDATE schema_version SET version = 4")
        migrate(self.db, fresh=False)
        self.assertEqual(self.db.scalar("SELECT format FROM tournaments WHERE tournament_id = 7"), "satellite")


if __name__ == "__main__":
    unittest.main()

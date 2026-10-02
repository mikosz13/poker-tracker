import unittest

from pokertracker.db import Database
from pokertracker.importer import import_texts
from pokertracker.migrations import LATEST
from pokertracker.report import build_report
from pokertracker.tournament_report import render_text, tournament_data
from tests.fixtures import HAND_1, SUMMARY_BOUNTY


def with_header(header, hand=HAND_1):
    return "\n".join([header] + hand.splitlines()[1:])


def late_reg(hand_id, tid, name="Deepstack Turbo", stack="20,000"):
    """Hero's first hand in a tournament at level 12 with a full starting stack that is not 10,000."""
    return (HAND_1.replace("TM1000000001", hand_id).replace("Tournament #900001", f"Tournament #{tid}")
            .replace("Bounty Hunters $10", f"{name} $10").replace("Level1(", "Level12(")
            .replace("Seat 3: Hero (5,000 in chips)", f"Seat 3: Hero ({stack} in chips)"))


def summary(tid, name="Deepstack Turbo", reentries=0):
    text = SUMMARY_BOUNTY.replace("Tournament #900001, Bounty Hunters $10", f"Tournament #{tid}, {name} $10")
    return text.replace("You made 1 re-entries", f"You made {reentries} re-entries")


def entries(db, tid):
    return db.query("SELECT entry_no, entry_level, start_stack FROM entries WHERE tournament_id = ? ORDER BY entry_no",
                    (tid,))


def starting_stack(db, tid):
    return db.scalar("SELECT starting_stack FROM tournaments WHERE tournament_id = ?", (tid,))


class EntryTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.addCleanup(self.db.close)
        self.db.init_schema()

    def test_late_reg_with_a_starting_stack_other_than_10000(self):
        import_texts(self.db, [("a", late_reg("TM2000000001", 900010)), ("b", late_reg("TM2000000002", 900011)),
                               ("s", summary(900010))])
        self.assertEqual(entries(self.db, 900010), [{"entry_no": 1, "entry_level": 12, "start_stack": 20000}])
        self.assertEqual(starting_stack(self.db, 900010), 20000)       # learned from both Deepstack Turbo entries
        text = render_text(tournament_data(self.db, 900010))
        self.assertIn("starting stack: 20,000", text)
        self.assertNotIn("incomplete", text + build_report(self.db))

    def test_summary_with_more_entries_than_the_hands_uses_the_hands(self):
        import_texts(self.db, [("a", late_reg("TM2000000001", 900010)), ("s", summary(900010, reentries=2))])
        self.assertEqual(len(entries(self.db, 900010)), 1)
        self.assertNotIn("incomplete", build_report(self.db) + render_text(tournament_data(self.db, 900010)))
        cost = self.db.scalar("SELECT total_cost FROM tournament_results WHERE tournament_id = 900010")
        self.assertEqual(cost, 30)                                      # money still from the summary: 3 x $10

    def test_starting_stack_unknown_without_two_agreeing_entries(self):
        import_texts(self.db, [("a", late_reg("TM2000000003", 900012, name="Lonely Event"))])
        self.assertIsNone(starting_stack(self.db, 900012))
        self.assertIn("starting stack: unknown", render_text(tournament_data(self.db, 900012)))

    def test_same_name_different_buyin_is_a_different_group(self):
        other = late_reg("TM2000000004", 900013).replace("Deepstack Turbo $10", "Deepstack Turbo $20")
        import_texts(self.db, [("a", late_reg("TM2000000001", 900010)), ("b", other)])
        self.assertIsNone(starting_stack(self.db, 900010))
        self.assertIsNone(starting_stack(self.db, 900013))


AOF_SUMMARY = """Tournament #316820499, AoF Hyper Sit & Go Satellite to Bounty Hunters Hyper Special $21.60, AoF Hold'em No Limit
Buy-in: $5.4
4 Players
Total Prize Pool: $21.6
Tournament started 2026/09/30 21:52:37
3rd : Hero, $0
You finished the tournament in 3rd place.
You received a total of $0.
"""
PLO_SUMMARY = """Tournament #309123331, PLO-5 Speed Racer Bounty $5.40, Omaha5 Pot Limit
Buy-in: $2.47+$0.43+$2.5
593 Players
Total Prize Pool: $2,947.21
Tournament started 2026/09/01 20:20:00
349th : Hero, $0
You finished the tournament in 349th place.
You made 1 re-entries and received a total of $0.
"""
YEN_SUMMARY = """Tournament #313537914, Zodiac Bounty ¥33 [Big Bounties], Hold'em No Limit
Buy-in: ¥9.36+¥2.64+¥21
1059 Players
Total Prize Pool: ¥32,151.24
Tournament started 2026/09/23 07:30:00
304th : Hero, ¥0
You finished the tournament in 304th place.
You received a total of ¥0.
"""
AOF_HAND = with_header("Poker Hand #TM57423475: Tournament #310773913, AoF Hyper Sit & Go Satellite to Bounty Hunters "
                       "Hyper Special $21.60 AoF Hold'em No Limit - Level1(50/100) - 2026/09/03 21:20:22")
FLIP_HAND = with_header("Poker Hand #TM6424709061: Tournament #313925042, FlipNGo Sit & Go Satellite to #25: The BIG "
                        "$500 Mystery Bounty NLH Hold'em No Limit - Level1(25/50(6)) - 2026/09/17 22:36:31")
PLO_HAND = with_header("Poker Hand #TM14055763: Tournament #309123331, PLO-5 Speed Racer Bounty $5.40 Omaha5 Pot Limit"
                       " - Level1(500/1,000(150)) - 2026/09/01 20:29:48")
YEN_HAND = with_header("Poker Hand #TM6447829243: Tournament #313537914, Zodiac Bounty ¥33 [Big Bounties] Hold'em No "
                       "Limit - Level13(400/800(100)) - 2026/09/23 09:48:06")
CASH_HAND = with_header("Poker Hand #RC1000000001: Hold'em No Limit ($0.05/$0.1) - 2026/09/03 19:19:00")
OUT = {316820499, 310773913, 313925042, 309123331, 313537914}


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.addCleanup(self.db.close)
        self.db.init_schema()

    def test_out_of_scope_files_are_never_imported_and_counted_by_reason(self):
        s = import_texts(self.db, [("aof-s", AOF_SUMMARY), ("plo-s", PLO_SUMMARY), ("yen-s", YEN_SUMMARY),
                                   ("aof-h", AOF_HAND), ("flip-h", FLIP_HAND), ("plo-h", PLO_HAND),
                                   ("yen-h", YEN_HAND), ("cash", CASH_HAND), ("ok", HAND_1)])
        self.assertEqual(s.ignored_counts(), {"Sit & Go": 3, "PLO/Omaha": 1, "not in $": 1, "cash game": 1})
        self.assertEqual(s.skipped, [])                                 # nothing "unrecognised"
        stored = {r["tournament_id"] for r in self.db.query("SELECT tournament_id FROM tournaments")}
        self.assertEqual(stored, {900001})
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM hands"), 1)

    def test_each_rule(self):
        from pokertracker.scope import hand_reason, tournament_reason
        self.assertEqual(tournament_reason("AoF Hyper Sit & Go Satellite", "AoF Hold'em No Limit"), "Sit & Go")
        self.assertEqual(tournament_reason("PLO Bounty Big Hunter", "Omaha Pot Limit"), "PLO/Omaha")
        self.assertEqual(tournament_reason("Some Stud Event", "7-Card Stud"), "other game")
        self.assertEqual(tournament_reason("Zodiac Bounty ¥33", "Hold'em No Limit"), "not in $")
        self.assertEqual(tournament_reason("Event", "Hold'em No Limit", "Buy-in: €9+€1"), "not in $")
        self.assertIsNone(tournament_reason("WSOP Online: $54 Sunday Mystery Bounty, $1M GTD", "Hold'em No Limit"))
        self.assertIsNone(tournament_reason("$50 Satellite to #25: The BIG $500 Mystery Bounty", "Hold'em No Limit"))
        self.assertEqual(hand_reason(CASH_HAND.splitlines()[0]), "cash game")
        self.assertIsNone(hand_reason(HAND_1.splitlines()[0]))


class MigrationV2Tests(unittest.TestCase):
    def test_upgrade_removes_out_of_scope_and_recomputes_entries(self):
        db = Database("sqlite:///:memory:")
        self.addCleanup(db.close)
        db.init_schema()
        import_texts(db, [("a", late_reg("TM2000000001", 900010)), ("b", late_reg("TM2000000002", 900011))])
        # What 0.3.0 left behind: a Zodiac tournament with a hand, an old flag, no starting stack, schema version 1
        db.execute("INSERT INTO tournaments (site, tournament_id, name) VALUES ('GGPoker', 313537914, 'Zodiac Bounty ¥33')")
        db.execute("INSERT INTO hands (site, hand_id, tournament_id, level, small_blind, big_blind, played_at) "
                   "VALUES ('GGPoker', 'TMZ', 313537914, 13, 400, 800, '2026-09-23 09:48:06')")
        db.execute("INSERT INTO hand_players (site, hand_id, nick, seat, stack, net_won, is_hero) "
                   "VALUES ('GGPoker', 'TMZ', 'Hero', 1, 30000, 0, TRUE)")
        db.execute("UPDATE entries SET starts_fresh = FALSE")
        db.execute("UPDATE tournaments SET starting_stack = NULL")
        db.execute("INSERT INTO equity_cache (cache_key, value) VALUES ('k', '[[0.5]]')")
        db.execute("UPDATE schema_version SET version = 1")
        db.commit()
        db.init_schema()
        self.assertEqual(db.scalar("SELECT version FROM schema_version"), LATEST)
        self.assertIsNone(db.scalar("SELECT tournament_id FROM tournaments WHERE tournament_id = 313537914"))
        self.assertEqual(db.scalar("SELECT COUNT(*) FROM hand_players WHERE hand_id = 'TMZ'"), 0)
        self.assertEqual(starting_stack(db, 900010), 20000)
        self.assertEqual(db.scalar("SELECT COUNT(*) FROM entries WHERE NOT starts_fresh"), 0)
        self.assertEqual(db.scalar("SELECT value FROM equity_cache WHERE cache_key = 'k'"), "[[0.5]]")


if __name__ == "__main__":
    unittest.main()

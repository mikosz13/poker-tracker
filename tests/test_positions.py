import os
import tempfile
import unittest

from pokertracker.db import SQL_DIR, Database
from pokertracker.hands import parse_hands, position_labels
from pokertracker.importer import import_texts
from pokertracker.migrations import LATEST
from pokertracker.replay import hand_replay

# 8 players, button on seat 5, seat 3 empty; everyone folds to the big blind
HAND_8 = """Poker Hand #TM1000000030: Tournament #900005, Bounty Hunters $10 Hold'em No Limit - Level1(25/50(5)) - 2026/01/05 10:00:00
Table '1' 9-max Seat #5 is the button
Seat 1: p1p1p1p1 (5,000 in chips)
Seat 2: p2p2p2p2 (5,000 in chips)
Seat 4: p4p4p4p4 (5,000 in chips)
Seat 5: p5p5p5p5 (5,000 in chips)
Seat 6: p6p6p6p6 (5,000 in chips)
Seat 7: Hero (5,000 in chips)
Seat 8: p8p8p8p8 (5,000 in chips)
Seat 9: p9p9p9p9 (5,000 in chips)
p1p1p1p1: posts the ante 5
p2p2p2p2: posts the ante 5
p4p4p4p4: posts the ante 5
p5p5p5p5: posts the ante 5
p6p6p6p6: posts the ante 5
Hero: posts the ante 5
p8p8p8p8: posts the ante 5
p9p9p9p9: posts the ante 5
p6p6p6p6: posts small blind 25
Hero: posts big blind 50
*** HOLE CARDS ***
Dealt to Hero [7c 2d]
p8p8p8p8: folds
p9p9p9p9: folds
p1p1p1p1: folds
p2p2p2p2: folds
p4p4p4p4: folds
p5p5p5p5: folds
p6p6p6p6: folds
Uncalled bet (25) returned to Hero
Hero collected 90 from pot
*** SUMMARY ***
Total pot 90 | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0
Seat 7: Hero (big blind) collected (90)
"""
EXPECTED_8 = {"p5p5p5p5": "BTN", "p6p6p6p6": "SB", "Hero": "BB", "p8p8p8p8": "UTG", "p9p9p9p9": "UTG+1",
              "p1p1p1p1": "LJ", "p2p2p2p2": "HJ", "p4p4p4p4": "CO"}


class PositionLabelTests(unittest.TestCase):
    EXPECTED = {
        2: ["BTN/SB", "BB"],
        3: ["BTN", "SB", "BB"],
        4: ["BTN", "SB", "BB", "UTG"],
        5: ["BTN", "SB", "BB", "UTG", "CO"],
        6: ["BTN", "SB", "BB", "UTG", "HJ", "CO"],
        7: ["BTN", "SB", "BB", "UTG", "LJ", "HJ", "CO"],
        8: ["BTN", "SB", "BB", "UTG", "UTG+1", "LJ", "HJ", "CO"],
        9: ["BTN", "SB", "BB", "UTG", "UTG+1", "MP", "LJ", "HJ", "CO"],
    }

    def test_every_table_size_from_2_to_9(self):
        for n, expected in self.EXPECTED.items():
            seats = list(range(1, n + 1))
            for button in seats:                                  # any button seat, labels go clockwise from it
                labels = position_labels(seats, button)
                ring = seats[seats.index(button):] + seats[:seats.index(button)]
                self.assertEqual([labels[s] for s in ring], expected, (n, button))

    def test_first_to_act_is_always_utg(self):
        for n in range(4, 10):
            labels = position_labels(range(1, n + 1), 1)
            self.assertEqual(labels[4], "UTG", n)                 # seat after the big blind

    def test_gaps_in_seat_numbers(self):
        self.assertEqual(position_labels([2, 5, 9], 9), {9: "BTN", 2: "SB", 5: "BB"})

    def test_button_on_an_empty_seat_gives_no_labels(self):
        self.assertEqual(position_labels([1, 2, 4], 3), {})

    def test_parser_uses_the_new_labels(self):
        h = parse_hands(HAND_8)[0]
        self.assertEqual(h.positions, EXPECTED_8)
        self.assertEqual(h.button, 5)


def positions(db, hand_id):
    return {r["nick"]: r["position"] for r in db.query("SELECT nick, position FROM hand_players WHERE hand_id = ?", (hand_id,))}


class StoredPositionTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.addCleanup(self.db.close)
        self.db.init_schema()

    def test_import_stores_button_and_positions(self):
        import_texts(self.db, [("h", HAND_8)])
        self.assertEqual(self.db.scalar("SELECT button_seat FROM hands WHERE hand_id = 'TM1000000030'"), 5)
        self.assertEqual(positions(self.db, "TM1000000030"), EXPECTED_8)

    def test_reimport_updates_positions_of_existing_hands(self):
        import_texts(self.db, [("h", HAND_8)])
        self.db.execute("UPDATE hand_players SET position = 'UTG+1' WHERE nick = 'p8p8p8p8'")
        self.db.execute("UPDATE hands SET button_seat = NULL")
        self.db.commit()
        s = import_texts(self.db, [("h", HAND_8)])
        self.assertEqual((s.hands_new, s.hands_duplicate), (0, 1))
        self.assertEqual(positions(self.db, "TM1000000030"), EXPECTED_8)
        self.assertEqual(self.db.scalar("SELECT button_seat FROM hands WHERE hand_id = 'TM1000000030'"), 5)

    def test_replayer_shows_the_new_names(self):
        import_texts(self.db, [("h", HAND_8)])
        r = hand_replay(self.db, "TM1000000030")
        self.assertEqual(r["steps"][0]["next"], "UTG")
        self.assertEqual(r["steps"][1]["label"], "UTG folds")

    def test_new_database_starts_at_the_latest_schema_version(self):
        self.assertEqual(self.db.scalar("SELECT version FROM schema_version"), LATEST)
        self.db.init_schema()                                     # running it again changes nothing
        self.assertEqual(self.db.scalar("SELECT COUNT(*) FROM schema_version"), 1)


class MigrationTests(unittest.TestCase):
    """A database created by 0.2.0 (no button_seat, no schema_version, old labels) is repaired in place."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, "old.db")
        old = (SQL_DIR / "schema.sql").read_text().replace("    button_seat    INTEGER,\n", "")
        old = old[:old.index("-- Version of this schema")] + old[old.index("-- Small key/value store"):]
        db = Database(f"sqlite:///{self.path}")
        db.script(old)
        db.execute("INSERT INTO tournaments (site, tournament_id, name) VALUES ('GGPoker', 900005, 'Bounty Hunters')")
        db.execute("INSERT INTO hands (site, hand_id, tournament_id, level, small_blind, big_blind, ante, played_at, "
                   "max_seats) VALUES ('GGPoker', 'H8', 900005, 1, 25, 50, 5, '2026-01-05 10:00:00', 9)")
        old_labels = {5: "BTN", 6: "SB", 7: "BB", 8: "UTG+1", 9: "MP", 1: "LJ", 2: "HJ", 4: "CO"}   # 0.2.0 output
        db.executemany("INSERT INTO hand_players (site, hand_id, nick, seat, position, stack, net_won, is_hero) "
                       "VALUES ('GGPoker', 'H8', ?, ?, ?, 5000, 0, ?)",
                       [("Hero" if s == 7 else f"p{s}", s, label, s == 7) for s, label in old_labels.items()])
        db.execute("INSERT INTO equity_cache (cache_key, value) VALUES ('k', '[[0.5]]')")
        db.commit()
        db.close()

    def test_old_database_is_upgraded_without_losing_data(self):
        db = Database(f"sqlite:///{self.path}")
        self.addCleanup(db.close)
        db.init_schema()
        self.assertTrue(db.has_column("hands", "button_seat"))
        self.assertEqual(db.scalar("SELECT version FROM schema_version"), LATEST)
        self.assertEqual(db.scalar("SELECT button_seat FROM hands WHERE hand_id = 'H8'"), 5)
        self.assertEqual(positions(db, "H8"), {"p5": "BTN", "p6": "SB", "Hero": "BB", "p8": "UTG", "p9": "UTG+1",
                                               "p1": "LJ", "p2": "HJ", "p4": "CO"})
        self.assertEqual(db.scalar("SELECT value FROM equity_cache WHERE cache_key = 'k'"), "[[0.5]]")
        self.assertEqual(db.scalar("SELECT position FROM hero_position_stats"), "BB")   # views see the new names
        self.assertTrue(os.path.exists(self.path + ".bak-v0"))

    def test_upgrade_runs_once(self):
        for _ in range(2):
            db = Database(f"sqlite:///{self.path}")
            db.init_schema()
            db.close()
        db = Database(f"sqlite:///{self.path}")
        self.addCleanup(db.close)
        self.assertEqual(db.query("SELECT version FROM schema_version"), [{"version": LATEST}])

    def test_interrupted_upgrade_can_be_rerun(self):
        db = Database(f"sqlite:///{self.path}")
        db.execute("ALTER TABLE hands ADD COLUMN button_seat INTEGER")   # as if the first run stopped after the DDL
        db.commit()
        db.init_schema()
        self.assertEqual(positions(db, "H8")["p8"], "UTG")
        db.close()


if __name__ == "__main__":
    unittest.main()

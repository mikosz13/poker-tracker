"""The whole upgrade path, from a 0.2.0 database to the latest schema, on SQLite and on PostgreSQL.

Migrations delete rows (out-of-scope tournaments) and rewrite others (positions, entries, hole cards), so the same
scenario runs on both databases: SQLite always, PostgreSQL when POKERTRACKER_TEST_POSTGRES points at a database that
may be wiped (CI provides one).
"""
import os
import tempfile
import unittest

from pokertracker.db import SQL_DIR, Database
from pokertracker.migrations import LATEST

POSTGRES = os.environ.get("POKERTRACKER_TEST_POSTGRES")


def schema_0_2_0():
    """schema.sql as 0.2.0 had it: no button seat, starting stack, entry count or schema version."""
    s = (SQL_DIR / "schema.sql").read_text()
    for line in ("    button_seat    INTEGER,\n",
                 "    starting_stack  NUMERIC,                 -- most common first-hand stack for this name + buy-in; NULL = unknown\n",
                 "    entries_found   INTEGER,                 -- entries detected in Hero's hands; NULL = no hands\n"):
        assert line in s, line
        s = s.replace(line, "")
    return s[:s.index("-- Version of this schema")] + s[s.index("-- Small key/value store"):]


OLD_LABELS = {5: "BTN", 6: "SB", 7: "BB", 8: "UTG+1", 9: "MP", 1: "LJ", 2: "HJ", 4: "CO"}   # what 0.2.0 wrote
NEW_LABELS = {5: "BTN", 6: "SB", 7: "BB", 8: "UTG", 9: "UTG+1", 1: "LJ", 2: "HJ", 4: "CO"}
OUT_OF_SCOPE = {313537914: "Zodiac Bounty ¥33 [Big Bounties]", 310773913: "AoF Hyper Sit & Go Satellite to Bounty Hunters"}


class UpgradeScenario:
    url = None

    def open(self):
        return Database(self.url)

    def setUp(self):
        db = self.open()
        self.prepare(db)
        db.script(schema_0_2_0())
        ex = db.execute
        ex("INSERT INTO tournaments (site, tournament_id, name) VALUES ('GGPoker', 900005, 'Bounty Hunters')")
        ex("INSERT INTO hands (site, hand_id, tournament_id, level, small_blind, big_blind, ante, played_at, max_seats) "
           "VALUES ('GGPoker', 'H8', 900005, 1, 25, 50, 5, '2026-01-05 10:00:00', 9)")
        for seat, label in OLD_LABELS.items():
            hero = seat == 7
            ex("INSERT INTO hand_players (site, hand_id, nick, seat, position, hole_cards, stack, net_won, is_hero) "
               "VALUES ('GGPoker', 'H8', ?, ?, ?, ?, 5000, 0, ?)",
               ("Hero" if hero else f"p{seat}", seat, label, "Kh" if hero else None, hero))   # Hero: one shown card
        ex("INSERT INTO entries (site, tournament_id, entry_no, entry_level, entered_at, start_stack, start_stack_bb, "
           "starts_fresh, first_hand_id) VALUES ('GGPoker', 900005, 1, 1, '2026-01-05 10:00:00', 5000, 100, FALSE, 'H8')")
        for tid, name in OUT_OF_SCOPE.items():
            hid = f"X{tid}"
            ex("INSERT INTO tournaments (site, tournament_id, name) VALUES ('GGPoker', ?, ?)", (tid, name))
            ex("INSERT INTO hands (site, hand_id, tournament_id, level, small_blind, big_blind, ante, played_at) "
               "VALUES ('GGPoker', ?, ?, 1, 25, 50, 0, '2026-01-06 10:00:00')", (hid, tid))
            ex("INSERT INTO hand_players (site, hand_id, nick, seat, position, stack, net_won, is_hero) "
               "VALUES ('GGPoker', ?, 'Hero', 1, 'BB', 3000, 0, TRUE)", (hid,))
            ex("INSERT INTO actions (site, hand_id, action_order, nick, street, action_type, amount) "
               "VALUES ('GGPoker', ?, 1, 'Hero', 'preflop', 'folds', 0)", (hid,))
            ex("INSERT INTO allin_ev (site, hand_id, nick, is_hero, lock_street, contestants, invested, collected, "
               "ev_net, luck) VALUES ('GGPoker', ?, 'Hero', TRUE, 'preflop', 2, 100, 0, -10, -90)", (hid,))
        ex("INSERT INTO equity_cache (cache_key, value) VALUES ('k', '[[0.5]]')")
        db.commit()
        db.close()

    def prepare(self, db):
        pass

    def count(self, db, table, where="", params=()):
        return db.scalar(f"SELECT COUNT(*) FROM {table} {where}", params)

    def test_upgrade_from_0_2_0_to_latest(self):
        db = self.open()
        self.addCleanup(db.close)
        db.init_schema()
        self.assertEqual(db.scalar("SELECT version FROM schema_version"), LATEST)
        for table, column in (("hands", "button_seat"), ("tournaments", "starting_stack"),
                              ("tournaments", "entries_found")):
            self.assertTrue(db.has_column(table, column), column)
        # migration 1: button seat from the old BTN label, positions renamed
        self.assertEqual(db.scalar("SELECT button_seat FROM hands WHERE hand_id = 'H8'"), 5)
        got = {r["seat"]: r["position"] for r in db.query("SELECT seat, position FROM hand_players WHERE hand_id = 'H8'")}
        self.assertEqual(got, NEW_LABELS)
        # migration 2: out-of-scope tournaments gone with every row that hangs on them, the rest kept
        for table in ("tournaments", "hands"):
            self.assertEqual(self.count(db, table, "WHERE tournament_id <> 900005"), 0, table)
        for table in ("hand_players", "actions", "allin_ev"):
            self.assertEqual(self.count(db, table, "WHERE hand_id <> 'H8'"), 0, table)
        self.assertEqual(self.count(db, "hand_players", "WHERE hand_id = 'H8'"), 8)
        self.assertEqual(db.scalar("SELECT value FROM equity_cache WHERE cache_key = 'k'"), "[[0.5]]")
        # entries recomputed from the hands; migration 3: entry count recorded, a single shown card becomes unknown
        self.assertEqual(db.query("SELECT entry_no, starts_fresh FROM entries WHERE tournament_id = 900005"),
                         [{"entry_no": 1, "starts_fresh": True}])
        self.assertEqual(db.scalar("SELECT entries_found FROM tournaments WHERE tournament_id = 900005"), 1)
        self.assertIsNone(db.scalar("SELECT hole_cards FROM hand_players WHERE hand_id = 'H8' AND is_hero"))

    def test_upgrade_runs_once(self):
        db = self.open()
        self.addCleanup(db.close)
        db.init_schema()
        before = [self.count(db, t) for t in ("tournaments", "hands", "hand_players", "entries", "equity_cache")]
        db.init_schema()
        self.assertEqual([self.count(db, t) for t in ("tournaments", "hands", "hand_players", "entries", "equity_cache")],
                         before)
        self.assertEqual(db.query("SELECT version FROM schema_version"), [{"version": LATEST}])


class SqliteUpgradeTests(UpgradeScenario, unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.url = f"sqlite:///{os.path.join(tmp.name, 'old.db')}"
        super().setUp()


@unittest.skipUnless(POSTGRES, "set POKERTRACKER_TEST_POSTGRES to a throwaway PostgreSQL database to run these tests")
class PostgresUpgradeTests(UpgradeScenario, unittest.TestCase):
    url = POSTGRES

    def prepare(self, db):
        db.script("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")


if __name__ == "__main__":
    unittest.main()

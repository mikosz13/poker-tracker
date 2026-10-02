import unittest
from datetime import datetime, timedelta

from pokertracker.classify import classify, level_minutes
from pokertracker.db import Database
from pokertracker.importer import import_texts
from tests.fixtures import HISTORY, SUMMARY_BOUNTY, SUMMARY_SATELLITE


def hands_every(minutes_per_level, levels, per_level=4, breaks=()):
    """Synthetic (level, timestamp) rows for a tournament with fixed level length."""
    t0, rows, offset = datetime(2026, 1, 1, 10, 0), [], 0.0
    for lv in levels:
        for i in range(per_level):
            rows.append((lv, t0 + timedelta(minutes=offset + i * minutes_per_level / per_level)))
        offset += minutes_per_level + (5 if lv in breaks else 0)
    return rows


class LevelMinutesTests(unittest.TestCase):
    def test_recovers_level_length(self):
        m, pairs = level_minutes(hands_every(8, range(5, 15)))
        self.assertEqual((m, pairs), (8.0, 9))

    def test_breaks_do_not_move_the_median(self):
        m, _ = level_minutes(hands_every(8, range(5, 20), breaks=(9, 14)))
        self.assertEqual(m, 8.0)

    def test_too_few_levels_gives_none(self):
        self.assertEqual(level_minutes(hands_every(8, [14, 15])), (None, 1))

    def test_gaps_in_observed_levels_are_ignored(self):
        rows = hands_every(8, [3, 4, 5, 6, 9, 10])         # levels 7-8 never seen
        m, pairs = level_minutes(rows)
        self.assertEqual((m, pairs), (8.0, 4))


class ClassifyTests(unittest.TestCase):
    def test_bounty_tournament(self):
        tags = classify("Bounty Hunters", "bounty", 21.6, 66, 8.1, 10, 1)
        self.assertEqual(set(tags), {"format:bounty", "stake:low", "field:medium", "speed:regular",
                                     "entry:late", "re-entered"})

    def test_boundaries(self):
        self.assertIn("stake:micro", classify("x", "regular", 5.5, 10, None, None, 0))
        self.assertIn("stake:low", classify("x", "regular", 5.51, 10, None, None, 0))
        self.assertIn("field:small", classify("x", "regular", 10, 49, None, None, 0))
        self.assertIn("field:medium", classify("x", "regular", 10, 50, None, None, 0))
        self.assertIn("speed:turbo", classify("x", "regular", 10, 50, 5.0, None, 0))
        self.assertIn("speed:hyper", classify("x", "regular", 10, 50, 3.0, None, 0))
        self.assertIn("stake:super", classify("x", "regular", 1000, 50, None, None, 0))

    def test_satellite_target_and_no_false_mystery_tag(self):
        tags = classify("$50 Satellite to #25: The BIG $500 Mystery Bounty, 20 Seats", "satellite", 50, 1076, None, 1, 0)
        self.assertIn("target:The BIG $500 Mystery Bounty", tags)
        self.assertNotIn("mystery-bounty", tags)
        self.assertIn("entry:start", tags)

    def test_real_mystery_bounty_tournament(self):
        self.assertIn("mystery-bounty", classify("Mystery Bounty Special", "bounty", 20, 100, None, None, 0))


class ClassificationImportTests(unittest.TestCase):
    def test_tags_stored_and_aggregated(self):
        db = Database("sqlite:///:memory:")
        self.addCleanup(db.close)
        db.init_schema()
        import_texts(db, [("history", HISTORY), ("bounty", SUMMARY_BOUNTY), ("sat", SUMMARY_SATELLITE)])
        tags = {r["tag"] for r in db.query("SELECT tag FROM tournament_tags WHERE tournament_id = 900001")}
        self.assertEqual(tags, {"format:bounty", "stake:low", "field:medium", "entry:start", "re-entered"})
        sat = {r["tag"] for r in db.query("SELECT tag FROM tournament_tags WHERE tournament_id = 900002")}
        self.assertEqual(sat, {"format:satellite", "target:Big Event", "stake:micro", "field:medium"})
        row = db.query("SELECT * FROM tag_results WHERE tag = 'format:satellite'")[0]
        self.assertEqual((int(row["tournaments"]), float(row["cash_won"]), float(row["ticket_value"])), (1, 0.0, 50.0))
        self.assertEqual(db.query("SELECT level_minutes FROM tournament_structure WHERE tournament_id = 900001")[0]["level_minutes"], None)


if __name__ == "__main__":
    unittest.main()

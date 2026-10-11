import unittest

from pokertracker.db import Database
from pokertracker.importer import import_texts
from pokertracker.places import place_stats, share_interval
from tests.fixtures import SUMMARY_BOUNTY, SUMMARY_SATELLITE
from tests.test_stages import STAGE1_ADVANCED, STAGE1_BUST
from tests.test_tickets import BIG_EVENT


class PlaceTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.addCleanup(self.db.close)
        self.db.init_schema()
        # 3rd of 50 (6 %), 5th of 100 (5 %), 1102nd of 9361 (11.8 %), 800th of 2000 (40 %); a Day 2 advance has none
        import_texts(self.db, [("b", SUMMARY_BOUNTY), ("s", SUMMARY_SATELLITE), ("bust", STAGE1_BUST),
                               ("big", BIG_EVENT), ("adv", STAGE1_ADVANCED)])

    def row(self, tid):
        return self.db.query("SELECT * FROM tournament_results WHERE tournament_id = ?", (tid,))[0]

    def test_itm_only_without_bounties(self):
        bounty, sat, big = self.row(900001), self.row(900002), self.row(900010)
        self.assertEqual((bounty["cashed"], bounty["in_the_money"]), (1, None))   # $20: place or knockouts, unknown
        self.assertEqual((sat["cashed"], sat["in_the_money"]), (1, 1))            # a ticket counts
        self.assertEqual((big["cashed"], big["in_the_money"]), (0, 0))

    def test_place_share_and_top_of_the_field(self):
        self.assertIsNone(self.row(900101)["place_pct"])                       # the day-1 advance is not a final place
        p = place_stats(self.db)
        self.assertEqual(p["n"], 4)
        self.assertEqual((p["top10"]["count"], p["top10"]["pct"]), (2, 50.0))
        self.assertEqual((p["top15"]["count"], p["top15"]["pct"]), (3, 75.0))
        self.assertEqual([(b["key"], b["count"], b["expected"]) for b in p["bands"]],
                         [("top10", 2, 10), ("10-25", 1, 15), ("25-50", 1, 25), ("50-100", 0, 50)])
        iv = p["top10"]["interval"]
        self.assertTrue(0 <= iv["low"] <= 50.0 <= iv["high"] <= 100)

    def test_share_interval(self):
        self.assertIsNone(share_interval([1]))
        self.assertEqual(share_interval([1] * 20), {"low": 100.0, "high": 100.0, "level": 95})
        iv = share_interval([1] * 10 + [0] * 90)                              # 10 % of 100 tournaments
        self.assertTrue(4 <= iv["low"] < 10 < iv["high"] <= 17)


if __name__ == "__main__":
    unittest.main()

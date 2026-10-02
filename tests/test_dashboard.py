import unittest

from pokertracker.dashboard import dashboard_data, render_html
from pokertracker.db import Database
from pokertracker.importer import import_texts
from tests.fixtures import HISTORY, SUMMARY_BOUNTY, SUMMARY_SATELLITE


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.addCleanup(self.db.close)
        self.db.init_schema()

    def test_empty_database(self):
        self.assertIn("No data yet", render_html(dashboard_data(self.db)))

    def test_numbers_and_curves(self):
        import_texts(self.db, [("h", HISTORY), ("b", SUMMARY_BOUNTY), ("s", SUMMARY_SATELLITE)])
        d = dashboard_data(self.db)
        self.assertEqual(d["tournaments"], 2)
        self.assertAlmostEqual(d["cost"], 25.0)                      # $10 x 2 entries + $5 satellite
        self.assertAlmostEqual(d["cash"], 20.0)                      # satellite prize is a ticket
        self.assertAlmostEqual(d["tickets"], 50.0)
        self.assertEqual(d["profit_curve"], [0.0, -5.0])             # chronological, cash only
        self.assertEqual(len(d["bb_actual"]), 1)                     # only one tournament has hands
        a = d["allins"]
        self.assertAlmostEqual(d["bb_actual"][0] - d["bb_adjusted"][0], a["luck_bb"], places=1)
        self.assertEqual(d["hands"], 3)
        self.assertEqual([(b["buyin"], b["n"]) for b in d["by_buyin"]], [(5.0, 1), (10.0, 1)])
        self.assertEqual([p["position"] for p in d["positions"]], ["BB"])

    def test_html(self):
        import_texts(self.db, [("h", HISTORY), ("b", SUMMARY_BOUNTY), ("s", SUMMARY_SATELLITE)])
        page = render_html(dashboard_data(self.db))
        for needle in ("<svg", "Small sample (2 tournaments)", "By category", "Recent tournaments", "viewport"):
            self.assertIn(needle, page)


if __name__ == "__main__":
    unittest.main()

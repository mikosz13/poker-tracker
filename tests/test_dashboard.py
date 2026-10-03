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



class PeriodTests(unittest.TestCase):
    """Summaries started 2026-01-01 09:00 (bounty, $10 x 2 entries) and 2026-01-02 09:00 (satellite, $5);
    hands on 2026-01-01 10:00-10:20."""

    def setUp(self):
        from datetime import datetime
        self.db = Database("sqlite:///:memory:")
        self.addCleanup(self.db.close)
        self.db.init_schema()
        import_texts(self.db, [("h", HISTORY), ("b", SUMMARY_BOUNTY), ("s", SUMMARY_SATELLITE)])
        self.now = datetime(2026, 1, 2, 12, 0)

    def test_period_start(self):
        from pokertracker.dashboard import period_start
        self.assertEqual(period_start("24h", self.now), "2026-01-01 12:00:00")
        self.assertEqual(period_start("1w", self.now), "2025-12-26 12:00:00")
        self.assertIsNone(period_start("max", self.now))

    def test_last_24h_keeps_only_what_happened_in_it(self):
        d = dashboard_data(self.db, period="24h", now=self.now)
        self.assertEqual((d["period"], d["tournaments"], d["hands"]), ("24h", 1, 0))   # only the satellite
        self.assertAlmostEqual(d["cost"], 5.0)
        self.assertEqual([b["buyin"] for b in d["by_buyin"]], [5.0])
        self.assertEqual((d["positions"], d["bb_points"], d["allins"]["count"]), ([], [], 0))

    def test_longer_period_equals_max_when_everything_is_inside(self):
        week, everything = (dashboard_data(self.db, period=p, now=self.now) for p in ("1w", "max"))
        for key in ("tournaments", "cost", "cash", "hands", "itm", "profit_points", "bb_points"):
            self.assertEqual(week[key], everything[key], key)

    def test_unknown_period_falls_back_to_max(self):
        self.assertEqual(dashboard_data(self.db, period="nonsense", now=self.now)["period"], "max")

    def test_itm_percent(self):
        d = dashboard_data(self.db, now=self.now)
        self.assertEqual((d["itm"], d["tournaments"], d["itm_pct"]), (2, 2, 100.0))      # 3rd place and a ticket
        self.assertEqual({b["buyin"]: b["itm_pct"] for b in d["by_buyin"]}, {5.0: 100.0, 10.0: 100.0})
        self.assertIsNone(dashboard_data(self.db, period="24h", now=datetime_after(self.now))["itm_pct"])

    def test_dated_chart_points(self):
        d = dashboard_data(self.db, now=self.now)
        self.assertEqual([(p["at"], p["total"]) for p in d["profit_points"]],
                         [("2026-01-01 09:00", 0.0), ("2026-01-02 09:00", -5.0)])
        self.assertEqual(d["bb_points"][0]["at"], "2026-01-01 10:00")
        self.assertAlmostEqual(d["bb_points"][0]["actual"] - d["bb_points"][0]["adjusted"], d["allins"]["luck_bb"],
                               places=1)


def datetime_after(now):
    from datetime import timedelta
    return now + timedelta(days=30)                                  # nothing in the last 24 h


if __name__ == "__main__":
    unittest.main()

"""Variance (pokertracker/variance.py): bootstrap of the next N tournaments from the ones played."""
import unittest

import numpy as np

from pokertracker.db import Database
from pokertracker.demo import build_demo
from pokertracker.importer import import_texts, set_provisional_prize
from pokertracker.variance import (DEFAULT_N, RUNS, abi_series, roi_factor, simulate, variance_data)
from tests.test_stages import DAY2_HANDS, STAGE1_ADVANCED


class SimulateTests(unittest.TestCase):
    def test_known_two_tournament_sample(self):
        # +9 buy-ins (cost 1, won 10) or -1: the final result is 10 k - n with k ~ Binomial(n, 1/2), mean 4 n, sd 5 sqrt(n)
        profit = np.array([9.0, -1.0])
        finals, dd, fan, steps = simulate(profit, 100)
        self.assertEqual(len(finals), RUNS)
        self.assertAlmostEqual(finals.mean(), 400, delta=3)              # 4 x 100; the mean of 10,000 runs, sd 0.5
        self.assertAlmostEqual(np.percentile(finals, 5), 400 - 1.645 * 50, delta=12)
        self.assertTrue((finals % 10 == 0).all())                        # 10 k - 100 is a multiple of 10
        self.assertEqual((steps[0], steps[-1]), (1, 100))
        np.testing.assert_array_equal(fan[:, -1], finals)

    def test_drawdown_from_the_highest_point_the_start_included(self):
        finals, dd, _, _ = simulate(np.array([-1.0]), 50, runs=10)
        self.assertTrue((finals == -50).all() and (dd == 50).all())      # only down: the whole fall from the start
        finals, dd, _, _ = simulate(np.array([1.0]), 50, runs=10)
        self.assertTrue((finals == 50).all() and (dd == 0).all())        # only up: never below the highest point
        # brute force on a few runs: the same seed draws the same tournaments
        profit = np.array([3.0, -1.0, -1.0, 0.5])
        finals, dd, _, _ = simulate(profit, 30, runs=5, seed=7)
        idx = np.random.default_rng(7).integers(0, 4, size=(5, 30))
        for run in range(5):
            total, peak, worst = 0.0, 0.0, 0.0
            for i in idx[run]:
                total += profit[i]
                peak = max(peak, total)
                worst = max(worst, peak - total)
            self.assertAlmostEqual(finals[run], total)
            self.assertAlmostEqual(dd[run], worst)

    def test_fixed_seed_gives_the_same_numbers(self):
        profit = np.array([5.0, -1.0, -1.0, -2.0])
        a, b = simulate(profit, 100), simulate(profit, 100)
        for x, y in zip(a, b):
            np.testing.assert_array_equal(x, y)


class WhatIfTests(unittest.TestCase):
    def test_prizes_scaled_to_the_chosen_roi_losers_stay_at_their_cost(self):
        cost = np.array([1.0, 1.0, 3.0, 1.0])                   # the third: two re-entries
        won = np.array([0.0, 2.5, 0.0, 6.0])
        for roi in (-20, 0, 12.5, 50):
            f = roi_factor(cost, won, roi)
            self.assertAlmostEqual(100 * ((won * f).sum() / cost.sum() - 1), roi)
            self.assertEqual(list((won * f - cost)[[0, 2]]), [-1.0, -3.0])
        self.assertEqual(roi_factor(cost, won, None), 1.0)
        self.assertIsNone(roi_factor(cost, np.zeros(4), 10))    # nothing won: nothing to scale


class AbiTests(unittest.TestCase):
    def test_by_week_for_a_short_history_by_month_for_a_long_one(self):
        rows = [{"started_at": "2026-09-01 10:00:00", "buyin_total": 10}, {"started_at": "2026-09-03 10:00:00", "buyin_total": 20},
                {"started_at": "2026-09-08 10:00:00", "buyin_total": 5}]
        self.assertEqual(abi_series(rows), {"unit": "week", "points": [
            {"key": "2026-08-31", "abi": 15.0, "tournaments": 2}, {"key": "2026-09-07", "abi": 5.0, "tournaments": 1}]})
        rows.append({"started_at": "2027-02-01 10:00:00", "buyin_total": 50})
        self.assertEqual([p["key"] for p in abi_series(rows)["points"]], ["2026-09", "2027-02"])


class VarianceDataTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.addCleanup(self.db.close)
        self.db.init_schema()

    def test_on_the_demo_tournaments(self):
        build_demo(self.db, n=12, equity=False)
        v = variance_data(self.db, n=100)
        self.assertEqual((v["tournaments"], v["unknown"], v["small"], v["n"]), (12, 0, True, 100))
        r = v["result"]
        self.assertTrue(r["p5"] <= r["median"] <= r["p95"])
        self.assertGreaterEqual(v["bankroll"], v["drawdown"]["p95"])
        self.assertEqual(v["roi"], v["roi_played"])
        what = variance_data(self.db, n=100, roi=25)
        self.assertEqual(what["roi"], 25.0)
        self.assertEqual(variance_data(self.db, n=77)["n"], DEFAULT_N)  # only the offered horizons
        self.assertEqual(variance_data(self.db, n=100, roi=900)["roi"], 50.0)   # kept on the slider

    def test_a_day_without_its_summary_is_left_out_until_a_prize_is_typed_in(self):
        import_texts(self.db, [("s1", STAGE1_ADVANCED), ("d2", DAY2_HANDS)], equity=False)
        v = variance_data(self.db)
        self.assertEqual((v["tournaments"], v["unknown"], v["result"]), (0, 1, None))
        set_provisional_prize(self.db, 900103, 250)
        self.assertEqual(variance_data(self.db)["unknown"], 0)


if __name__ == "__main__":
    unittest.main()

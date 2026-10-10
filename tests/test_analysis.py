import random
import unittest

from pokertracker import analysis as A
from pokertracker.db import Database
from pokertracker.importer import import_texts
from tests.fixtures import HISTORY, SUMMARY_BOUNTY, SUMMARY_SATELLITE


def acts(*seq):
    """('Hero', 'raises') ... ; an action ending in '!' is all-in."""
    return [{"nick": n, "action_type": t.rstrip("!"), "all_in": t.endswith("!")} for n, t in
            [("p1", "posts_small_blind"), ("p2", "posts_big_blind"), *seq]]


class PreflopSpotTests(unittest.TestCase):
    def spot(self, *seq):
        return A.preflop_spots(acts(*seq))

    def test_unopened(self):
        self.assertEqual(self.spot(("Hero", "raises")), ("open", None))
        self.assertEqual(self.spot(("Hero", "raises!")), ("open_shove", None))
        self.assertEqual(self.spot(("Hero", "calls")), ("limp", None))
        self.assertEqual(self.spot(("p3", "calls"), ("Hero", "checks")), ("bb_check", None))
        self.assertEqual(self.spot(("Hero", "folds")), ("fold_unopened", None))

    def test_facing_an_open(self):
        self.assertEqual(self.spot(("p3", "raises"), ("Hero", "calls")), ("call_vs_open", None))
        self.assertEqual(self.spot(("p3", "raises"), ("Hero", "raises")), ("3bet", None))
        self.assertEqual(self.spot(("p3", "raises"), ("Hero", "raises!")), ("3bet_shove", None))
        self.assertEqual(self.spot(("p3", "raises"), ("Hero", "folds")), ("fold_vs_open", None))

    def test_two_raises_before_hero_are_cold_spots_not_a_3bet_against_hero(self):
        self.assertEqual(self.spot(("p3", "raises"), ("p4", "raises"), ("Hero", "folds")), ("fold_vs_3bet_cold", None))
        self.assertEqual(self.spot(("p3", "raises"), ("p4", "raises"), ("Hero", "raises")), ("4bet_cold", None))

    def test_answer_to_a_3bet_after_hero_opened(self):
        for answer, expected in (("folds", "fold"), ("calls", "call"), ("raises", "4bet")):
            self.assertEqual(self.spot(("Hero", "raises"), ("p3", "raises"), ("Hero", answer)), ("open", expected))
        self.assertEqual(self.spot(("Hero", "raises"), ("p3", "calls")), ("open", None))      # flat call: no 3-bet
        self.assertEqual(self.spot(("Hero", "raises!"), ("p3", "calls")), ("open_shove", None))


def hand(net, spot="open", position="CO", stack=30.0, after=None, cards="As Kd"):
    return {"hand_id": f"H{random.random()}", "tournament_id": 1, "at": "2026-01-01 10:00", "position": position,
            "stack_bb": stack, "net_bb": net, "vpip": 1, "pfr": 1, "cards": cards, "spot": spot, "after_3bet": after}


class ConfidenceTests(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual([A.confidence(z) for z in (None, 0.5, -0.99, 1.0, -1.99, 2.0, -3.5)],
                         [None, None, None, "possible", "possible", "likely", "likely"])


class LeakTests(unittest.TestCase):
    def setUp(self):
        random.seed(1)

    def test_big_blind_call_compared_with_folding(self):
        calls = [hand(-3.0 + random.uniform(-0.5, 0.5), "call_vs_open", "BB") for _ in range(200)]
        folds = [hand(-1.1, "fold_vs_open", "BB") for _ in range(200)]
        leak = next(l for l in A.leaks(calls + folds) if l["key"] == "bb_defence")
        self.assertEqual(leak["kind"], "vs_fold")
        self.assertAlmostEqual(leak["value"], -1.9, delta=0.1)              # compared with folding, not a raw sum
        self.assertEqual(leak["confidence"], "likely")
        self.assertAlmostEqual(leak["cost_bb"], 380, delta=20)
        self.assertEqual(len(leak["worst"]), 5)

    def test_a_difference_inside_the_noise_is_not_a_leak(self):
        calls = [hand(random.choice([-20.0, 18.0]), "call_vs_open", "BB") for _ in range(100)]
        folds = [hand(-1.1, "fold_vs_open", "BB") for _ in range(100)]
        self.assertFalse([l for l in A.leaks(calls + folds) if l["key"] == "bb_defence"])

    def test_calling_better_than_folding_is_not_a_leak(self):
        calls = [hand(-0.5, "call_vs_open", "BB") for _ in range(100)]
        folds = [hand(-1.1, "fold_vs_open", "BB") for _ in range(100)]
        self.assertFalse([l for l in A.leaks(calls + folds) if l["key"] == "bb_defence"])

    def test_too_few_hands_are_hidden(self):
        calls = [hand(-5.0, "call_vs_open", "BB", cards="") for _ in range(A.HIDE_BELOW - 1)]
        folds = [hand(-1.1, "fold_vs_open", "BB", cards="") for _ in range(100)]
        self.assertFalse(A.leaks(calls + folds))

    def test_folding_to_3bets_is_a_frequency_after_hero_opened(self):
        often = [hand(-2.5, "open", after="fold") for _ in range(90)] + [hand(5.0, "open", after="call") for _ in range(10)]
        leak = next(l for l in A.leaks(often) if l["key"].startswith("fold_to_3bet"))
        self.assertEqual((leak["kind"], leak["value"], leak["hands"]), ("frequency", 90.0, 100))
        self.assertIn("20-40 BB", leak["title"])
        normal = [hand(-2.5, "open", after="fold") for _ in range(40)] + [hand(5.0, "open", after="call") for _ in range(60)]
        self.assertFalse([l for l in A.leaks(normal) if l["key"].startswith("fold_to_3bet")])

    def test_hand_types_need_two_errors_and_stay_possible(self):
        bad = [hand(-6.0 + random.uniform(-1, 1), "call_vs_open", "CO", cards="Kh 9c") for _ in range(40)]
        leak = next(l for l in A.leaks(bad) if l["key"] == "hand_K9o")
        self.assertEqual(leak["confidence"], "possible")                   # ~80 hand types: never "likely"

    def test_likely_leaks_come_first(self):
        hands = ([hand(-3.0 + random.uniform(-0.2, 0.2), "call_vs_open", "BB") for _ in range(300)]
                 + [hand(-1.1, "fold_vs_open", "BB") for _ in range(300)])
        out = A.leaks(hands)
        self.assertEqual(out[0]["confidence"], "likely")


class MoneyTests(unittest.TestCase):
    def test_roi_margin(self):
        trs = [{"total_cost": 10, "profit": 10}, {"total_cost": 10, "profit": -10}]
        # ROI 0; sum of squared deviations 200, x n/(n-1) = 400, sqrt 20, / cost 20 = 1 -> 1.96 x 100 %
        self.assertEqual(A.roi_margin(trs), 196)
        self.assertIsNone(A.roi_margin(trs[:1]))


class AnalysisDataTests(unittest.TestCase):
    def test_whole_history_shape(self):
        db = Database("sqlite:///:memory:")
        self.addCleanup(db.close)
        db.init_schema()
        import_texts(db, [("h", HISTORY), ("b", SUMMARY_BOUNTY), ("s", SUMMARY_SATELLITE)])
        d = A.analysis_data(db)
        self.assertEqual(set(d), {"overview", "leaks", "strengths", "money", "thresholds"})
        self.assertEqual((d["overview"]["hands"], d["overview"]["tournaments"]), (3, 2))
        self.assertEqual([h["spot"] for h in A.load_hands(db)], ["call_vs_open", "call_vs_open", None])
        self.assertEqual(d["money"]["reentries"], {"tournaments": 1, "extra_cost": 10.0, "profit": 0.0})   # 2 x $10, won $20
        self.assertEqual(d["leaks"], [])                                   # three hands: nothing stands out


if __name__ == "__main__":
    unittest.main()

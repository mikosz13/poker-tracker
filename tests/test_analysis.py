import random
import unittest

from pokertracker import analysis as A
from pokertracker.db import Database
from pokertracker.importer import import_texts
from tests.fixtures import HISTORY, SUMMARY_BOUNTY, SUMMARY_SATELLITE

# 6-max, button on seat 1: seat 2 SB, 3 BB, 4 UTG, 5 HJ, 6 CO. Blinds 100/200, ante 25, stacks 10,000.
POS_SEAT = {"BTN": 1, "SB": 2, "BB": 3, "UTG": 4, "HJ": 5, "CO": 6}


def gg_hand(n, hero, actions):
    """A GGPoker hand history with Hero in position `hero`; actions are 'NICK: text' lines after the hole cards,
    where NICK is a position (UTG, HJ ...) or Hero."""
    nick = {pos: ("Hero" if pos == hero else f"p{seat}aaaa") for pos, seat in POS_SEAT.items()}
    lines = [f"Poker Hand #TM20000000{n:02d}: Tournament #910000, Bounty Hunters $10 Hold'em No Limit - "
             f"Level5(100/200(25)) - 2026/02/01 10:{n:02d}:00",
             "Table '1' 6-max Seat #1 is the button"]
    lines += [f"Seat {seat}: {nick[pos]} (10,000 in chips)" for pos, seat in sorted(POS_SEAT.items(), key=lambda x: x[1])]
    lines += [f"{nick[pos]}: posts the ante 25" for pos in POS_SEAT]
    lines += [f"{nick['SB']}: posts small blind 100", f"{nick['BB']}: posts big blind 200", "*** HOLE CARDS ***",
              "Dealt to Hero [Ah Kd]"]
    for a in actions:
        who, text = a.split(": ", 1)
        lines.append(f"{nick.get(who, who)}: {text}")
    lines += ["*** SUMMARY ***", "Total pot 0 | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0"]
    return "\n".join(lines) + "\n"


SPOT_HANDS = {   # name: (hero position, actions, expected (spot, answer to a 3-bet))
    "open": ("UTG", ["Hero: raises 300 to 500", "HJ: folds", "CO: folds", "BTN: folds", "SB: folds", "BB: folds"],
             ("open", None)),
    "open_shove": ("UTG", ["Hero: raises 9,775 to 9,975 and is all-in", "HJ: folds", "CO: folds", "BTN: folds",
                           "SB: folds", "BB: folds"], ("open_shove", None)),
    "fold_unopened": ("UTG", ["Hero: folds", "HJ: folds", "CO: folds", "BTN: folds", "SB: folds"], ("fold_unopened", None)),
    "sb_complete": ("SB", ["UTG: folds", "HJ: folds", "CO: folds", "BTN: folds", "Hero: calls 100", "BB: checks"],
                    ("limp", None)),
    "bb_check": ("BB", ["UTG: calls 200", "HJ: folds", "CO: folds", "BTN: folds", "SB: calls 100", "Hero: checks"],
                 ("bb_check", None)),
    "bb_call": ("BB", ["UTG: raises 300 to 500", "HJ: folds", "CO: folds", "BTN: folds", "SB: folds", "Hero: calls 300"],
                ("call_vs_open", None)),
    "bb_fold": ("BB", ["UTG: raises 300 to 500", "HJ: folds", "CO: folds", "BTN: folds", "SB: folds", "Hero: folds"],
                ("fold_vs_open", None)),
    "3bet": ("CO", ["UTG: raises 300 to 500", "HJ: folds", "Hero: raises 1,000 to 1,500", "BTN: folds", "SB: folds",
                    "BB: folds", "UTG: folds"], ("3bet", None)),
    "3bet_shove": ("CO", ["UTG: raises 300 to 500", "HJ: folds", "Hero: raises 9,475 to 9,975 and is all-in", "BTN: folds",
                          "SB: folds", "BB: folds", "UTG: folds"], ("3bet_shove", None)),
    "own_open_folds_to_3bet": ("UTG", ["Hero: raises 300 to 500", "HJ: raises 1,000 to 1,500", "CO: folds", "BTN: folds",
                                       "SB: folds", "BB: folds", "Hero: folds"], ("open", "fold")),
    "own_open_calls_3bet": ("UTG", ["Hero: raises 300 to 500", "HJ: raises 1,000 to 1,500", "CO: folds", "BTN: folds",
                                    "SB: folds", "BB: folds", "Hero: calls 1,000"], ("open", "call")),
    "own_open_4bets": ("UTG", ["Hero: raises 300 to 500", "HJ: raises 1,000 to 1,500", "CO: folds", "BTN: folds",
                               "SB: folds", "BB: folds", "Hero: raises 2,000 to 3,500", "HJ: folds"], ("open", "4bet")),
    # two raises before Hero acts: a cold spot, never "folding to a 3-bet after your own open"
    "two_raises_before_hero": ("CO", ["UTG: raises 300 to 500", "HJ: raises 1,000 to 1,500", "Hero: folds", "BTN: folds",
                                      "SB: folds", "BB: folds", "UTG: folds"], ("fold_vs_3bet_cold", None)),
}


class SpotDefinitionTests(unittest.TestCase):
    """Every spot on a real GGPoker hand history: parsed, imported and classified like Mik's exports."""

    @classmethod
    def setUpClass(cls):
        cls.db = Database("sqlite:///:memory:")
        cls.db.init_schema()
        cls.names = list(SPOT_HANDS)
        import_texts(cls.db, [(name, gg_hand(i, *SPOT_HANDS[name][:2])) for i, name in enumerate(cls.names)])
        cls.hands = {h["hand_id"]: h for h in A.load_hands(cls.db)}

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def hand(self, name):
        return self.hands[f"TM20000000{self.names.index(name):02d}"]

    def test_every_spot(self):
        for name, (hero, _, expected) in SPOT_HANDS.items():
            h = self.hand(name)
            self.assertEqual((h["spot"], h["after_3bet"]), expected, name)
            self.assertEqual(h["position"], hero, name)

    def test_folding_to_a_3bet_counts_only_after_heros_own_open(self):
        opens = [h for h in self.hands.values() if h["spot"] == "open" and h["after_3bet"]]
        self.assertEqual(sorted(h["after_3bet"] for h in opens), ["4bet", "call", "fold"])
        cold = self.hand("two_raises_before_hero")
        self.assertIsNone(cold["after_3bet"])

    def test_posted_chips_are_exactly_blind_and_ante(self):
        self.assertAlmostEqual(self.hand("bb_fold")["posted_bb"], (200 + 25) / 200)
        self.assertAlmostEqual(self.hand("sb_complete")["posted_bb"], (100 + 25) / 200)
        self.assertAlmostEqual(self.hand("open")["posted_bb"], 25 / 200)
        self.assertAlmostEqual(self.hand("bb_fold")["adj_bb"], -(200 + 25) / 200)   # a fold loses just that


def hand(adj, spot="open", position="CO", stack=30.0, after=None, cards="", posted=0.125, net=None):
    return {"hand_id": f"H{random.random()}", "tournament_id": 1, "at": "2026-01-01 10:00", "position": position,
            "stack_bb": stack, "net_bb": adj if net is None else net, "adj_bb": adj, "posted_bb": posted, "vpip": 1,
            "pfr": 1, "cards": cards, "spot": spot, "after_3bet": after}


class StatisticsTests(unittest.TestCase):
    def test_benjamini_hochberg(self):
        # sorted p 0.005, 0.01, 0.03, 0.04 (m = 4): p * m / rank = 0.02, 0.02, 0.04, 0.04, then made monotone
        q = A.benjamini_hochberg([0.01, 0.04, 0.03, 0.005])
        self.assertEqual([round(x, 4) for x in q], [0.02, 0.04, 0.04, 0.02])

    def test_one_and_two_sided_p_values(self):
        self.assertAlmostEqual(A.p_value(-1.96), 0.05, places=3)
        self.assertAlmostEqual(A.p_value(-1.645, "leak"), 0.05, places=3)
        self.assertAlmostEqual(A.p_value(-1.645, "strength"), 0.95, places=3)   # the wrong side is not a finding
        self.assertAlmostEqual(A.p_value(1.645, "strength"), 0.05, places=3)

    def test_roi_bootstrap_is_a_95_percent_interval(self):
        # 20 tournaments, cost 1 each, half +1 and half -1: resampled ROI = (2k/20 - 1) * 100 with k ~ Binomial(20, 1/2),
        # whose 2.5 % and 97.5 % points are k = 6 and k = 14, i.e. -40 % and +40 %
        trs = [{"total_cost": 1, "profit": 1}] * 10 + [{"total_cost": 1, "profit": -1}] * 10
        ri = A.roi_interval(trs)
        self.assertEqual((ri["level"], ri["samples"]), (95, A.BOOTSTRAP_SAMPLES))
        self.assertAlmostEqual(ri["low"], -40, delta=5)
        self.assertAlmostEqual(ri["high"], 40, delta=5)
        self.assertEqual(A.roi_interval(trs), ri)                                   # seeded: reproducible

    def test_roi_bootstrap_weighs_by_cost_with_reentries(self):
        same = [{"total_cost": 20, "profit": -10}, {"total_cost": 10, "profit": -5}]  # every tournament at -50 %
        self.assertEqual({k: A.roi_interval(same)[k] for k in ("low", "high")}, {"low": -50.0, "high": -50.0})
        self.assertIsNone(A.roi_interval(same[:1]))


class LeakRuleTests(unittest.TestCase):
    def setUp(self):
        random.seed(1)

    def classify(self, hands):
        return A.classify(A.spot_tests(hands))

    def test_big_blind_call_against_exactly_the_posted_blind_and_ante(self):
        calls = [hand(-3.0 + random.uniform(-0.3, 0.3), "call_vs_open", "BB", posted=1.125) for _ in range(200)]
        leaks, _ = self.classify(calls)
        leak = next(l for l in leaks if l["key"] == "bb_defence")
        self.assertAlmostEqual(leak["folded"], -1.125, places=2)                    # baseline: blind + ante
        self.assertAlmostEqual(leak["value"], -3.0 + 1.125, delta=0.05)
        self.assertEqual(leak["confidence"], "likely")

    def test_ev_adjusted_result_is_used(self):
        # actual results look awful (lost coinflips), but the EV-adjusted results equal folding: no leak
        calls = [hand(-1.125, "call_vs_open", "BB", posted=1.125, net=-30.0) for _ in range(200)]
        leaks, _ = self.classify(calls)
        self.assertFalse([l for l in leaks if l["key"] == "bb_defence"])

    def test_one_effect_among_many_noise_tests(self):
        # 60 hand types of pure noise plus one real leak: the correction keeps the noise out
        ranks = "23456789TJQKA"
        hands = []
        for i in range(60):                          # 60 distinct offsuit hand types, each swinging +-3 BB around 0
            hi, lo = ranks[12 - i % 12], ranks[(i // 12) % 5]
            hands += [hand(3.0 if k % 2 else -3.0, stack=60.0, cards=f"{hi}c {lo}d", posted=0.0) for k in range(40)]
        hands += [hand(-4.0 + random.gauss(0, 0.5), "call_vs_open", "BB", posted=1.125) for _ in range(150)]
        leaks, _ = self.classify(hands)
        self.assertIn("bb_defence", [l["key"] for l in leaks if l["confidence"] == "likely"])
        self.assertFalse([l for l in leaks if l["key"].startswith("hand_")])

    def test_hand_types_against_folding_them(self):
        # a trash hand folded from the blinds loses the blind and ante, which is not a leak
        trash = [hand(-1.125, "fold_vs_open", "BB", cards="7c 2d", posted=1.125) for _ in range(100)]
        leaks, _ = self.classify(trash)
        self.assertFalse([l for l in leaks if l["key"] == "hand_72o"])

    def test_folding_to_3bets_often_is_a_leak_rarely_is_not_praise(self):
        often = [hand(-2.5, after="fold") for _ in range(90)] + [hand(5.0, after="call") for _ in range(10)]
        leaks, strengths = self.classify(often)
        self.assertTrue([l for l in leaks if l["key"].startswith("fold_to_3bet")])
        rarely = [hand(-2.5, after="fold") for _ in range(20)] + [hand(5.0, after="call") for _ in range(80)]
        leaks, strengths = self.classify(rarely)
        self.assertFalse([x for x in leaks + strengths if x["key"].startswith("fold_to_3bet")])

    def test_profitable_line_is_a_strength(self):
        shoves = [hand(1.5 + random.uniform(-0.5, 0.5), "open_shove") for _ in range(150)]
        _, strengths = self.classify(shoves)
        self.assertEqual(next(s for s in strengths if s["key"] == "line_open_shove")["confidence"], "likely")


class AnalysisDataTests(unittest.TestCase):
    def test_whole_history_shape(self):
        db = Database("sqlite:///:memory:")
        self.addCleanup(db.close)
        db.init_schema()
        import_texts(db, [("h", HISTORY), ("b", SUMMARY_BOUNTY), ("s", SUMMARY_SATELLITE)])
        d = A.analysis_data(db)
        self.assertEqual(set(d), {"overview", "leaks", "strengths", "money", "tested", "thresholds"})
        self.assertEqual((d["overview"]["hands"], d["overview"]["tournaments"]), (3, 2))
        self.assertEqual(d["money"]["reentries"], {"tournaments": 1, "extra_cost": 10.0, "profit": 0.0})
        self.assertEqual(d["leaks"], [])
        self.assertEqual(d["money"]["roi_interval"]["level"], 95)


if __name__ == "__main__":
    unittest.main()

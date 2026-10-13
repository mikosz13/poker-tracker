"""PokerTracker 4 style preflop rates (pokertracker/preflop.py) on GGPoker hand texts."""
import unittest
from datetime import datetime

from pokertracker import preflop
from pokertracker.analysis import DEPTHS, load_hands
from pokertracker.db import Database
from pokertracker.importer import import_texts
from tests.test_analysis import gg_hand

FOLDS_AFTER_UTG = ["HJ: folds", "CO: folds", "BTN: folds", "SB: folds", "BB: folds"]
CASES = {   # name: (Hero's position, actions, expected counts (rfi_opp, rfi, shove, tb_opp, tb, f3_opp, f3))
    "rfi_open": ("UTG", ["Hero: raises 300 to 500", *FOLDS_AFTER_UTG], (1, 1, 0, 0, 0, 0, 0)),
    "rfi_open_shove": ("UTG", ["Hero: raises 9,775 to 9,975 and is all-in", *FOLDS_AFTER_UTG], (1, 1, 1, 0, 0, 0, 0)),
    "rfi_fold": ("UTG", ["Hero: folds", "HJ: folds", "CO: folds", "BTN: folds", "SB: folds"], (1, 0, 0, 0, 0, 0, 0)),
    "rfi_limp_is_not_a_raise": ("UTG", ["Hero: calls 200", "HJ: folds", "CO: folds", "BTN: folds", "SB: folds",
                                        "BB: checks"], (1, 0, 0, 0, 0, 0, 0)),
    "sb_complete_is_an_rfi_chance": ("SB", ["UTG: folds", "HJ: folds", "CO: folds", "BTN: folds", "Hero: calls 100",
                                            "BB: checks"], (1, 0, 0, 0, 0, 0, 0)),
    "raise_over_a_limper_is_not_rfi": ("CO", ["UTG: calls 200", "HJ: folds", "Hero: raises 600 to 800", "BTN: folds",
                                              "SB: folds", "BB: folds", "UTG: folds"], (0, 0, 0, 0, 0, 0, 0)),
    "bb_never_has_rfi": ("BB", ["UTG: calls 200", "HJ: folds", "CO: folds", "BTN: folds", "SB: folds", "Hero: checks"],
                         (0, 0, 0, 0, 0, 0, 0)),
    "3bet_chance_called": ("BB", ["UTG: raises 300 to 500", "HJ: folds", "CO: folds", "BTN: folds", "SB: folds",
                                  "Hero: calls 300"], (0, 0, 0, 1, 0, 0, 0)),
    "3bet": ("CO", ["UTG: raises 300 to 500", "HJ: folds", "Hero: raises 1,000 to 1,500", "BTN: folds", "SB: folds",
                    "BB: folds", "UTG: folds"], (0, 0, 0, 1, 1, 0, 0)),
    "squeeze_is_a_3bet": ("CO", ["UTG: raises 300 to 500", "HJ: calls 500", "Hero: raises 1,500 to 2,000", "BTN: folds",
                                 "SB: folds", "BB: folds", "UTG: folds", "HJ: folds"], (0, 0, 0, 1, 1, 0, 0)),
    "two_raises_before_is_no_3bet_chance": ("BTN", ["UTG: raises 300 to 500", "HJ: raises 1,000 to 1,500", "CO: folds",
                                                    "Hero: folds", "SB: folds", "BB: folds", "UTG: folds"],
                                            (0, 0, 0, 0, 0, 0, 0)),
    "fold_to_3bet": ("UTG", ["Hero: raises 300 to 500", "HJ: raises 1,000 to 1,500", "CO: folds", "BTN: folds",
                             "SB: folds", "BB: folds", "Hero: folds"], (1, 1, 0, 0, 0, 1, 1)),
    "call_a_3bet": ("UTG", ["Hero: raises 300 to 500", "HJ: raises 1,000 to 1,500", "CO: folds", "BTN: folds",
                            "SB: folds", "BB: folds", "Hero: calls 1,000"], (1, 1, 0, 0, 0, 1, 0)),
    "3bet_and_cold_4bet_is_no_fold_to_3bet": ("UTG", ["Hero: raises 300 to 500", "HJ: raises 1,000 to 1,500",
                                                      "CO: raises 2,500 to 4,000", "BTN: folds", "SB: folds", "BB: folds",
                                                      "Hero: folds", "HJ: folds"], (1, 1, 0, 0, 0, 0, 0)),
    "open_shove_re_raised_is_no_fold_to_3bet": ("UTG", ["Hero: raises 9,775 to 9,975 and is all-in", "HJ: calls 9,975",
                                                        "CO: folds", "BTN: folds", "SB: folds", "BB: folds"],
                                                (1, 1, 1, 0, 0, 0, 0)),
}


class HandStatsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database("sqlite:///:memory:")
        cls.db.init_schema()
        import_texts(cls.db, [(name, gg_hand(i, hero, actions)) for i, (name, (hero, actions, _)) in
                              enumerate(CASES.items(), 1)], equity=False)
        cls.hands = {h["hand_id"]: h for h in load_hands(cls.db)}

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_each_case(self):
        for i, (name, (_, _, expected)) in enumerate(CASES.items(), 1):
            pf = self.hands[f"TM20000000{i:02d}"]["pf"]
            self.assertEqual(tuple(pf[k] for k in preflop.COUNTS), expected, name)

    def test_rates_count_only_opportunities(self):
        t = preflop.summarise(list(self.hands.values()))
        self.assertEqual((t["rfi"]["count"], t["rfi"]["n"]), (6, 9))       # 6 raises of 9 unopened first decisions
        self.assertEqual((t["shove"]["count"], t["shove"]["n"]), (2, 9))
        self.assertEqual((t["threebet"]["count"], t["threebet"]["n"]), (2, 3))
        self.assertEqual((t["fold3"]["count"], t["fold3"]["n"]), (1, 2))
        self.assertTrue(t["fold3"]["few"])                                 # under 30 opportunities: greyed
        rows = {r["position"]: r for r in preflop.by_position(list(self.hands.values()))}
        self.assertEqual(rows["BB"]["rfi"]["n"], 0)                         # the big blind never raises first in
        self.assertEqual(list(rows), [p for p in preflop.POSITIONS if p in rows])
        depths = preflop.by_depth(list(self.hands.values()), DEPTHS)
        self.assertEqual([d["depth"] for d in depths], ["40+ BB"])          # 10,000 chips at 200: 50 BB


class AllInRaiseTests(unittest.TestCase):
    """A 3-bet chance facing an all-in raise only when Hero can raise over it (decision 2026-10-13)."""

    def stats(self, n, actions, utg_chips=None):
        from tests.test_analysis import POS_SEAT
        text = gg_hand(n, "BB", actions)
        if utg_chips:                                   # a short UTG: all-in for less than Hero has
            seat = POS_SEAT["UTG"]
            text = text.replace(f"Seat {seat}: p{seat}aaaa (10,000 in chips)", f"Seat {seat}: p{seat}aaaa ({utg_chips} in chips)")
        db = Database("sqlite:///:memory:")
        self.addCleanup(db.close)
        db.init_schema()
        import_texts(db, [("h", text)], equity=False)
        pf = load_hands(db)[0]["pf"]
        return pf["tb_opp"], pf["tb"]

    def test_an_all_in_hero_cannot_raise_over_is_no_chance(self):
        # Hero has 10,000 and posts a 25 ante: calling 9,975 puts Hero all-in, so a re-raise is impossible
        self.assertEqual(self.stats(1, ["UTG: raises 9,775 to 9,975 and is all-in", "HJ: folds", "CO: folds",
                                        "BTN: folds", "SB: folds", "Hero: calls 9,775"]), (0, 0))

    def test_an_all_in_for_less_stays_a_chance_for_an_isolation(self):
        # UTG is all-in for 4,200; Hero has 10,000 and can re-raise to isolate
        self.assertEqual(self.stats(2, ["UTG: raises 4,000 to 4,200 and is all-in", "HJ: folds", "CO: folds",
                                        "BTN: folds", "SB: folds", "Hero: raises 5,575 to 9,775 and is all-in"],
                                    utg_chips="4,225"), (1, 1))
        self.assertEqual(self.stats(3, ["UTG: raises 4,000 to 4,200 and is all-in", "HJ: folds", "CO: folds",
                                        "BTN: folds", "SB: folds", "Hero: calls 4,000"], utg_chips="4,225"), (1, 0))


def fake(at, vpip, tb_opp=0, tb=0):
    return {"at": at, "adj_bb": 0.0, "decided": 1, "vpip": vpip, "pfr": 0,
            "pf": dict(dict.fromkeys(preflop.COUNTS, 0), tb_opp=tb_opp, tb=tb)}


class TrendTests(unittest.TestCase):
    now = datetime(2026, 10, 13, 12, 0)

    def test_no_trend_without_500_hands_on_each_side(self):
        hands = [fake("2026-10-10 10:00", 1)] * 499 + [fake("2026-08-01 10:00", 0)] * 2000
        tr = preflop.trend(hands, self.now)
        self.assertEqual((tr["recent_hands"], tr["stats"], tr["arrow"]), (499, {}, None))

    def test_one_arrow_for_the_largest_change_beyond_noise(self):
        recent = [fake("2026-10-10 10:00", 1 if i < 400 else 0, tb_opp=1, tb=1 if i < 120 else 0) for i in range(1000)]
        older = [fake("2026-08-01 10:00", 1 if i < 300 else 0, tb_opp=1, tb=1 if i < 100 else 0) for i in range(1000)]
        tr = preflop.trend(recent + older, self.now)
        self.assertGreater(abs(tr["stats"]["vpip"]["z"]), 2.5)             # 40 % vs 30 %
        self.assertGreater(abs(tr["stats"]["threebet"]["z"]), 1.0)         # 12 % vs 10 %: not beyond noise
        self.assertEqual(tr["arrow"], {"key": "vpip", "up": True})

    def test_a_rate_with_too_few_opportunities_is_not_compared(self):
        recent = [fake("2026-10-10 10:00", 1, tb_opp=1 if i < 99 else 0, tb=1) for i in range(600)]
        older = [fake("2026-08-01 10:00", 1, tb_opp=1, tb=0) for i in range(600)]
        tr = preflop.trend(recent + older, self.now)
        self.assertNotIn("threebet", tr["stats"])                          # 99 opportunities in the last 30 days


if __name__ == "__main__":
    unittest.main()

"""Showdown lines (analysis.showdown_lines) on GGPoker hand texts: which hands Hero took to showdown."""
import unittest

from pokertracker.analysis import load_hands, showdown_lines
from pokertracker.db import Database
from pokertracker.importer import import_texts
from tests.test_analysis import gg_hand

CALL_TO_RIVER = ["UTG: raises 300 to 500", "HJ: folds", "CO: folds", "BTN: folds", "SB: folds", "Hero: calls 300",
                 "*** FLOP *** [2c 7d 9h]", "Hero: checks", "UTG: checks", "*** TURN *** [2c 7d 9h] [Js]",
                 "Hero: checks", "UTG: checks", "*** RIVER *** [2c 7d 9h Js] [3d]", "Hero: checks", "UTG: checks",
                 "*** SHOWDOWN ***"]
CASES = {   # name: (Hero's position, actions, Hero at showdown)
    "showdown_won": ("BB", CALL_TO_RIVER + ["UTG: shows [Qc Qd]", "Hero: shows [Ah Kd]", "Hero collected 1,150 from pot"],
                     True),
    "showdown_lost": ("BB", CALL_TO_RIVER + ["UTG: shows [Jc Jd]", "Hero: shows [Ah Kd]", "UTG collected 1,150 from pot"],
                      True),
    "fold_on_the_river_then_others_show": ("BB", ["UTG: raises 300 to 500", "HJ: calls 500", "CO: folds", "BTN: folds",
                                                  "SB: folds", "Hero: calls 300", "*** FLOP *** [2c 7d 9h]",
                                                  "Hero: checks", "UTG: bets 500", "HJ: calls 500", "Hero: folds",
                                                  "*** TURN *** [2c 7d 9h] [Js]", "UTG: checks", "HJ: checks",
                                                  "*** RIVER *** [2c 7d 9h Js] [3d]", "UTG: checks", "HJ: checks",
                                                  "*** SHOWDOWN ***", "UTG: shows [Qc Qd]", "HJ: shows [Tc Td]",
                                                  "UTG collected 2,600 from pot"], False),
    "preflop_all_in_called": ("UTG", ["Hero: raises 9,775 to 9,975 and is all-in", "HJ: calls 9,975", "CO: folds",
                                      "BTN: folds", "SB: folds", "BB: folds", "Hero: shows [Ah Kd]",
                                      "HJ: shows [Qc Qd]", "*** FLOP *** [2c 7d 9h]", "*** TURN *** [2c 7d 9h] [Js]",
                                      "*** RIVER *** [2c 7d 9h Js] [Kc]", "*** SHOWDOWN ***",
                                      "Hero collected 20,400 from pot"], True),
    "uncalled_shove_is_a_steal": ("UTG", ["Hero: raises 9,775 to 9,975 and is all-in", "HJ: folds", "CO: folds",
                                          "BTN: folds", "SB: folds", "BB: folds",
                                          "Uncalled bet (9,775) returned to Hero", "Hero collected 450 from pot"], False),
}


class ShowdownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database("sqlite:///:memory:")
        cls.db.init_schema()
        import_texts(cls.db, [(name, gg_hand(i, hero, actions)) for i, (name, (hero, actions, _)) in
                              enumerate(CASES.items(), 1)], equity=False)
        cls.hands = load_hands(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_each_case(self):
        by_id = {h["hand_id"]: h for h in self.hands}
        for i, (name, (_, _, expected)) in enumerate(CASES.items(), 1):
            self.assertEqual(by_id[f"TM20000000{i:02d}"]["showdown"], expected, name)

    def test_lines_add_up_and_count_showdowns(self):
        s = showdown_lines(self.hands)
        f = s["final"]
        self.assertEqual((s["hands"], s["showdowns"]), (5, 3))
        self.assertAlmostEqual(f["sd"] + f["nsd"], f["total"], places=1)          # every hand is on exactly one side
        self.assertAlmostEqual(f["total"], round(sum(h["net_bb"] for h in self.hands), 1), places=1)
        self.assertEqual(s["points"][-1]["n"], 5)

    def test_points_are_thinned_but_keep_the_last_hand(self):
        hands = [dict(self.hands[0], at="2026-02-01 10:00") for _ in range(1000)]
        s = showdown_lines(hands, points=300)
        self.assertLessEqual(len(s["points"]), 300)
        self.assertEqual(s["points"][-1]["n"], 1000)


if __name__ == "__main__":
    unittest.main()

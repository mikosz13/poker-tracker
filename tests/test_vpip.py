"""VPIP and PFR as PokerTracker 4 counts them, on GGPoker hand texts (format of tests.test_analysis.gg_hand)."""
import unittest

from pokertracker.dashboard import dashboard_data
from pokertracker.db import Database
from pokertracker.importer import import_texts
from tests.test_analysis import gg_hand


def forced_all_in(text):
    """Hero in the big blind with 225 chips: the ante and the blind put Hero all-in before any decision."""
    return (text.replace("Seat 3: Hero (10,000 in chips)", "Seat 3: Hero (225 in chips)")
                .replace("Hero: posts big blind 200", "Hero: posts big blind 200 and is all-in"))


HANDS = {   # name: (hand text, expected (decided, vpip, pfr))
    "walk": (gg_hand(1, "BB", ["UTG: folds", "HJ: folds", "CO: folds", "BTN: folds", "SB: folds"]), (0, 0, 0)),
    "bb_checks_a_limped_pot": (gg_hand(2, "BB", ["UTG: calls 200", "HJ: folds", "CO: folds", "BTN: folds",
                                                 "SB: calls 100", "Hero: checks"]), (1, 0, 0)),
    "sb_completes": (gg_hand(3, "SB", ["UTG: folds", "HJ: folds", "CO: folds", "BTN: folds", "Hero: calls 100",
                                       "BB: checks"]), (1, 1, 0)),
    "all_in_forced_by_the_blind": (forced_all_in(gg_hand(4, "BB", ["UTG: calls 200", "HJ: folds", "CO: folds",
                                                                    "BTN: folds", "SB: folds"])), (0, 0, 0)),
    "limp_raise": (gg_hand(5, "UTG", ["Hero: calls 200", "HJ: raises 300 to 500", "CO: folds", "BTN: folds",
                                      "SB: folds", "BB: folds", "Hero: raises 1,000 to 1,500", "HJ: folds"]), (1, 1, 1)),
    "fold": (gg_hand(6, "CO", ["UTG: folds", "HJ: folds", "Hero: folds", "BTN: folds", "SB: folds"]), (1, 0, 0)),
}


class VpipPfrTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.addCleanup(self.db.close)
        self.db.init_schema()
        import_texts(self.db, [(name, text) for name, (text, _) in HANDS.items()], equity=False)
        self.rows = {r["hand_id"]: r for r in self.db.query("SELECT hand_id, decided, vpip, pfr FROM hero_hands")}

    def test_each_case(self):
        for i, (name, (_, expected)) in enumerate(HANDS.items(), 1):
            r = self.rows[f"TM20000000{i:02d}"]
            self.assertEqual((r["decided"], r["vpip"], r["pfr"]), expected, name)

    def test_walks_and_forced_all_ins_leave_the_denominator(self):
        d = dashboard_data(self.db)
        self.assertEqual((d["hands"], d["decided"]), (6, 4))
        self.assertEqual((round(d["vpip_pct"], 1), round(d["pfr_pct"], 1)), (50.0, 25.0))   # 2 of 4, 1 of 4


if __name__ == "__main__":
    unittest.main()

import unittest

from pokertracker.dashboard import MIN_HANDS, best_and_worst, hand_class, luck_badge


def allin(equity, pot_bb, won, invested_bb=None):
    """Heads-up all-in for a pot of pot_bb: luck = actual - expected."""
    invested = pot_bb / 2 if invested_bb is None else invested_bb
    ev = equity * pot_bb - invested
    net = (pot_bb if won else 0) - invested
    return {"equity": equity, "ev_bb": ev, "invested_bb": invested, "luck_bb": net - ev}


class LuckBadgeTests(unittest.TestCase):
    def test_no_allins(self):
        b = luck_badge([])
        self.assertEqual((b["level"], b["z"], b["count"]), ("No all-ins", None, 0))

    def test_z_is_luck_over_the_typical_swing(self):
        # one 50% all-in for 100 BB lost: luck -50 BB, swing sqrt(.25 * 100^2) = 50 BB -> z = -1
        b = luck_badge([allin(0.5, 100, False)])
        self.assertEqual((b["z"], b["luck_bb"], b["level"], b["small_sample"]), (-1.0, -50.0, "Bad run", True))

    def test_two_lost_coinflips_are_not_a_worst_run_but_a_series_of_80_percent_losses_is(self):
        flips = luck_badge([allin(0.5, 100, False), allin(0.5, 100, True)] * 10 + [allin(0.5, 100, False)] * 2)
        self.assertEqual(flips["level"], "Average")
        usual = luck_badge([allin(0.8, 100, False)] * 6 + [allin(0.8, 100, True)] * 20)   # 6 of 26 lost: 5.2 expected
        self.assertEqual(usual["level"], "Average")
        beats = luck_badge([allin(0.8, 100, False)] * 6 + [allin(0.8, 100, True)] * 4)    # 6 of 10 lost: 2 expected
        self.assertEqual((beats["level"], beats["z"]), ("Worst run", -3.16))

    def test_levels_and_boundaries(self):
        def level(z):                                               # luck chosen so that z comes out exactly
            return luck_badge([{"equity": 0.5, "ev_bb": 0, "invested_bb": 50, "luck_bb": 50 * z}])["level"]
        self.assertEqual([level(z) for z in (2, 1.5, 0.5, 0.49, -0.49, -0.5, -1.49, -1.5, -3)],
                         ["Very lucky", "Very lucky", "Lucky", "Average", "Average", "Bad run", "Bad run",
                          "Worst run", "Worst run"])

    def test_sure_things_add_no_swing(self):
        b = luck_badge([allin(1.0, 100, True), allin(0.5, 100, True)])
        self.assertEqual(b["z"], 1.0)


class HandClassTests(unittest.TestCase):
    def test_classes(self):
        self.assertEqual([hand_class(c) for c in ("Td 5d", "5d Td", "Qh Tc", "9s 9c", "Ah Kh")],
                         ["T5s", "T5s", "QTo", "99", "AKs"])

    def test_not_two_cards(self):
        self.assertEqual([hand_class(c) for c in (None, "", "7s", "As Ks Qs")], [None, None, None, None])


class BestAndWorstTests(unittest.TestCase):
    def test_only_groups_with_enough_hands_are_ranked(self):
        groups = [{"hand": "AA", "hands": MIN_HANDS, "net_bb": 50.0}, {"hand": "72o", "hands": MIN_HANDS + 5, "net_bb": -9.0},
                  {"hand": "KK", "hands": MIN_HANDS - 1, "net_bb": 999.0}, {"hand": "32o", "hands": 3, "net_bb": -999.0}]
        r = best_and_worst(groups, "net_bb")
        self.assertEqual((r["best"]["hand"], r["worst"]["hand"], r["ranked"]), ("AA", "72o", 2))

    def test_nothing_qualifies(self):
        r = best_and_worst([{"hand": "AA", "hands": MIN_HANDS - 1, "net_bb": 5.0}], "net_bb")
        self.assertEqual((r["best"], r["worst"], r["ranked"]), (None, None, 0))

    def test_one_group_has_no_worst(self):
        r = best_and_worst([{"position": "BB", "hands": MIN_HANDS, "bb_per_100": -20.0}], "bb_per_100")
        self.assertEqual((r["best"]["position"], r["worst"]), ("BB", None))


if __name__ == "__main__":
    unittest.main()

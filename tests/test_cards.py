import unittest

from pokertracker.cards import sort_hole_cards


class SortHoleCardsTests(unittest.TestCase):
    def test_higher_card_goes_left(self):
        self.assertEqual(sort_hole_cards("7h Ac"), "Ac 7h")
        self.assertEqual(sort_hole_cards("2c 9d"), "9d 2c")

    def test_right_order_is_kept(self):
        self.assertEqual(sort_hole_cards("Ac 7h"), "Ac 7h")
        self.assertEqual(sort_hole_cards("Kd Qs"), "Kd Qs")

    def test_pair_keeps_the_order_of_the_data(self):
        self.assertEqual(sort_hole_cards("9s 9c"), "9s 9c")
        self.assertEqual(sort_hole_cards("9c 9s"), "9c 9s")
        self.assertEqual(sort_hole_cards(["Ah", "Ad"]), ["Ah", "Ad"])

    def test_ace_beats_every_other_rank(self):
        for r in "KQJT98765432":
            self.assertEqual(sort_hole_cards(f"{r}s Ah"), f"Ah {r}s")

    def test_broadway_ranks(self):
        self.assertEqual(sort_hole_cards("Tc Jd"), "Jd Tc")
        self.assertEqual(sort_hole_cards("Jh Qh"), "Qh Jh")
        self.assertEqual(sort_hole_cards("Qs Kc"), "Kc Qs")
        self.assertEqual(sort_hole_cards("9d Td"), "Td 9d")

    def test_input_list_is_not_mutated(self):
        cards = ["7h", "Ac"]
        self.assertEqual(sort_hole_cards(cards), ["Ac", "7h"])
        self.assertEqual(cards, ["7h", "Ac"])

    def test_empty_comes_back_unchanged(self):
        self.assertEqual(sort_hole_cards(""), "")
        self.assertIsNone(sort_hole_cards(None))
        self.assertEqual(sort_hole_cards([]), [])


if __name__ == "__main__":
    unittest.main()

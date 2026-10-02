import unittest

from pokertracker.db import Database
from pokertracker.importer import import_texts
from pokertracker.replay import hand_replay
from tests.fixtures import HAND_3WAY, HISTORY


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.addCleanup(self.db.close)
        self.db.init_schema()
        import_texts(self.db, [("h", HISTORY), ("t", HAND_3WAY)])

    def test_unknown_hand(self):
        self.assertIsNone(hand_replay(self.db, "nope"))

    def test_chip_accounting_step_by_step(self):
        r = hand_replay(self.db, "TM1000000001")
        steps = r["steps"]
        self.assertEqual(steps[0]["pot"], 0)
        # after antes and blinds: 3 x 5 + 25 + 50
        posted = [s for s in steps if s["label"].startswith("Hero posts big blind")][0]
        self.assertEqual(posted["pot"], 90)
        # before the uncalled bet is returned the pot holds everything that was put in
        self.assertEqual(steps[-2]["pot"], 15 + 25 + 150 + 150 + 200)
        # chips are conserved on every step until the payout
        for s in steps[:-1]:
            self.assertAlmostEqual(sum(p["stack"] for p in s["players"]) + s["pot"], 15000)

    def test_final_state_matches_results(self):
        r = hand_replay(self.db, "TM1000000001")
        final = {p["nick"]: p for p in r["steps"][-1]["players"]}
        self.assertEqual((final["Hero"]["stack"], final["aaaa1111"]["stack"], final["bbbb2222"]["stack"]),
                         (5000 - 155, 5000 + 185, 5000 - 30))
        self.assertTrue(r["steps"][-1]["result"])
        self.assertIn("aaaa1111 wins +185", r["steps"][-1]["label"])

    def test_board_is_revealed_street_by_street(self):
        r = hand_replay(self.db, "TM1000000001")
        boards = [len(s["board"]) for s in r["steps"]]
        self.assertEqual(boards[0], 0)
        self.assertIn(3, boards)
        self.assertEqual(max(boards), 3)                          # hand ended on the flop

    def test_all_in_runout_and_card_reveal(self):
        r = hand_replay(self.db, "TM1000000010")
        labels = [s["label"] for s in r["steps"]]
        self.assertTrue(any(l.startswith("Turn:") for l in labels))
        self.assertTrue(any(l.startswith("River:") for l in labels))
        first = {p["nick"]: p for p in r["steps"][0]["players"]}
        last = {p["nick"]: p for p in r["steps"][-1]["players"]}
        self.assertEqual(first["Hero"]["cards"], ["Ks", "Kh"])    # hero sees his own cards from the start
        self.assertEqual(first["bbbb2222"]["cards"], [])           # opponents only at showdown
        self.assertEqual(last["bbbb2222"]["cards"], ["Ac", "Qd"])
        self.assertTrue(first["Hero"]["hero"])
        all_in_step = [s for s in r["steps"] if "Hero raises to 2,945 (all-in)" in s["label"]][0]
        self.assertTrue(next(p for p in all_in_step["players"] if p["nick"] == "Hero")["all_in"])
        self.assertEqual(last["Hero"]["stack"], 7000)


if __name__ == "__main__":
    unittest.main()

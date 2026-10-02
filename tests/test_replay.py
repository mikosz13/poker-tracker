import json
import unittest

from pokertracker.db import Database
from pokertracker.importer import import_texts
from pokertracker.replay import hand_replay
from tests.fixtures import HAND_3WAY, HAND_SHORT, HISTORY


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.addCleanup(self.db.close)
        self.db.init_schema()
        import_texts(self.db, [("h", HISTORY), ("t", HAND_3WAY), ("s", HAND_SHORT)])

    def test_unknown_hand(self):
        self.assertIsNone(hand_replay(self.db, "nope"))

    def test_chip_accounting_step_by_step(self):
        r = hand_replay(self.db, "TM1000000001")
        steps = r["steps"]
        # before the uncalled bet is returned the pot holds everything that was put in
        before = [s for s in steps if s["kind"] == "return"][0]
        self.assertEqual(steps[steps.index(before) - 1]["pot"], 15 + 25 + 150 + 150 + 200)
        self.assertEqual(before["label"], "Uncalled 200 returned to BTN")
        self.assertEqual(before["pot"], r["total_pot"])           # what is left is exactly what gets paid out
        # chips are conserved on every step until the payout
        for s in steps[:-1]:
            self.assertAlmostEqual(sum(p["stack"] for p in s["players"]) + s["pot"], 15000)

    def test_first_step_has_antes_and_blinds_in_the_pot(self):
        first = hand_replay(self.db, "TM1000000001")["steps"][0]
        self.assertEqual(first["kind"], "start")
        self.assertEqual(first["pot"], 3 * 5 + 25 + 50)
        stacks = {p["nick"]: (p["stack"], p["commit"]) for p in first["players"]}
        self.assertEqual(stacks, {"BTN": (4995, 0), "SB": (4970, 25), "Hero": (4945, 50)})
        self.assertEqual(first["next"], "BTN")                    # first voluntary action, not a blind

    def test_forced_bets_are_not_steps(self):
        for hid in ("TM1000000001", "TM1000000002", "TM1000000010", "TM1000000020"):
            kinds = [s["action"]["type"] for s in hand_replay(self.db, hid)["steps"] if s["action"]]
            self.assertFalse([k for k in kinds if k.startswith("posts")], hid)

    def test_heads_up_button_acts_first_preflop(self):
        r = hand_replay(self.db, "TM1000000002")
        first = r["steps"][0]
        self.assertEqual(first["pot"], 2 * 5 + 25 + 50)
        self.assertEqual(first["next"], "BTN/SB")
        self.assertEqual(r["steps"][1]["action"]["nick"], "BTN/SB")

    def test_short_stack_all_in_on_the_ante(self):
        r = hand_replay(self.db, "TM1000000020")
        first = r["steps"][0]
        short = next(p for p in first["players"] if p["nick"] == "BTN")
        self.assertEqual((short["stack"], short["all_in"]), (0, True))
        self.assertEqual(first["pot"], 8 + 10 + 10 + 50 + 100)
        self.assertEqual(first["next"], "SB")                     # the all-in button has nothing left to decide
        ret = [s for s in r["steps"] if s["kind"] == "return"][0]
        self.assertEqual(ret["label"], "Uncalled 50 returned to Hero")
        self.assertEqual(ret["pot"], 128)
        self.assertEqual([s["label"].split(":")[0] for s in r["steps"] if s["kind"] == "deal"], ["Flop", "Turn", "River"])
        final = {p["nick"]: p["stack"] for p in r["steps"][-1]["players"]}
        self.assertEqual(final, {"BTN": 0, "SB": 1940, "Hero": 3068})
        self.assertEqual(r["max_seats"], 8)

    def test_final_state_matches_results(self):
        r = hand_replay(self.db, "TM1000000001")
        final = {p["nick"]: p for p in r["steps"][-1]["players"]}
        self.assertEqual((final["Hero"]["stack"], final["BTN"]["stack"], final["SB"]["stack"]),
                         (5000 - 155, 5000 + 185, 5000 - 30))
        self.assertTrue(r["steps"][-1]["result"])
        self.assertIn("BTN wins +185", r["steps"][-1]["label"])

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
        self.assertEqual(first["SB"]["cards"], [])           # opponents only at showdown
        self.assertEqual(last["SB"]["cards"], ["Ac", "Qd"])
        self.assertTrue(first["Hero"]["hero"])
        all_in_step = [s for s in r["steps"] if "Hero raises to 2,945 (all-in)" in s["label"]][0]
        self.assertTrue(next(p for p in all_in_step["players"] if p["nick"] == "Hero")["all_in"])
        self.assertEqual(last["Hero"]["stack"], 7000)

    def test_equity_shown_from_the_all_in_moment(self):
        r = hand_replay(self.db, "TM1000000010")
        lock = [i for i, s in enumerate(r["steps"]) if s["kind"] == "action"][-1]
        hero = lambda s: next(p for p in s["players"] if p["nick"] == "Hero")
        self.assertIsNone(hero(r["steps"][lock - 1])["equity"])
        sb = lambda s: next(p for p in s["players"] if p["nick"] == "SB")
        self.assertEqual(sb(r["steps"][lock - 1])["cards"], [])     # face down while betting is open ...
        self.assertEqual(sb(r["steps"][lock])["cards"], ["Ac", "Qd"])   # ... face up together with the equity
        self.assertTrue(all(sb(s)["cards"] == ["Ac", "Qd"] for s in r["steps"][lock:]))
        self.assertGreater(hero(r["steps"][lock])["equity"], 0.5)   # KK vs 77 vs AQ on 2-8-9
        self.assertEqual(r["hero_allin"]["street"], "flop")
        self.assertAlmostEqual(r["hero_allin"]["equity"], hero(r["steps"][lock])["equity"])


    def test_no_early_reveal_without_an_all_in(self):
        r = hand_replay(self.db, "TM1000000001")                  # opponent wins without showdown
        for s in r["steps"]:
            self.assertTrue(all(p["cards"] == [] for p in s["players"] if not p["hero"]))

    def test_opponents_are_named_by_position_never_by_id(self):
        positions = {"UTG", "UTG+1", "MP", "LJ", "HJ", "CO", "BTN", "SB", "BB", "BTN/SB"}
        for hid in ("TM1000000001", "TM1000000002", "TM1000000003", "TM1000000010", "TM1000000020"):
            ids = {x["nick"] for x in self.db.query("SELECT nick FROM hand_players WHERE hand_id = ?", (hid,))} - {"Hero"}
            r = hand_replay(self.db, hid)
            for s in r["steps"]:
                for p in s["players"]:
                    if p["hero"]:
                        self.assertEqual(p["nick"], "Hero")
                    else:
                        self.assertIn(p["nick"], positions, hid)
            data = json.dumps(r)
            for nick in ids:                                      # not in labels, log, next actor, payouts ...
                self.assertNotIn(nick, data, hid)


if __name__ == "__main__":
    unittest.main()

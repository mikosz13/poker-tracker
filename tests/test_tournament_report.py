import unittest
from html.parser import HTMLParser

import numpy as np

from pokertracker import tournament_report as T
from pokertracker.db import Database
from pokertracker.equity import evaluate, parse_cards
from pokertracker.importer import import_texts
from tests.fixtures import HISTORY, SUMMARY_BOUNTY, SUMMARY_SATELLITE


def score(text):
    return int(evaluate(np.array([parse_cards(text)]))[0])


class DescribeHandTests(unittest.TestCase):
    def test_descriptions(self):
        self.assertEqual(T.describe_hand(score("As Ad Ac Kh Kd 2c 3d")), "Aces full of Kings")
        self.assertEqual(T.describe_hand(score("Ah 2d 3c 4s 5h 9d Kc")), "5-high straight")
        self.assertEqual(T.describe_hand(score("Kh Kd 7c 8s 2h 9d 3c")), "pair of Kings")
        self.assertEqual(T.describe_hand(score("Ah 2h 7h 9h Kh 3d 4c")), "A-high flush")
        self.assertEqual(T.describe_hand(score("Qh Qd 7c 7s 2h 9d 3c")), "two pair, Queens and Sevens")
        self.assertEqual(T.describe_hand(score("9h 9d 9c 2s 5h Kd 3c")), "three Nines")
        self.assertEqual(T.describe_hand(score("2h 2d 2c 2s 5h Kd 3c")), "four Twos")
        self.assertEqual(T.describe_hand(score("Ah Kh Qh Jh Th 2d 3c")), "A-high straight flush")
        self.assertEqual(T.describe_hand(score("Ah Kd 7c 8s 2h 9d 3c")), "A high")


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.addCleanup(self.db.close)
        self.db.init_schema()
        import_texts(self.db, [("h", HISTORY), ("b", SUMMARY_BOUNTY), ("s", SUMMARY_SATELLITE)])
        self.d = T.tournament_data(self.db, 900001)

    def test_numbers(self):
        d = self.d
        self.assertEqual((d["hands"], len(d["entries"]), d["levels"]), (3, 2, (1, 1)))
        self.assertAlmostEqual(d["biggest_losses"][0]["net_bb"], -96.9, places=1)     # KK vs AA all-in
        self.assertAlmostEqual(d["biggest_wins"][0]["net_bb"], 0.6, places=1)
        self.assertAlmostEqual(d["net_bb"], (-155 - 4845 + 30) / 50, places=6)
        self.assertEqual(d["strongest_showdown"]["hand"], "pair of Kings")
        self.assertEqual(d["allins"]["count"], 1)
        self.assertLess(d["allins"]["luck_bb"], 0)
        self.assertEqual(d["result"]["place"], 3)

    def test_small_samples_are_not_ranked(self):
        self.assertIsNone(self.d["best_position"])
        self.assertIsNone(self.d["worst_position"])
        T.MIN_POSITION_HANDS, old = 1, T.MIN_POSITION_HANDS
        try:
            self.assertEqual(T.tournament_data(self.db, 900001)["best_position"]["position"], "BB")
        finally:
            T.MIN_POSITION_HANDS = old

    def test_stack_path_peak_includes_final_result(self):
        s = T.tournament_data(self.db, 900001)["stack"]
        self.assertEqual(len(s["path"]), 4)                      # before each of 3 hands + after the last
        self.assertEqual(s["peak_bb"], max(s["path"]))
        self.assertEqual(s["end_bb"], s["path"][-1])

    def test_summary_only_tournament(self):
        d = T.tournament_data(self.db, 900002)
        self.assertEqual(d["hands"], 0)
        self.assertIn("no hand history", T.render_text(d))
        self.assertIn("<h1>", T.render_html(d))

    def test_unknown_tournament(self):
        self.assertIsNone(T.tournament_data(self.db, 1))
        self.assertEqual(T.render_text(None), "Tournament not found.")

    def test_text_report(self):
        text = T.render_text(self.d)
        for needle in ("place 3/50", "entry #2", "all-ins: 1", "biggest losses", "strongest showdown hand: pair of Kings",
                       "too small to rank"):
            self.assertIn(needle, text)

    def test_html_is_well_formed_and_escaped(self):
        class P(HTMLParser):
            def __init__(self):
                super().__init__(); self.tags = []
            def handle_starttag(self, tag, attrs): self.tags.append(tag)
        page = T.render_html(self.d)
        p = P(); p.feed(page)
        self.assertIn("svg", p.tags)
        self.assertIn("viewport", page)
        evil = dict(self.d, name="<script>alert(1)</script>")
        self.assertNotIn("<script>", T.render_html(evil))


class StackPointsTests(unittest.TestCase):
    def test_points_entries_and_bust_for_the_app_chart(self):
        db = Database("sqlite:///:memory:")
        self.addCleanup(db.close)
        db.init_schema()
        import_texts(db, [("h", HISTORY)])                          # entry 1 busts in hand 2, re-entry in hand 3
        d = T.tournament_data(db, 900001)
        pts = d["stack"]["points"]
        self.assertEqual([p["hand_id"] for p in pts], ["TM1000000001", "TM1000000002", "TM1000000003"])
        self.assertEqual([p["after_bb"] for p in pts], [96.9, 0.0, 100.6])      # 4,845 / 50, bust, 5,030 / 50
        self.assertEqual(pts[0]["at"], "2026-01-01 10:00:00")
        self.assertEqual([(e["entry_no"], e["first_hand_id"]) for e in d["entries"]],
                         [(1, "TM1000000001"), (2, "TM1000000003")])
        self.assertEqual(d["stack"]["path"][0], pts[0]["before_bb"])         # the CLI/HTML report keeps its path


if __name__ == "__main__":
    unittest.main()


class KnockoutTests(unittest.TestCase):
    def test_knockouts(self):
        from tests.fixtures import HAND_3WAY
        db = Database("sqlite:///:memory:")
        self.addCleanup(db.close)
        db.init_schema()
        import_texts(db, [("h", HISTORY), ("t", HAND_3WAY)])
        # Hero busts in hand 2 of tournament 900001 (that is not a knockout for Hero)
        self.assertEqual(T.tournament_data(db, 900001)["knockouts"], {"sole": 0, "shared": 0})
        # in the three-way all-in Hero wins both pots and eliminates both opponents
        self.assertEqual(T.tournament_data(db, 900003)["knockouts"], {"sole": 2, "shared": 0})
        busted = {r["busted_nick"] for r in db.query("SELECT busted_nick FROM hero_knockouts")}
        self.assertEqual(busted, {"aaaa1111", "bbbb2222"})
        self.assertIn("knockouts: 2", T.render_text(T.tournament_data(db, 900003)))


class TournamentListTests(unittest.TestCase):
    def test_knockouts_per_tournament(self):
        from pokertracker.server import tournaments_list
        from tests.fixtures import HAND_3WAY
        db = Database("sqlite:///:memory:")
        self.addCleanup(db.close)
        db.init_schema()
        import_texts(db, [("h", HISTORY), ("t", HAND_3WAY)])
        ko = {r["tournament_id"]: r["knockouts"] for r in tournaments_list(db)}
        self.assertEqual(ko[900003], 2)                                 # Hero's KK busts both short stacks
        self.assertIsNone(ko[900001])                                   # no knockout in that tournament

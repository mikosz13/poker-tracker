"""Export (pokertracker/export.py): a hand or a result as text, CSV for Excel, saving without overwriting."""
import csv
import io
import tempfile
import unittest
from pathlib import Path

from pokertracker.db import Database
from pokertracker.export import csv_text, hand_text, hands_csv, name_matches, save, tournament_text, tournaments_csv
from pokertracker.importer import import_texts, set_provisional_prize
from tests.fixtures import HISTORY, SUMMARY_BOUNTY
from tests.test_analysis import gg_hand
from tests.test_showdown import CASES as SHOWDOWN
from tests.test_stages import DAY2_HANDS, STAGE1_ADVANCED


def read_csv(text, lang):
    assert text.startswith("﻿")                                   # a BOM, so Excel reads UTF-8
    return list(csv.reader(io.StringIO(text[1:]), delimiter=";" if lang == "pl" else ","))


class HandTextTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.addCleanup(self.db.close)
        self.db.init_schema()

    def test_every_street_positions_and_no_opponent_ids(self):
        hero, actions, _ = SHOWDOWN["showdown_won"]
        text = gg_hand(1, hero, actions).replace("*** SUMMARY ***", "*** SUMMARY ***\nBoard [2c 7d 9h Js 3d]")
        import_texts(self.db, [("h", text)], equity=False)
        text = hand_text(self.db, "TM2000000001", "en")
        for needle in ("Level 5 · blinds 100/200, ante 25", "Hero (BB) 50.0 BB", "Hero: Ah Kd",
                       "Preflop: UTG raise to 2.5 BB", "Flop 2c 7d 9h: Hero check", "Turn 2c 7d 9h Js:",
                       "River 2c 7d 9h Js 3d:", "Board: 2c 7d 9h Js 3d", "Shown: UTG Qc Qd", "Hero's result:"):
            self.assertIn(needle, text)
        self.assertNotIn("aaaa", text)                                 # opponents by position only
        self.assertEqual(text.index("UTG 50.0 BB") < text.index("Hero (BB)"), True)   # in acting order

    def test_an_all_in_with_its_ev_in_polish(self):
        import_texts(self.db, [("h", HISTORY)])
        text = hand_text(self.db, "TM1000000002", "pl")
        self.assertIn("all-in", text)
        self.assertIn("Wynik Hero: −96,9 BB (wg EV", text)              # KK lost to AA; the EV next to it

    def test_provisional_results_are_marked(self):
        import_texts(self.db, [("s1", STAGE1_ADVANCED), ("d2", DAY2_HANDS)], equity=False)
        self.assertIn("missing", tournament_text(self.db, 900103, "en"))
        set_provisional_prize(self.db, 900103, 250)
        for text in (tournament_text(self.db, 900103, "en"), hand_text(self.db, "TM1000000001", "en")):
            self.assertIn("provisional result: prize typed in", text)
        self.assertIn("won $257.02", tournament_text(self.db, 900103, "en"))   # $7.02 knockouts + $250, one value
        rows = read_csv(tournaments_csv(self.db, {}, "en")[0], "en")
        day2 = next(r for r in rows if r[1] == "900103")
        self.assertEqual(day2[-1], "yes")


class CsvTests(unittest.TestCase):
    def test_quoting_and_decimals_follow_the_language(self):
        rows = [["$5 Ocean KO Opener, $1M GTD", 'a "quoted" name', 12.5, None]]
        pl, en = read_csv(csv_text(["a", "b", "c", "d"], rows, "pl"), "pl"), read_csv(csv_text(["a", "b", "c", "d"], rows, "en"), "en")
        self.assertEqual(pl[1], ["$5 Ocean KO Opener, $1M GTD", 'a "quoted" name', "12,50", ""])
        self.assertEqual(en[1], ["$5 Ocean KO Opener, $1M GTD", 'a "quoted" name', "12.50", ""])

    def test_lists_of_tournaments_and_hands(self):
        db = Database("sqlite:///:memory:")
        self.addCleanup(db.close)
        db.init_schema()
        import_texts(db, [("h", HISTORY), ("b", SUMMARY_BOUNTY)])
        text, n = tournaments_csv(db, {"format": "bounty"}, "pl")
        rows = read_csv(text, "pl")
        self.assertEqual((n, rows[0][0], rows[1][1], rows[1][4]), (1, "data", "900001", "10,00"))
        text, n = hands_csv(db, {"cards": "KK"}, "en")
        rows = read_csv(text, "en")
        self.assertEqual((n, rows[1][4], rows[1][7]), (1, "Kc Kd", "yes"))   # the KK all-in

    def test_the_name_search_of_the_tournament_list(self):
        row = {"name": "$15 Mini Wednesday Wonderbox [Mystery BIG Bounty]", "tournament_id": 320223914}
        for q in ("", "wonderbox", "BOUNTY mini", "mystery big", "3202239", "#320223914"):
            self.assertTrue(name_matches(row, q), q)
        for q in ("sunday", "bounty sunday", "999"):
            self.assertFalse(name_matches(row, q), q)
        self.assertTrue(name_matches({"name": "Żółw Łódź Turbo", "tournament_id": 1}, "zolw lodz"))   # no Polish letters needed
        db = Database("sqlite:///:memory:")
        self.addCleanup(db.close)
        db.init_schema()
        import_texts(db, [("h", HISTORY), ("b", SUMMARY_BOUNTY)])
        self.assertEqual(tournaments_csv(db, {"q": "hunters"}, "en")[1], 1)       # the CSV holds what the list shows
        self.assertEqual(tournaments_csv(db, {"q": "satellite"}, "en")[1], 0)

    def test_saving_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = save("x", "poker-tracker-test", tmp), save("y", "poker-tracker-test", tmp)
            self.assertNotEqual(first, second)
            self.assertTrue(second.endswith(" (2).csv"))
            self.assertEqual((Path(first).read_text(), Path(second).read_text()), ("x", "y"))


if __name__ == "__main__":
    unittest.main()

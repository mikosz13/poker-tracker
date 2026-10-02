import unittest

from pokertracker.hands import detect_entries, parse_hand, parse_hands
from pokertracker.summary import parse_summary
from tests.fixtures import HAND_1, HAND_2, HISTORY, SUMMARY_BOUNTY, SUMMARY_SATELLITE


class HandParserTests(unittest.TestCase):
    def test_header_and_level(self):
        h = parse_hand(HAND_1)
        self.assertEqual((h.hand_id, h.tournament_id, h.tournament_name, h.buyin_total),
                         ("TM1000000001", 900001, "Bounty Hunters", 10.0))
        self.assertEqual((h.level, h.sb, h.bb, h.ante, h.played_at), (1, 25, 50, 5, "2026-01-01 10:00:00"))

    def test_chips_are_conserved(self):
        for text in (HAND_1, HAND_2):
            h = parse_hand(text)
            self.assertAlmostEqual(sum(h.net(n) for n in h.seats), 0, places=6)

    def test_hero_result_and_positions(self):
        h1 = parse_hand(HAND_1)
        self.assertEqual(h1.net("Hero"), -155)
        self.assertEqual(h1.net("aaaa1111"), 185)
        self.assertEqual(h1.positions, {"aaaa1111": "BTN", "bbbb2222": "SB", "Hero": "BB"})
        self.assertEqual(h1.total_pot, 340)
        self.assertEqual(h1.board, "2c 7d Th")

    def test_all_in_and_showdown(self):
        h2 = parse_hand(HAND_2)
        self.assertTrue(h2.showdown)
        self.assertEqual(h2.net("Hero"), -4845)
        self.assertEqual(h2.positions, {"aaaa1111": "BTN/SB", "Hero": "BB"})
        self.assertTrue(any(a[2] == "Hero" and a[5] for a in h2.actions))   # Hero's call was all-in

    def test_history_is_sorted_oldest_first(self):
        hands = parse_hands(HISTORY)
        self.assertEqual([h.hand_id for h in hands], ["TM1000000001", "TM1000000002", "TM1000000003"])

    def test_pdf_style_header_split_over_two_lines(self):
        pdf_like = HAND_1.replace(" Hold'em No Limit - Level1", "\nHold'em No Limit - Level1", 1)
        self.assertNotEqual(pdf_like, HAND_1)
        h = parse_hand(pdf_like)
        self.assertEqual((h.hand_id, h.level, h.net("Hero")), ("TM1000000001", 1, -155))
        self.assertIsNone(parse_hand("garbage\nlines\nonly"))

    def test_reentry_detected_after_bust(self):
        entries = detect_entries(parse_hands(HISTORY))
        self.assertEqual([e["entry_no"] for e in entries], [1, 2])
        self.assertEqual(entries[1]["first_hand_id"], "TM1000000003")

    def test_late_entry_starts_where_hero_first_appears(self):
        late = HAND_2.replace("Level1(", "Level5(")
        entries = detect_entries([parse_hand(late)])
        self.assertEqual((len(entries), entries[0]["entry_level"], entries[0]["start_stack"]), (1, 5, 4845))


class SummaryParserTests(unittest.TestCase):
    def test_bounty_summary(self):
        t = parse_summary(SUMMARY_BOUNTY)
        self.assertEqual((t.id, t.name, t.format, t.buyin_total, t.reentries), (900001, "Bounty Hunters", "bounty", 10.0, 1))
        self.assertEqual((t.finish_place, t.players, t.prize_won, t.prize_is_ticket), (3, 50, 20.0, False))
        self.assertEqual(t.started_at, "2026-01-01 09:00:00")

    def test_satellite_ticket(self):
        t = parse_summary(SUMMARY_SATELLITE)
        self.assertEqual((t.format, t.buyin_total, t.prize_won, t.prize_is_ticket), ("satellite", 5.0, 50.0, True))
        self.assertIn("Satellite", t.name)

    def test_unknown_format_raises(self):
        with self.assertRaises(ValueError):
            parse_summary("hello world")


if __name__ == "__main__":
    unittest.main()

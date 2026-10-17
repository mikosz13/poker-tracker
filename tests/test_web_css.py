import re
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "pokertracker" / "web"

# Classes a replayer seat (.st) carries next to its own; styled anywhere else they leak into the seat.
SEAT_STATES = ("hero", "fold", "act", "nxt", "win")


class SeatClassTests(unittest.TestCase):
    def test_seat_state_classes_are_styled_only_on_seats(self):
        page = (WEB / "index.html").read_text(encoding="utf-8")
        css = re.sub(r"\{[^{}]*\}", "{}", page[page.index("<style>") + 7:page.index("</style>")])
        found = []
        for selector in re.split(r"[{},]", css):
            for compound in re.split(r"[\s>+~]+", selector.strip()):
                classes = re.findall(r"\.([\w-]+)", re.sub(r":not\([^)]*\)", "", compound))
                found += [compound for c in SEAT_STATES if c in classes and "st" not in classes]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()

"""Help: every section exists in both languages and every "?" link in the app points at an existing section."""
import json
import re
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "pokertracker" / "web"


class HelpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (WEB / "index.html").read_text(encoding="utf-8")
        cls.sections = re.search(r"const HELP = \[([^\]]*)\]", cls.page)[1]
        cls.sections = re.findall(r'"([a-z]+)"', cls.sections)

    def test_every_section_in_both_languages(self):
        for lang in ("pl", "en"):
            texts = json.loads((WEB / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
            for k in self.sections:
                self.assertTrue(texts.get(f"help.{k}.title") and len(texts.get(f"help.{k}.body", "")) > 200, (lang, k))

    def test_every_help_link_points_at_a_section(self):
        links = set(re.findall(r'helpLink\("([a-z]+)"\)', self.page)) | set(re.findall(r'helpLink\([^)]*\? "([a-z]+)" : "([a-z]+)"\)', self.page)[0])
        self.assertTrue(links)
        self.assertLessEqual(links, set(self.sections))

    def test_every_definition_of_analysis_is_explained(self):
        for lang, words in (("pl", ("VPIP", "PFR", "RFI", "Open shove", "3-bet", "Fold to 3-bet", "bb/100 wg EV", "q ≤ 0,05")),
                            ("en", ("VPIP", "PFR", "RFI", "Open shove", "3-bet", "Fold to 3-bet", "bb/100 by EV", "q ≤ 0.05"))):
            body = json.loads((WEB / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))["help.analysis.body"]
            for w in words:
                self.assertIn(w, body, (lang, w))


if __name__ == "__main__":
    unittest.main()

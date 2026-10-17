"""Help v2: Markdown subpages in both languages, the same anchors in each, every "?" link and internal link points at an
existing page and anchor, nothing of Help v1 is lost, FAQ and About hold what Mik asked for, one source of the
version."""
import json
import re
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from pokertracker import __version__
from pokertracker.server import HELP_PAGES, changes_of, serve_in_background

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "pokertracker" / "web"
LANGS = ("pl", "en")


def page(lang, name):
    return (WEB / "help" / lang / f"{name}.md").read_text(encoding="utf-8")


def anchors(md):
    return re.findall(r"^#{1,3} .+ \{#([\w-]+)\}$", md, re.M)


class HelpPagesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = (WEB / "index.html").read_text(encoding="utf-8")

    def test_every_page_in_both_languages_with_a_title(self):
        js_pages = re.findall(r'"(\w+)"', re.search(r"const HELP_PAGES = \[([^\]]*)\]", self.index)[1])
        self.assertEqual(tuple(js_pages), HELP_PAGES)
        for lang in LANGS:
            for name in HELP_PAGES:
                md = page(lang, name)
                self.assertTrue(md.startswith("# ") and len(md) > 400, (lang, name))

    def test_the_same_anchors_in_both_languages(self):
        for name in HELP_PAGES:
            self.assertEqual(anchors(page("pl", name)), anchors(page("en", name)), name)

    def test_nothing_of_the_first_help_is_lost(self):
        # the nine sections of Help v1 (#54) and the page "How luck is calculated", now on these pages
        where = {"start": {"import", "dashboard", "tournaments", "hands", "backup"}, "how": {"analysis", "money", "luck"}}
        for lang in LANGS:
            for name, keys in where.items():
                self.assertLessEqual(keys, set(anchors(page(lang, name))), (lang, name))
            self.assertIn("{{luck}}", page(lang, "how"))
            self.assertGreaterEqual(page(lang, "glossary").count("\n- **"), 11)
        self.assertIn("Otwórz mimo to", page("pl", "problems"))
        self.assertIn("Open Anyway", page("en", "problems"))

    def test_every_link_points_at_a_page_and_anchor(self):
        targets = {f"{name}/{a}" for name in HELP_PAGES for a in anchors(page("en", name))} | set(HELP_PAGES)
        mapping = dict(re.findall(r'(\w+): "([\w/]+)"', re.search(r"const HELP_TARGET = \{([^}]*)\}", self.index)[1]))
        used = set(re.findall(r'helpLink\("(\w+)"\)', self.index)) | {"money", "analysis"}
        self.assertLessEqual(used, set(mapping))
        self.assertLessEqual(set(mapping.values()), targets)
        for lang in LANGS:                                   # links inside the pages themselves
            for name in HELP_PAGES:
                for link in re.findall(r"\]\(#/help/([\w/]+)\)", page(lang, name)):
                    self.assertIn(link, targets, (lang, name, link))

    def test_every_definition_of_analysis_is_explained(self):
        for lang, words in (("pl", ("VPIP", "PFR", "RFI", "Open shove", "3-bet", "Fold to 3-bet", "bb/100 wg EV", "q ≤ 0,05")),
                            ("en", ("VPIP", "PFR", "RFI", "Open shove", "3-bet", "Fold to 3-bet", "bb/100 by EV", "q ≤ 0.05"))):
            for w in words:
                self.assertIn(w, page(lang, "how"), (lang, w))

    def test_faq_and_about(self):
        for lang in LANGS:
            self.assertLessEqual({"data", "move", "update", "delete", "offline"}, set(anchors(page(lang, "faq"))))
            about = page(lang, "about")
            self.assertLessEqual({"changes", "source", "bug", "license"}, set(anchors(about)))
            for needle in ("{{version}}", "{{changes}}", "https://github.com/mikosz13/poker-tracker",
                           "https://github.com/mikosz13/poker-tracker/issues/new", "MIT", "Mikołaj Szcześniak"):
                self.assertIn(needle, about, (lang, needle))


class VersionTests(unittest.TestCase):
    def test_one_source_of_the_version(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertNotRegex(pyproject, r'(?m)^version\s*=\s*"')                 # no number typed in here
        self.assertIn('version = {attr = "pokertracker.__version__"}', pyproject)
        self.assertIn("__version__", (ROOT / "packaging" / "pokertracker.spec").read_text(encoding="utf-8"))

    def test_changes_of_a_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "CHANGELOG.md"
            log.write_text("# Changelog\n\n## Unreleased\n- next\n\n## 1.2.0 (2026-10-20)\n- one\n- two\n\n## 1.1.0\n- old\n")
            self.assertEqual(changes_of("1.2.0", log), "- one\n- two")
            self.assertIsNone(changes_of("9.9.9", log))
            self.assertIsNone(changes_of("1.2.0", Path(tmp) / "missing.md"))
        self.assertTrue(changes_of(__version__))             # the repository's CHANGELOG has this version


class HelpServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.server, cls.url = serve_in_background(f"sqlite:///{Path(cls.tmp.name) / 'h.db'}")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def get(self, path):
        try:
            with urllib.request.urlopen(self.url + path.lstrip("/")) as r:
                return r.status, r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read().decode("utf-8")

    def test_pages_and_about(self):
        status, md = self.get("/help/pl/faq.md")
        self.assertEqual((status, md.splitlines()[0]), (200, "# Najczęstsze pytania"))
        for bad in ("/help/de/faq.md", "/help/pl/../server.py", "/help/pl/secret.md", "/help/pl/faq"):
            self.assertEqual(self.get(bad)[0], 404, bad)
        about = json.loads(self.get("/api/about")[1])
        self.assertEqual(about["version"], __version__)
        self.assertTrue(about["changes"])


if __name__ == "__main__":
    unittest.main()

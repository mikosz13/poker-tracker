import json
import re
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from pokertracker import analysis as A
from pokertracker import i18n as I
from pokertracker.db import Database
from pokertracker.importer import import_texts
from pokertracker.server import serve_in_background, tournaments_list
from pokertracker.session import session_insights
from tests.fixtures import HISTORY, SUMMARY_BOUNTY
from tests.test_analysis import tournament

WEB = Path(I.__file__).parent / "web"
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def placeholders(value):
    forms = value.values() if isinstance(value, dict) else [value]
    return {p for f in forms for p in PLACEHOLDER.findall(f)}


class FileTests(unittest.TestCase):
    def setUp(self):
        self.en, self.pl = I.strings("en"), I.strings("pl")

    def test_same_keys_in_both_languages(self):
        self.assertEqual(sorted(set(self.en) - set(self.pl)), [])
        self.assertEqual(sorted(set(self.pl) - set(self.en)), [])

    def test_same_placeholders_in_both_languages(self):
        for key in self.en:
            self.assertEqual(placeholders(self.en[key]), placeholders(self.pl[key]), key)

    def test_plural_forms(self):
        for key, value in self.en.items():
            if isinstance(value, dict):
                self.assertLessEqual({"one", "other"}, set(value), key)
        for key, value in self.pl.items():
            if isinstance(value, dict):
                self.assertLessEqual({"one", "few", "many"}, set(value), key)


class LabelTests(unittest.TestCase):
    def test_every_tag_has_a_label(self):
        from pokertracker import classify as C
        tags = {"format.bounty", "format.regular", "format.satellite", "mystery-bounty", "entry.start", "entry.late",
                "re-entered", "stake.super", "field.huge", "speed.regular"}
        tags |= {f"stake.{x}" for _, x in C.STAKE_TIERS} | {f"field.{x}" for _, x in C.FIELD_SIZES}
        tags |= {f"speed.{x}" for _, x in C.SPEED_BOUNDS}
        for lang in I.LANGS:
            self.assertEqual([x for x in sorted(tags) if f"tag.{x}" not in I.strings(lang)], [], lang)

    def test_hand_names_in_polish(self):
        name = lambda cat, r0, r1="2": I.t("pl", f"hand.cat.{cat}", **{
            "top": I.t("pl", f"rank.top.{r0}"), "topn": I.t("pl", f"rank.topn.{r0}"), "a": I.t("pl", f"rank.of.{r0}"),
            "b": I.t("pl", f"rank.of.{r1}"), "an": I.t("pl", f"rank.pl.{r0}"), "bn": I.t("pl", f"rank.pl.{r1}")})
        self.assertEqual([name(4, "A"), name(1, "K"), name(6, "A", "K"), name(2, "J", "8"), name(0, "Q")],
                         ["strit do asa", "para króli", "full: asy na króle", "dwie pary: waletów i ósemek",
                          "wysoka karta: dama"])
        for lang in I.LANGS:
            for c in "23456789TJQKA":
                for form in ("top", "topn", "of", "pl"):
                    self.assertIn(f"rank.{form}.{c}", I.strings(lang))


class PluralTests(unittest.TestCase):
    def test_polish_rule(self):
        self.assertEqual([I.plural("pl", n) for n in (1, 2, 5, 12, 22, 25)], ["one", "few", "many", "many", "few", "many"])
        self.assertEqual([I.plural("pl", n) for n in (0, 4, 14, 104, 111, 1.5)], ["many", "few", "many", "few", "many", "other"])
        self.assertEqual([I.plural("en", n) for n in (1, 2, 5)], ["one", "other", "other"])

    def test_tournaments_and_hands_in_polish(self):
        counts = (1, 2, 5, 12, 22, 25)
        self.assertEqual([I.t("pl", "common.tournaments", n=n) for n in counts],
                         ["1 turniej", "2 turnieje", "5 turniejów", "12 turniejów", "22 turnieje", "25 turniejów"])
        self.assertEqual([I.t("pl", "common.handsN", n=n) for n in counts],
                         ["1 ręka", "2 ręce", "5 rąk", "12 rąk", "22 ręce", "25 rąk"])
        self.assertEqual([I.t("pl", "sum.busts", n=n) for n in counts],
                         ["1 odpadnięcie", "2 odpadnięcia", "5 odpadnięć", "12 odpadnięć", "22 odpadnięcia", "25 odpadnięć"])

    def test_english(self):
        self.assertEqual([I.t("en", "common.handsN", n=n) for n in (1, 2, 1234)], ["1 hand", "2 hands", "1,234 hands"])

    def test_missing_key_falls_back_to_english(self):
        real = I.strings
        try:
            I.strings = lambda lang: {"x": {"one": "{n} thing", "other": "{n} things"}} if lang == "en" else {}
            self.assertEqual(I.t("pl", "x", n=2), "2 things")          # English text with the English plural rule
            self.assertEqual(I.t("pl", "nothing.here"), "nothing.here")
        finally:
            I.strings = real


class NumberTests(unittest.TestCase):
    def test_polish_numbers_do_not_wrap(self):
        self.assertEqual(I.num("pl", 2445.05, 2), "2 445,05")
        self.assertEqual(I.money("pl", 2445.05), "2 445,05 $")
        self.assertEqual(I.num("pl", -54.8, 1) + "%", "−54,8%")
        self.assertEqual(I.num("pl", 1.5, 1, sign=True), "+1,5")

    def test_english_numbers(self):
        self.assertEqual(I.money("en", -45.31), "−$45.31")
        self.assertEqual(I.money("en", 0, sign=True), "+$0.00")
        self.assertEqual(I.num("en", 12345.678, 1), "12,345.7")
        self.assertEqual(I.num("en", -0.04, 1), "0.0")                 # no "−0.0"


class PythonTextTests(unittest.TestCase):
    def setUp(self):
        self.db = Database("sqlite:///:memory:")
        self.addCleanup(self.db.close)
        self.db.init_schema()

    def test_money_in_polish(self):
        for i in range(12):
            tournament(self.db, 1000 + i, 50.0)
        for i in range(12):
            tournament(self.db, 2000 + i, 10.0, prize=20.0 if i % 2 else 0.0)
        tournament(self.db, 3000, 4.0)
        self.db.commit()
        m = A.money(self.db, lang="pl")
        tiers = {g["key"]: g for g in m["tiers"]}
        self.assertEqual((tiers["30+"]["verdict"], tiers["5-15"]["verdict"], tiers["under5"]["verdict"]),
                         ("strata ponad przypadek", "za mało danych", "za mało turniejów"))
        self.assertEqual(tiers["under5"]["label"], "poniżej $5")
        self.assertEqual(m["facts"][0], "$30+: strata ponad przypadek; to 83% Twoich wydatków, więc ma największy wpływ "
                                        "na Twój ogólny wynik.")
        self.assertEqual(A.money(self.db)["tiers"][0]["verdict"], "too few tournaments")    # English by default

    def test_session_summary_in_polish(self):
        import_texts(self.db, [("h", HISTORY), ("b", SUMMARY_BOUNTY)])
        rows = [x for x in tournaments_list(self.db) if x["tournament_id"] == 900001]
        text = session_insights(self.db, rows, lang="pl")["summary"]
        self.assertTrue(text.startswith("1 turniej, 1 ITM, +0,00 $."), text)
        self.assertIn("1 odpadnięcie.", text)


class ServerDisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.server, cls.url = serve_in_background(f"sqlite:///{Path(cls.tmp.name) / 'test.db'}", watch_seconds=60)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def get(self, path):
        try:
            with urllib.request.urlopen(self.url + path.lstrip("/")) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            e.close()
            return e.code, b""

    def test_translation_files_and_the_saved_language(self):
        status, body = self.get("/i18n/pl.json")
        self.assertEqual((status, json.loads(body)["nav.dashboard"]), (200, "Pulpit"))
        self.assertEqual(self.get("/i18n/de.json")[0], 404)
        self.assertIsNone(json.loads(self.get("/api/settings")[1])["lang"])       # unset: the page uses the system's
        req = urllib.request.Request(self.url + "api/display", data=b'{"lang": "pl"}', method="POST",
                                     headers={"Content-Type": "application/json", "X-Token": self.server.token})
        with urllib.request.urlopen(req) as r:
            self.assertEqual(json.loads(r.read())["lang"], "pl")
        self.assertEqual(json.loads(self.get("/api/settings")[1])["lang"], "pl")
        self.assertEqual(self.get("/api/analysis?lang=pl")[0], 200)

    def test_saved_theme_is_on_the_page_from_the_start(self):
        self.assertNotIn(b"data-theme=", self.get("/")[1].split(b"<head>")[0])    # unset: the system theme
        req = urllib.request.Request(self.url + "api/display", data=b'{"theme": "dark"}', method="POST",
                                     headers={"Content-Type": "application/json", "X-Token": self.server.token})
        with urllib.request.urlopen(req) as r:
            self.assertEqual(json.loads(r.read())["theme"], "dark")
        self.assertIn(b'<html lang="en" data-theme="dark">', self.get("/")[1])
        self.assertEqual(json.loads(self.get("/api/settings")[1])["theme"], "dark")


# ---- no hard-coded texts in the page ------------------------------------------------------------------------------

# Words allowed as they are: poker jargon that stays English in every language, and ids compared with server data
ALLOWED_WORDS = {"VPIP", "PFR", "ROI", "ITM", "ALL-IN", "All-in", "all-in", "Hero", "Polski", "English", "Poker",
                 "Tracker"}
ALLOWED_STRINGS = {"Very lucky", "Lucky", "Average", "Bad run", "Worst run",                  # luck level ids
                   "Sit & Go", "PLO/Omaha", "other game", "not in $", "cash game", "unrecognised summary",   # reason ids
                   "raises to",                                                         # replayer actions stay English
                   "scrollbox picks", "names tickets",                                                   # CSS classes
                   "Content-Type", "X-Token", "POST", "Hero"}


def js_literals(src):
    """The text of every string and template literal in JavaScript source; a template's ${...} becomes \\0."""
    out, i, n = [], 0, len(src)

    def literal(i):
        q, buf = src[i], []
        i += 1
        while i < n:
            c = src[i]
            if c == "\\":
                buf.append(src[i:i + 2])
                i += 2
            elif c == q:
                out.append("".join(buf))
                return i + 1
            elif q == "`" and src.startswith("${", i):
                buf.append("\0")
                i = code(i + 2, "}")
            else:
                buf.append(c)
                i += 1
        return i

    def code(i, end=None):
        depth, prev = 0, "("
        while i < n:
            c = src[i]
            if c in "\"'`":
                i = literal(i)
                prev = "x"
                continue
            if src.startswith("//", i):
                i = src.find("\n", i)
                i = n if i < 0 else i
                continue
            if src.startswith("/*", i):
                i = src.find("*/", i) + 2
                continue
            if c == "/" and prev in "(,=:[!&|?;{}+":                    # a regex literal, not a division
                i += 1
                in_class = False
                while i < n and (src[i] != "/" or in_class):
                    if src[i] == "\\":
                        i += 1
                    elif src[i] == "[":
                        in_class = True
                    elif src[i] == "]":
                        in_class = False
                    i += 1
                i += 1
                prev = "x"
                continue
            if end and c == "{":
                depth += 1
            elif end and c == end:
                if depth == 0:
                    return i + 1
                depth -= 1
            if not c.isspace():
                prev = c
            i += 1
        return i

    code(0)
    return out


def visible_words(text):
    """Words a user would read in a piece of page text: tags, attributes, paths, keys and CSS are left out; title and
    placeholder attributes count as visible."""
    shown = " ".join(re.findall(r'(?:title|placeholder)="([^"]*)"', text))
    s = re.sub(r"<[^<>]*>", " ", text)
    s = re.sub(r"<[^<>]*$", " ", s)                         # a tag that goes on after this piece
    s = re.sub(r"^[^<>]*>", " ", s)                         # the end of a tag that began before it
    s = " ".join([s, shown])
    s = re.sub(r"&#?\w+;", " ", s)
    s = re.sub(r"[#/]?[\w\-\0]*/[\w/\-\0.?=&]*", " ", s)    # paths and routes
    s = re.sub(r"\b[\w\-]+(\.[\w\-\0]*)+", " ", s)          # translation keys
    s = re.sub(r"[?&]\w+=", " ", s)                         # URL parameters
    s = re.sub(r"\b[a-z\-]+:[^\s;]*;?", " ", s)            # CSS
    return [w for w in re.findall(r"[A-Za-z][A-Za-z'\-]{2,}", s) if w not in ALLOWED_WORDS]


class NoHardCodedTextTests(unittest.TestCase):
    def setUp(self):
        page = (WEB / "index.html").read_text(encoding="utf-8")
        self.script = page[page.index("<script>") + 8:page.index("</script>")]
        self.body = page[page.index("<body>"):page.index("<script>")]

    def test_page_markup_has_no_text(self):
        self.assertEqual(visible_words(self.body), [])

    def test_script_texts_go_through_translations(self):
        found = []
        for lit in js_literals(self.script):
            if lit in ALLOWED_STRINGS:
                continue
            if "`" in lit or "<" in lit or "\0" in lit or " " in lit.strip() or re.fullmatch(r"[A-Z][a-z]{2,}[.!?…]?", lit):
                if lit.startswith(("#", ".", "(")) and "<" not in lit:       # CSS selectors and media queries
                    continue
                found += [(w, lit[:60]) for w in visible_words(lit)]
        self.assertEqual(found, [])

    def test_the_checker_finds_hard_coded_text(self):
        lits = js_literals('const a = `<p class="m">Not enough data ${x}</p>`, b = "Tournament", c = /["\']/g, d = "#nav a";')
        self.assertEqual([w for x in lits for w in visible_words(x)], ["Not", "enough", "data", "Tournament", "nav"])


if __name__ == "__main__":
    unittest.main()

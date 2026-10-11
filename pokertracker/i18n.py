"""Translations shared by the server and the page: pokertracker/web/i18n/<lang>.json.

A value is a string with {name} placeholders, or plural forms {"one": ..., "few": ..., "many": ..., "other": ...}
chosen by the count n, with the same rules as Intl.PluralRules in the page. A key missing in a language falls back to
English. Numbers in Polish use a decimal comma and a non-breaking space between thousands, so "2 445,05 $" never
wraps; the CLI HTML reports do not use this module and stay in English.
"""
import json
from functools import lru_cache
from pathlib import Path

I18N = Path(__file__).parent / "web" / "i18n"
LANGS = ("en", "pl")
DEFAULT = "en"
NBSP = " "
MINUS = "−"


def pick(lang):
    """A supported language from a request or a setting, English otherwise."""
    return lang if lang in LANGS else DEFAULT


@lru_cache(maxsize=None)
def strings(lang):
    return json.loads((I18N / f"{pick(lang)}.json").read_text(encoding="utf-8"))


def plural(lang, n):
    """CLDR plural category of n: English one/other; Polish one/few/many for whole numbers, other for fractions."""
    if lang == "pl":
        if n != int(n):
            return "other"
        n = abs(int(n))
        if n == 1:
            return "one"
        if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
            return "few"
        return "many"
    return "one" if n == 1 else "other"


def t(lang, key, n=None, **params):
    """The text for key in lang, with {placeholders} filled in; {n} is the count, formatted as a number."""
    lang = pick(lang)
    own = strings(lang)
    value, rule = (own[key], lang) if key in own else (strings(DEFAULT).get(key, key), DEFAULT)
    if isinstance(value, dict):
        value = value.get(plural(rule, n)) or value.get("other") or value.get("many")
    if n is not None:
        params.setdefault("n", num(lang, n, 0))
    return value.format(**params)


def num(lang, x, d=0, sign=False):
    """1234.5 -> '1,234.5' (en) or '1 234,5' (pl, with a non-breaking space); a true minus sign, '+' when asked."""
    if x is None:
        return "–"
    s = f"{abs(float(x)):,.{d}f}"
    if pick(lang) == "pl":
        s = s.replace(",", NBSP).replace(".", ",")
    zero = float(f"{abs(float(x)):.{d}f}") == 0
    return (MINUS if x < 0 and not zero else "+" if sign else "") + s


def money(lang, x, sign=False):
    """'$2,445.05' / '−$45.31' in English, '2 445,05 $' / '−45,31 $' in Polish."""
    if x is None:
        return "–"
    if pick(lang) == "pl":
        return num(lang, x, 2, sign) + NBSP + "$"
    n = num(lang, abs(x), 2)
    zero = float(f"{abs(float(x)):.2f}") == 0
    return (MINUS if x < 0 and not zero else "+" if sign else "") + "$" + n

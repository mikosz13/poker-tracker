"""What the tracker analyses: No-Limit Hold'em tournaments in dollars. Everything else is never imported.

The rules look at what the files say (game, name, currency), not at a list of tournament names, so new Sit & Go
variants or other games are left out without code changes.
"""
import re

SIT_AND_GO = "Sit & Go"
OMAHA = "PLO/Omaha"
OTHER_GAME = "other game"
NOT_DOLLARS = "not in $"
CASH = "cash game"
FREEROLL = "freeroll"                       # nothing paid to enter: promotions, freerolls (never a ticket entry)
UNRECOGNISED = "unrecognised summary"      # a summary that cannot be read: the whole tournament is left out
USER = "ignored"                            # the player chose to leave the tournament out (can be restored)
REASONS = (SIT_AND_GO, OMAHA, OTHER_GAME, NOT_DOLLARS, CASH, FREEROLL, UNRECOGNISED)

NLH = "Hold'em No Limit"
OTHER_CURRENCY = re.compile(r"[¥€£₩₹₽]|CN¥|\bRMB\b")
SNG = re.compile(r"sit\s*&\s*go|sit\s*n\s*go|\bsng\b", re.I)


def tournament_reason(name, game=None, amounts=""):
    """Why a tournament is out of scope, or None. game=None when only the name is known (e.g. stored rows)."""
    if SNG.search(name or ""):
        return SIT_AND_GO
    if game is not None:
        if "omaha" in game.lower() or re.search(r"\bPLO", name or ""):
            return OMAHA
        if game.strip() != NLH:
            return OTHER_GAME
    elif re.search(r"\bPLO|omaha", name or "", re.I):
        return OMAHA
    if OTHER_CURRENCY.search(name or "") or OTHER_CURRENCY.search(amounts or ""):
        return NOT_DOLLARS
    return None


def buyin_paid(buyin_line):
    """Sum of the amounts on a summary's 'Buy-in:' line, or None without one.

    A ticket entry is written with the full buy-in (e.g. 'Buy-in: $237.5+$25+$237.5' for a $500 seat won in a
    satellite), so only a tournament nobody paid to enter adds up to zero.
    """
    if not buyin_line:
        return None
    amounts = re.findall(r"\d[\d,]*(?:\.\d+)?", buyin_line.split(":", 1)[-1])
    return sum(float(a.replace(",", "")) for a in amounts) if amounts else None


def hand_reason(header):
    """Why the hand whose first line(s) are `header` is out of scope, or None.

    Tournament hands look like 'Poker Hand #TM1: Tournament #9, <name> <game> - Level1(...) - <date>'.
    """
    if "Tournament #" not in header:
        return CASH
    title = header.split(" - Level", 1)[0]
    if SNG.search(title):
        return SIT_AND_GO
    if "omaha" in title.lower():
        return OMAHA
    if not title.endswith(" " + NLH):
        return OTHER_GAME
    if OTHER_CURRENCY.search(title):
        return NOT_DOLLARS
    return None

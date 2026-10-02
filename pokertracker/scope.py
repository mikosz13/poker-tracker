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
REASONS = (SIT_AND_GO, OMAHA, OTHER_GAME, NOT_DOLLARS, CASH)

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

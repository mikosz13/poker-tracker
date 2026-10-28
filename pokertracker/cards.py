"""Hole cards for display: the higher card on the left ("7h Ac" is shown as "Ac 7h").

Display only: the parser, the database and the equity code keep the order of the hand history, so imports stay
idempotent. Boards are never sorted: their order is the deal (flop, turn, river).
"""
ORDER = {r: i for i, r in enumerate("AKQJT98765432")}


def sort_hole_cards(cards):
    """'7h Ac' -> 'Ac 7h'; a list gives a new list (the input is left as it is). Highest rank first; cards of the same
    rank (a pair) keep their order. Empty or None comes back unchanged."""
    if not cards:
        return cards
    if isinstance(cards, str):
        return " ".join(sort_hole_cards(cards.split()))
    return sorted(cards, key=lambda c: ORDER.get(c[:1].upper(), len(ORDER)))      # sorted() is stable: pairs keep order

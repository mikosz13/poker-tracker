"""Slow, independent reference evaluator (tuple comparison, no bit tricks) used to validate the fast one."""
import itertools
from collections import Counter


def ref5(cards):
    ranks = sorted((c >> 2 for c in cards), reverse=True)
    suits = [c & 3 for c in cards]
    cnt = Counter(ranks)
    groups = sorted(cnt.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    shape = [g[1] for g in groups]
    order = [g[0] for g in groups]
    flush = len(set(suits)) == 1
    uniq = sorted(cnt, reverse=True)
    straight = None
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            straight = uniq[0]
        elif uniq == [12, 3, 2, 1, 0]:
            straight = 3
    if straight is not None and flush:
        return (8, straight)
    if shape == [4, 1]:
        return (7, *order)
    if shape == [3, 2]:
        return (6, *order)
    if flush:
        return (5, *ranks)
    if straight is not None:
        return (4, straight)
    if shape == [3, 1, 1]:
        return (3, *order)
    if shape == [2, 2, 1]:
        return (2, *order)
    if shape == [2, 1, 1, 1]:
        return (1, *order)
    return (0, *ranks)


def ref7(cards):
    return max(ref5(c) for c in itertools.combinations(cards, 5))

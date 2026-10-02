"""Exact all-in equity and all-in adjusted EV (the "All-in Adjusted EV" idea of PokerTracker).

No Monte Carlo: when the betting is closed and the cards of every live player are known, every possible
runout is enumerated (e.g. 1,712,304 boards for a heads-up preflop all-in) and scored with a vectorised
7-card evaluator. Ties split the pot, side pots are handled, and unknown cards of folded players are
simply part of the unseen deck (uniform over the remaining cards, as in the real game).
"""
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
from itertools import chain, combinations
from math import comb

import numpy as np

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CHUNK = 200_000
BAD_BEAT_EQUITY = 0.80

HAND_NAMES = ["high card", "pair", "two pair", "three of a kind", "straight", "flush",
              "full house", "four of a kind", "straight flush"]


def card_int(s: str) -> int:
    return RANKS.index(s[0]) * 4 + SUITS.index(s[1])


def card_str(c: int) -> str:
    return RANKS[c >> 2] + SUITS[c & 3]


def parse_cards(text: str):
    return [card_int(t) for t in text.split()]


# ---- hand evaluator ---------------------------------------------------------

def _build_tables():
    n = 1 << 13
    pop = np.zeros(n, np.int32)
    hb = np.zeros(n, np.int32)
    straight = np.full(n, -1, np.int32)
    top = {k: np.zeros(n, np.int32) for k in (2, 3, 5)}
    wheel = (1 << 12) | 0b1111
    for m in range(n):
        bits = [r for r in range(12, -1, -1) if m >> r & 1]
        pop[m] = len(bits)
        hb[m] = bits[0] if bits else 0
        for k in top:
            v = 0
            for i in range(k):
                v = (v << 4) | (bits[i] if i < len(bits) else 0)
            top[k][m] = v
        for high in range(12, 3, -1):
            need = sum(1 << (high - i) for i in range(5))
            if m & need == need:
                straight[m] = high
                break
        else:
            if m & wheel == wheel:
                straight[m] = 3                      # A-2-3-4-5, five-high
    return pop, hb, straight, top[2], top[3], top[5]


POP, HB, STRAIGHT, TOP2, TOP3, TOP5 = _build_tables()


def _bit(x):
    return np.left_shift(np.int32(1), x)


def evaluate(cards) -> np.ndarray:
    """Score 5-7 card hands. cards: (N, n) ints 0..51 (rank*4+suit). Higher score = stronger hand.

    score = category << 20 | up to five 4-bit ranks (tie-breakers, most significant first).
    Rare categories are computed only on the rows that need them (that is where the speed comes from).
    """
    c = np.asarray(cards, dtype=np.int32)
    if c.ndim == 1:
        c = c[None, :]
    n_hands = c.shape[0]
    ranks, suits = c >> 2, c & 3
    bits = _bit(ranks)

    m1 = np.zeros(n_hands, np.int32)   # ranks present
    m2 = np.zeros(n_hands, np.int32)   # ranks with >=2 cards
    m3 = np.zeros(n_hands, np.int32)   # >=3
    m4 = np.zeros(n_hands, np.int32)   # 4
    for j in range(c.shape[1]):
        b = bits[:, j]
        m4 |= m3 & b
        m3 |= m2 & b
        m2 |= m1 & b
        m1 |= b

    score = TOP5[m1]                                                        # high card

    i = np.nonzero(m2)[0]                                                   # pair
    if i.size:
        p = HB[m2[i]]
        score[i] = (1 << 20) | (p << 16) | (TOP3[m1[i] & ~_bit(p)] << 4)

    i = np.nonzero(POP[m2] >= 2)[0]                                         # two pair
    if i.size:
        hi = HB[m2[i]]
        lo = HB[m2[i] & ~_bit(hi)]
        kick = HB[m1[i] & ~_bit(hi) & ~_bit(lo)]
        score[i] = (2 << 20) | (hi << 16) | (lo << 12) | (kick << 8)

    i = np.nonzero(m3)[0]                                                   # three of a kind
    if i.size:
        t = HB[m3[i]]
        score[i] = (3 << 20) | (t << 16) | (TOP2[m1[i] & ~_bit(t)] << 8)

    sh = STRAIGHT[m1]
    i = np.nonzero(sh >= 0)[0]                                              # straight
    if i.size:
        score[i] = (4 << 20) | (sh[i] << 16)

    # flush: pack the four suit counts into one int (8 bits each) and look only at rows with 5+ of a suit
    packed = np.left_shift(1, suits * 8).sum(axis=1)
    maybe = np.nonzero(((packed & 255) >= 5) | (((packed >> 8) & 255) >= 5)
                       | (((packed >> 16) & 255) >= 5) | (((packed >> 24) & 255) >= 5))[0]
    if maybe.size:
        sub_bits, sub_suits = bits[maybe], suits[maybe]
        fm = np.zeros(maybe.size, np.int32)
        for s_ in range(4):
            sm = np.where(sub_suits == s_, sub_bits, 0).sum(axis=1).astype(np.int32)
            fm = np.where(POP[sm] >= 5, sm, fm)
        has = fm != 0
        rows, fm = maybe[has], fm[has]
        score[rows] = (5 << 20) | TOP5[fm]                                  # flush

    i = np.nonzero(m3)[0]                                                   # full house
    if i.size:
        t = HB[m3[i]]
        pair_part = m2[i] & ~_bit(t)
        ok = pair_part != 0
        score[i[ok]] = (6 << 20) | (t[ok] << 16) | (HB[pair_part[ok]] << 12)

    i = np.nonzero(m4)[0]                                                   # four of a kind
    if i.size:
        q = HB[m4[i]]
        score[i] = (7 << 20) | (q << 16) | (HB[m1[i] & ~_bit(q)] << 12)

    if maybe.size and rows.size:                                            # straight flush
        sfh = STRAIGHT[fm]
        ok = sfh >= 0
        score[rows[ok]] = (8 << 20) | (sfh[ok] << 16)
    return score.astype(np.int32)


def category(score) -> int:
    return int(score) >> 20


# ---- exact enumeration ------------------------------------------------------

def _combos(deck, k):
    deck = np.asarray(deck, dtype=np.int32)
    if k == 0:
        return np.empty((1, 0), dtype=np.int32)
    n = len(deck)
    idx = np.fromiter(chain.from_iterable(combinations(range(n), k)), dtype=np.int16,
                      count=comb(n, k) * k).reshape(-1, k)
    return deck[idx]


def runout_scores(holes, board) -> np.ndarray:
    """Score of every player on every possible runout. holes: list of 2-card lists. Returns (R, players)."""
    known = set(board) | {c for h in holes for c in h}
    deck = [c for c in range(52) if c not in known]
    runs = _combos(deck, 5 - len(board))
    out = np.empty((len(runs), len(holes)), np.int32)
    board_arr = np.array(board, dtype=np.int32)
    for start in range(0, len(runs), CHUNK):
        part = runs[start:start + CHUNK]
        n = len(part)
        full = np.concatenate([np.broadcast_to(board_arr, (n, len(board))), part], axis=1)
        for i, h in enumerate(holes):
            cards = np.concatenate([np.broadcast_to(np.array(h, dtype=np.int32), (n, 2)), full], axis=1)
            out[start:start + n, i] = evaluate(cards)
    return out


def share_matrix(scores, eligible):
    """Per-runout share of a pot for the players in `eligible` (ties split equally)."""
    sub = scores[:, list(eligible)]
    win = sub == sub.max(axis=1, keepdims=True)
    return win / win.sum(axis=1, keepdims=True)


def equity(holes, board=()):
    """Exact equity of each hand against the others (one pot, all players eligible)."""
    scores = runout_scores([list(h) for h in holes], list(board))
    return tuple(share_matrix(scores, range(len(holes))).mean(axis=0))


def _canon(holes, board):
    """Relabel suits by first appearance: equity is invariant under suit permutations."""
    mapping = {}

    def m(c):
        mapping.setdefault(c & 3, len(mapping))
        return (c >> 2) * 4 + mapping[c & 3]

    return tuple(tuple(m(c) for c in h) for h in holes), tuple(m(c) for c in board)


@lru_cache(maxsize=4096)
def _pot_equities(holes, board, eligible_sets):
    scores = runout_scores([list(h) for h in holes], list(board))
    return tuple(tuple(share_matrix(scores, el).mean(axis=0)) for el in eligible_sets)


def pot_equities(holes, board, eligible_sets, cache=None):
    """For each eligible set (tuple of player indices): equity of its members for that pot.

    cache: optional object with get(key) -> value | None and set(key, value), e.g. database backed.
    """
    ch, cb = _canon(holes, board)
    el = tuple(tuple(e) for e in eligible_sets)
    if cache is None:
        return _pot_equities(ch, cb, el)
    key = repr((ch, cb, el))
    hit = cache.get(key)
    if hit is None:
        hit = _pot_equities(ch, cb, el)
        cache.set(key, hit)
    return hit


def side_pots(invested, contestants):
    """Layer the pot by contribution level. Returns [(amount, eligible_contestants)], main pot first."""
    pots, prev = [], 0.0
    for lvl in sorted({invested[n] for n in contestants}):
        amount = sum(min(v, lvl) - min(v, prev) for v in invested.values())
        eligible = tuple(n for n in contestants if invested[n] >= lvl)
        if amount > 1e-9:
            pots.append((amount, eligible))
        prev = lvl
    leftover = sum(invested.values()) - sum(a for a, _ in pots)
    if pots and leftover > 1e-6:                   # dead money above the top contestant level
        pots[-1] = (pots[-1][0] + leftover, pots[-1][1])
    return pots


# ---- all-in detection on a parsed hand --------------------------------------

BOARD_LEN = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}


def find_lock(hand):
    """Street and live players at the moment betting is closed: >= 2 players still in the hand,
    at most one of them with chips behind, and nobody left who still owes a call."""
    folded, allin = set(), set()
    commit = defaultdict(float)
    street = None
    for st, _order, nick, act, amount, is_allin in hand.actions:
        if st != street:
            street = st
            if st != "preflop":
                commit = defaultdict(float)
        if act == "folds":
            folded.add(nick)
        elif act in ("calls", "posts_small_blind", "posts_big_blind"):
            commit[nick] += amount
        elif act in ("bets", "raises"):
            commit[nick] = amount
        if is_allin:
            allin.add(nick)
        active = [n for n in hand.seats if n not in folded]
        if len(active) < 2:
            return None
        live = [n for n in active if n not in allin]
        top = max(commit.values(), default=0.0)
        if len(live) <= 1 and all(commit[n] >= top for n in live):
            return st, active
    return None


def prepare_allin(hand, hero=None):
    """Everything compute_allin needs before the expensive part, or None when no EV applies."""
    lock = find_lock(hand)
    if lock is None:
        return None
    street, active = lock
    if hero is not None and hero not in active:
        return None
    full_board = parse_cards(hand.board) if hand.board else []
    n_board = BOARD_LEN[street]
    if n_board >= 5 or len(full_board) < 5:
        return None
    if any(n not in hand.hole_cards for n in active):
        return None
    holes = [parse_cards(hand.hole_cards[n]) for n in active]
    board = full_board[:n_board]
    invested = {n: round(v, 2) for n, v in hand.invested.items()}
    pots = side_pots(invested, active)
    if abs(sum(a for a, _ in pots) - sum(invested.values())) > 0.01:
        return None
    idx = {n: i for i, n in enumerate(active)}
    eligible = [tuple(idx[n] for n in el) for _, el in pots]
    return {"street": street, "active": active, "holes": holes, "board": board, "full_board": full_board,
            "invested": invested, "pots": pots, "idx": idx, "eligible": eligible}


def cache_key(prep):
    ch, cb = _canon(prep["holes"], prep["board"])
    return repr((ch, cb, tuple(prep["eligible"])))


def _solve(args):
    """Worker entry point (must be top level so other processes can import it)."""
    holes, board, eligible = args
    ch, cb = _canon(holes, board)
    return _pot_equities(ch, cb, tuple(tuple(e) for e in eligible))


def precompute(preps, cache, workers=None):
    """Fill the cache for all distinct matchups in preps, in parallel when there are several of them.

    Results are identical to the serial path (same function, same exact enumeration); only the work is spread
    over CPU cores. Falls back to serial if worker processes cannot be started.
    """
    todo, seen = [], set()
    for prep in preps:
        key = cache_key(prep)
        if key not in seen and cache.get(key) is None:
            seen.add(key)
            todo.append((key, (prep["holes"], prep["board"], prep["eligible"])))
    if not todo:
        return 0
    workers = workers or os.cpu_count() or 1
    results = None
    if workers > 1 and len(todo) > 1:
        try:
            with ProcessPoolExecutor(max_workers=min(workers, len(todo))) as pool:
                results = list(pool.map(_solve, [args for _, args in todo]))
        except Exception:                                         # e.g. sandboxed environments
            results = None
    if results is None:
        results = [_solve(args) for _, args in todo]
    for (key, _), value in zip(todo, results):
        cache.set(key, value)
    return len(todo)


def compute_allin(hand, cache=None, hero=None, prepared=None):
    """All-in adjusted EV for one parsed hand, or None if it is not an all-in with cards to come,
    some live player's cards are unknown, or (when hero is given) hero is not one of the live players."""
    prep = prepared or prepare_allin(hand, hero)
    if prep is None:
        return None
    street, active, holes, board = prep["street"], prep["active"], prep["holes"], prep["board"]
    full_board, invested, pots = prep["full_board"], prep["invested"], prep["pots"]
    idx = prep["idx"]
    eq_by_pot = pot_equities(tuple(tuple(h) for h in holes), tuple(board), prep["eligible"], cache)
    expected = defaultdict(float)
    for (amount, eligible), eqs in zip(pots, eq_by_pot):
        for n, e in zip(eligible, eqs):
            expected[n] += amount * e
    main_eq = dict(zip(pots[0][1], eq_by_pot[0]))

    final = np.array([[*h, *full_board] for h in holes], dtype=np.int32)
    actual = evaluate(final)
    best = max(actual[idx[n]] for n in pots[0][1])
    winners = [n for n in pots[0][1] if actual[idx[n]] == best]

    rows = []
    for n in active:
        collected = round(hand.collected[n], 2)
        inv = invested.get(n, 0.0)
        net = collected - inv
        ev_net = expected[n] - inv
        result = None
        if n in pots[0][1]:
            result = "split" if (n in winners and len(winners) > 1) else "win" if n in winners else "lose"
        rows.append({"nick": n, "hole_cards": hand.hole_cards[n], "equity": main_eq.get(n),
                     "invested": inv, "collected": collected, "net": net, "ev_net": ev_net,
                     "luck": net - ev_net, "result": result})
    return {"street": street, "board_at_lock": " ".join(card_str(c) for c in board), "players": rows}

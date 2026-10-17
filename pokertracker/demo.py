"""Demo data: synthetic GGPoker files (hand histories and tournament summaries) that the normal importer reads into a
separate demo database, so a new player can look at every screen before importing their own files, and the README
can show screenshots without anyone's real data.

The hands are played, not drawn: 6-max tables, blinds and antes, a simple preflop strategy by hand strength and
stack, small bets after the flop, all-ins with side pots (equity.side_pots) and winners chosen by the app's own
evaluator, so every hand conserves chips like a real one. Tournaments use the reserved numbers 990000001… and names
starting with "DEMO", so they can never be taken for real ones.
"""
import random
from datetime import datetime, timedelta

from .equity import evaluate, parse_cards, side_pots

DEMO_FIRST_ID = 990_000_001
DEMO_SEED = 13           # a mixed run: a drawdown, then a climb to a modest profit (README screenshots)
RANKS, SUITS = "23456789TJQKA", "cdhs"
LEVELS = [(50, 100, 15), (75, 150, 20), (100, 200, 25), (150, 300, 35), (200, 400, 50), (250, 500, 60), (300, 600, 75),
          (400, 800, 100), (500, 1000, 125), (600, 1200, 150), (800, 1600, 200), (1000, 2000, 250), (1200, 2400, 300),
          (1500, 3000, 375), (2000, 4000, 500), (2500, 5000, 600), (3000, 6000, 750)]
HANDS_PER_LEVEL = 9
START_STACK = 10_000
KINDS = (  # name, buy-in parts (prize, fee, bounty), field size range, weight
    ("DEMO Bounty Hunters $10.80", (4.5, 0.8, 5.5), (300, 1200), 6),
    ("DEMO Bounty Hunters $21.60", (9.0, 1.6, 11.0), (150, 700), 4),
    ("DEMO Daily Main $5.40", (4.9, 0.5, 0.0), (400, 1500), 3),
    ("DEMO Speed Racer $2.50", (2.25, 0.25, 0.0), (800, 2500), 2),
    ("DEMO $11 Satellite to DEMO Sunday $109", (10.0, 1.0, 0.0), (90, 250), 1),
)


def _fmt(x):
    return f"{int(round(x)):,}"


def _money(x):
    return f"{x:,.2f}".rstrip("0").rstrip(".") if x != int(x) else f"{int(x):,}"


def _ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _strength(cards):
    """0..1 preflop strength from the two cards (pairs, high cards, suited, connected)."""
    a, b = sorted((RANKS.index(c[0]) for c in cards), reverse=True)
    suited, gap = cards[0][1] == cards[1][1], a - b
    if a == b:
        return 0.55 + a / 26
    s = (a + b) / 30 + (0.06 if suited else 0) + (0.04 if gap == 1 else 0) - (0.03 * max(0, gap - 3))
    return max(0.0, min(0.95, s + (0.12 if a >= 11 and b >= 9 else 0)))


class Hand:
    """One hand at a 6-max table: plays it and writes it in GGPoker's format."""

    def __init__(self, rnd, hand_id, tid, name, level, when, seats, stacks, button):
        self.rnd, self.lines, self.level = rnd, [], level
        sb, bb, ante = LEVELS[level]
        self.sb, self.bb, self.ante = sb, bb, ante
        self.seats = seats                                     # [(seat number, nick)] at the table
        self.stack = dict(stacks)
        self.order = [n for _, n in seats]
        self.button = button
        self.invested = {n: 0.0 for n in self.order}
        self.street = {n: 0.0 for n in self.order}
        self.folded, self.allin = set(), set()
        deck = [r + s for r in RANKS for s in SUITS]
        rnd.shuffle(deck)
        self.cards = {n: [deck.pop(), deck.pop()] for n in self.order}
        self.board_cards = [deck.pop() for _ in range(5)]
        self.board = []
        self.lines.append(f"Poker Hand #{hand_id}: Tournament #{tid}, {name} Hold'em No Limit - Level{level + 1}"
                          f"({_fmt(sb)}/{_fmt(bb)}({_fmt(ante)})) - {when:%Y/%m/%d %H:%M:%S}")
        seat_of = dict((n, s) for s, n in seats)
        self.lines.append(f"Table '{(tid % 97) + 1}' 6-max Seat #{seat_of[self.order[button]]} is the button")
        self.lines += [f"Seat {s}: {n} ({_fmt(self.stack[n])} in chips)" for s, n in seats]
        self.seat_of = seat_of

    def put(self, n, amount, street=True):
        amount = min(amount, self.stack[n])
        self.stack[n] -= amount
        self.invested[n] += amount
        if street:
            self.street[n] += amount
        if self.stack[n] <= 0:
            self.allin.add(n)
        return amount

    def active(self):
        return [n for n in self.order if n not in self.folded]

    def can_act(self):
        return [n for n in self.order if n not in self.folded and n not in self.allin]

    def betting(self, first, preflop):
        """One betting round from seat index first; each player decides from strength, price and stack."""
        k, n_players = first, len(self.order)
        current = max(self.street.values())
        last_raise = self.bb
        to_act = set(self.can_act())
        raised = preflop                                      # the big blind counts as the bet to beat preflop
        while to_act and len(self.active()) > 1:
            n = self.order[k % n_players]
            k += 1
            if n not in to_act:
                continue
            to_act.discard(n)
            to_call = current - self.street[n]
            s = _strength(self.cards[n]) if preflop else self._made(n)
            stack_bb = (self.stack[n] + self.street[n]) / self.bb
            r = self.rnd.random()
            if to_call <= 0:                                  # check or bet
                if not preflop and r < 0.15 + 0.5 * s and current == 0:
                    bet = max(self.bb, round(0.5 * sum(self.invested.values()) / self.bb) * self.bb)
                    amt = self.put(n, bet)
                    self.lines.append(f"{n}: bets {_fmt(amt)}" + (" and is all-in" if n in self.allin else ""))
                    current, last_raise = self.street[n], amt
                    to_act = set(self.can_act()) - {n}
                elif preflop and r < 0.3 + 0.5 * s:            # the big blind raises a limped pot sometimes
                    target = current + 2 * self.bb if r < 0.2 * s else None
                    if target:
                        amt = self.put(n, target - self.street[n])
                        self.lines.append(f"{n}: raises {_fmt(target - current)} to {_fmt(self.street[n])}"
                                          + (" and is all-in" if n in self.allin else ""))
                        current, last_raise = self.street[n], target - current
                        to_act = set(self.can_act()) - {n}
                    else:
                        self.lines.append(f"{n}: checks")
                else:
                    self.lines.append(f"{n}: checks")
                continue
            facing_shove = any(m in self.allin and self.street[m] >= current for m in self.order if m != n)
            if preflop:
                unopened = current <= self.bb and not any(self.street[m] > self.bb for m in self.order)
                if stack_bb <= 12 and s > 0.55 - (0.15 if unopened else 0):
                    target = self.street[n] + self.stack[n]
                elif unopened and s > 0.62 - 0.05 * (k % n_players) / n_players:
                    target = round(2.2 * self.bb)
                elif not unopened and s > 0.86 and not facing_shove:
                    target = current * 3
                elif (not unopened and s > (0.82 if facing_shove else 0.66)) or (unopened and r < 0.06 and s > 0.4):
                    target = current                          # call (or limp)
                else:
                    target = None
            else:
                target = current if s > 0.45 or r < 0.25 else None
            if target is None:
                self.folded.add(n)
                self.lines.append(f"{n}: folds")
                continue
            target = min(target, self.street[n] + self.stack[n])
            if target > current and target - current >= min(last_raise, self.stack[n]):
                before = self.street[n]
                self.put(n, target - before)
                self.lines.append(f"{n}: raises {_fmt(self.street[n] - current)} to {_fmt(self.street[n])}"
                                  + (" and is all-in" if n in self.allin else ""))
                last_raise, current = self.street[n] - current, self.street[n]
                to_act = set(self.can_act()) - {n}
            else:
                amt = self.put(n, min(current, self.street[n] + self.stack[n]) - self.street[n])
                if amt <= 0:
                    self.lines.append(f"{n}: checks")
                else:
                    self.lines.append(f"{n}: calls {_fmt(amt)}" + (" and is all-in" if n in self.allin else ""))

    def _made(self, n):
        """0..1: how good the hand is on the current board (category of the best five cards)."""
        score = int(evaluate([parse_cards(" ".join(self.cards[n] + self.board))])[0])
        return min(1.0, (score >> 20) / 4 + 0.1)

    def return_uncalled(self):
        tops = sorted(self.invested.values(), reverse=True)
        top = max(self.order, key=lambda n: self.invested[n])
        extra = tops[0] - (tops[1] if len(tops) > 1 else 0)
        if extra > 0:
            self.invested[top] -= extra
            self.stack[top] += extra
            self.allin.discard(top) if self.stack[top] > 0 else None
            self.lines.append(f"Uncalled bet ({_fmt(extra)}) returned to {top}")

    def deal(self, street):
        cut = {"FLOP": 3, "TURN": 4, "RIVER": 5}[street]
        before = " ".join(self.board)
        self.board = self.board_cards[:cut]
        new = " ".join(self.board[len(before.split()) if before else 0:])
        self.lines.append(f"*** {street} *** [{before}] [{new}]" if before else f"*** {street} *** [{new}]")
        self.street = {n: 0.0 for n in self.order}

    def play(self):
        order, nb = self.order, len(self.order)
        for n in order:
            amt = self.put(n, self.ante, street=False)
            self.lines.append(f"{n}: posts the ante {_fmt(amt)}")
        sb_n, bb_n = order[(self.button + 1) % nb], order[(self.button + 2) % nb]
        self.lines.append(f"{sb_n}: posts small blind {_fmt(self.put(sb_n, self.sb))}")
        self.lines.append(f"{bb_n}: posts big blind {_fmt(self.put(bb_n, self.bb))}")
        self.lines.append("*** HOLE CARDS ***")
        self.lines += [f"Dealt to {n} [{' '.join(self.cards[n])}]" if n == "Hero" else f"Dealt to {n} " for n in order]
        self.betting(self.button + 3, preflop=True)
        shown = False
        for street in ("FLOP", "TURN", "RIVER"):
            if len(self.active()) < 2:
                break
            if len(self.can_act()) <= 1 and not shown:          # all-in: cards shown, the board runs out
                self.return_uncalled()
                self.lines += [f"{n}: shows [{' '.join(self.cards[n])}]" for n in self.active()]
                shown = True
            self.deal(street)
            if len(self.can_act()) > 1:
                self.betting(self.button + 1, preflop=False)
        self.return_uncalled()
        winners = self.settle(shown)
        pot = sum(self.invested.values())
        self.lines.append("*** SUMMARY ***")
        self.lines.append(f"Total pot {_fmt(pot)} | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0")
        if self.board:
            self.lines.append(f"Board [{' '.join(self.board)}]")
        return winners

    def settle(self, shown):
        alive = self.active()
        won = {n: 0.0 for n in self.order}
        if len(alive) == 1:
            won[alive[0]] = sum(self.invested.values())
            self.lines.append(f"{alive[0]} collected {_fmt(won[alive[0]])} from pot")
        else:
            self.lines.append("*** SHOWDOWN ***")
            if not shown:
                self.lines += [f"{n}: shows [{' '.join(self.cards[n])}]" for n in alive]
            scores = dict(zip(alive, (int(x) for x in evaluate([parse_cards(" ".join(self.cards[n] + self.board))
                                                                for n in alive]))))
            for amount, eligible in side_pots(self.invested, alive):
                best = max(scores[n] for n in eligible)
                winners = [n for n in eligible if scores[n] == best]
                share, extra = divmod(int(round(amount)), len(winners))
                for i, n in enumerate(winners):
                    got = share + (1 if i < extra else 0)
                    won[n] += got
                    self.lines.append(f"{n} collected {_fmt(got)} from pot")
        for n, w in won.items():
            self.stack[n] += w
        return won


def _place_prize(rnd, field, place, prize_part, pool):
    paid = max(1, field * 15 // 100)
    if place > paid:
        return 0.0
    share = 0.18 * (1 / place) ** 0.85 if place > 1 else 0.18
    return round(max(prize_part * 1.8, pool * share), 2)


def tournament(rnd, index, start, kind):
    """One tournament: its hand history (newest first) and summary, with Hero's late registration, re-entries,
    knockouts and the finish decided by the hands themselves."""
    name, (prize_part, fee, bounty), (lo, hi), _ = kind
    tid = DEMO_FIRST_ID + index
    field = rnd.randint(lo, hi)
    late = rnd.random() < 0.4
    level = rnd.randint(2, 5) if late else 0
    nicks = [f"{rnd.getrandbits(32):08x}" for _ in range(5)]
    hero_seat = rnd.randint(1, 6)
    seats = sorted([(hero_seat, "Hero")] + list(zip([s for s in range(1, 7) if s != hero_seat], nicks)))
    avg = START_STACK * (1 + 0.35 * level)
    stacks = {n: (START_STACK if n == "Hero" else round(avg * rnd.uniform(0.5, 1.8) / 10) * 10) for _, n in seats}
    when, button, hands, kos, reentries, busted = start, 0, [], 0, 0, False
    target = rnd.randint(40, 170)
    hero_money = 0.0
    for k in range(target):
        lvl = min(len(LEVELS) - 1, level + k // HANDS_PER_LEVEL)
        hand_id = f"TM99{index:04d}{k:05d}"
        h = Hand(rnd, hand_id, tid, name, lvl, when, seats, stacks, button)
        won = h.play()
        hands.append("\n".join(h.lines))
        stacks = h.stack
        for n in [n for n in h.order if stacks[n] <= 0 and n != "Hero"]:
            if won.get("Hero", 0) > 0:
                kos += 1
                hero_money += bounty / 2 if bounty else 0
            new = f"{rnd.getrandbits(32):08x}"
            seats = [(s, new if m == n else m) for s, m in seats]
            stacks.pop(n)
            stacks[new] = round(sum(stacks.values()) / len(stacks) * rnd.uniform(0.6, 1.4) / 10) * 10
        if stacks["Hero"] <= 0:
            if reentries < 2 and lvl < 6 and rnd.random() < 0.6:
                reentries += 1
                stacks["Hero"] = START_STACK
            else:
                busted = True
                break
        button = (button + 1) % 6
        when += timedelta(seconds=rnd.randint(25, 70))
    played = len(hands)
    # the hands cover the start of the tournament: a bust places Hero by how far it got, surviving them leaves the
    # rest of the tournament to chance (most deep runs still end before the money, as in real tournaments)
    if busted:
        frac = min(0.97, played / 260)
        place = max(2, int(field * (1 - frac) * rnd.uniform(0.75, 1.0)))
    else:
        place = rnd.randint(1, max(2, field * 45 // 100))
    entries = 1 + reentries
    pool = round(field * 1.15 * prize_part, 2)
    satellite = "Satellite" in name
    lines = [f"Tournament #{tid}, {name}, Hold'em No Limit",
             "Buy-in: $" + "+$".join(_money(x) for x in ((prize_part, fee, bounty) if bounty else (prize_part, fee))),
             f"{field} Players", f"Total Prize Pool: ${_money(pool + field * bounty)}",
             f"Tournament started {start:%Y/%m/%d %H:%M:%S} "]
    if satellite:
        seats_won = field // 10
        prize_text = "$109 Entry" if place <= seats_won else "$0"
    else:
        prize = _place_prize(rnd, field, place, prize_part, pool) + hero_money
        prize_text = f"${_money(round(prize, 2))}"
    lines.append(f"{_ordinal(place)} : Hero, {prize_text}")
    lines.append(f"You finished the tournament in {_ordinal(place)} place.")
    lines.append(f"You made {reentries} re-entries and received a total of {prize_text}." if reentries
                 else f"You received a total of {prize_text}.")
    stamp = f"{start:%Y%m%d}"
    return [(f"GG{stamp} - Tournament #{tid} - {name}.txt", "\n".join(lines) + "\n"),
            (f"GG{stamp}-{start:%H%M} - {name}.txt", "\n\n".join(reversed(hands)) + "\n")]


def demo_files(n=40, seed=DEMO_SEED, today=None):
    """[(file name, text)] for n tournaments over the last ~45 days (deterministic for a seed and a day)."""
    rnd = random.Random(seed)
    today = today or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    weights = [k[3] for k in KINDS]
    out = []
    starts = sorted(today - timedelta(days=rnd.uniform(1, 45), hours=rnd.uniform(-6, 6)) for _ in range(n))
    for i, start in enumerate(starts):
        start = start.replace(minute=rnd.choice((0, 15, 30, 45)), second=0)
        out += tournament(rnd, i, start, rnd.choices(KINDS, weights)[0])
    return out


def build_demo(db, n=40, seed=DEMO_SEED, equity=True):
    """Fill an empty database with the demo tournaments through the normal importer."""
    from .importer import import_texts
    return import_texts(db, demo_files(n, seed), equity=equity)


DEMO_STALE_DAYS = 14     # older demo data is rebuilt, so the dashboard's recent periods are never empty


def demo_url(real_url):
    """The demo database: next to the player's SQLite database, or in the data folder (PostgreSQL players)."""
    from pathlib import Path
    from .db import data_dir
    if real_url.startswith("sqlite:///") and not real_url.endswith(":memory:"):
        return "sqlite:///" + str(Path(real_url[len("sqlite:///"):]).with_name("demo.db"))
    return "sqlite:///" + str(data_dir() / "demo.db")


def ensure_demo(real_url, now=None, equity=True):
    """The demo database's URL, built (or rebuilt when missing, empty or stale) through the normal importer."""
    from pathlib import Path
    from .db import Database
    url = demo_url(real_url)
    path = Path(url[len("sqlite:///"):])
    if path.exists():
        with Database(url) as db:
            db.init_schema()
            last = db.scalar("SELECT MAX(played_at) FROM hands")
        fresh = last and str(last)[:10] >= ((now or datetime.now()) - timedelta(days=DEMO_STALE_DAYS)).strftime("%Y-%m-%d")
        if fresh:
            return url
        path.unlink()
    with Database(url) as db:
        db.init_schema()
        build_demo(db, equity=equity)
        db.commit()
    return url

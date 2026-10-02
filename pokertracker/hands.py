"""Parser for GGPoker tournament hand histories (PokerCraft export: .txt or text-layer .pdf)."""
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

HERO = "Hero"
DEFAULT_STARTING_STACK = 10_000

AMT = r"\d[\d,]*(?:\.\d+)?"
HEADER = re.compile(r"Poker Hand #(?P<id>\w+): Tournament #(?P<tid>\d+), (?P<name>.+?) Hold'em No Limit")
NAME_PRICE = re.compile(r"^(?P<name>.+?) \$(?P<price>" + AMT + r")$")
LEVEL = re.compile(
    r"Hold'em No Limit - Level(?P<lvl>\d+)\((?P<sb>" + AMT + r")/(?P<bb>" + AMT + r")\((?P<ante>" + AMT
    + r")\)\) - (?P<ts>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})"
)
TABLE = re.compile(r"Table '(?P<name>[^']+)' (?P<max>\d+)-max Seat #(?P<button>\d+) is the button")
SEAT = re.compile(r"Seat (?P<seat>\d+): (?P<nick>\S+) \((?P<stack>" + AMT + r") in chips\)")
DEALT = re.compile(r"Dealt to (?P<nick>\S+) \[(?P<cards>[^\]]+)\]")
STREET = re.compile(r"\*\*\* (?P<s>HOLE CARDS|FLOP|TURN|RIVER|SHOWDOWN|SUMMARY) \*\*\*")
ACTION = re.compile(
    r"^(?P<nick>\S+): (?P<act>folds|checks|calls|bets|raises|posts the ante|posts small blind|posts big blind|shows)"
    r"(?: (?P<a1>" + AMT + r"))?(?: to (?P<a2>" + AMT + r"))?(?P<allin> and is all-in)?"
)
SHOWS = re.compile(r"^(?P<nick>\S+): shows \[(?P<cards>[^\]]+)\]")
UNCALLED = re.compile(r"Uncalled bet \((?P<amt>" + AMT + r")\) returned to (?P<nick>\S+)")
COLLECTED = re.compile(r"^(?P<nick>\S+) collected (?P<amt>" + AMT + r") from pot")
POT = re.compile(r"Total pot (?P<pot>" + AMT + r") \| Rake (?P<rake>" + AMT + r")")
BOARD = re.compile(r"^Board \[(?P<b>[^\]]+)\]")

STREET_MAP = {"HOLE CARDS": "preflop", "FLOP": "flop", "TURN": "turn", "RIVER": "river"}
# Labels of the players before the button, by how many there are. The first to act preflop is always UTG.
EARLY_LABELS = {
    0: [], 1: ["UTG"], 2: ["UTG", "CO"], 3: ["UTG", "HJ", "CO"], 4: ["UTG", "LJ", "HJ", "CO"],
    5: ["UTG", "UTG+1", "LJ", "HJ", "CO"], 6: ["UTG", "UTG+1", "MP", "LJ", "HJ", "CO"],
}


def num(s):
    return float(s.replace(",", "")) if s else 0.0


@dataclass
class Hand:
    hand_id: str
    tournament_id: int
    tournament_name: str
    buyin_total: float | None
    level: int
    sb: float
    bb: float
    ante: float
    played_at: str                                   # ISO 'YYYY-MM-DD HH:MM:SS'
    table: str
    max_seats: int
    button: int
    seats: dict = field(default_factory=dict)        # nick -> (seat, stack)
    positions: dict = field(default_factory=dict)    # nick -> label
    hole_cards: dict = field(default_factory=dict)   # nick -> "Qs Kc"
    actions: list = field(default_factory=list)      # (street, order, nick, type, amount, all_in)
    board: str = ""
    total_pot: float = 0.0
    rake: float = 0.0
    invested: dict = field(default_factory=lambda: defaultdict(float))
    collected: dict = field(default_factory=lambda: defaultdict(float))
    showdown: bool = False

    def net(self, nick):
        return self.collected[nick] - self.invested[nick]


def position_labels(seats, button):
    """Seat number -> position label for the occupied seats, or {} if the button is not on an occupied seat."""
    seats = sorted(seats)
    if button not in seats or len(seats) < 2:
        return {}
    i = seats.index(button)
    ring = seats[i:] + seats[:i]          # button first, clockwise
    if len(ring) == 2:
        return {ring[0]: "BTN/SB", ring[1]: "BB"}
    early = EARLY_LABELS.get(len(ring) - 3)
    if early is None:                     # more than 9 players: never seen on GGPoker
        return {}
    return dict(zip(ring, ["BTN", "SB", "BB"] + early))


def assign_positions(hand: Hand):
    by_seat = position_labels([seat for seat, _ in hand.seats.values()], hand.button)
    hand.positions = {nick: by_seat[seat] for nick, (seat, _) in hand.seats.items() if seat in by_seat}


def parse_hand(block: str) -> Hand | None:
    lines = [l.strip() for l in block.replace("\f", "").splitlines() if l.strip()]
    if len(lines) < 3:
        return None
    # .txt exports keep header and level on one line; the PDF splits them over two
    head, idx = lines[0], 1
    if not LEVEL.search(head):
        head, idx = head + " " + lines[1], 2
    h, lv, tb = HEADER.match(head), LEVEL.search(head), TABLE.match(lines[idx])
    if not (h and lv and tb):
        return None
    np_ = NAME_PRICE.match(h["name"])       # 'Bounty Hunters $54' -> name + price; satellites have no price
    name, price = (np_["name"], num(np_["price"])) if np_ else (h["name"], None)
    hand = Hand(h["id"], int(h["tid"]), name, price, int(lv["lvl"]), num(lv["sb"]), num(lv["bb"]),
                num(lv["ante"]), lv["ts"].replace("/", "-"), tb["name"], int(tb["max"]), int(tb["button"]))
    street, order = "preflop", 0
    street_commit = defaultdict(float)
    in_summary = False
    for line in lines[idx + 1:]:
        if s := SEAT.match(line):
            if not in_summary:
                hand.seats[s["nick"]] = (int(s["seat"]), num(s["stack"]))
        elif d := DEALT.match(line):
            hand.hole_cards[d["nick"]] = d["cards"]
        elif st := STREET.match(line):
            name_ = st["s"]
            if name_ == "SUMMARY":
                in_summary = True
            elif name_ in STREET_MAP:
                street = STREET_MAP[name_]
                if name_ != "HOLE CARDS":      # blinds are posted before HOLE CARDS and stay committed
                    street_commit = defaultdict(float)
        elif in_summary:
            if m := POT.match(line):
                hand.total_pot, hand.rake = num(m["pot"]), num(m["rake"])
            elif m := BOARD.match(line):
                hand.board = m["b"]
        elif m := UNCALLED.match(line):
            hand.invested[m["nick"]] -= num(m["amt"])
        elif m := COLLECTED.match(line):
            hand.collected[m["nick"]] += num(m["amt"])
        elif a := ACTION.match(line):
            nick, act = a["nick"], a["act"]
            if act == "shows":
                hand.showdown = True
                if sm := SHOWS.match(line):
                    hand.hole_cards[nick] = sm["cards"]      # opponents' cards are only known when shown
                continue
            order += 1
            amount = num(a["a2"] or a["a1"])
            if act == "posts the ante":
                hand.invested[nick] += amount
            elif act in ("posts small blind", "posts big blind", "calls"):
                street_commit[nick] += amount
                hand.invested[nick] += amount
            elif act in ("bets", "raises"):
                # 'raises X to Y' -> Y is the player's total on this street
                new_total = amount if (act == "bets" or a["a2"]) else street_commit[nick] + amount
                hand.invested[nick] += new_total - street_commit[nick]
                street_commit[nick] = new_total
            hand.actions.append((street, order, nick, act.replace(" ", "_"), amount, bool(a["allin"])))
    assign_positions(hand)
    return hand


def parse_hands(text: str):
    """Return Hand objects from an export, oldest first (GG exports newest first)."""
    blocks = re.split(r"\n(?=Poker Hand #)", text.replace("\f", "").strip())
    hands = [h for b in blocks if (h := parse_hand(b))]
    return sorted(hands, key=lambda h: h.played_at)


def load_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True,
                              text=True, check=True).stdout
    return path.read_text(encoding="utf-8-sig")


def entries_from_rows(rows):
    """Split Hero's hands of one tournament into entries (late reg / re-entries).

    rows: chronological tuples (hand_id, level, played_at, big_blind, stack, net_won).
    Entry #1 starts at Hero's first hand; a new entry starts on the first hand after Hero's stack hit zero.
    If Hero played from level 1, that stack is the starting stack (satellites 5,000; Bounty Hunters 10,000),
    otherwise the default is assumed. starts_fresh=False means earlier hands of the entry are missing.
    """
    lvl1 = [r for r in rows if r[1] == 1]
    starting = lvl1[0][4] if lvl1 else DEFAULT_STARTING_STACK
    entries, prev_after = [], None
    for hand_id, level, played_at, bb, stack, net in rows:
        if prev_after is None or prev_after <= 0.5:
            entries.append({
                "entry_no": len(entries) + 1, "entry_level": level, "entered_at": played_at,
                "start_stack": stack, "start_stack_bb": round(stack / bb, 2),
                "starts_fresh": abs(stack - starting) < 1, "first_hand_id": hand_id,
            })
        prev_after = stack + net
    return entries


def detect_entries(hands, hero=HERO):
    rows = [(h.hand_id, h.level, h.played_at, h.bb, h.seats[hero][1], h.net(hero))
            for h in sorted(hands, key=lambda h: (h.played_at, h.hand_id)) if hero in h.seats]
    return entries_from_rows(rows)

"""Parser for GGPoker tournament summary files (PokerCraft export)."""
import re
from dataclasses import dataclass

from .scope import FREEROLL, buyin_paid, tournament_reason

AMT = r"\d[\d,]*(?:\.\d+)?"
HEADER = re.compile(r"Tournament #(?P<id>\d+), (?P<name>.+?)(?: \$?" + AMT + r")?, (?P<game>Hold'em No Limit.*)")
BUYIN = re.compile(
    r"Buy-in: \$?(?P<prize>" + AMT + r")\+\$?(?P<fee>" + AMT + r")(?:\+\$?(?P<bounty>" + AMT + r"))?"
)
FIRST_LINE = re.compile(r"Tournament #(?P<id>\d+), (?P<name>.+), (?P<game>[^,]+)$")   # any game, any currency
PLAYERS = re.compile(r"(?P<n>\d+) Players")
POOL = re.compile(r"Total Prize Pool: \$?(?P<pool>" + AMT + r")")
STARTED = re.compile(r"Tournament started (?P<ts>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})")
PLACE = re.compile(r"You finished the tournament in (?P<place>\d+)(?:st|nd|rd|th) place")
REENTRIES = re.compile(r"You made (?P<n>\d+) re-entries|You have re-entered (?P<n2>\d+) times")
RECEIVED = re.compile(r"received a total of (?P<prize>.+?)\.?\s*$", re.M)
HERO_PRIZE = re.compile(r"^\d+(?:st|nd|rd|th) : Hero, (?P<prize>.+?)\s*$", re.M)
ADVANCED = re.compile(r"advanced to (?P<day>Day ?\d+|Final Day|Stage ?\d+) with (?P<chips>" + AMT + r") chips", re.I)
# "Stage 2", "[Day 3]", "Day 1B", "Final Day": a day of a tournament that runs over several days
STAGE = re.compile(r"\b(?:Stage|Day) ?(?P<n>\d+)[A-Z]?\b|\bFinal Day\b", re.I)


def stage_of(name):
    """1 for a first day (or a one-day tournament), N for "Stage N" / "Day N", 99 for a "Final Day"."""
    m = STAGE.search(name or "")
    if not m:
        return 1
    return int(m["n"]) if m["n"] else 99


def prize_parts(text):
    """(cash, ticket face value) of a prize such as "$20", "$500 Entry", "$0 Entry$7.02" or "0 chips"."""
    tickets = [money(a) for a in re.findall(r"\$(" + AMT + r") Entry", text or "")]
    cash = [money(a) for a in re.findall(r"\$(" + AMT + r")(?! Entry)\b", text or "")]
    return round(sum(cash), 2), round(sum(tickets), 2)


class OutOfScope(ValueError):
    """A summary of something the tracker never imports (Sit & Go, PLO, not in $ ...)."""

    def __init__(self, reason, tournament_id, name=None):
        super().__init__(f"{reason}: tournament #{tournament_id}")
        self.reason, self.tournament_id, self.name = reason, tournament_id, name


class UnrecognisedSummary(ValueError):
    """A summary that cannot be read; tournament_id is known when at least its first line is a GGPoker header."""

    def __init__(self, tournament_id=None, name=None):
        super().__init__("Unrecognized tournament summary format")
        self.tournament_id, self.name = tournament_id, name


def money(s):
    return float(s.replace(",", "")) if s else 0.0


@dataclass
class Tournament:
    id: int
    site: str
    name: str
    game_type: str
    format: str            # 'bounty', 'satellite' or 'regular'
    buyin_prize: float
    buyin_fee: float
    buyin_bounty: float
    buyin_total: float
    players: int
    prize_pool: float
    started_at: str        # ISO 'YYYY-MM-DD HH:MM:SS'
    finish_place: int | None
    prize_won: float       # cash (knockouts included)
    prize_is_ticket: bool  # a ticket was won (prize_ticket > 0)
    reentries: int
    prize_ticket: float = 0.0      # face value of the tickets won (a satellite seat)
    stage: int = 1                 # day of a multi-day tournament (99: final day)
    advanced_to: str = None        # "Day 2" when Hero went through to the next day
    advanced_chips: float = None   # chips carried to it


def parse_summary(text: str) -> Tournament:
    first = next((l.strip() for l in text.lstrip("\ufeff").splitlines() if l.strip()), "")
    if m := FIRST_LINE.match(first):
        buyin = next((l for l in text.splitlines() if l.startswith("Buy-in:")), "")
        if reason := tournament_reason(m["name"], m["game"], buyin):
            raise OutOfScope(reason, int(m["id"]), m["name"])
        # e.g. "Buy-in: $0": a freeroll or promotion, unless it is a later day (paid on day 1)
        if buyin_paid(buyin) == 0 and stage_of(m["name"]) == 1:
            raise OutOfScope(FREEROLL, int(m["id"]), m["name"])
    h, b = HEADER.search(text), BUYIN.search(text)
    later_day = h and stage_of(h["name"]) > 1 and buyin_paid(
        next((l for l in text.splitlines() if l.startswith("Buy-in:")), "")) == 0
    if not (h and (b or later_day)):
        raise UnrecognisedSummary(int(m["id"]) if m else None, m["name"] if m else None)

    def find(rx, group, default=None):
        m = rx.search(text)
        return m[group] if m else default

    prize, fee, bounty = (money(b["prize"]), money(b["fee"]), money(b["bounty"])) if b else (0.0, 0.0, 0.0)
    started = find(STARTED, "ts")
    # the prize: "received a total of ...", or the Hero line when that sentence is missing (e.g. a day-1 advance)
    cash, ticket = prize_parts(find(RECEIVED, "prize") or find(HERO_PRIZE, "prize") or "")
    re_m = REENTRIES.search(text)
    adv = ADVANCED.search(text)
    return Tournament(
        id=int(h["id"]), site="GGPoker", name=h["name"], game_type=h["game"],
        format=("satellite" if "satellite" in h["name"].lower() else "bounty" if bounty > 0 else "regular"),
        buyin_prize=prize, buyin_fee=fee, buyin_bounty=bounty, buyin_total=round(prize + fee + bounty, 2),
        players=int(find(PLAYERS, "n", 0)),
        prize_pool=money(find(POOL, "pool")),
        started_at=started.replace("/", "-") if started else None,
        finish_place=int(p) if (p := find(PLACE, "place")) else None,
        prize_won=cash, prize_is_ticket=ticket > 0, prize_ticket=ticket,
        reentries=int(re_m["n"] or re_m["n2"]) if re_m else 0,
        stage=stage_of(h["name"]),
        advanced_to=re.sub(r"(?i)^(day|stage) ?(\d+)$", lambda x: f"{x[1].capitalize()} {x[2]}", adv["day"]) if adv else None,
        advanced_chips=money(adv["chips"]) if adv else None,
    )

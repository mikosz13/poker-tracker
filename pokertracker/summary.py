"""Parser for GGPoker tournament summary files (PokerCraft export)."""
import re
from dataclasses import dataclass

from .scope import tournament_reason

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
REENTRIES = re.compile(r"You made (?P<n>\d+) re-entries")
RECEIVED = re.compile(r"received a total of \$?(?P<prize>" + AMT + r")(?P<ticket> Entry)?")


class OutOfScope(ValueError):
    """A summary of something the tracker never imports (Sit & Go, PLO, not in $ ...)."""

    def __init__(self, reason, tournament_id):
        super().__init__(f"{reason}: tournament #{tournament_id}")
        self.reason, self.tournament_id = reason, tournament_id


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
    prize_won: float       # cash, or the face value of the ticket if prize_is_ticket
    prize_is_ticket: bool
    reentries: int


def parse_summary(text: str) -> Tournament:
    first = next((l.strip() for l in text.lstrip("\ufeff").splitlines() if l.strip()), "")
    if m := FIRST_LINE.match(first):
        buyin = next((l for l in text.splitlines() if l.startswith("Buy-in:")), "")
        if reason := tournament_reason(m["name"], m["game"], buyin):
            raise OutOfScope(reason, int(m["id"]))
    h, b = HEADER.search(text), BUYIN.search(text)
    if not (h and b):
        raise ValueError("Unrecognized tournament summary format")

    def find(rx, group, default=None):
        m = rx.search(text)
        return m[group] if m else default

    prize, fee, bounty = money(b["prize"]), money(b["fee"]), money(b["bounty"])
    started = find(STARTED, "ts")
    return Tournament(
        id=int(h["id"]), site="GGPoker", name=h["name"], game_type=h["game"],
        format=("satellite" if "satellite" in h["name"].lower() else "bounty" if bounty > 0 else "regular"),
        buyin_prize=prize, buyin_fee=fee, buyin_bounty=bounty, buyin_total=round(prize + fee + bounty, 2),
        players=int(find(PLAYERS, "n", 0)),
        prize_pool=money(find(POOL, "pool")),
        started_at=started.replace("/", "-") if started else None,
        finish_place=int(p) if (p := find(PLACE, "place")) else None,
        prize_won=money(find(RECEIVED, "prize")),
        prize_is_ticket=bool(find(RECEIVED, "ticket")),
        reentries=int(find(REENTRIES, "n", 0)),
    )

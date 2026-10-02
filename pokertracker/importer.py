"""Import GGPoker hand histories and tournament summaries into the database (idempotent)."""
import json
import subprocess
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .classify import refresh_classification
from .hands import HERO, entries_from_rows, out_of_scope, parse_hands, starting_stack
from .summary import OutOfScope, Tournament, parse_summary

SITE = "GGPoker"


@dataclass
class ImportStats:
    files: int = 0
    hand_files: int = 0
    summary_files: int = 0
    hands_new: int = 0
    hands_duplicate: int = 0
    allins: int = 0
    unchanged: int = 0
    tournaments: set = field(default_factory=set)
    skipped: list = field(default_factory=list)
    ignored: dict = field(default_factory=dict)     # reason -> {tournament id, or 'cash'}: never imported

    def ignored_counts(self):
        """{reason: how many tournaments (or cash-game files)} that were left out on purpose."""
        return {reason: len(ids) for reason, ids in sorted(self.ignored.items())}

    def ignore(self, reason, key):
        self.ignored.setdefault(reason, set()).add(key)


def classify(text: str):
    for line in text.lstrip("\ufeff").splitlines():
        line = line.strip()
        if line:
            if line.startswith("Poker Hand #"):
                return "hands"
            if line.startswith("Tournament #"):
                return "summary"
            return None
    return None


def _pdf_text(path: Path) -> str:
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True,
                          text=True, check=True).stdout


SUFFIXES = {".txt", ".pdf", ".zip"}


def list_files(path):
    """Importable files under path (or the path itself), sorted."""
    path = Path(path)
    if path.is_dir():
        return sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in SUFFIXES)
    return [path] if path.is_file() else []


def read_source(f: Path):
    """Yield (label, text) for one file: a .txt, a text-layer .pdf, or every .txt inside a .zip."""
    suffix = f.suffix.lower()
    try:
        if suffix == ".txt":
            yield f.name, f.read_text(encoding="utf-8-sig")
        elif suffix == ".pdf":
            yield f.name, _pdf_text(f)
        elif suffix == ".zip":
            with zipfile.ZipFile(f) as z:
                for name in sorted(z.namelist()):
                    if name.lower().endswith(".txt"):
                        yield f"{f.name}:{name}", z.read(name).decode("utf-8-sig")
    except (OSError, zipfile.BadZipFile, subprocess.SubprocessError, UnicodeDecodeError):
        yield f.name, ""


def iter_sources(path):
    for f in list_files(path):
        yield from read_source(f)


def _fingerprint(f: Path):
    st = f.stat()
    return st.st_size, round(st.st_mtime, 3)


def changed_files(db, path):
    """Files under path that are new or changed since they were last imported."""
    return changed_files_from(db, list_files(path))


def _mark_imported(db, f: Path):
    size, mtime = _fingerprint(f)
    db.execute("INSERT INTO imported_files (path, size, mtime) VALUES (?, ?, ?) "
               "ON CONFLICT (path) DO UPDATE SET size = excluded.size, mtime = excluded.mtime",
               (str(f.resolve()), size, mtime))


# ---- row builders -----------------------------------------------------------

def _hand_row(h):
    return (SITE, h.hand_id, h.tournament_id, h.level, h.sb, h.bb, h.ante, h.played_at, h.table,
            h.max_seats, h.button, h.board, h.total_pot, h.rake, h.showdown)


def _player_rows(h):
    return [(SITE, h.hand_id, nick, seat, h.positions.get(nick), h.hole_cards.get(nick), stack,
             round(stack / h.bb, 2), round(h.net(nick), 2), nick == HERO)
            for nick, (seat, stack) in h.seats.items()]


def _action_rows(h):
    return [(SITE, h.hand_id, order, nick, street, act, amount, allin)
            for street, order, nick, act, amount, allin in h.actions]


class DbEquityCache:
    """equity_cache table behind the interface equity.pot_equities expects."""

    def __init__(self, db):
        self.db, self.mem = db, {}

    def get(self, key):
        if key in self.mem:
            return self.mem[key]
        raw = self.db.scalar("SELECT value FROM equity_cache WHERE cache_key = ?", (key,))
        if raw is None:
            return None
        self.mem[key] = tuple(tuple(x) for x in json.loads(raw))
        return self.mem[key]

    def set(self, key, value):
        self.mem[key] = value
        self.db.execute("INSERT INTO equity_cache (cache_key, value) VALUES (?, ?) "
                        "ON CONFLICT (cache_key) DO NOTHING", (key, json.dumps([list(v) for v in value])))


# ---- storage ----------------------------------------------------------------

def _store_hands(db, hands, equity=True):
    existing = set()
    for tid in {h.tournament_id for h in hands}:
        existing |= {r["hand_id"] for r in db.query(
            "SELECT hand_id FROM hands WHERE site = ? AND tournament_id = ?", (SITE, tid))}
    before = db.scalar("SELECT COUNT(*) FROM hands WHERE site = ?", (SITE,))
    seen = {}
    for h in hands:
        seen.setdefault(h.tournament_id, h)
    db.executemany(
        "INSERT INTO tournaments (site, tournament_id, name, format, buyin_total) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT (site, tournament_id) DO NOTHING",
        [(SITE, tid, h.tournament_name, "satellite" if "satellite" in h.tournament_name.lower() else None,
          h.buyin_total) for tid, h in seen.items()])
    db.executemany(
        "INSERT INTO hands (site, hand_id, tournament_id, level, small_blind, big_blind, ante, played_at, "
        "table_name, max_seats, button_seat, board, total_pot, rake, showdown) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT (site, hand_id) DO UPDATE SET button_seat = excluded.button_seat", [_hand_row(h) for h in hands])
    db.executemany(
        "INSERT INTO hand_players (site, hand_id, nick, seat, position, hole_cards, stack, stack_bb, net_won, "
        "is_hero) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT (site, hand_id, nick) DO UPDATE SET position = excluded.position",
        [r for h in hands for r in _player_rows(h)])
    db.executemany(
        "INSERT INTO actions (site, hand_id, action_order, nick, street, action_type, amount, all_in) "
        "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT (site, hand_id, action_order) DO NOTHING",
        [r for h in hands for r in _action_rows(h)])
    after = db.scalar("SELECT COUNT(*) FROM hands WHERE site = ?", (SITE,))
    new = int(after - before)
    allins, warnings = 0, []
    if equity:
        allins, warnings = _store_allins(db, [h for h in hands if h.hand_id not in existing])
    return new, len(hands) - new, allins, warnings


def _store_allins(db, hands):
    """All-in adjusted EV for hands that are new in this import (exact enumeration, see equity.py)."""
    try:
        from .equity import compute_allin, precompute, prepare_allin
    except ImportError:
        return 0, ["all-in EV skipped: numpy is not installed"]
    rows, warnings, count = [], [], 0
    cache = DbEquityCache(db)
    prepared = {}
    for h in hands:
        try:
            prepared[h.hand_id] = prepare_allin(h, hero=HERO)
        except Exception as e:
            warnings.append(f"all-in EV failed for hand {h.hand_id}: {e}")
    precompute([p for p in prepared.values() if p], cache)   # distinct matchups, spread over CPU cores
    for h in hands:
        if h.hand_id not in prepared:
            continue
        try:
            res = compute_allin(h, cache=cache, prepared=prepared[h.hand_id]) if prepared[h.hand_id] else None
        except Exception as e:                      # one odd hand must not abort the whole import
            warnings.append(f"all-in EV failed for hand {h.hand_id}: {e}")
            continue
        if not res:
            continue
        count += 1
        for p in res["players"]:
            rows.append((SITE, h.hand_id, p["nick"], p["nick"] == HERO, res["street"], res["board_at_lock"],
                         p["hole_cards"], len(res["players"]),
                         None if p["equity"] is None else round(float(p["equity"]), 6),
                         round(p["invested"], 2), round(p["collected"], 2), round(p["ev_net"], 2),
                         round(p["luck"], 2), p["result"]))
    db.executemany(
        "INSERT INTO allin_ev (site, hand_id, nick, is_hero, lock_street, board_at_lock, hole_cards, contestants, "
        "equity, invested, collected, ev_net, luck, result) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT (site, hand_id, nick) DO NOTHING", rows)
    return count, warnings


def _store_summary(db, t: Tournament):
    db.execute(
        "INSERT INTO tournaments (site, tournament_id, name, format, buyin_total, buyin_prize, buyin_fee, "
        "buyin_bounty, players, prize_pool, started_at, finish_place, prize_won, prize_is_ticket, reentries, "
        "has_summary) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT (site, tournament_id) DO UPDATE SET name = excluded.name, format = excluded.format, "
        "buyin_total = excluded.buyin_total, buyin_prize = excluded.buyin_prize, buyin_fee = excluded.buyin_fee, "
        "buyin_bounty = excluded.buyin_bounty, players = excluded.players, prize_pool = excluded.prize_pool, "
        "started_at = excluded.started_at, finish_place = excluded.finish_place, prize_won = excluded.prize_won, "
        "prize_is_ticket = excluded.prize_is_ticket, reentries = excluded.reentries, "
        "has_summary = excluded.has_summary",
        (SITE, t.id, t.name, t.format, t.buyin_total, t.buyin_prize, t.buyin_fee, t.buyin_bounty, t.players,
         t.prize_pool, t.started_at, t.finish_place, t.prize_won, t.prize_is_ticket, t.reentries, True))


def refresh_entries(db, tournament_id):
    """Recompute Hero's entries from everything stored, so files can be imported in any order."""
    rows = db.query(
        "SELECT h.hand_id, h.level, h.played_at, h.big_blind, hp.stack, hp.net_won FROM hands h "
        "JOIN hand_players hp ON hp.site = h.site AND hp.hand_id = h.hand_id "
        "WHERE h.site = ? AND h.tournament_id = ? AND hp.is_hero ORDER BY h.played_at, h.hand_id",
        (SITE, tournament_id))
    entries = entries_from_rows([(r["hand_id"], r["level"], r["played_at"], float(r["big_blind"]),
                                  float(r["stack"]), float(r["net_won"])) for r in rows])
    db.execute("DELETE FROM entries WHERE site = ? AND tournament_id = ?", (SITE, tournament_id))
    db.executemany(
        "INSERT INTO entries (site, tournament_id, entry_no, entry_level, entered_at, start_stack, "
        "start_stack_bb, starts_fresh, first_hand_id) VALUES (?,?,?,?,?,?,?,?,?)",
        [(SITE, tournament_id, e["entry_no"], e["entry_level"], e["entered_at"], e["start_stack"],
          e["start_stack_bb"], True, e["first_hand_id"]) for e in entries])


def refresh_starting_stacks(db):
    """Set tournaments.starting_stack for every name + buy-in group from Hero's entries (NULL when unknown)."""
    groups = {}
    for r in db.query("SELECT t.site, t.tournament_id, t.name, t.buyin_total, e.start_stack FROM tournaments t "
                      "LEFT JOIN entries e ON e.site = t.site AND e.tournament_id = t.tournament_id"):
        g = groups.setdefault((r["site"], r["name"], None if r["buyin_total"] is None else float(r["buyin_total"])),
                              {"ids": set(), "stacks": []})
        g["ids"].add(r["tournament_id"])
        if r["start_stack"] is not None:
            g["stacks"].append(float(r["start_stack"]))
    db.executemany("UPDATE tournaments SET starting_stack = ? WHERE site = ? AND tournament_id = ?",
                   [(starting_stack(g["stacks"]), site, tid) for (site, _, _), g in groups.items() for tid in g["ids"]])


def _import_one(db, stats, label, text, equity):
    """Import one source text; returns the tournament ids it touched."""
    stats.files += 1
    kind = classify(text or "")
    if kind == "hands":
        stats.hand_files += 1
        ignored = out_of_scope(text)
        for reason, ids in ignored.items():
            for key in ids:
                stats.ignore(reason, label if key == "cash" else key)
        hands = parse_hands(text)
        if not hands:
            if not ignored:                       # a file of only out-of-scope hands is not a problem
                stats.skipped.append(f"{label}: no hands recognised")
            return set(), set()
        new, dup, allins, warnings = _store_hands(db, hands, equity)
        stats.hands_new += new
        stats.hands_duplicate += dup
        stats.allins += allins
        stats.skipped.extend(f"{label}: {w}" for w in warnings)
        ids = {h.tournament_id for h in hands}
        stats.tournaments |= ids
        return ids, ids
    if kind == "summary":
        try:
            t = parse_summary(text)
        except OutOfScope as e:
            stats.ignore(e.reason, e.tournament_id)
            return set(), set()
        except ValueError:
            stats.skipped.append(f"{label}: unrecognised summary format")
            return set(), set()
        _store_summary(db, t)
        stats.summary_files += 1
        stats.tournaments.add(t.id)
        return set(), {t.id}
    stats.skipped.append(f"{label}: not a GGPoker hand history or summary")
    return set(), set()


def _refresh(db, hand_tids, all_tids):
    for tid in sorted(hand_tids):
        refresh_entries(db, tid)
    if hand_tids or all_tids:
        refresh_starting_stacks(db)
    for tid in sorted(all_tids):
        refresh_classification(db, SITE, tid)


def import_texts(db, items, equity=True) -> ImportStats:
    """Import already-read texts (used by tests and by anything that is not a file)."""
    stats = ImportStats()
    hand_tids, all_tids = set(), set()
    for label, text in items:
        h, a = _import_one(db, stats, label, text, equity)
        hand_tids |= h
        all_tids |= a
    _refresh(db, hand_tids, all_tids)
    db.commit()
    return stats


def import_files(db, files, equity=True, progress=None, skip_unchanged=False) -> ImportStats:
    """Import files one by one, committing after each so an interrupted import keeps what it finished.

    progress(done, total, current_name) is called after every file. With skip_unchanged, files whose size and
    modification time match the last import are skipped (that is what makes re-importing a big folder fast).
    """
    stats = ImportStats()
    files = list(files)
    todo = set(changed_files_from(db, files)) if skip_unchanged else set(files)
    for i, f in enumerate(files, 1):
        if f not in todo:
            stats.unchanged += 1
        else:
            hand_tids, all_tids = set(), set()
            for label, text in read_source(f):
                h, a = _import_one(db, stats, label, text, equity)
                hand_tids |= h
                all_tids |= a
            _refresh(db, hand_tids, all_tids)
            _mark_imported(db, f)
            db.commit()
        if progress:
            progress(i, len(files), f.name)
    return stats


def changed_files_from(db, files):
    known = {r["path"]: (int(r["size"]), float(r["mtime"])) for r in db.query("SELECT * FROM imported_files")}
    return [f for f in files if known.get(str(f.resolve())) != _fingerprint(f)]


def import_path(db, path, equity=True, progress=None, skip_unchanged=False) -> ImportStats:
    return import_files(db, list_files(path), equity, progress, skip_unchanged)

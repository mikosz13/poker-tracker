"""Schema migrations: an existing database is upgraded in place on startup, so nothing is lost (e.g. the equity cache).

schema.sql always describes the latest schema, so a new database starts at LATEST. An older database runs every
step above its stored version, in order, each one committed together with the new version number.
"""
from .hands import position_labels
from .scope import tournament_reason

LATEST = 3


def repair_positions(db):
    """Recompute hand_players.position from the seats and hands.button_seat; returns how many rows changed."""
    buttons = {(r["site"], r["hand_id"]): r["button_seat"]
               for r in db.query("SELECT site, hand_id, button_seat FROM hands WHERE button_seat IS NOT NULL")}
    seats = {}
    for r in db.query("SELECT site, hand_id, nick, seat, position FROM hand_players"):
        seats.setdefault((r["site"], r["hand_id"]), []).append(r)
    changes = []
    for key, players in seats.items():
        if key not in buttons:
            continue
        labels = position_labels([p["seat"] for p in players], buttons[key])
        changes += [(labels.get(p["seat"]), key[0], key[1], p["nick"]) for p in players
                    if labels.get(p["seat"]) != p["position"]]
    db.executemany("UPDATE hand_players SET position = ? WHERE site = ? AND hand_id = ? AND nick = ?", changes)
    return len(changes)


def _v1_button_seat(db):
    """Store the button seat and fix position names (first to act is UTG; 0.2.0 started at UTG+1 or MP)."""
    if not db.has_column("hands", "button_seat"):         # DDL may commit on its own: make a rerun safe
        db.execute("ALTER TABLE hands ADD COLUMN button_seat INTEGER")
    # The old code always found the button correctly, so its BTN label tells us the seat; no files needed.
    db.executemany("UPDATE hands SET button_seat = ? WHERE site = ? AND hand_id = ?", [
        (r["seat"], r["site"], r["hand_id"]) for r in db.query(
            "SELECT site, hand_id, seat FROM hand_players WHERE position IN ('BTN', 'BTN/SB')")])
    repair_positions(db)


def _v2_scope_and_entries(db):
    """Remove tournaments that are never analysed, recompute entries and add the data-derived starting stack.

    0.3.0 imported some Sit & Go and non-dollar tournaments whose hand format happened to parse, and flagged late
    registrations as "history incomplete" when the starting stack was not 10,000.
    """
    from .importer import refresh_entries, refresh_starting_stacks     # here, to avoid an import cycle
    if not db.has_column("tournaments", "starting_stack"):
        db.execute("ALTER TABLE tournaments ADD COLUMN starting_stack NUMERIC")
    out = [(r["site"], r["tournament_id"]) for r in db.query("SELECT site, tournament_id, name FROM tournaments")
           if tournament_reason(r["name"])]
    remove_tournaments(db, out)
    for r in db.query("SELECT DISTINCT site, tournament_id FROM hands"):
        refresh_entries(db, r["tournament_id"])
    refresh_starting_stacks(db)


def remove_tournaments(db, keys):
    """Delete every row of these (site, tournament_id) tournaments; the equity cache is shared and stays."""
    for site, tid in keys:
        hands = "(SELECT hand_id FROM hands WHERE site = ? AND tournament_id = ?)"
        for table in ("allin_ev", "actions", "hand_players"):
            db.execute(f"DELETE FROM {table} WHERE site = ? AND hand_id IN {hands}", (site, site, tid))
        for table in ("hands", "entries", "tournament_tags", "tournament_structure", "tournaments"):
            db.execute(f"DELETE FROM {table} WHERE site = ? AND tournament_id = ?", (site, tid))
    return len(keys)


def _v3_entries_found_and_shown_cards(db):
    """Record how many entries the hands show, and drop hole cards that were a single shown card.

    Before 0.5.0 a player showing one card (allowed after a fold) replaced the dealt cards with that card; the real
    cards are only in the files, so the wrong value becomes unknown until the files are read again.
    """
    from .importer import refresh_entries                               # here, to avoid an import cycle
    if not db.has_column("tournaments", "entries_found"):
        db.execute("ALTER TABLE tournaments ADD COLUMN entries_found INTEGER")
    for r in db.query("SELECT DISTINCT tournament_id FROM hands"):
        refresh_entries(db, r["tournament_id"])
    db.execute("UPDATE hand_players SET hole_cards = NULL WHERE LENGTH(hole_cards) = 2")


MIGRATIONS = {1: _v1_button_seat, 2: _v2_scope_and_entries, 3: _v3_entries_found_and_shown_cards}


# Every column added after 0.2.0. The steps below recompute data with the current importer code, which writes all of
# them, so on an old database they are added before any step runs (e.g. step 2 recomputes entries, which also sets
# entries_found from step 3).
COLUMNS = (("hands", "button_seat", "INTEGER"), ("tournaments", "starting_stack", "NUMERIC"),
           ("tournaments", "entries_found", "INTEGER"))


def add_missing_columns(db):
    for table, column, kind in COLUMNS:
        if not db.has_column(table, column):
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")


def migrate(db, fresh):
    version = db.scalar("SELECT MAX(version) FROM schema_version")
    if version is None:
        version = LATEST if fresh else 0
        db.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
        db.commit()
    if version < LATEST:
        db.backup(f"bak-v{version}")
        add_missing_columns(db)
    for v in range(version + 1, LATEST + 1):
        MIGRATIONS[v](db)
        db.execute("UPDATE schema_version SET version = ?", (v,))
        db.commit()

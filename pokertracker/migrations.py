"""Schema migrations: an existing database is upgraded in place on startup, so nothing is lost (e.g. the equity cache).

schema.sql always describes the latest schema, so a new database starts at LATEST. An older database runs every
step above its stored version, in order, each one committed together with the new version number.
"""
from .hands import position_labels

LATEST = 1


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


MIGRATIONS = {1: _v1_button_seat}


def migrate(db, fresh):
    version = db.scalar("SELECT MAX(version) FROM schema_version")
    if version is None:
        version = LATEST if fresh else 0
        db.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
        db.commit()
    if version < LATEST:
        db.backup(f"bak-v{version}")
    for v in range(version + 1, LATEST + 1):
        MIGRATIONS[v](db)
        db.execute("UPDATE schema_version SET version = ?", (v,))
        db.commit()

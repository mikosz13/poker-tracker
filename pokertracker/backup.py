"""Backup and restore of the SQLite database (docs/tasks/export.md).

A backup is a full copy made with SQLite's online backup (safe while the app runs), named with the date. A restore
first checks the file is a Poker Tracker database this version can open (an older one is upgraded after the
restore, a newer one is refused), saves the current database next to itself, then copies the backup in. PostgreSQL
users back up with their own tools (pg_dump).
"""
import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

from .migrations import LATEST


class BackupError(Exception):
    """code: not_sqlite | not_found | not_ours | too_new | unreadable"""

    def __init__(self, code, detail=""):
        super().__init__(detail or code)
        self.code = code


def supported(db_url):
    """Backup and restore work on an SQLite file; PostgreSQL users use pg_dump (the app does not offer them)."""
    return db_url.startswith("sqlite:///") and not db_url.endswith(":memory:")


def _sqlite_path(db_url):
    if not supported(db_url):
        raise BackupError("not_sqlite")
    return Path(db_url[len("sqlite:///"):])


def _free(folder, stem, suffix):
    path = folder / f"{stem}{suffix}"
    k = 2
    while path.exists():
        path = folder / f"{stem} ({k}){suffix}"
        k += 1
    return path


def _copy(source, target, uri=False):
    """SQLite's online backup from source into target; both connections closed after (Windows locks open files)."""
    with closing(sqlite3.connect(source, uri=uri)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
        dst.execute("PRAGMA journal_mode=DELETE")                  # one self-contained file (the app's own is WAL)


def make_backup(db_url, folder=None):
    """Copy the database into folder (Downloads, else the home folder) as poker-tracker-YYYY-MM-DD.db."""
    source = _sqlite_path(db_url)
    home = Path.home()
    folder = Path(folder) if folder else (home / "Downloads" if (home / "Downloads").is_dir() else home)
    target = _free(folder, f"poker-tracker-{date.today().isoformat()}", ".db")
    _copy(source, target)
    return str(target)


def check_backup(path):
    """What a backup holds (schema version, tournaments, hands, last hand), or BackupError if it is not one."""
    p = Path(path).expanduser()
    if not p.is_file():
        raise BackupError("not_found")
    try:
        with closing(sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True)) as c:
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            if not {"tournaments", "hands", "hand_players", "schema_version"} <= tables:
                raise BackupError("not_ours")
            version = c.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] or 0
            info = {"path": str(p), "version": int(version),
                    "tournaments": c.execute("SELECT COUNT(*) FROM tournaments").fetchone()[0],
                    "hands": c.execute("SELECT COUNT(*) FROM hands").fetchone()[0],
                    "last_hand": str(c.execute("SELECT MAX(played_at) FROM hands").fetchone()[0] or "")[:16] or None}
    except sqlite3.DatabaseError as e:                   # not an SQLite file at all
        raise BackupError("unreadable", str(e)) from e
    if info["version"] > LATEST:
        raise BackupError("too_new", f"schema {info['version']} > {LATEST}")
    return info


def restore(db_url, path):
    """Replace the database with a backup; the current one is kept next to it first. Returns (info, saved copy)."""
    from .db import Database
    info = check_backup(path)
    current = _sqlite_path(db_url)
    saved = _free(current.parent, f"{current.name}.before-restore-{datetime.now():%Y%m%d-%H%M%S}", "")
    _copy(current, saved)
    _copy(Path(path).expanduser().resolve().as_uri() + "?mode=ro", current, uri=True)
    with Database(db_url) as db:                          # an older backup is upgraded to this version
        db.init_schema()
    return info, str(saved)

"""Thin database layer: PostgreSQL (psycopg 3) or SQLite behind one interface.

SQL in this project is written with '?' placeholders and standard syntax
(ON CONFLICT ... DO NOTHING/UPDATE), so the same statements run on both.
"""
import os
import sqlite3
import sys
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parent / "sql"


def data_dir() -> Path:
    """Per-user application data folder (where the app keeps its database)."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "PokerTracker"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home())) / "PokerTracker"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "pokertracker"
    base.mkdir(parents=True, exist_ok=True)
    return base


def default_url() -> str:
    return f"sqlite:///{data_dir() / 'pokertracker.db'}"


class Database:
    def __init__(self, url: str | None = None):
        self.url = url or os.environ.get("DATABASE_URL") or default_url()
        if self.url.startswith(("postgres://", "postgresql://")):
            try:
                import psycopg
            except ImportError as e:
                raise RuntimeError("PostgreSQL support needs: pip install 'psycopg[binary]'") from e
            self.kind = "postgres"
            self.conn = psycopg.connect(self.url)
        elif self.url.startswith("sqlite:///"):
            self.kind = "sqlite"
            self.conn = sqlite3.connect(self.url[len("sqlite:///"):])
        else:
            raise ValueError(f"Unsupported database URL: {self.url!r}")

    def _q(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.kind == "postgres" else sql

    def script(self, sql: str):
        if self.kind == "sqlite":
            self.conn.executescript(sql)
        else:
            self.conn.cursor().execute(sql)   # no parameters -> multiple statements allowed
        self.conn.commit()

    def init_schema(self):
        """Create missing tables, upgrade an older database in place, then (re)create the views."""
        from .migrations import migrate
        fresh = not self.has_table("hands")
        self.script((SQL_DIR / "schema.sql").read_text())
        migrate(self, fresh)
        self.script((SQL_DIR / "views.sql").read_text())

    def has_table(self, name: str) -> bool:
        if self.kind == "sqlite":
            sql = "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = ?"
        else:
            sql = ("SELECT COUNT(*) FROM information_schema.tables "
                   "WHERE table_schema = current_schema() AND table_name = ?")
        return bool(self.scalar(sql, (name,)))

    def has_column(self, table: str, column: str) -> bool:
        if self.kind == "sqlite":
            return any(r["name"] == column for r in self.query(f"PRAGMA table_info({table})"))
        return bool(self.scalar("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = current_schema() "
                                "AND table_name = ? AND column_name = ?", (table, column)))

    def backup(self, suffix: str):
        """Copy a file-based SQLite database next to itself (no-op otherwise); returns the backup path."""
        path = self.url[len("sqlite:///"):] if self.kind == "sqlite" else ""
        if not path or path == ":memory:":
            return None
        target = f"{path}.{suffix}"
        with sqlite3.connect(target) as dst:
            self.conn.backup(dst)
        dst.close()
        return target

    def execute(self, sql: str, params=()):
        self.conn.cursor().execute(self._q(sql), params)

    def executemany(self, sql: str, rows):
        rows = list(rows)
        if rows:
            self.conn.cursor().executemany(self._q(sql), rows)

    def query(self, sql: str, params=()):
        cur = self.conn.cursor()
        cur.execute(self._q(sql), params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def scalar(self, sql: str, params=()):
        rows = self.query(sql, params)
        return next(iter(rows[0].values())) if rows else None

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

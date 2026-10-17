"""Smoke test of the PACKAGED app (the PyInstaller build), driven through its own command line and local API.

    python tools/smoke_packaged.py dist/PokerTracker.app/Contents/MacOS/PokerTracker WORK_DIR
    python tools/smoke_packaged.py dist/PokerTracker/PokerTracker.exe WORK_DIR

Every run uses a fresh profile inside WORK_DIR (HOME and APPDATA point there), so it never touches a real database.
Checks: a clean start creates the database at the latest schema; the made-up demo files import with all-in EV
(parallel equity inside the frozen binary) and a second import adds nothing; the main screens answer; the sample-data
switch; backup, check and restore; an old (0.2.0) database is upgraded on start. Run from the repository root (it
uses the repository's Python to write the old database and read the results).
"""
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pokertracker.migrations import LATEST          # noqa: E402

BIN, WORK = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def scalar(db, sql):
    with closing(sqlite3.connect(db)) as c:
        return c.execute(sql).fetchone()[0]


def free_port():
    with closing(socket.socket()) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class App:
    """The packaged binary running `serve` on a free port, with its own profile."""

    def __init__(self, home, db=None):
        self.env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home), "APPDATA": str(home / "AppData"),
                    "POKERTRACKER_EXPORT_DIR": str(home / "exports-out")}
        (home / "AppData").mkdir(parents=True, exist_ok=True)
        (home / "exports-out").mkdir(exist_ok=True)
        port = free_port()
        args = [str(BIN)] + (["--db", f"sqlite:///{db}"] if db else []) + ["serve", "--port", str(port)]
        self.proc = subprocess.Popen(args, env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.url = f"http://127.0.0.1:{port}/"
        for _ in range(240):                              # a packaged build needs a few seconds to unpack
            try:
                page = self.get("", raw=True)
                break
            except OSError:
                if self.proc.poll() is not None:
                    raise RuntimeError(f"the packaged app exited with {self.proc.returncode}")
                time.sleep(0.5)
        else:
            raise RuntimeError("the packaged app did not start its server")
        self.token = page.split('const TOKEN = "', 1)[1].split('"', 1)[0]

    def get(self, path, raw=False):
        with urllib.request.urlopen(self.url + path, timeout=300) as r:
            body = r.read().decode("utf-8")
        return body if raw else json.loads(body)

    def post(self, path, body):
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "X-Token": self.token})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read())

    def import_and_wait(self, folder, timeout=900):
        status, r = self.post("api/import", {"path": str(folder)})
        if status not in (200, 202):
            raise RuntimeError(f"import refused: {r}")
        end = time.time() + timeout
        while time.time() < end:
            st = self.get("api/status")
            if not st.get("running"):
                return st
            time.sleep(1)
        raise RuntimeError("import did not finish")

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(15)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(15)


def profile(name):
    home = WORK / name
    shutil.rmtree(home, ignore_errors=True)
    home.mkdir(parents=True)
    return home


def default_db(home):
    mac = home / "Library" / "Application Support" / "PokerTracker" / "pokertracker.db"
    win = home / "AppData" / "PokerTracker" / "pokertracker.db"
    linux = home / ".local" / "share" / "pokertracker" / "pokertracker.db"
    return next((p for p in (mac, win, linux) if p.exists()), None)


# 1. a clean profile: the binary writes the demo files, the app creates its database where it keeps it
home = profile("clean")
folder = WORK / "demo-files"
shutil.rmtree(folder, ignore_errors=True)
subprocess.run([str(BIN), "demo-files", str(folder)], check=True, timeout=300)
files = sorted(folder.glob("*.txt"))
check("command line in the packaged binary: demo files written", len(files) == 80, f"{len(files)} files")
app = App(home)
try:
    db = default_db(home)
    d = app.get("api/dashboard")["dashboard"]
    check("clean profile: starts with an empty dashboard", d["tournaments"] == 0 and d["hands"] == 0)
    check(f"clean profile: database created at schema {LATEST}",
          db and scalar(db, "SELECT MAX(version) FROM schema_version") == LATEST, str(db))

    # 2. import the folder, then the same files again
    t = time.time()
    st = app.import_and_wait(folder)
    counts = (scalar(db, "SELECT COUNT(*) FROM tournaments"), scalar(db, "SELECT COUNT(*) FROM hands"),
              scalar(db, "SELECT COUNT(*) FROM allin_ev"))
    check("import: finished without an error or a skipped file", not st.get("error") and not (st.get("result") or {}).get("skipped"),
          f"{round(time.time() - t)} s, tournaments {counts[0]}, hands {counts[1]}, all-in EV rows {counts[2]}")
    check("import: 40 tournaments, hands and all-in EV (parallel equity in the frozen binary)",
          counts[0] == 40 and counts[1] > 1000 and counts[2] > 0)
    st = app.import_and_wait(folder)
    again = (scalar(db, "SELECT COUNT(*) FROM tournaments"), scalar(db, "SELECT COUNT(*) FROM hands"),
             scalar(db, "SELECT COUNT(*) FROM allin_ev"))
    check("second import: nothing new", (st.get("result") or {}).get("hands_new") == 0 and again == counts, str(again))

    # 3. the main screens answer
    d = app.get("api/dashboard?period=max")["dashboard"]
    check("dashboard: the whole history", d["tournaments"] == 40 and d["hands"] == counts[1], f"ROI {round(d['roi_pct'] or 0)} %")
    a = app.get("api/analysis")
    check("analysis: preflop and showdown lines", a["preflop"]["total"]["hands"] == counts[1] and a["showdown"]["hands"] > 0)
    s = app.get("api/search?cards=AA,KK")
    check("hands: search", s["count"] > 0, f"{s['count']} hands with AA or KK")
    tid = app.get("api/tournaments")[0]["tournament_id"]
    check("tournament screen", app.get(f"api/tournament/{tid}")["result"] is not None)

    # 4. backup, check, restore
    status, made = app.post("api/backup", {})
    status2, info = app.post("api/backup/check", {"path": made.get("path", "")})
    check("backup: a copy that checks out", status == 200 and status2 == 200 and info["tournaments"] == 40, made.get("path", made))
    status, done = app.post("api/backup/restore", {"path": made.get("path", "")})
    check("restore: the database replaced, the old one kept", status == 200 and Path(done["saved"]).exists()
          and scalar(db, "SELECT COUNT(*) FROM hands") == counts[1])

    # 5. sample data: a separate database, imports refused meanwhile, then back
    status, r = app.post("api/demo", {"on": True})
    demo = app.get("api/dashboard?period=max")["dashboard"]
    refused = app.post("api/import", {"path": str(folder)})
    check("sample data: switched, a separate database, imports refused",
          status == 200 and r["demo"] and demo["tournaments"] == 40 and refused[0] == 409
          and (db.parent / "demo.db").exists())
    status, r = app.post("api/demo", {"on": False})
    check("sample data: back to the player's data", status == 200 and not r["demo"])
finally:
    app.stop()

# 6. an old database (0.2.0) is upgraded when the app opens it
home = profile("upgrade")
old = home / "old.db"
from tests.test_migrations import schema_0_2_0          # noqa: E402
with closing(sqlite3.connect(old)) as c:
    c.executescript(schema_0_2_0())
    c.execute("INSERT INTO tournaments (site, tournament_id, name) VALUES ('GGPoker', 900005, 'Bounty Hunters')")
    c.commit()
app = App(home, old)
try:
    app.get("api/dashboard")
    check(f"upgrade: a 0.2.0 database opens at schema {LATEST}", scalar(old, "SELECT MAX(version) FROM schema_version") == LATEST)
finally:
    app.stop()

print(f"\n{sum(results)} of {len(results)} passed", flush=True)
sys.exit(0 if all(results) else 1)

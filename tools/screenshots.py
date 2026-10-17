"""README screenshots, made again from the made-up demo data (never from a player's database):

    python tools/screenshots.py [--chrome PATH] [--theme light|dark]

Imports the demo files into a temporary database, serves the app on it and captures a few screens with headless
Chrome into docs/img/.
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pokertracker.db import Database                       # noqa: E402
from pokertracker.demo import build_demo                   # noqa: E402
from pokertracker.server import serve_in_background, set_setting   # noqa: E402

CHROME = ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "google-chrome", "chromium", "chrome")


def find_chrome(given):
    for c in ([given] if given else CHROME):
        if Path(c).exists() or shutil.which(c):
            return c
    sys.exit("Chrome not found; pass --chrome PATH")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--chrome")
    p.add_argument("--theme", default="light", choices=("light", "dark"))
    args = p.parse_args()
    chrome = find_chrome(args.chrome)
    out = ROOT / "docs" / "img"
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        url = f"sqlite:///{Path(tmp) / 'demo.db'}"
        with Database(url) as db:
            db.init_schema()
            build_demo(db)
            set_setting(db, "lang", "en")
            set_setting(db, "theme", args.theme)
            db.commit()
            # the tournament with the most all-ins (stack chart with markers) and its biggest all-in (replayer)
            tid = db.scalar("SELECT h.tournament_id FROM allin_ev e JOIN hands h ON h.site = e.site AND h.hand_id = e.hand_id "
                            "WHERE e.is_hero GROUP BY h.tournament_id ORDER BY COUNT(*) DESC, h.tournament_id LIMIT 1")
            hand = db.scalar("SELECT e.hand_id FROM allin_ev e JOIN hands h ON h.site = e.site AND h.hand_id = e.hand_id "
                             "WHERE e.is_hero AND h.tournament_id = ? ORDER BY ABS(e.ev_net) DESC LIMIT 1", (tid,))
        server, base = serve_in_background(url)
        shots = [("dashboard", "#/", 1300), ("analysis", "#/analysis", 1150), ("hands", "#/hands", 900),
                 ("tournament", f"#/t/{tid}", 1100), ("replayer", f"#/hand/{hand}", 800)]
        try:
            for name, route, height in shots:
                target = out / f"{name}.png"
                subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--lang=en-US",
                                f"--user-data-dir={Path(tmp) / 'chrome'}", f"--window-size=1100,{height}",
                                "--force-device-scale-factor=1.5", "--virtual-time-budget=15000",
                                f"--screenshot={target}", base + route],
                               check=True, capture_output=True, timeout=120)
                print(f"{target.relative_to(ROOT)}  ({route})")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":                       # the guard: equity runs in worker processes
    main()

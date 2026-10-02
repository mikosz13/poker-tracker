# PyInstaller build description for the desktop app: `pyinstaller --noconfirm packaging/pokertracker.spec`
# Produces dist/PokerTracker.app on macOS and dist/PokerTracker/PokerTracker.exe on Windows.
import sys
from pathlib import Path

root = Path(SPECPATH).parent

a = Analysis(
    [str(root / "packaging" / "launch.py")],
    pathex=[str(root)],
    datas=[
        (str(root / "pokertracker" / "sql"), "pokertracker/sql"),
        (str(root / "pokertracker" / "web"), "pokertracker/web"),
    ],
    hiddenimports=["webview"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PokerTracker", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="PokerTracker")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="PokerTracker.app",
        bundle_identifier="io.github.pokertracker",
        info_plist={"NSHighResolutionCapable": True, "CFBundleShortVersionString": "0.2.0"},
    )

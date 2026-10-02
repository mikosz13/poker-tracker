# Installing Poker Tracker

Free desktop app for GGPoker tournament players. Your data never leaves your computer.

## macOS (Apple Silicon)

1. Download `PokerTracker-macOS.zip` from the latest release and unzip it.
2. Move `PokerTracker.app` to Applications.
3. First start: right-click the app and choose **Open**, then **Open** again. The app is not signed with a paid
   Apple developer certificate, so macOS asks once. If it is still blocked: System Settings → Privacy & Security →
   **Open Anyway**.

## Windows 10 / 11

1. Download `PokerTracker-Windows.zip` from the latest release and unzip it anywhere.
2. Start `PokerTracker.exe` inside the folder.
3. If SmartScreen appears: **More info** → **Run anyway** (the app is not code-signed).
4. If the window stays blank, install the free *Microsoft Edge WebView2 Runtime* from Microsoft.

## First use

1. Export your hand histories and tournament summaries from PokerCraft into one folder.
2. In the app open **Import**, paste that folder and press **Import**. The first import takes longest, because
   every all-in is computed exactly.
3. Tick **Watch this folder** and new exports are picked up automatically while the app is open.
4. After each session: check **Dashboard → Last session**, open a tournament, replay the hands that hurt.

## Where is my data?

- macOS: `~/Library/Application Support/PokerTracker/pokertracker.db`
- Windows: `%APPDATA%\PokerTracker\pokertracker.db`

To start from scratch, quit the app and delete that file. To uninstall, delete the app and that folder.

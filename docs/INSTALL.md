# Installing Poker Tracker

Free desktop app for GGPoker tournament players. Your data never leaves your computer.

## macOS (Apple Silicon)

1. Download `PokerTracker-macOS.zip` from the latest release and unzip it.
2. Move `PokerTracker.app` to Applications.
3. First start: macOS blocks it once, because the app is not signed with a paid Apple developer certificate. The
   message says Apple could not verify that "PokerTracker" is free of malware. Click **Done** (not "Move to Bin"),
   then open **System Settings → Privacy & Security**, scroll down to **Security**, click **Open Anyway** next to
   PokerTracker and confirm with your password or Touch ID. Start the app again and choose **Open Anyway** once more.
   macOS remembers this, so it happens only once.
   - On older macOS versions (before 15) right-clicking the app and choosing **Open**, then **Open** again, also works.
   - Alternative in Terminal, if you moved the app to Applications:
     `xattr -dr com.apple.quarantine /Applications/PokerTracker.app`

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

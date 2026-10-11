# Installing Poker Tracker

Free desktop app for GGPoker tournament players. Your data never leaves your computer.

## Jak zacząć (PL)

1. **Pobierz aplikację** z GitHuba, zakładka [Releases](https://github.com/mikosz13/poker-tracker/releases):
   `PokerTracker-macOS.zip` (Mac) albo `PokerTracker-Windows.zip`. Rozpakuj.
2. **Uruchom ją.**
   - Mac: przenieś do Aplikacji i otwórz. Jak macOS zablokuje, kliknij **Gotowe**, wejdź w
     **Ustawienia → Prywatność i ochrona → Otwórz mimo to**.
   - Windows: **Więcej informacji → Uruchom mimo to**.
3. **Zrób jeden folder na eksporty**, np. `Dokumenty/PokerCraft`.
4. **W PokerCraft pobieraj tam historie rąk i podsumowania turniejów.** Zipy też mogą być.
5. **W aplikacji wejdź w Import**, wklej ścieżkę do folderu, zaznacz **„Watch this folder”** i kliknij **Import**.
6. **Gotowe.** Po każdej sesji wrzucasz nowe pliki do tego folderu, a aplikacja sama je wciąga, gdy jest włączona.
7. **Patrzysz:** Dashboard (jak poszła sesja), Analysis (co poprawić), replayer (ręce do obejrzenia).

## Getting started (EN)

1. **Download the app** from GitHub → [Releases](https://github.com/mikosz13/poker-tracker/releases):
   `PokerTracker-macOS.zip` or `PokerTracker-Windows.zip`. Unzip.
2. **Start it.**
   - Mac: move it to Applications and open it. If macOS blocks it, click **Done**, then
     **System Settings → Privacy & Security → Open Anyway**.
   - Windows: **More info → Run anyway**.
3. **Make one folder for your exports**, e.g. `Documents/PokerCraft`.
4. **In PokerCraft, download your hand histories and tournament summaries into it.** Zips are fine.
5. **In the app, open Import**, paste the folder path, tick **"Watch this folder"** and click **Import**.
6. **Done.** After every session, drop the new files into that folder; the app picks them up while it is open.
7. **Then look at:** Dashboard (how the session went), Analysis (what to fix), the replayer (hands to review).

---

If something does not work, the details are below.

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

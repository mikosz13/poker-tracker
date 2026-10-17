# Frequently asked questions

## Where is my data, and does anything leave my computer? {#data}

Everything stays with you, in one database file:

- macOS: `~/Library/Application Support/PokerTracker/pokertracker.db`
- Windows: `%APPDATA%\PokerTracker\pokertracker.db`

The app sends no data anywhere: there is no account, no sign-in, no usage statistics and no ads. Its window talks only to a small server on your own computer (`127.0.0.1`), which the network cannot reach. It does not change or copy your PokerCraft files; it reads them from the folder you choose. Only you need the internet: to download exports from PokerCraft and new versions of the app, and when you click a link to GitHub yourself.

## How do I back up and move my data to another computer? {#move}

1. On the old computer: **Settings → Backup → Make a backup**. A dated file appears in Downloads, e.g. `poker-tracker-2026-10-17.db`.
2. Move that file to the new computer (USB stick, cloud drive, an e-mail to yourself).
3. On the new computer install the app, open **Settings → Restore from a backup**, choose the file and confirm. The app checks the file, keeps the current database next to it and loads the backup; an older backup is upgraded straight away.

You can also import the same PokerCraft files on the new computer and get the same result, but PokerCraft offers hand histories of the last 90 days only, so the backup is the safer way.

## How do I update the app? {#update}

Download the new version from [Releases on GitHub](https://github.com/mikosz13/poker-tracker/releases) and replace the old one with it (macOS: drag it to Applications and choose "Replace"; Windows: unzip it over the old folder). Your data is kept apart, in the folder above, so it stays. On its first start the new version upgrades the database by itself and keeps a copy from before the upgrade next to it (`pokertracker.db.bak-v…`). What changed is in [About](#/help/about/changes).

## How do I delete my data? {#delete}

- **One tournament**: on its page, **Ignore this tournament**. It disappears from every result and does not come back with the next import; you can restore it in Settings.
- **Everything**: close the app and delete the data folder (paths above). That removes the database, the copies from before upgrades and the sample data (`demo.db`). The app starts with an empty database next time.
- Deleting the app alone does not delete your data, and deleting the data does not touch your PokerCraft files.

## Does the app work without the internet? {#offline}

Yes, fully. Everything it shows, this Help included, is inside the app; it loads nothing from the web. Without the internet you only cannot download new exports from PokerCraft.

## Does the app know my GGPoker password? {#account}

No. It does not connect to GGPoker or PokerCraft; it only reads the files you download and choose yourself.

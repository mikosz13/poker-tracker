# Task (sketch): Export and backup

Queue: after hand search, before Help.

## What
- **Ręka do schowka**: a button in the replayer copies the hand as plain text for forums and chats: blinds and ante,
  positions instead of seat names, stacks in BB, Hero's cards, actions per street, board, result. Opponents stay
  anonymous (position only).
- **CSV**: the tournament list (as shown, with the active filters) and the hand-search results. UTF-8 with BOM for
  Excel, a header row, dot or comma decimals following the language.
- **Backup / restore** (SQLite): a copy of the database named with the date (`poker-tracker-2026-10-13.db`), a restore
  that checks the file is a Poker Tracker database of a supported schema version (migrates it if older) and keeps
  the current one as a backup before replacing it.

## Checks
- Tests: text export of a hand with each street and an all-in; CSV quoting (names with commas and quotes); backup and
  restore round trip, refusing a foreign file.
- PostgreSQL users: backup is not offered (a note points to pg_dump).

# Check: importing a 668-file folder against the full database (13.10.2026)

Question: a test import of a folder with 668 PokerCraft files gave 135 tournaments and 6,157 hands, while the app on
Mik's database showed 188 tournaments and 11,446 hands. Is anything lost on import?

Answer: no. The folder is an older export (files from 1.09 to 2.10, the last hand 3.10 00:42), a sample of the history,
not all of it. Compared on copies, read-only (Mik's database and `bak-v6` unchanged, checksums the same before and
after):

- **Hands**: up to the same moment Mik's database holds exactly 6,157 hands. No hand is in the test and missing from
  the database, nor the other way round.
- **Tournaments**: all 135 tournaments of the test are in the database.
- **Summaries**: 4 tournaments had no summary in the test; they are the summaries of 2.10 that Mik exported again later.
  In the database only the Day 2 (#317182864) is still without a summary.
- **Left out**: 7 tournaments in the test against 2 on the ignore list in the database. They are the same tournaments
  out of scope (2 × PLO, 4 × Sit & Go, 1 × in yen) and the database does not hold them either; older versions skipped
  them without writing them to the list of left-out tournaments, which exists since 11.10.
- **188 tournaments in the app**: the database holds 198 tournament rows; 10 flights of one multi-day event count as
  that event (Day 2), so 198 − 10 = 188, with 11,446 hands.
- **Day 2 flights**: Mik played 30 Opener flights; 10 advanced and all 10 are joined to the Day 2 (24 entries, 14 of
  them re-entries), no advancing flight is outside the event, and the re-entries of every flight's summary match the
  entries found in its hands.

The same folder was also the import scenario of the packaged-app smoke test for 0.8.0 (78 s locally, 89 s on the CI
build; a second import of the same files added nothing).

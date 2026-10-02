# Task: Position names

Context: read CLAUDE.md, pokertracker/hands.py (assign_positions), pokertracker/importer.py, pokertracker/db.py,
pokertracker/sql/schema.sql and pokertracker/sql/views.sql first.

## 1. Correct labels
- The first player to act preflop is always UTG.
- Players before the button, by table size:
  - 9: UTG, UTG+1, MP, LJ, HJ, CO
  - 8: UTG, UTG+1, LJ, HJ, CO
  - 7: UTG, LJ, HJ, CO
  - 6: UTG, HJ, CO
  - 5: UTG, CO
  - 4: UTG
- Then BTN, SB, BB. Heads-up: BTN/SB and BB.
- Fix in hands.assign_positions, with tests for 2 to 9 players.

## 2. Repair existing databases without deleting them
- Existing databases must be fixable in place, so the equity cache is not lost.
- Store the button seat in `hands`.
- Simple schema migration mechanism: schema version stored in the database, ALTER TABLE on startup.
- A command or option that, when the same files are imported again, updates the positions of hands that are
  already in the database.

## 3. Everything shows the new names
- Per-position statistics and the replayer show the new names afterwards.

## 4. Done when
- Plan presented before coding.
- Tests pass, including the label tests for 2 to 9 players and the migration of an old database.
- CHANGELOG.md (Unreleased) updated; summary at the end.

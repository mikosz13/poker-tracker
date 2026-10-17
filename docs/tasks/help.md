# Task (sketch): Help

Queue: after export, before 1.0. Sketch by Claude (14.10.2026), Mik: "zrób szkic i dalej".

## Goal
A player who never used a tracker installs the app, exports from PokerCraft and understands every number without
asking. Short, plain texts (the luck page is the model), PL and EN, inside the app (offline), no external links needed.

## Where
- A **Pomoc / Help** page (`#/help`) reached from a "?" in the header, with a table of contents and anchors.
- Small **"?" links** next to screens and hard numbers open the matching section (`#/help/analysis`, …).
- "Jak liczymy szczęście" stays its own page; Help links to it.

## Sections
1. **Pierwsze kroki**: what to download from PokerCraft (hand histories and tournament summaries, about 10 tournaments
   at a time, the last 90 days only), how to import (a folder, a watched folder, "read everything again"), what is
   left out and why (cash, Sit & Go, PLO, other currencies, freerolls, unrecognised summaries) and the ignore list.
2. **Pulpit**: periods, the last session and its screen, the four tiles, Worth knowing.
3. **Turnieje**: the list and its filters, a tournament page (place, prize, ROI), late registration and re-entries,
   the stack chart in BB or chips with all-in markers, multi-day events and Day 2 (also without a summary, and
   `pokertracker provisional`).
4. **Ręce i replayer**: the filters, next / previous across results, copying a hand.
5. **Analiza**: every definition (VPIP, PFR, RFI, open shove, 3-bet, fold to 3-bet, bb/100 by EV) with its
   denominator, n and grey cells, the trend rule, leaks and strengths (q ≤ 0.05, "closest to the line"), the
   starting-hand grid against folding, the showdown lines.
6. **Finanse**: ROI with tickets at face value and "w tym gotówka", the 95 % interval and the verdicts, ITM only where
   the files say it, top 10 % / 15 % of the field, late registration against the start.
7. **Kopia zapasowa i eksport**: backup, restore, CSV, text for forums.
8. **Problemy**: macOS "Otwórz mimo to", Windows SmartScreen, where the database lives, a summary PokerCraft does not
   offer, numbers that changed after a re-import.
9. **Słowniczek**: short entries for the poker words kept in English (from docs/glossary-pl.md).

## Rules
- Every number the app shows has its definition in Help, in the same words as its tooltip.
- No more than a screen per section at 1100 px; PL and EN; both themes; 800 px without overflow.
- Tests: every section exists in both languages, every "?" link points at an existing anchor, no hard-coded text.

## Help v2 (Mik, 17.10.2026)

Keeps everything of #54 and adds what Mik had decided earlier:

- **Subpages with a side menu**: Pierwsze kroki (files and import, the dashboard, tournaments, hands and the replayer,
  backup and export), Jak liczymy (Analysis, Money, and "Jak liczymy szczęście", which `#/luck` now opens),
  Słowniczek, Problemy i rozwiązania, Najczęstsze pytania, O aplikacji. The nine sections of v1 keep their anchors on
  these pages; nothing is dropped.
- **Content as Markdown per language**: `pokertracker/web/help/<pl|en>/<page>.md`, served by `/help/<lang>/<page>.md`
  and drawn by a small renderer (headings with `{#anchor}`, paragraphs, lists, bold, italic, code, links;
  `{{luck}}`, `{{version}}`, `{{changes}}` filled in by the app). External links open outside the app window.
- **Search** over all pages, cut at their `##` sections, without case or Polish letters ("otworz" finds "Otwórz").
- **FAQ**: where the data is and that nothing leaves the computer, backup and moving to another computer, updating,
  deleting data, working offline, the GGPoker password.
- **O aplikacji**: the version from one source (`pokertracker/__init__.py`; `pyproject.toml` reads it, the
  PyInstaller spec too), this version's section of CHANGELOG.md (bundled in the app), GitHub, how to report a bug,
  the MIT license.
- **"?" links** map the old section keys to `#/help/<page>/<anchor>`.
- Tests: every page in both languages, the same anchors in PL and EN, every "?" and internal link points at an
  existing page and anchor, the v1 sections and analysis definitions are there, FAQ and About hold their topics, the
  server serves only the known pages, the version has one source.

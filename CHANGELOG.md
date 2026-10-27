# Changelog

## Unreleased

## 0.8.0 (2026-10-27)
- **Upgrade from 0.7.0:** on the first start the database goes from schema 5 to 8 (a copy from before the upgrade is
  kept next to it, `pokertracker.db.bak-v5`) and switches to WAL mode: while the app runs, two helper files sit next
  to it (`pokertracker.db-wal`, `pokertracker.db-shm`). No need to import the files again.
- README, Known limitations: PokerCraft writes times in the time zone of the moment of download, so exports from
  both sides of a daylight-saving change can be about an hour apart (checked on Mik's exports of 27.10).
- README screenshots made again on the sample data: the starting-hand grid with picked hands, the dashboard's
  scrolling recent tournaments, the Back button and Help in the menu (`tools/screenshots.py`: the dashboard on 30 days,
  Hands with a few picked hands).
- Back: a "←" button at the start of the menu (and Alt+← or Cmd+[) goes to the previous screen and scrolls it to where
  it was, e.g. from Help back to the hand in the replayer. Greyed out on the first screen. In the replayer the plain
  arrows still step through the hand.
- Tournaments: a search by name, as you type, with the other filters. Every word must be in the name, without case or
  Polish letters ("bounty 21" finds "Bounty Hunters $21.60"); a tournament number finds that tournament. The summary
  above the list and "Export CSV" follow the search; it stays when you open a tournament and come back.
- Hands → Starting hands: always open, in a box of its own under the filters. Square cells of one size, so rows and
  columns line up; pairs, suited and offsuit hands tinted as in a range chart, with a legend; the clear and group
  buttons in a column next to the grid (under it in a narrow window); the picked hands listed above it.
- Fix: while an import was writing, the app could not read the database ("database is locked"), so the import's
  progress and screens opened meanwhile failed. The SQLite database now runs in WAL mode (reads never wait for a
  write) and a write waits up to 30 s for another; backups and the copies made before an upgrade stay one plain file.
- Hands → Starting hands: "Clear the hands" and quick groups above the grid (pairs, suited, offsuit, broadway; a group
  already picked in full is dropped); the picked hands are listed next to their count.
- Replayer: "Normal" plays a little slower (1.2 s a step instead of 0.9 s).
- Dashboard → Recent tournaments: every tournament of the period (up to 100) in a scrolling list with a fixed header,
  instead of the last five. The CLI dashboard report keeps its last ten.
- Menu: "How luck works" at the top is now "Help" (Pomoc), opening Help; it stays highlighted on every Help page.
  How luck is calculated is in Help → How we count.
- Hand search on PostgreSQL: a test that every filter finds the same hands, totals and order as on SQLite (runs in
  CI); `tools/bench_hand_search.py --db postgresql://… --explain` measures it there too (in its own schema, dropped
  afterwards) and prints how each query is read. 500,000 hands: slowest 91 ms on PostgreSQL 16, 129 ms on SQLite.
- Security: `/api/settings` and the Import screen no longer show the database password; a PostgreSQL URL is shown
  as `user:***@host` (also `password=***` in its parameters). SQLite paths are shown as before.
- Help → How we count → Sessions: "after a hard moment" and the comparison at the same stack and stage (#61).
- README: "Known limitations" (what it reads, installing, what it can and cannot know, databases, out of scope).
- Help v2: subpages with a side menu (Getting started, How we count with "How luck is calculated", Glossary, Problems
  and solutions, FAQ, About), a search over all of Help (without case or Polish letters), the text as Markdown files
  per language (`pokertracker/web/help/`). New FAQ: where the data is and that nothing leaves the computer, backup and
  moving to another computer, updating, deleting data, working offline. About: the version, this version's changes,
  GitHub, how to report a bug, the MIT license. The version has one source, `pokertracker/__init__.py`
  (`pyproject.toml` reads it). "?" links open the right subpage and section; `#/luck` opens its section in Help.
- Settings → Backup with PostgreSQL: no backup or restore buttons, only a note to use pg_dump (as planned in
  docs/tasks/export.md; before, the button was there and answered with an error).
- Docs: `docs/checks/import-668-files.md`, the check that a 668-file test import lost nothing (13.10).
- CI: tests also on Python 3.14 (Linux, macOS, Windows); release builds stay on 3.12.
- License: MIT (`LICENSE`), linked from the README.
- Analysis → Sessions, "After a hard moment": your hands on every table within 15 minutes after an all-in lost as a
  favourite (60 %+ equity), a pot lost by 20 BB or more, or a bust, against the calm hands. All Sessions comparisons
  now hold the stage of the tournament fixed as well as the stack (blind levels 1–5, 6–10, 11–15, 16+): after a bust
  the next hands are often the early levels of a new entry, which looked like tilt and was not.
- README: the Variance and Sessions tabs.
- Analysis → Sessions: VPIP, PFR, bb/100 by EV and ROI by the number of tournaments played at once (1 / 2 / 3+), the
  time of day and the time since the session started (first hour, 1–2 h, 2–3 h, 3 h+; a session ends after a break of
  more than 3 hours, as for "Last session"). Each group is compared with the rest of the hands at the same stack depth
  (a short stack alone plays fewer hands), the uncertainty is counted by session (hands of one evening are not
  independent; at least 300 hands from 5 sessions), and the comparisons are corrected together (Benjamini-Hochberg);
  only differences with q ≤ 0.05 are listed. ROI per group with its interval, not judged. Times are the GG files' own:
  the player's local time (the file names are UTC, checked 17.10.2026). `/api/context`.
- Analysis → Variance: 10,000 runs of the next 100 / 500 / 1,000 tournaments drawn from your own (bootstrap; every
  tournament as a result in buy-ins, re-entries and tickets included). The typical result with the half and 9-in-10
  bands, the chance of a loss, the largest drawdown, and how many buy-ins keep the risk of a bigger drawdown under 5 %
  (in $ at the average buy-in of the last 30 tournaments; at a losing ROI it says no roll is enough). A "what if my ROI
  were" slider (−20 … +50 %) scales every prize by one factor, so tournaments without a prize still cost their buy-in.
  The average buy-in by week or month. Fixed seed; a clear note under 100 tournaments; a day without its summary and
  no prize typed in is left out. `/api/variance?n=&roi=`.
- README for players first: what the app answers, screenshots on the made-up sample data (dashboard, tournament,
  Analysis, Hands, the replayer), getting started with the sample-data button; outdated lines fixed (tickets in ROI, the dashboard
  since v3). `python tools/screenshots.py` makes the screenshots again (headless Chrome, temporary database).
- Replayer: Hero's hole cards sit side by side above Hero's box again instead of one above the other over the
  replay buttons. The Dashboard's tile row shared Hero's seat class and turned the seat into a four-column grid; the
  tiles have their own class now.
- Release builds test the packaged app before uploading it (`tools/smoke_packaged.py`, macOS and Windows): a clean
  profile, the demo files imported twice (with all-in EV, so parallel equity inside the frozen binary), the main
  screens, backup and restore, sample data, and the upgrade of a 0.2.0 database. The packaged binary also runs the
  command line when given arguments (`PokerTracker serve --port 8790`, `PokerTracker import FOLDER`); new command
  `serve`: the app's server without a window.
- Sample data: "Look around on sample data" on the empty Dashboard (and in Settings) opens the app on 40 made-up
  tournaments (Bounty Hunters, a daily, a turbo, satellites with tickets, late registrations and re-entries, about
  2,500 hands) in a separate `demo.db` next to your database, which is never touched. A bar on every screen says it
  is sample data and goes back in one click; importing and backups are off meanwhile. The files are made by
  `pokertracker/demo.py` in GG's own format and go through the normal importer; older than two weeks, they are made
  again, so the recent periods are never empty. `python -m pokertracker demo-files FOLDER` writes them out (screenshots,
  tests).
- Help: one page (the "?" in the header) with getting started, the dashboard, tournaments, hands and the replayer,
  every Analysis definition, money (ROI with tickets, the interval, ITM), backup and export, problems and a glossary,
  in Polish and English. A "?" next to each screen's title opens its section.
- Settings → Backup: "Make a backup" copies the whole database into Downloads (`poker-tracker-2026-10-14.db`, never
  overwritten). "Restore from a backup" checks the file first (a Poker Tracker database this version can open; an older
  one is upgraded, a newer one or a foreign file is refused), keeps the current database next to itself, then replaces
  it. In the app window a system file dialog picks the file. PostgreSQL users back up with pg_dump.
- Export: "Copy the hand" in the replayer and "Copy the result" on a tournament give plain text for forums and chats
  (positions instead of opponent ids, stacks in BB, every street and the board, shown cards, the result and the result
  by EV; a provisional result says so). "Export CSV" on the tournament list and in Hands saves what is shown (with the
  filters) into Downloads: UTF-8 for Excel, decimal commas and ';' in Polish, a "provisional" column; never overwrites.
- New tab Hands: filter every hand by period, buy-in, format, positions, starting hands (click or drag across the
  13×13 grid), stack, preflop action (the Analysis v2 definitions), all-in, showdown and result (actual or by EV);
  newest first with totals and "show more". A hand opens in the replayer with next / previous across the results and
  a way back. Leak and strength cards, the "closest to the line" list and the starting-hand grid link to their hands.
- Hand search, data and API: every Hero hand gets a row in `hand_facts` (position, hand type, stack in BB, the
  preflop action by the Analysis v2 definitions, all-in, showdown, result and result by EV), rebuilt after each import
  and filled by database schema 8. `/api/search` filters by period, buy-in, format, position, hands, stack, preflop
  action, all-in, showdown and result, newest first with paging. On 500,000 synthetic hands every tested combination
  answers in under 0.15 s (`python tools/bench_hand_search.py`).
- Dashboard v3: about 1.5 screens instead of 3. The last session as a short card with a link to its own screen (the
  full session and the hands to review); four tiles (profit, ROI, tournaments, luck) and one line of smaller numbers;
  one chart with a $ / BB switch; "Worth knowing" (best tournament, tickets, whether your play changed beyond noise);
  five recent tournaments. Starting hands and positions live in Analysis; late registration against the start moved
  to Money (whole history).
- Tournament stack chart: every all-in is a dot (green won, red lost, grey split on the real board), with a legend.
  The tooltip adds Hero's cards against the opponents', the street, Hero's equity when the money went in, the result
  and the luck in BB; a click opens the hand in the replayer, as for any point.
- Analysis v2, stage 2 (Leaks and strengths):
  - A leak or strength card only at q <= 0.05 after the correction for every spot; the "possible" level is gone.
    When no leak passes, a message and a folded list of the five spots closest to the line (spot, hands, result, q).
  - Cards show a mini-trend (the cumulative result by EV over time), the hands behind a leak with links to the
    replayer, and "a fact (by EV)" for the all-in EV card.
  - Folding to 3-bets is compared with your own history (the last 30 days against the rest, 30+ spots a side) instead
    of a 70 % reference range.
  - Starting hands: a 13×13 grid of the result per hand by EV against folding the same hand; fewer than 30 hands
    greyed, n and the meaning of the colour in the tooltip, a click lists the hands with links to the replayer.
- Test: importing a Day 2 summary after a provisional amount leaves one record with the amount from the file.
- The ROI tile in Analysis says in its tooltip why it has no interval and links to the 95 % interval in Money;
  "How luck works" explains the interval and the verdicts built on it. Money keeps the interval.
- Session review: the biggest pots won and lost (and bad beats / suckouts) name their tournament, like busts.
- Analysis → Overview: the ROI tile shows the number only (the 95 % bar was squeezed and unclear there; Money keeps
  the interval next to its verdicts).
- ITM only: one ITM tile (reached the paid places), counted where the files say it, in tournaments without bounties
  and satellites. "Cashed (place or bounty)" is gone from the dashboard, Analysis, the tables in Money, late reg vs
  start and the session sentence; bounty money still counts in profit and ROI. The tooltip and "How luck works" say
  why bounty tournaments are left out.
- The VPIP, PFR and 3-bet tiles show the rate only; n is in the tooltip (tables keep it).
- Analysis → Overview: cumulative result in BB over your hands in four lines: total, with showdown, without showdown
  (uncalled shoves included) and the total by all-in EV (dashed). A called preflop all-in is a showdown; an uncalled
  shove is a steal. The tooltip gives the hand number, date and all four values; "How luck works" explains the split.
- Analysis v2, stage 1:
  - Overview: ROI with its 95 % interval bar, ITM / cashed, VPIP, PFR and 3-bet with n, all-in EV, the luck badge
    and "Where you finish". A trend arrow compares the last 30 days with the rest of the history, only with 500+
    hands and 100+ opportunities on each side and a change beyond noise (|z| ≥ 2.5), at most one at a time.
  - New tab Preflop: per position VPIP, PFR, RFI, 3-bet, fold to 3-bet and bb/100 by EV, with a total row.
  - New tab Stack depth: the same per stack band plus open shove, each band out of its own RFI chances.
  - Every rate is counted over its opportunities as PokerTracker 4 does (RFI without limpers, 3-bet with squeezes,
    fold to 3-bet after Hero's own non-all-in open), shows n, is greyed under 30 opportunities and has its
    definition in a tooltip; tests on GGPoker hands.
  - A single all-in raise is a 3-bet chance only when Hero can raise over it (an all-in for less than Hero has is an
    isolation chance; one Hero can only call is not): on Mik's data 3-bet 14.6 % (n = 4,728) instead of 14.1 % (4,878).
- Tournament stack chart: a BB / Chips switch (remembered). In chips a deep run shows how the stack grew even while it
  fell in big blinds (Mik's Day 2: 977k → peak 9.3M → bust from 5.6M, which is 279 → 11 BB). The tooltip shows both,
  with the big blind; the line under the chart follows the unit.
- Dashboard periods: Last session · 24 h · 7 days · 14 days · 30 days, and under "More" 3 months, 6 months, All
  history and a custom range (from–to, whole days, remembered). The heading shows the dates the period covers and links
  to the tournament list with the same period; the list takes its bounds from the app, so both count the same
  tournaments. An empty period says when you last played and offers the last session. "3 days" is gone; a period
  remembered by 0.7 ("1 week", "2 weeks", "4 weeks") becomes 7, 14 or 30 days.
- A Day 2 without a summary (PokerCraft offered Mik's Day 2 hands but no Day 2 summary): the day is recognised from the
  name in its hands ("[Day 2]") and joins its flights as one event. The event counts the cost of every flight and the
  cash known so far; the place is unknown and the Day 2 prize is not counted, and that is flagged on the tournament,
  in the list (*) and next to ROI. The Day 2 no longer counts as an entry from the start (it starts with chips
  carried over), and its flights no longer say "Day 2 not played" after 7 days. Database schema 7.
- `pokertracker provisional <tournament id> <amount>`: the cash won on a day whose summary is missing, counted and
  flagged as provisional until the summary is imported, which replaces it (an exception to "nothing typed in", for a
  summary GGPoker does not offer; no form in the app).
- Multi-day events: every day-1 flight that went through joins its Day 2 (and later days) as one tournament under its
  last day: the cost of all flights (buy-in × entries), the knockout cash of every flight plus the later days' prize,
  and one final place. Flights are matched by name without the day marker and "GTD" (GGPoker renamed "$1M GTD" to
  "$1M" mid-series), played before the Day 2 and not taken by another one. A flight in an event says "counted in …"
  with a link; an advance whose Day 2 has not been imported shows "Advanced to Day 2" for 7 days, then "Advanced,
  Day 2 not played". Database schema 6 groups what is stored.
- Consistency:
  - VPIP and PFR leave out hands without a preflop decision (a walk in the big blind, an all-in forced by the blind or
    ante), as PokerTracker 4 leaves out walks; checking the big blind is not VPIP, completing the small blind is, and a
    limp-raise counts for both (tests on GGPoker hands).
  - Number format: rates (VPIP, PFR, ITM, cashed, top % of the field, …) with one decimal and n; ROI without
    decimals everywhere. Rows and tiles with fewer than 10 tournaments or 30 hands are greyed, with a tooltip.
  - Best and worst starting hand and position are ranked by the result with all-in luck removed (EV).
  - Dashboard: late registration and positions are folded under "More"; by buy-in and by category moved to
    Analysis → Money (with a link); "Tickets" shows the period, with a link to the whole history in Money.
- The count column says "Count" in English (it said "Tournaments"); Polish keeps "Turnieje".

## 0.7.0 (2026-10-11)
- **Upgrade:** the database goes from schema 3 to 5 on first start (a backup is made next to it first). Then run
  Import once with "Re-read every file": multi-day tournaments get their knockout cash and re-entries, and freerolls
  leave the database.
- Tables say "Tournaments" instead of "n", with a tooltip on what is counted (for categories: a tournament counts
  under each of its labels, so the numbers add up to more than the total).
- Places in the field apart for entries from the start and late registrations: with a late registration, players
  who busted before Hero sat down count in the field, so the share looks better than it is. "Where you finish" shows
  both, with the average player's line only for entries from the start; the top 10% / 15% tiles show both under the
  total, and every place figure explains it in a tooltip. Money's bootstrap reads tournaments in a fixed order, so the
  overall interval and the groups' intervals come from the same resampling.
- ITM is shown only where the files can tell it: tournaments without bounties and satellites (a ticket counts).
  In bounty tournaments the summary gives only the total and hand histories hold no bounty payouts, so a cash there
  can be knockouts alone: the app shows "Cashed (place or bounty)" with an explanation, and tables show "Cashed".
  New facts instead of an ITM estimate: "Top 10% / Top 15% of the field" (place / players) with a 95% bootstrap
  interval on the dashboard and in Money, and a chart of where you finish (top 10%, 10–25%, 25–50%, 50–100%) against
  an average player in Analysis, Overview. "How luck works" explains it. On Mik's data the old "ITM 29.6%" was
  mostly knockout-only cashes: ITM without bounties 2 of 12, top 10% of the field 14% (95%: 9–19%).
- Tickets count in ROI at face value, on both sides: a satellite returns the seat's value, and a tournament entered
  with a ticket costs its full buy-in, so the total matches the cash that moved. Profit and ROI on the dashboard and in
  Money include tickets, with "incl. cash" under them; Money's verdicts use the ROI with tickets. A won seat shows as
  "Won ticket $500" with a ticket icon, the satellite's page and the session summary say "Satellite won: a ticket to
  …", and a "Tickets" box on the dashboard lists every ticket with its status: used (with a link to the tournament it
  was probably used in) or not used yet (its value apart: not real money yet). A tournament probably entered with a
  ticket is marked "Ticket entry" (information only). Satellites are recognised by name ("Satellite", "MEGA",
  "Super Satellite", "Sat", "Step N", "Qualifier" … "to …") or by a ticket worth something; schema 5 turns stored
  "MEGA to" satellites (stored as regular) into satellites with their target.
- Multi-day tournaments (e.g. "$5 Ocean KO Opener [Stage 1]"): going through to Day 2 shows as "Advanced to Day 2
  (20,801 chips)" instead of a place, with its own icon, and in the last session's summary. Fixes: the knockout cash of
  a day-1 advance ("$0 Entry$7.02") was lost, and re-entries written as "You have re-entered N times" were not
  counted, so day-1 cost and return were wrong (on Mik's data: $37.92 cash and $70 of re-entries missing). A prize
  with cash and a ticket counts both. A later day (Day 2, Final Day) with a $0 buy-in is never a freeroll: it joins its
  day 1 as one tournament (cost paid on day 1, cash of every day, place of the last day, in the money only from a day
  that paid). A later day's first stack is carried chips: it is not used as a starting stack or for late reg vs start.
  Database schema 4 keeps a ticket's face value apart from cash; read the summaries again ("Re-read every file") so
  existing day-1 tournaments get the fixes.
- Control over what is imported. "Import" first lists the tournaments in the new or changed files (date, name,
  buy-in, hands, whether there is a summary), all ticked; ones the scope rules leave out are greyed with the reason.
  Unticked tournaments go on a lasting ignore list: their data is removed and they do not come back in later imports.
  The watched folder still imports by itself and skips ignored tournaments; afterwards a notice on every screen offers
  "Review" with the same list. A tournament's page has "Ignore this tournament". ⚙ Settings (next to the theme
  switch) lists ignored tournaments with "Restore" (it comes back at the next import of its files: the app remembers
  which files held each tournament) and, read-only, the tournaments the rules left out.
- Freerolls and promotions are never imported: a summary whose buy-in adds up to $0 (e.g. the Bounty Hunters
  Series Cash Drop) leaves the whole tournament out, together with any of its hands imported before; its hands stay out
  in later imports too. A ticket entry is never a freeroll: GGPoker writes it with the full buy-in. A summary that
  cannot be read leaves its tournament out the same way, with a safety fuse: when more than 3 summaries in one import
  (or more than 20 % of them) cannot be read, nothing is removed and the import warns that GGPoker may have changed its
  file format. Tournaments known only from hand histories stay. The import report (CLI and Import screen) names the
  files of each reason. `pokertracker scope-review <folder>` shows, without changing anything, what the rules would
  remove from a database, with the amounts on each summary, and which tournaments were probably entered with a ticket.
- Translated the rest of the app: tournament tags as readable labels ("Micro stakes (up to $5.50)",
  "Players: 1,000+", "Satellite to …"), the strongest showdown hand by name in Polish ("strit do asa", "full: asy na
  króle"), and the import's messages about skipped files (the import now reports a code per file; the CLI keeps
  English text).
- The app speaks Polish: a PL | EN switch in the top right corner, starting in the system language and remembered,
  switching at once (the replayer stays on the same step). Every text goes through translation files shared by the
  page and the server (session summary, tips, money facts), with Polish plural forms (1 turniej, 2 turnieje,
  5 turniejów), a decimal comma and non-breaking thousands (2 445,05 $), dates as 11.10.2026 and a 24 h clock. Poker
  jargon (positions, actions, VPIP, all-in…) stays English, as agreed in docs/glossary-pl.md. The CLI HTML reports stay
  English. Tests check that both languages have the same keys and placeholders and that the page has no hard-coded
  text.
- Light and dark theme: a switch next to the language one. Without a choice the app follows the system theme; a
  chosen theme is remembered and applied from the first paint.
- Layout: long table headers wrap instead of widening the table, the dashboard's three boxes go to two columns in a
  narrow window, and the replayer's all-in equity and luck sit on two lines so they no longer run under a bet.
- Dashboard: the last session's tournament list scrolls inside its box (about 8 rows, the column header stays visible)
  instead of growing the page, with "All tournaments →" opening the tournament list for the dashboard's period. The
  tournament list has a period filter.
- Analysis has tabs (Overview, Leaks & strengths, Money). The new Money tab shows ROI with a 95 % bootstrap interval
  for each buy-in tier and format, first entries against re-entries (what re-entries cost and returned, and the average
  starting stack of each), and each group's share of spend and of the result. All groups are judged together like the
  leaks (Benjamini-Hochberg); only results beyond chance get a verdict and a plain fact, otherwise "too little data".

## 0.6.0 (2026-10-11)
- docs/INSTALL.md starts with a seven-step "Getting started" in English and Polish (download, start, one export
  folder, import with "Watch this folder", done); README links to it.
- Last session on the dashboard tells what happened at a glance:
  - a summary sentence (result, all-in luck, busts and the bust worth a look),
  - the session's luck badge,
  - VPIP, PFR and bb/100 compared with your usual play (flagged only beyond chance),
  - short numbers (time played, most tournaments at once, knockouts, re-entries and their cost, best finish),
  - "Hands to review": every bust with both hands and your equity, bad beats and suckouts, and the biggest pots won
    and lost, each opening the replayer.
- Fix: a tournament played alongside a long one could fall out of the last session; the gap is now measured from the
  earliest start in the session so far.
- The tournament list (and the dashboard's last session) loads in about 0.1 s instead of 0.7 s: knockouts are counted
  once for all tournaments instead of once per tournament.
- The app window can be made no narrower than 800 px: the app is designed for a desktop window (the HTML
  reports from the command line stay phone friendly).
- New "Analysis" view over the whole history, with built-in tips: overview, leaks, strengths, and money and variance.
  Leaks are measured against a baseline (a big blind call compared with folding in the same spot, folding to 3-bets as
  a frequency after your own open), never as raw sums. A finding is shown only when it stands out from chance.
  Every finding shows its sample, a plain-words tip and the 5 worst hands. Results are EV-adjusted (all-in EV instead of the actual
  result in all-in hands); folding means losing exactly the blind and ante posted in that hand; all checked spots are
  corrected together for multiple comparisons (Benjamini-Hochberg: "likely" at q <= 5 %, "possible" at q <= 20 %); the
  ROI comes with a 95 % bootstrap interval over tournaments.

## 0.5.2 (2026-10-11)
- Luck badge: all-ins drawing dead (equity 0) or locked (equity 1) add no variance, now covered by tests; when a period
  has only such all-ins the badge no longer claims "1 in 2 players".
- Tournament list fits the window: long tournament names wrap and dates are short ("Oct 10"), so the Luck BB column is no
  longer cut off; on a phone the buy-in and KO columns are hidden and place and profit are shortened.

## 0.5.1 (2026-10-04)
- Luck badge says in plain words how rare the result is for a player with average luck ("a run this bad or worse
  happens to about 1 in 6 players"), from the normal distribution. Luck is measured in big blinds, now covered by a test.
- Strongest and weakest position are chosen among the positions outside the blinds; the small and big blind are shown
  on their own with a note that the blinds lose money for almost every player.
- Best and worst starting hand: a note that with this many hands a result depends mostly on a few big pots.

## 0.5.0 (2026-10-03)
- Fix: a database still on schema 1 (0.3.0) failed to upgrade, because step 2 used a column that only step 3 added.
  All columns are now added before the upgrade steps run. The whole upgrade from 0.2.0 is tested on SQLite and PostgreSQL.
- docs/INSTALL.md: first start on current macOS ("Open Anyway" in Privacy & Security).
- CI and release workflows use the current action versions (Node.js 24).
- Dashboard period: 24 h, 3 days, 1, 2 or 4 weeks, 3 or 6 months, or max. Every number, chart and table on the dashboard
  uses it ("Last session" does not); the choice is remembered.
- Cash profit and result/luck charts on a date axis, with labelled values and a tooltip per tournament.
- ITM as a percentage on the dashboard and in the buy-in, late-reg and category tables.
- Luck badge (Very lucky … Worst run, or No all-ins): total all-in luck compared with how much it could swing by chance
  (z-score); "How luck works" explains it.
- Best and worst starting hand (e.g. ATo, Q9o) and strongest and weakest position on a small table diagram, ranked
  only with at least 30 hands and always shown with the number of hands; heads-up (BTN/SB) is shown on its own.
- Tournament page: the stack in BB is a time chart with annotations where each entry starts (late reg or re-entry, level,
  stack in BB; the full starting stack in the tooltip) and a mark where the stack hit zero. Clicking it replays the hand.
- Position diagram on the dashboard goes clockwise from the big blind, the way the action moves (as in the replayer).
- Fix: a page that finished loading after you had already moved on (e.g. the dashboard) no longer replaces the page
  you opened.
- Late registration vs start leaves out tournaments whose summary reports more entries than the hands show, with a
  footnote count.
- Fix: a player showing one card after folding no longer replaces the dealt cards (16 of Hero's hands were affected).
  Database upgrade (schema 3) turns such cards into unknown; re-reading the files restores them.

## 0.4.0 (2026-10-03)
- Only No-Limit Hold'em tournaments in dollars are imported. Sit & Go (AoF, FlipNGo ...), PLO/Omaha and other games,
  tournaments in other currencies (e.g. Zodiac in ¥) and cash-game hands are never imported; the import result (CLI and
  app) counts them by reason instead of reporting "unrecognised summary format".
- No more "history incomplete" flag: entries always come from the hands (cost and ROI still from the summary). 0.3.0
  flagged late registrations whenever the starting stack was not 10,000.
- The starting stack is learned from the data: the most common first-hand stack of entries for the same tournament
  name and buy-in, shown in the tournament details and reports, or "unknown".
- Database upgrade (schema 2, automatic, backup first): removes out-of-scope tournaments imported by 0.3.0, recomputes
  entries and starting stacks; the equity cache is kept.

## 0.3.0 (2026-10-03)
- Position names fixed: the first player to act is always UTG (0.2.0 started at UTG+1 on 8-handed tables and at MP
  on 7-handed ones). Per-position statistics, reports and the replayer use the new names.
- Existing databases are upgraded in place on startup (schema version stored in the database). The first upgrade
  stores the button seat and recomputes positions from data already in the database, keeping the equity cache;
  a SQLite database is copied to `<name>.bak-v0` first. Re-importing files also refreshes positions of hands that
  are already stored.
- Replayer v2: oval table with seats rotated so Hero sits at the bottom, cards, bets in front of players, dealer
  button, all-in badges and equity at the all-in moment; autoplay (3 speeds), space = play/pause, Home/End, and an
  action log grouped by street where clicking a line jumps to that step. Light/dark theme, works down to 380 px.
- Replayer starts at the first decision: antes and blinds are already in the pot instead of being steps. Uncalled
  bets are shown being returned, so the pot that is left equals the total pot paid out.
- Replayer names opponents by position (UTG ... BB, heads-up BTN/SB and BB) instead of their hashed IDs, on the
  table and in the log; Hero stays "Hero" with the position as a small label. No database changes.
- Replayer: when the betting closes with a player all-in, the cards shown at showdown are face up from that moment,
  together with the equities, instead of only at the end.
- Replayer: after an all-in the equity of every player is recomputed exactly on the flop, turn and river (main pot),
  like on GGPoker. Luck still uses the equity at the all-in moment; "How luck works" says so.
- Four-colour deck everywhere cards are shown (app and HTML report): spades black, hearts red, diamonds blue,
  clubs green, so flush draws are visible at a glance. A "4-colour deck" switch under the replayer turns the app back to
  classic red/black; the choice is remembered in the database.
- Tests close their in-memory databases (no more ResourceWarnings on macOS Python 3.12).
- README: the "what it is not" list no longer says there is no replayer.
- docs/CHECKPOINT.md: results and feedback from the first run on a real Mac.

## 0.2.0
- Desktop app (`python -m pokertracker app`): dashboard with last session, tournament list with filters,
  tournament details, built-in hand replayer, import screen, "How luck works".
- Background import with progress; already-imported files are skipped; optional folder watching.
- Knockout counts (shared knockouts reported separately).
- Parallel precompute of exact all-in equities across CPU cores.
- Results by buy-in and by position on the dashboard.
- CI on Linux/macOS/Windows plus PostgreSQL 16; release workflow building macOS and Windows apps.

## 0.1.0
- Parsers, importer, portable SQL schema, exact all-in EV, classification, tournament report, HTML dashboard.

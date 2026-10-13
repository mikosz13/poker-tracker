# Changelog

## Unreleased
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

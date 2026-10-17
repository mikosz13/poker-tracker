# Getting started

## Files and import {#import}

The app reads two kinds of files from **PokerCraft** (GGPoker): **hand histories** and **tournament summaries**, as .txt or .zip (a PDF with a text layer works too). PokerCraft lets you download about ten tournaments at a time, and hand histories only from the last 90 days, so import after every session.

In **Import** choose the folder with the files: a preview lists the tournaments, untick any you do not want, then import. With "Watch this folder" new exports come in on their own while the app is open. Importing the same files again changes nothing; "Re-read every file" rebuilds everything from the files (only needed after an update).

Left out, with the reason shown: cash games, Sit & Go, PLO, tournaments in other currencies, freerolls and promotions ($0 buy-in), and summaries the app does not recognise (a safety catch for a change in GG's format). Tournaments you ignore yourself can be brought back in Settings.

**Sample data**: a button on the empty Dashboard (and in Settings) opens the app on 40 made-up tournaments in a separate database, `demo.db`, next to yours. Your database is not touched; importing and backups are off meanwhile, and the bar at the top takes you back to your data in one click.

## Dashboard {#dashboard}

At the top, your **last session**: tournaments that ran with gaps under three hours. "Session details" opens its screen: luck in all-ins, the session against your usual play, busts, bad beats and the biggest pots to review.

Below, a **period**: the last session, 24 hours, 7, 14 or 30 days, or under "More" 3 or 6 months, all history and your own dates. Four tiles: profit (tickets at face value, the cash part under it), ROI, tournaments and luck. One chart switches between profit in $ and the result in BB with and without all-in luck. "Worth knowing" names the best tournament, the tickets won and whether your play changed beyond noise.

## Tournaments {#tournaments}

The list filters by period, buy-in, format and entry (from the start or late). A tournament page shows the place, prize, cost and ROI, every entry with its level and starting stack, and a warning when the files show fewer entries than the summary.

The **stack chart** switches between big blinds and chips (a deep run can grow in chips while it falls in BB). Every all-in is a dot: green won, red lost, grey split; its tooltip shows the cards, your equity and the luck. A click opens the hand.

**Multi-day events**: every day-1 flight that went through joins its Day 2 as one tournament (the cost of all flights, one final place). When PokerCraft offers the Day 2 hands but no summary, the event counts what is known and is flagged; `pokertracker provisional <id> <amount>` counts a prize you type in until the summary comes and replaces it.

## Hands and the replayer {#hands}

**Hands** finds hands by period, buy-in, format, position, starting hands (click or drag across the grid), stack in BB, preflop action, all-in, showdown and result (actual or by EV). The preflop actions are the Analysis definitions, so "3-bet" finds exactly the hands Analysis counts.

A click opens the **replayer**: step through the hand, play it, see the equity at each all-in. Under it, the previous and next result of your search. "Copy the hand" gives a text for forums: positions instead of opponents' names, stacks in BB, every street, the result.

## Backup and export {#backup}

**Settings → Backup**: "Make a backup" saves the whole database into Downloads with the date. "Restore from a backup" checks the file first, keeps the current database next to itself, then replaces it; an older backup is upgraded.

**Export CSV** on the tournament list and in Hands saves what is shown into Downloads, for Excel. "Copy the result" and "Copy the hand" give plain text. A provisional prize is marked everywhere.

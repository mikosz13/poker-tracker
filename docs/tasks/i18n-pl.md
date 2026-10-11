# Task: Polish language (PL | EN)

To be done after Money (#20) and before Analysis v2. Decisions by Mik (2026-10-11).

## 1. Feature
- A PL | EN switch in the top right corner of the app. Default: the system language; the choice is remembered.
- Switching works immediately, without a restart.

## 2. Technical
- Every UI text goes through keys in translation files (e.g. `pokertracker/web/i18n/en.json` and `pl.json`),
  falling back to English when a key is missing.
- Texts generated in Python (facts, tips, verdicts, session summaries) are translated too: the API returns a key with
  parameters, or accepts the language.
- Tests: both files have the same set of keys; the UI has no hard-coded texts.
- In Polish, numbers use a decimal comma (1,5 BB) and dates look like 11.10.2026.
- The HTML reports from the CLI stay in English for now.

## 3. Translation rules (the most important part)
- Translate only what sounds natural in Polish. Poker jargon stays in English, because that is how Polish players
  talk.
- Stays in English: positions (UTG, MP, LJ, HJ, CO, BTN, SB, BB), big blind, small blind, ante, all-in, VPIP, PFR, RFI,
  3-bet, 4-bet, c-bet, fold, call, raise, check, bet, preflop, flop, turn, river, showdown, equity, EV, ROI, ITM,
  buy-in, re-entry, late reg, bounty, knockout (KO), bad beat, suckout, heads-up, open shove, re-shove, stack, Hero.
- Translated: tournament, hand, session, pot, luck, result, profit, loss, ticket, satellite, period, settings, import,
  "too little data", likely / possible, buttons and screen descriptions.
- Playing-style terms: the English term with the Polish one in brackets or in a tooltip, e.g. "Loose (luźny)",
  "Tight (ciasny)", "Passive (pasywny)", "Aggressive (agresywny)", "Leak (wyciek)", "Tilt".

## 4. Order
1. `docs/glossary-pl.md`: every term with its decision (stays / translated / term + brackets) and example sentences from
   several screens (Dashboard, Analysis, Last session, "How luck works"). Approved by Mik on 2026-10-11.
2. Implementation in a PR, checked visually in both languages (Polish texts are longer; nothing may be cut off at
   800 px).

-- Analytics views (plain views, portable). Drop in reverse dependency order, create in order.
DROP VIEW IF EXISTS hero_knockouts;
DROP VIEW IF EXISTS tag_results;
DROP VIEW IF EXISTS tournament_luck;
DROP VIEW IF EXISTS hero_allins;
DROP VIEW IF EXISTS format_results;
DROP VIEW IF EXISTS hero_tournament_stats;
DROP VIEW IF EXISTS hero_stack_depth_stats;
DROP VIEW IF EXISTS hero_position_stats;
DROP VIEW IF EXISTS tournament_results;
DROP VIEW IF EXISTS hero_hands;

-- One row per hand Hero was dealt into, with VPIP / PFR flags and result in big blinds.
-- decided: Hero had a preflop decision. Not in a walk (everyone folded to Hero's big blind) or when the blind or ante
-- put Hero all-in; such hands are left out of the VPIP / PFR denominator, as in PokerTracker 4.
-- VPIP: a call, bet or raise preflop (a small blind completing counts; a big blind checking does not).
-- PFR: a raise preflop (a limp-raise counts for both).
-- adj_bb: the result with all-in luck removed (the all-in EV in all-in hands), used to rank hands and positions.
CREATE VIEW hero_hands AS
SELECT h.site, h.hand_id, h.tournament_id, h.level, h.played_at, h.big_blind,
       hp.position, hp.stack_bb, hp.net_won,
       hp.net_won * 1.0 / h.big_blind AS net_bb,
       COALESCE((SELECT ae.ev_net FROM allin_ev ae WHERE ae.site = h.site AND ae.hand_id = h.hand_id AND ae.is_hero),
                hp.net_won) * 1.0 / h.big_blind AS adj_bb,
       CASE WHEN EXISTS (
            SELECT 1 FROM actions a
            WHERE a.site = h.site AND a.hand_id = h.hand_id AND a.nick = hp.nick
              AND a.street = 'preflop' AND a.action_type IN ('folds', 'checks', 'calls', 'raises', 'bets')
       ) THEN 1 ELSE 0 END AS decided,
       CASE WHEN EXISTS (
            SELECT 1 FROM actions a
            WHERE a.site = h.site AND a.hand_id = h.hand_id AND a.nick = hp.nick
              AND a.street = 'preflop' AND a.action_type IN ('calls', 'raises', 'bets')
       ) THEN 1 ELSE 0 END AS vpip,
       CASE WHEN EXISTS (
            SELECT 1 FROM actions a
            WHERE a.site = h.site AND a.hand_id = h.hand_id AND a.nick = hp.nick
              AND a.street = 'preflop' AND a.action_type = 'raises'
       ) THEN 1 ELSE 0 END AS pfr
FROM hands h
JOIN hand_players hp ON hp.site = h.site AND hp.hand_id = h.hand_id
WHERE hp.is_hero;

-- One row per tournament with a summary. A tournament played over several days is one row, under its last day: the
-- cost of every day-1 flight that went through (buy-in x entries), the cash and tickets of every day, the last day's
-- place. Cashed only on a day that paid: going through to the next day is not cashing by itself.
-- Tickets count at face value on both sides: a satellite returns the ticket's value, the tournament entered with it
-- costs its full buy-in, so the result over both equals the cash that moved. profit and roi_pct include tickets;
-- cash_profit and roi_cash_pct are the cash part.
-- A later day can come without a summary (PokerCraft does not always offer one): the event still counts, with the
-- cash the player typed in for that day (provisional_prize) or none. summary_missing and provisional flag it.
CREATE VIEW tournament_results AS
WITH ev AS (   -- a multi-day event (flights that went through, Day 2, ...) summed under its last day
    SELECT site, event_id,
           SUM(CASE WHEN COALESCE(stage, 1) > 1 THEN 0 ELSE buyin_total * (1 + COALESCE(reentries, 0)) END) AS cost,
           SUM(CASE WHEN has_summary THEN prize_won ELSE COALESCE(provisional_prize, 0) END) AS cash,
           SUM(COALESCE(prize_ticket, 0)) AS ticket, SUM(COALESCE(reentries, 0)) AS reentries,
           MIN(started_at) AS started_at, COUNT(*) AS days,
           MAX(CASE WHEN COALESCE(stage, 1) = 1 THEN buyin_total END) AS buyin_total,
           MAX(CASE WHEN COALESCE(stage, 1) = 1 THEN format END) AS first_format,
           MAX(CASE WHEN has_summary THEN 0 ELSE 1 END) AS summary_missing,
           MAX(CASE WHEN NOT has_summary AND provisional_prize IS NOT NULL THEN 1 ELSE 0 END) AS provisional
    FROM tournaments
    WHERE (has_summary OR COALESCE(stage, 1) > 1) AND event_id IS NOT NULL
    GROUP BY site, event_id
), c AS (
    SELECT t.site, t.tournament_id, t.name, COALESCE(e.first_format, t.format, 'unknown') AS format,
           COALESCE(e.started_at, t.started_at) AS started_at, t.players,
           COALESCE(e.reentries, t.reentries) AS reentries, COALESCE(e.buyin_total, t.buyin_total) AS buyin_total,
           CASE WHEN t.has_summary THEN t.prize_won ELSE t.provisional_prize END AS prize_won, t.finish_place,
           COALESCE(e.cost, CASE WHEN COALESCE(t.stage, 1) > 1 THEN 0
                                 ELSE t.buyin_total * (1 + COALESCE(t.reentries, 0)) END) AS total_cost,
           COALESCE(e.cash, t.prize_won) AS cash_won,
           COALESCE(e.ticket, COALESCE(t.prize_ticket, 0)) AS ticket_value,
           COALESCE(t.stage, 1) AS stage, t.advanced_to, t.advanced_chips, COALESCE(e.days, 1) AS days,
           CASE WHEN t.advanced_to IS NULL AND COALESCE(CASE WHEN t.has_summary THEN t.prize_won ELSE t.provisional_prize END, 0)
                     + COALESCE(t.prize_ticket, 0) > 0 THEN 1 ELSE 0 END AS cashed,
           COALESCE(e.summary_missing, 0) AS summary_missing, COALESCE(e.provisional, 0) AS provisional,
           -- the place as a share of the field; none while Hero is still through to a later day
           CASE WHEN t.advanced_to IS NOT NULL THEN NULL
                ELSE 100.0 * t.finish_place / NULLIF(t.players, 0) END AS place_pct
    FROM tournaments t
    LEFT JOIN ev e ON e.site = t.site AND e.event_id = t.tournament_id
    WHERE ((t.has_summary AND t.prize_won IS NOT NULL) OR e.days > 1)    -- a later day without summary: with its flights
      AND (t.event_id IS NULL OR t.event_id = t.tournament_id)
)
-- cashed: any cash or ticket. In a bounty tournament that can be knockouts alone (the summary gives only the total
-- and hand histories hold no bounty payouts), so in_the_money is known only without bounties (NULL otherwise).
SELECT c.*,
       CASE WHEN c.format = 'bounty' THEN NULL ELSE c.cashed END AS in_the_money,
       c.cash_won + c.ticket_value AS won_total,
       c.cash_won + c.ticket_value - c.total_cost AS profit,
       c.cash_won - c.total_cost AS cash_profit,
       ROUND(100.0 * (c.cash_won + c.ticket_value - c.total_cost) / NULLIF(c.total_cost, 0), 1) AS roi_pct,
       ROUND(100.0 * (c.cash_won - c.total_cost) / NULLIF(c.total_cost, 0), 1) AS roi_cash_pct
FROM c;

CREATE VIEW format_results AS
SELECT format,
       COUNT(*)                AS tournaments,
       SUM(total_cost)         AS total_cost,
       SUM(cash_won)           AS cash_won,
       SUM(ticket_value)       AS ticket_value,
       SUM(cashed)             AS cashed,
       SUM(in_the_money)       AS itm,
       COUNT(in_the_money)     AS itm_known,
       ROUND(100.0 * (SUM(cash_won) + SUM(ticket_value) - SUM(total_cost)) / NULLIF(SUM(total_cost), 0), 1) AS roi_pct,
       ROUND(100.0 * (SUM(cash_won) - SUM(total_cost)) / NULLIF(SUM(total_cost), 0), 1) AS roi_cash_pct
FROM tournament_results
GROUP BY format;

CREATE VIEW hero_position_stats AS
SELECT position,
       COUNT(*) AS hands,
       ROUND(100.0 * SUM(vpip) / NULLIF(SUM(decided), 0), 1) AS vpip_pct,
       ROUND(100.0 * SUM(pfr) / NULLIF(SUM(decided), 0), 1)  AS pfr_pct,
       ROUND(SUM(net_bb), 1)                  AS net_bb,
       ROUND(100.0 * SUM(net_bb) / COUNT(*), 1) AS bb_per_100,
       ROUND(100.0 * SUM(adj_bb) / COUNT(*), 1) AS bb_per_100_ev
FROM hero_hands
GROUP BY position;

CREATE VIEW hero_stack_depth_stats AS
SELECT CASE WHEN stack_bb < 10 THEN '1: <10 BB'
            WHEN stack_bb < 15 THEN '2: 10-15 BB'
            WHEN stack_bb < 25 THEN '3: 15-25 BB'
            WHEN stack_bb < 40 THEN '4: 25-40 BB'
            ELSE '5: 40+ BB' END AS depth,
       COUNT(*) AS hands,
       ROUND(100.0 * SUM(vpip) / NULLIF(SUM(decided), 0), 1) AS vpip_pct,
       ROUND(100.0 * SUM(pfr) / NULLIF(SUM(decided), 0), 1)  AS pfr_pct,
       ROUND(SUM(net_bb), 1)                  AS net_bb,
       ROUND(100.0 * SUM(net_bb) / COUNT(*), 1) AS bb_per_100
FROM hero_hands
GROUP BY 1;

CREATE VIEW hero_tournament_stats AS
SELECT site, tournament_id,
       COUNT(*) AS hands,
       ROUND(100.0 * SUM(vpip) / NULLIF(SUM(decided), 0), 1) AS vpip_pct,
       ROUND(100.0 * SUM(pfr) / NULLIF(SUM(decided), 0), 1)  AS pfr_pct,
       ROUND(SUM(net_bb), 1)                  AS net_bb
FROM hero_hands
GROUP BY site, tournament_id;

-- Hero's all-ins with cards to come. Bad beat: >= 80% equity and lost the main pot; suckout: <= 20% and won.
CREATE VIEW hero_allins AS
SELECT a.site, a.hand_id, h.tournament_id, h.level, h.played_at, h.big_blind,
       a.lock_street, a.hole_cards, a.board_at_lock, a.contestants, a.equity, a.result,
       a.collected - a.invested AS net,
       a.invested * 1.0 / h.big_blind AS invested_bb,
       a.ev_net, a.luck,
       (a.collected - a.invested) * 1.0 / h.big_blind AS net_bb,
       a.ev_net * 1.0 / h.big_blind AS ev_bb,
       a.luck * 1.0 / h.big_blind AS luck_bb,
       CASE WHEN a.equity >= 0.8 AND a.result = 'lose' THEN 1 ELSE 0 END AS bad_beat,
       CASE WHEN a.equity <= 0.2 AND a.result = 'win'  THEN 1 ELSE 0 END AS suckout
FROM allin_ev a
JOIN hands h ON h.site = a.site AND h.hand_id = a.hand_id
WHERE a.is_hero;

CREATE VIEW tournament_luck AS
SELECT site, tournament_id,
       COUNT(*)                  AS allins,
       ROUND(SUM(net_bb), 1)     AS net_bb,
       ROUND(SUM(ev_bb), 1)      AS ev_bb,
       ROUND(SUM(luck_bb), 1)    AS luck_bb,
       SUM(bad_beat)             AS bad_beats,
       SUM(suckout)              AS suckouts
FROM hero_allins
GROUP BY site, tournament_id;

-- Results per tag (a tournament appears under every tag it carries). Cash ROI, tickets separate.
CREATE VIEW tag_results AS
SELECT g.tag,
       COUNT(*)                AS tournaments,
       SUM(r.total_cost)       AS total_cost,
       SUM(r.cash_won)         AS cash_won,
       SUM(r.ticket_value)     AS ticket_value,
       SUM(r.cashed)           AS cashed,
       SUM(r.in_the_money)     AS itm,
       COUNT(r.in_the_money)   AS itm_known,
       ROUND(100.0 * (SUM(r.cash_won) + SUM(r.ticket_value) - SUM(r.total_cost)) / NULLIF(SUM(r.total_cost), 0), 1) AS roi_pct,
       ROUND(100.0 * (SUM(r.cash_won) - SUM(r.total_cost)) / NULLIF(SUM(r.total_cost), 0), 1) AS roi_cash_pct
FROM tournament_results r
JOIN tournament_tags g ON g.site = r.site AND g.tournament_id = r.tournament_id
GROUP BY g.tag;

-- Opponents eliminated in hands Hero won. sole = 1 when Hero was the only player who won chips in that hand;
-- otherwise (side pots, split pots) the knockout is counted as shared rather than guessed.
CREATE VIEW hero_knockouts AS
SELECT h.site, h.hand_id, h.tournament_id, h.played_at, b.nick AS busted_nick,
       CASE WHEN (SELECT COUNT(*) FROM hand_players w
                  WHERE w.site = h.site AND w.hand_id = h.hand_id AND w.net_won > 0) = 1 THEN 1 ELSE 0 END AS sole
FROM hands h
JOIN hand_players hero ON hero.site = h.site AND hero.hand_id = h.hand_id AND hero.is_hero AND hero.net_won > 0
JOIN hand_players b ON b.site = h.site AND b.hand_id = h.hand_id AND NOT b.is_hero AND b.stack + b.net_won <= 0.001;

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
CREATE VIEW hero_hands AS
SELECT h.site, h.hand_id, h.tournament_id, h.level, h.played_at, h.big_blind,
       hp.position, hp.stack_bb, hp.net_won,
       hp.net_won * 1.0 / h.big_blind AS net_bb,
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

-- One row per tournament with a summary. A tournament played over several days is one row, under its first day:
-- the cost is paid on day 1 (buy-in x entries); the cash and tickets of every day add up; the place is the last
-- day's. In the money only from a day with payouts: going through to the next day is not ITM by itself.
-- Tickets count at face value on both sides: a satellite returns the ticket's value, the tournament entered with it
-- costs its full buy-in, so the result over both equals the cash that moved. profit and roi_pct include tickets;
-- cash_profit and roi_cash_pct are the cash part.
CREATE VIEW tournament_results AS
WITH later AS (
    SELECT site, first_day_id, SUM(prize_won) AS cash, SUM(COALESCE(prize_ticket, 0)) AS ticket, MAX(stage) AS last_stage
    FROM tournaments
    WHERE has_summary AND COALESCE(stage, 1) > 1 AND first_day_id IS NOT NULL
    GROUP BY site, first_day_id
), c AS (
    SELECT t.site, t.tournament_id, t.name, COALESCE(t.format, 'unknown') AS format,
           t.started_at, t.players, t.reentries, t.buyin_total, t.prize_won,
           COALESCE((SELECT x.finish_place FROM tournaments x WHERE x.site = t.site AND x.first_day_id = t.tournament_id
                     AND x.has_summary ORDER BY x.stage DESC LIMIT 1), t.finish_place) AS finish_place,
           CASE WHEN COALESCE(t.stage, 1) > 1 THEN 0
                ELSE t.buyin_total * (1 + COALESCE(t.reentries, 0)) END AS total_cost,
           t.prize_won + COALESCE(l.cash, 0) AS cash_won,
           COALESCE(t.prize_ticket, 0) + COALESCE(l.ticket, 0) AS ticket_value,
           COALESCE(t.stage, 1) AS stage, t.advanced_to, t.advanced_chips, l.last_stage,
           CASE WHEN COALESCE(l.cash, 0) + COALESCE(l.ticket, 0) > 0 THEN 1
                WHEN t.advanced_to IS NULL AND t.prize_won + COALESCE(t.prize_ticket, 0) > 0 THEN 1
                ELSE 0 END AS in_the_money
    FROM tournaments t
    LEFT JOIN later l ON l.site = t.site AND l.first_day_id = t.tournament_id
    WHERE t.has_summary AND t.prize_won IS NOT NULL
      AND NOT (COALESCE(t.stage, 1) > 1 AND t.first_day_id IS NOT NULL)
)
SELECT c.*,
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
       SUM(in_the_money)       AS itm,
       ROUND(100.0 * (SUM(cash_won) + SUM(ticket_value) - SUM(total_cost)) / NULLIF(SUM(total_cost), 0), 1) AS roi_pct,
       ROUND(100.0 * (SUM(cash_won) - SUM(total_cost)) / NULLIF(SUM(total_cost), 0), 1) AS roi_cash_pct
FROM tournament_results
GROUP BY format;

CREATE VIEW hero_position_stats AS
SELECT position,
       COUNT(*) AS hands,
       ROUND(100.0 * SUM(vpip) / COUNT(*), 1) AS vpip_pct,
       ROUND(100.0 * SUM(pfr) / COUNT(*), 1)  AS pfr_pct,
       ROUND(SUM(net_bb), 1)                  AS net_bb,
       ROUND(100.0 * SUM(net_bb) / COUNT(*), 1) AS bb_per_100
FROM hero_hands
GROUP BY position;

CREATE VIEW hero_stack_depth_stats AS
SELECT CASE WHEN stack_bb < 10 THEN '1: <10 BB'
            WHEN stack_bb < 15 THEN '2: 10-15 BB'
            WHEN stack_bb < 25 THEN '3: 15-25 BB'
            WHEN stack_bb < 40 THEN '4: 25-40 BB'
            ELSE '5: 40+ BB' END AS depth,
       COUNT(*) AS hands,
       ROUND(100.0 * SUM(vpip) / COUNT(*), 1) AS vpip_pct,
       ROUND(100.0 * SUM(pfr) / COUNT(*), 1)  AS pfr_pct,
       ROUND(SUM(net_bb), 1)                  AS net_bb,
       ROUND(100.0 * SUM(net_bb) / COUNT(*), 1) AS bb_per_100
FROM hero_hands
GROUP BY 1;

CREATE VIEW hero_tournament_stats AS
SELECT site, tournament_id,
       COUNT(*) AS hands,
       ROUND(100.0 * SUM(vpip) / COUNT(*), 1) AS vpip_pct,
       ROUND(100.0 * SUM(pfr) / COUNT(*), 1)  AS pfr_pct,
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
       SUM(r.in_the_money)     AS itm,
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

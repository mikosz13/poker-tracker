-- Portable DDL: runs unchanged on PostgreSQL and SQLite.
-- Natural keys everywhere, so re-importing the same file is always safe (ON CONFLICT DO NOTHING).

CREATE TABLE IF NOT EXISTS tournaments (
    site            TEXT    NOT NULL,
    tournament_id   BIGINT  NOT NULL,
    name            TEXT,
    format          TEXT,                    -- 'bounty' | 'satellite' | 'regular' (known once a summary is imported)
    buyin_total     NUMERIC,                 -- prize + fee + bounty
    buyin_prize     NUMERIC,
    buyin_fee       NUMERIC,
    buyin_bounty    NUMERIC,
    players         INTEGER,
    prize_pool      NUMERIC,
    started_at      TIMESTAMP,
    finish_place    INTEGER,
    prize_won       NUMERIC,                 -- cash, or face value of the ticket when prize_is_ticket
    prize_is_ticket BOOLEAN NOT NULL DEFAULT FALSE,
    reentries       INTEGER,
    has_summary     BOOLEAN NOT NULL DEFAULT FALSE,
    starting_stack  NUMERIC,                 -- most common first-hand stack for this name + buy-in; NULL = unknown
    PRIMARY KEY (site, tournament_id)
);

CREATE TABLE IF NOT EXISTS hands (
    site           TEXT    NOT NULL,
    hand_id        TEXT    NOT NULL,
    tournament_id  BIGINT  NOT NULL,
    level          INTEGER NOT NULL,
    small_blind    NUMERIC NOT NULL,
    big_blind      NUMERIC NOT NULL,
    ante           NUMERIC NOT NULL DEFAULT 0,
    played_at      TIMESTAMP NOT NULL,
    table_name     TEXT,
    max_seats      INTEGER,
    button_seat    INTEGER,
    board          TEXT,
    total_pot      NUMERIC,
    rake           NUMERIC,
    showdown       BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (site, hand_id),
    FOREIGN KEY (site, tournament_id) REFERENCES tournaments (site, tournament_id)
);

CREATE TABLE IF NOT EXISTS hand_players (
    site        TEXT    NOT NULL,
    hand_id     TEXT    NOT NULL,
    nick        TEXT    NOT NULL,
    seat        INTEGER NOT NULL,
    position    TEXT,
    hole_cards  TEXT,
    stack       NUMERIC NOT NULL,
    stack_bb    NUMERIC,
    net_won     NUMERIC NOT NULL,
    is_hero     BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (site, hand_id, nick),
    FOREIGN KEY (site, hand_id) REFERENCES hands (site, hand_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS actions (
    site          TEXT    NOT NULL,
    hand_id       TEXT    NOT NULL,
    action_order  INTEGER NOT NULL,
    nick          TEXT    NOT NULL,
    street        TEXT    NOT NULL,
    action_type   TEXT    NOT NULL,
    amount        NUMERIC NOT NULL DEFAULT 0,
    all_in        BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (site, hand_id, action_order),
    FOREIGN KEY (site, hand_id) REFERENCES hands (site, hand_id) ON DELETE CASCADE
);

-- One row per entry (late reg / re-entry), derived from Hero's hands.
CREATE TABLE IF NOT EXISTS entries (
    site            TEXT    NOT NULL,
    tournament_id   BIGINT  NOT NULL,
    entry_no        INTEGER NOT NULL,
    entry_level     INTEGER NOT NULL,
    entered_at      TIMESTAMP NOT NULL,
    start_stack     NUMERIC NOT NULL,
    start_stack_bb  NUMERIC,
    starts_fresh    BOOLEAN NOT NULL,        -- unused since schema 2 (always TRUE): entries come from the hands
    first_hand_id   TEXT,
    PRIMARY KEY (site, tournament_id, entry_no)
);

-- All-in adjusted EV: one row per player live at the moment the betting closed with cards still to come.
CREATE TABLE IF NOT EXISTS allin_ev (
    site          TEXT    NOT NULL,
    hand_id       TEXT    NOT NULL,
    nick          TEXT    NOT NULL,
    is_hero       BOOLEAN NOT NULL DEFAULT FALSE,
    lock_street   TEXT    NOT NULL,          -- street on which the last bet was called
    board_at_lock TEXT,
    hole_cards    TEXT,
    contestants   INTEGER NOT NULL,
    equity        NUMERIC,                   -- exact equity in the main pot
    invested      NUMERIC NOT NULL,
    collected     NUMERIC NOT NULL,
    ev_net        NUMERIC NOT NULL,          -- expected (collected - invested) at the all-in moment
    luck          NUMERIC NOT NULL,          -- actual net minus ev_net, in chips
    result        TEXT,                      -- actual main-pot result on the real board: win | lose | split
    PRIMARY KEY (site, hand_id, nick),
    FOREIGN KEY (site, hand_id) REFERENCES hands (site, hand_id) ON DELETE CASCADE
);

-- Structure facts and tags derived automatically from imported data (see pokertracker/classify.py).
CREATE TABLE IF NOT EXISTS tournament_structure (
    site           TEXT    NOT NULL,
    tournament_id  BIGINT  NOT NULL,
    level_minutes  NUMERIC,                  -- NULL until enough levels were observed
    level_pairs    INTEGER NOT NULL,
    hands_seen     INTEGER NOT NULL,
    PRIMARY KEY (site, tournament_id)
);

CREATE TABLE IF NOT EXISTS tournament_tags (
    site           TEXT    NOT NULL,
    tournament_id  BIGINT  NOT NULL,
    tag            TEXT    NOT NULL,
    PRIMARY KEY (site, tournament_id, tag)
);

-- Exact equities are expensive (up to 1.7M boards) and depend only on the matchup, so they are stored once.
CREATE TABLE IF NOT EXISTS equity_cache (
    cache_key  TEXT PRIMARY KEY,
    value      TEXT NOT NULL
);

-- Files already imported, so re-scanning a big export folder only reads what is new or changed.
CREATE TABLE IF NOT EXISTS imported_files (
    path   TEXT PRIMARY KEY,
    size   BIGINT NOT NULL,
    mtime  NUMERIC NOT NULL
);

-- Version of this schema the database is at; older databases are upgraded by pokertracker/migrations.py.
CREATE TABLE IF NOT EXISTS schema_version (
    version  INTEGER NOT NULL
);

-- Small key/value store for the app (e.g. the last import folder).
CREATE TABLE IF NOT EXISTS settings (
    name   TEXT PRIMARY KEY,
    value  TEXT
);

CREATE INDEX IF NOT EXISTS idx_hands_tournament ON hands (site, tournament_id, played_at);
CREATE INDEX IF NOT EXISTS idx_players_hero     ON hand_players (site, is_hero, hand_id);
CREATE INDEX IF NOT EXISTS idx_actions_lookup   ON actions (site, hand_id, nick, street);

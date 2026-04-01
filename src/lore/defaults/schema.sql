CREATE TABLE lore_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT INTO lore_meta (key, value) VALUES ('schema_version', '6');

CREATE TABLE quests (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'closed')),
    priority    INTEGER NOT NULL DEFAULT 2 CHECK (priority BETWEEN 0 AND 4),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    closed_at   TEXT,
    deleted_at  TEXT,
    auto_close  INTEGER NOT NULL DEFAULT 0 CHECK (auto_close IN (0, 1))
);

CREATE TABLE missions (
    id           TEXT PRIMARY KEY,
    quest_id     TEXT REFERENCES quests(id),
    title        TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'blocked', 'closed')),
    priority     INTEGER NOT NULL DEFAULT 2 CHECK (priority BETWEEN 0 AND 4),
    knight       TEXT,
    block_reason TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    closed_at    TEXT,
    deleted_at   TEXT,
    mission_type TEXT
);

CREATE TABLE dependencies (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id TEXT NOT NULL,
    to_id   TEXT NOT NULL,
    type    TEXT NOT NULL DEFAULT 'blocks' CHECK (type IN ('blocks')),
    deleted_at TEXT,
    UNIQUE(from_id, to_id, type)
);

CREATE TABLE board_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id  TEXT NOT NULL,
    message    TEXT NOT NULL,
    sender     TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    deleted_at TEXT
);

CREATE INDEX idx_quests_status ON quests(status);
CREATE INDEX idx_missions_quest_id ON missions(quest_id);
CREATE INDEX idx_missions_status_priority ON missions(status, priority, created_at);
CREATE INDEX idx_deps_from ON dependencies(from_id);
CREATE INDEX idx_deps_to ON dependencies(to_id);
CREATE INDEX idx_board_entity ON board_messages(entity_id);

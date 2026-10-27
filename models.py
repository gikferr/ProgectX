SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    via_bot INTEGER DEFAULT 0,
    is_organizer_allowed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS organizer_codes (
    code TEXT PRIMARY KEY,
    created_by INTEGER REFERENCES users(user_id),
    used_by INTEGER REFERENCES users(user_id),
    used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    event_date TIMESTAMP NOT NULL,
    organizer_id INTEGER REFERENCES users(user_id),
    invite_code TEXT UNIQUE,
    is_active INTEGER DEFAULT 1,
    finished_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS event_members (
    event_id INTEGER REFERENCES events(event_id),
    user_id INTEGER REFERENCES users(user_id),
    role TEXT DEFAULT 'member',
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (event_id, user_id)
);

CREATE TABLE IF NOT EXISTS polls (
    poll_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER REFERENCES events(event_id),
    theme TEXT NOT NULL,
    deadline TIMESTAMP,
    is_active INTEGER DEFAULT 1,
    reminded_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS poll_options (
    option_id INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_id INTEGER REFERENCES polls(poll_id),
    option_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS votes (
    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_id INTEGER REFERENCES polls(poll_id),
    user_id INTEGER REFERENCES users(user_id),
    option_id INTEGER REFERENCES poll_options(option_id),
    UNIQUE(poll_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_members_user ON event_members(user_id);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_votes_poll ON votes(poll_id);
"""
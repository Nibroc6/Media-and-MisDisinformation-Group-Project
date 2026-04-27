-- SQLite Schema for Truth Social Misinformation Tracker

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    display_name TEXT,
    created_at DATETIME,
    followers_count INTEGER,
    following_count INTEGER,
    statuses_count INTEGER,
    raw_data JSON
);

CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    author_id TEXT NOT NULL,
    content TEXT,
    created_at DATETIME,
    reblogs_count INTEGER,
    replies_count INTEGER,
    favourites_count INTEGER,
    raw_data JSON,
    FOREIGN KEY(author_id) REFERENCES users(id)
);

-- Edges table for network mapping
-- interaction_type could be 'repost', 'reply', 'mention', etc.
CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_user_id TEXT NOT NULL,
    target_user_id TEXT NOT NULL,
    post_id TEXT NOT NULL,
    interaction_type TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(source_user_id) REFERENCES users(id),
    FOREIGN KEY(target_user_id) REFERENCES users(id),
    FOREIGN KEY(post_id) REFERENCES posts(id),
    UNIQUE(source_user_id, target_user_id, post_id, interaction_type)
);

"""The local SQLite store: posts, the keys used to spot repeats, runs and sent digests."""

import json
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    source TEXT,
    author TEXT NOT NULL,
    author_kind TEXT NOT NULL,
    posted_at TEXT,
    posted_at_text TEXT,
    text TEXT NOT NULL DEFAULT '',
    link TEXT,
    is_sponsored INTEGER NOT NULL DEFAULT 0,
    is_suggested INTEGER NOT NULL DEFAULT 0,
    is_reshare INTEGER NOT NULL DEFAULT 0,
    reshared_from TEXT,
    images TEXT NOT NULL DEFAULT '[]',
    first_seen_at TEXT NOT NULL,
    run_id INTEGER,
    -- keep / leave_out / NULL while waiting for a label
    decision TEXT,
    -- why it was left out: a hard-rule code, a label, 'preference' or 'cap'
    left_out_reason TEXT,
    label TEXT,
    label_reason TEXT,
    pinned INTEGER NOT NULL DEFAULT 0,
    digested_at TEXT
);
CREATE TABLE IF NOT EXISTS post_keys (
    key TEXT PRIMARY KEY,
    post_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    platform TEXT NOT NULL,
    source TEXT,
    n_seen INTEGER NOT NULL,
    n_new INTEGER NOT NULL,
    note TEXT
);
CREATE TABLE IF NOT EXISTS digests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sent_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    n_posts INTEGER NOT NULL,
    n_friends INTEGER NOT NULL,
    subject TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if dt else None


def parse_iso(value):
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def connect(cfg):
    cfg.home.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(cfg.db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def get_kv(conn, key, default=None):
    row = conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


def set_kv(conn, key, value):
    conn.execute(
        "INSERT INTO kv (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, json.dumps(value)),
    )


def find_existing(conn, keys):
    for key in keys:
        row = conn.execute("SELECT post_id FROM post_keys WHERE key = ?", (key,)).fetchone()
        if row:
            return row["post_id"]
    return None


def add_keys(conn, post_id, keys):
    for key in keys:
        conn.execute("INSERT OR IGNORE INTO post_keys (key, post_id) VALUES (?, ?)", (key, post_id))


def post_images(row):
    return json.loads(row["images"] or "[]")

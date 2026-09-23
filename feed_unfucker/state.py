"""What has to survive between runs when the machine is wiped (cloud mode), and forgetting old content.

A cloud run keeps only: the keys of posts already seen, recent sends per
friend (for the weekly per-person limit), when the last digest went out,
close friends and the limit, and preferences.md. No post text or photos.
"""

import shutil
from datetime import timedelta

from . import store

VERSION = 1


def export_state(conn, cfg):
    week_ago = store.iso(store.utcnow() - timedelta(days=8))
    prefs = cfg.preferences_path.read_text(encoding="utf-8") if cfg.preferences_path.exists() else None
    return {
        "version": VERSION,
        "keys": [r["key"] for r in conn.execute("SELECT key FROM post_keys ORDER BY key")],
        "recent": [dict(r) for r in conn.execute(
            "SELECT author, digested_at FROM posts WHERE digested_at > ? AND left_out_reason IS NULL", (week_ago,))],
        "digests": [dict(r) for r in conn.execute(
            "SELECT sent_at, kind, n_posts, n_friends, subject FROM digests ORDER BY sent_at DESC LIMIT 10")],
        "kv": {r["key"]: store.get_kv(conn, r["key"]) for r in conn.execute("SELECT key FROM kv")},
        "preferences_md": prefs,
    }


def import_state(conn, cfg, data):
    if data.get("version") != VERSION:
        raise SystemExit(f"Unknown state file version {data.get('version')!r}")
    placeholder = "imported"
    conn.executemany("INSERT OR IGNORE INTO post_keys (key, post_id) VALUES (?, ?)", [(k, placeholder) for k in data["keys"]])
    for i, r in enumerate(data.get("recent", [])):
        # A content-free stand-in so the weekly per-person limit still counts earlier sends.
        conn.execute(
            """INSERT OR IGNORE INTO posts (id, platform, author, author_kind, text, first_seen_at, decision, digested_at)
               VALUES (?, 'imported', ?, 'person', '', ?, 'keep', ?)""",
            (f"imported-{i}-{r['digested_at']}", r["author"], r["digested_at"], r["digested_at"]),
        )
    for d in data.get("digests", []):
        exists = conn.execute("SELECT 1 FROM digests WHERE sent_at = ? AND kind = ?", (d["sent_at"], d["kind"])).fetchone()
        if not exists:
            conn.execute("INSERT INTO digests (sent_at, kind, n_posts, n_friends, subject) VALUES (?, ?, ?, ?, ?)",
                         (d["sent_at"], d["kind"], d["n_posts"], d["n_friends"], d["subject"]))
    for key, value in data.get("kv", {}).items():
        store.set_kv(conn, key, value)
    if data.get("preferences_md") and not cfg.preferences_path.exists():
        cfg.preferences_path.write_text(data["preferences_md"], encoding="utf-8")
    conn.commit()
    return len(data["keys"])


def prune(conn, cfg, cutoff):
    """Blank the text and delete photos of posts handled before cutoff. Keys stay, so nothing repeats."""
    rows = conn.execute(
        "SELECT id FROM posts WHERE digested_at IS NOT NULL AND digested_at < ? AND (text != '' OR images != '[]')",
        (cutoff,),
    ).fetchall()
    for r in rows:
        shutil.rmtree(cfg.images_dir / r["id"], ignore_errors=True)
    conn.executemany("UPDATE posts SET text = '', images = '[]', link = NULL WHERE id = ?", [(r["id"],) for r in rows])
    conn.commit()
    return len(rows)

"""What has to survive between runs when the machine is wiped (cloud mode), and forgetting old content.

A cloud run keeps only: the keys of posts already seen, recent sends per
friend (for the weekly per-person limit), when the last digest went out,
close friends and the limit, preferences.md and the non-secret settings.
No post text or photos, and never a password or token.
"""

import shutil
from datetime import timedelta

from . import store
from .config import PORTABLE_SETTINGS, REPO_ROOT, read_env_file, set_env_value

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
        "settings": {k: v for k, v in read_env_file(cfg.home / "config.env").items() if k in PORTABLE_SETTINGS and v},
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
    # The saved choices win over a fresh machine's defaults, but never over a value
    # someone already changed on this machine.
    env = cfg.home / "config.env"
    current = read_env_file(env)
    example = read_env_file(REPO_ROOT / "config.example.env")
    for key, value in data.get("settings", {}).items():
        if key in PORTABLE_SETTINGS and value and current.get(key, "") in ("", example.get(key)):
            set_env_value(env, key, value)
    prefs = data.get("preferences_md")
    example_prefs = (REPO_ROOT / "preferences.example.md").read_text(encoding="utf-8")
    if prefs and (not cfg.preferences_path.exists() or cfg.preferences_path.read_text(encoding="utf-8") == example_prefs):
        cfg.preferences_path.write_text(prefs, encoding="utf-8")
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

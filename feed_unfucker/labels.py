"""Stage 2: hand the agent the posts that need judging, and store what it decides."""

from . import store
from .filters import LABELS, decide


def pending(conn, cfg, limit=None):
    rows = conn.execute(
        "SELECT * FROM posts WHERE decision IS NULL ORDER BY first_seen_at, id" + (" LIMIT ?" if limit else ""),
        (limit,) if limit else (),
    ).fetchall()
    prefs = cfg.preferences_path.read_text(encoding="utf-8") if cfg.preferences_path.exists() else ""
    known = [r[0] for r in conn.execute(
        "SELECT DISTINCT author FROM posts WHERE author_kind != 'page' AND platform != 'imported' ORDER BY author")]
    return {
        "preferences_md": prefs,
        "stored_preferences": {
            "close_friends": store.get_kv(conn, "close_friends", []),
            "max_per_person_per_week": store.get_kv(conn, "max_per_person_per_week"),
        },
        "known_authors": known,
        "labels": LABELS,
        "posts": [
            {
                "id": r["id"],
                "platform": r["platform"],
                "author": r["author"],
                "author_kind": r["author_kind"],
                "posted": r["posted_at"] or r["posted_at_text"],
                "text": r["text"],
                "reshared_from": r["reshared_from"],
                "photos": [
                    {"file": str(cfg.home / im["file"]) if im.get("file") else None, "alt": im.get("alt", "")}
                    for im in store.post_images(r)
                ],
            }
            for r in rows
        ],
    }


class LabelError(ValueError):
    pass


def apply_labels(conn, doc):
    """Store a labels file. Returns counts of kept and left-out posts."""
    errors = []
    if not isinstance(doc, dict):
        raise LabelError("the file must hold one JSON object with labels and, optionally, preferences")

    prefs = doc.get("preferences") or {}
    close = prefs.get("close_friends", [])
    cap = prefs.get("max_per_person_per_week")
    if not isinstance(close, list) or not all(isinstance(n, str) for n in close):
        errors.append("preferences.close_friends must be a list of names")
    if cap is not None and (not isinstance(cap, int) or cap < 1):
        errors.append("preferences.max_per_person_per_week must be a whole number above 0, or null")

    labels = doc.get("labels")
    if not isinstance(labels, list):
        errors.append("labels must be a list")
        labels = []
    resolved = []
    for i, item in enumerate(labels):
        where = f"labels[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object")
            continue
        row = conn.execute("SELECT id FROM posts WHERE id = ?", (item.get("id"),)).fetchone()
        if not row:
            errors.append(f"{where}: no post with id {item.get('id')!r}")
            continue
        label = item.get("label")
        if label not in LABELS:
            errors.append(f"{where}: label must be one of {', '.join(LABELS)}")
            continue
        try:
            decision, reason = decide(label, item.get("decision"))
        except ValueError as exc:
            errors.append(f"{where}: {exc}")
            continue
        resolved.append((decision, reason, label, (item.get("reason") or "")[:300], int(bool(item.get("pinned"))), item["id"]))
    if errors:
        raise LabelError("\n".join(errors))

    if "preferences" in doc:
        store.set_kv(conn, "close_friends", [n.strip() for n in close if n.strip()])
        store.set_kv(conn, "max_per_person_per_week", cap)
    conn.executemany(
        "UPDATE posts SET decision = ?, left_out_reason = ?, label = ?, label_reason = ?, pinned = ? WHERE id = ?",
        resolved,
    )
    conn.commit()
    kept = sum(1 for r in resolved if r[0] == "keep")
    return {"labelled": len(resolved), "kept": kept, "left_out": len(resolved) - kept,
            "still_waiting": conn.execute("SELECT COUNT(*) FROM posts WHERE decision IS NULL").fetchone()[0]}

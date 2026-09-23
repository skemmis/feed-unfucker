"""Pick what goes in a digest: group by friend, apply per-person limits, order close friends first."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta

from . import store
from .config import WEEKDAYS
from .filters import EVERYDAY_CAP

# Kept posts older than this (by when we first saw them) are too stale to send.
MAX_AGE_DAYS = 14


@dataclass
class Post:
    id: str
    platform: str
    text: str
    link: str
    when: object  # datetime used for ordering
    when_text: str  # what to print if the exact time isn't known
    images: list
    label: str
    pinned: bool


@dataclass
class Friend:
    name: str
    close: bool
    posts: list = field(default_factory=list)

    @property
    def first_name(self):
        return self.name.split()[0]

    @property
    def latest(self):
        return max(p.when for p in self.posts)


@dataclass
class Digest:
    cadence: str
    period_start: object
    period_end: object
    friends: list
    left_out: Counter
    capped_ids: list
    posts_read: int
    waiting_for_label: int

    @property
    def n_posts(self):
        return sum(len(f.posts) for f in self.friends)

    @property
    def broke(self):
        """No posts were read at all in this period, so something is wrong with reading."""
        return self.posts_read == 0

    @property
    def post_ids(self):
        return [p.id for f in self.friends for p in f.posts]


def is_close(name, close_friends):
    """'Jen' in preferences matches 'Jen Park' in the feed; full names match exactly."""
    name_l = name.lower()
    first = name_l.split()[0] if name_l else ""
    for c in close_friends:
        c_l = c.lower().strip()
        if c_l and (c_l == name_l or c_l == first):
            return True
    return False


def period_start(conn, cfg, now):
    last = conn.execute("SELECT sent_at FROM digests WHERE kind = 'digest' ORDER BY sent_at DESC LIMIT 1").fetchone()
    fallback = now - timedelta(days=cfg.cadence_days)
    return max(store.parse_iso(last["sent_at"]), now - timedelta(days=MAX_AGE_DAYS)) if last else fallback


def build(conn, cfg, now=None):
    now = now or store.utcnow()
    start = period_start(conn, cfg, now)
    start_s = store.iso(start)
    close_friends = store.get_kv(conn, "close_friends", [])
    weekly_cap = store.get_kv(conn, "max_per_person_per_week")

    posts_read = conn.execute("SELECT COALESCE(SUM(n_seen), 0) FROM runs WHERE started_at > ?", (start_s,)).fetchone()[0]
    waiting = conn.execute("SELECT COUNT(*) FROM posts WHERE decision IS NULL AND first_seen_at > ?", (start_s,)).fetchone()[0]
    left_out = Counter(
        r["left_out_reason"]
        for r in conn.execute(
            "SELECT left_out_reason FROM posts WHERE decision = 'leave_out' AND digested_at IS NULL AND first_seen_at > ?",
            (start_s,),
        )
    )

    oldest = store.iso(now - timedelta(days=MAX_AGE_DAYS))
    rows = conn.execute(
        "SELECT * FROM posts WHERE decision = 'keep' AND digested_at IS NULL AND first_seen_at > ? ORDER BY first_seen_at",
        (oldest,),
    ).fetchall()

    by_author = {}
    for r in rows:
        when = store.parse_iso(r["posted_at"]) or store.parse_iso(r["first_seen_at"])
        post = Post(r["id"], r["platform"], r["text"], r["link"], when, r["posted_at_text"] or "",
                    store.post_images(r), r["label"], bool(r["pinned"]))
        by_author.setdefault(r["author"], []).append(post)

    week_ago = store.iso(now - timedelta(days=7))
    friends, capped = [], []
    for author, posts in by_author.items():
        # Pinned first, then life updates and photos, then everyday posts; newest first within each.
        posts.sort(key=lambda p: (not p.pinned, p.label == "everyday", -p.when.timestamp()))
        allowed = None
        if weekly_cap:
            already = conn.execute(
                "SELECT COUNT(*) FROM posts WHERE author = ? AND digested_at > ? AND left_out_reason IS NULL",
                (author, week_ago),
            ).fetchone()[0]
            allowed = max(weekly_cap - already, 0)
        chosen, everyday = [], 0
        for p in posts:
            if not p.pinned:
                if allowed is not None and len([c for c in chosen if not c.pinned]) >= allowed:
                    capped.append(p.id)
                    continue
                if p.label == "everyday":
                    if everyday >= EVERYDAY_CAP:
                        capped.append(p.id)
                        continue
                    everyday += 1
            chosen.append(p)
        if chosen:
            chosen.sort(key=lambda p: -p.when.timestamp())
            friends.append(Friend(author, is_close(author, close_friends), chosen))

    friends.sort(key=lambda f: (not f.close, -f.latest.timestamp()))
    if capped:
        left_out["cap"] += len(capped)
    return Digest(cfg.cadence, start, now, friends, left_out, capped, posts_read, waiting)


def mark_sent(conn, digest, subject, kind="digest"):
    now = store.iso(digest.period_end)
    ids = digest.post_ids
    conn.executemany("UPDATE posts SET digested_at = ? WHERE id = ?", [(now, i) for i in ids])
    conn.executemany(
        "UPDATE posts SET decision = 'leave_out', left_out_reason = 'cap', digested_at = ? WHERE id = ?",
        [(now, i) for i in digest.capped_ids],
    )
    # Left-out posts are reported once, in this digest's footer.
    conn.execute(
        "UPDATE posts SET digested_at = ? WHERE decision = 'leave_out' AND digested_at IS NULL AND first_seen_at <= ?",
        (now, now),
    )
    conn.execute(
        "INSERT INTO digests (sent_at, kind, n_posts, n_friends, subject) VALUES (?, ?, ?, ?, ?)",
        (now, kind, digest.n_posts, len(digest.friends), subject),
    )
    conn.commit()


def is_due(conn, cfg, now=None):
    """True if a digest should go out now. A missed day (laptop asleep) catches up on the next run."""
    now = now or store.utcnow()
    local_now = now.astimezone(cfg.tz)
    last = conn.execute("SELECT sent_at FROM digests WHERE kind = 'digest' ORDER BY sent_at DESC LIMIT 1").fetchone()
    last_local = store.parse_iso(last["sent_at"]).astimezone(cfg.tz) if last else None
    if last_local and last_local.date() == local_now.date():
        return False
    if cfg.cadence == "daily":
        return True
    if last_local is None:
        return local_now.weekday() == WEEKDAYS.index(cfg.weekly_day)
    if (local_now.date() - last_local.date()).days >= 7:
        return True
    return local_now.weekday() == WEEKDAYS.index(cfg.weekly_day) and (local_now.date() - last_local.date()).days >= 2

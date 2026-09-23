"""Turn the agent's posts JSON into stored posts: validate, spot repeats, fetch images, apply stage 1."""

import hashlib
import json
import mimetypes
import re
import shutil
import urllib.request
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from . import store
from .filters import stage1

PLATFORMS = ("facebook", "instagram")
AUTHOR_KINDS = ("person", "page", "group", "unknown")
MAX_IMAGES_PER_POST = 6
MAX_IMAGE_BYTES = 6 * 1024 * 1024

# Query parameters that only track clicks; they differ between loads of the same post.
TRACKING_PARAMS = re.compile(r"^(__cft__.*|__tn__|mibextid|rdid|share_url|igsh|igshid|utm_.*|ref|fbclid|sfnsn|paipv|eav|_rdr)$")


class IngestError(ValueError):
    pass


def normalize_link(url):
    if not url:
        return None
    parts = urlsplit(url.strip())
    host = parts.netloc.lower()
    for prefix in ("www.", "m.", "web.", "mbasic."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    query = [(k, v) for k, v in parse_qsl(parts.query) if not TRACKING_PARAMS.match(k)]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, urlencode(sorted(query)), ""))


def normalize_text(text):
    return re.sub(r"\s+", " ", text or "").strip().lower()


def post_keys(platform, post):
    """Keys that identify a post across runs. Any one matching means we've seen it."""
    keys = []
    link = normalize_link(post.get("link"))
    if link:
        keys.append("link:" + link)
    text = normalize_text(post.get("text"))
    if text:
        basis = f"{platform}|{normalize_text(post['author'])}|{text[:280]}"
        keys.append("text:" + hashlib.sha256(basis.encode()).hexdigest()[:32])
    elif not link:
        # A photo with no words and no link: fall back to author, day and photo count.
        day = (post.get("posted_at") or "")[:10]
        basis = f"{platform}|{normalize_text(post['author'])}|{day}|{len(post.get('images') or [])}"
        keys.append("photo:" + hashlib.sha256(basis.encode()).hexdigest()[:32])
    return keys


def _bool(post, name, errors, where):
    value = post.get(name, False)
    if not isinstance(value, bool):
        errors.append(f"{where}: {name} must be true or false")
        return False
    return value


def validate(doc):
    """Check the posts JSON and return a cleaned copy. Raises IngestError listing every problem."""
    errors = []
    if not isinstance(doc, dict):
        raise IngestError("the file must hold one JSON object with platform and posts")
    platform = doc.get("platform")
    if platform not in PLATFORMS:
        errors.append(f"platform must be one of {', '.join(PLATFORMS)}")
    posts = doc.get("posts")
    if not isinstance(posts, list):
        errors.append("posts must be a list (it can be empty)")
        posts = []
    clean = []
    for i, post in enumerate(posts):
        where = f"posts[{i}]"
        if not isinstance(post, dict):
            errors.append(f"{where}: must be an object")
            continue
        author = (post.get("author") or "").strip()
        if not author:
            errors.append(f"{where}: author is required")
        kind = post.get("author_kind", "unknown")
        if kind not in AUTHOR_KINDS:
            errors.append(f"{where}: author_kind must be one of {', '.join(AUTHOR_KINDS)}")
        posted_at = post.get("posted_at")
        if posted_at:
            try:
                posted_at = store.iso(store.parse_iso(posted_at))
            except ValueError:
                errors.append(f"{where}: posted_at must be ISO 8601, like 2026-09-22T17:12:00Z, or null")
        images = post.get("images") or []
        if not isinstance(images, list) or not all(isinstance(im, dict) and (im.get("url") or im.get("path")) for im in images):
            errors.append(f"{where}: images must be a list of objects with a url or a path")
            images = []
        text = post.get("text") or ""
        if not isinstance(text, str):
            errors.append(f"{where}: text must be a string")
            text = ""
        clean.append({
            "author": author,
            "author_kind": kind,
            "posted_at": posted_at or None,
            "posted_at_text": post.get("posted_at_text") or None,
            "text": text.strip(),
            "link": post.get("link") or None,
            "is_sponsored": _bool(post, "is_sponsored", errors, where),
            "is_suggested": _bool(post, "is_suggested", errors, where),
            "is_reshare": _bool(post, "is_reshare", errors, where),
            "reshared_from": post.get("reshared_from") or None,
            "images": images[:MAX_IMAGES_PER_POST],
        })
    if errors:
        raise IngestError("\n".join(errors))
    return {"platform": platform, "source": doc.get("source"), "note": doc.get("note"), "posts": clean}


def _guess_ext(content_type, url):
    ext = mimetypes.guess_extension((content_type or "").split(";")[0].strip()) or ""
    if ext in (".jpe", ".jpeg"):
        ext = ".jpg"
    if not ext:
        ext = Path(urlsplit(url).path).suffix.lower() or ".jpg"
    return ext


def fetch_image(image, dest_stem, base_dir):
    """Save one image next to the store. Returns the saved path, or raises OSError."""
    if image.get("path"):
        src = Path(image["path"])
        if not src.is_absolute():
            src = (base_dir / src).resolve()
        if src.stat().st_size > MAX_IMAGE_BYTES:
            raise OSError("image is too large")
        dest = dest_stem.with_suffix(src.suffix.lower() or ".png")
        shutil.copyfile(src, dest)
        return dest
    url = image["url"]
    local = urlsplit(url).hostname in ("localhost", "127.0.0.1")  # the fake feed in fixtures/
    if not (url.startswith("https://") or (url.startswith("http://") and local)):
        raise OSError("only https image links are fetched")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (feed-unfucker; personal digest)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        content_type = resp.headers.get("Content-Type", "")
        if not content_type.startswith("image/"):
            raise OSError(f"not an image ({content_type or 'no content type'})")
        data = resp.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise OSError("image is too large")
    dest = dest_stem.with_suffix(_guess_ext(content_type, url))
    dest.write_bytes(data)
    return dest


def ingest(conn, cfg, doc, base_dir, fetch=fetch_image):
    """Store one read of one feed. Returns a summary dict."""
    doc = validate(doc)
    now = store.iso(store.utcnow())
    cur = conn.execute(
        "INSERT INTO runs (started_at, platform, source, n_seen, n_new, note) VALUES (?, ?, ?, ?, 0, ?)",
        (now, doc["platform"], doc["source"], len(doc["posts"]), doc["note"]),
    )
    run_id = cur.lastrowid
    summary = {"run_id": run_id, "seen": len(doc["posts"]), "new": 0, "repeats": 0,
               "dropped": {}, "waiting_for_label": 0, "image_problems": []}
    for post in doc["posts"]:
        keys = post_keys(doc["platform"], post)
        existing = store.find_existing(conn, keys)
        if existing:
            store.add_keys(conn, existing, keys)
            summary["repeats"] += 1
            continue
        post_id = hashlib.sha256(keys[0].encode()).hexdigest()[:16]
        saved = []
        img_dir = cfg.images_dir / post_id
        for n, image in enumerate(post["images"]):
            alt = (image.get("alt") or "").strip()
            try:
                img_dir.mkdir(parents=True, exist_ok=True)
                path = fetch(image, img_dir / str(n), base_dir)
                saved.append({"file": str(path.relative_to(cfg.home)), "alt": alt})
            except (OSError, ValueError) as exc:
                # Keep a placeholder so the digest can say a photo is missing.
                saved.append({"file": None, "alt": alt})
                summary["image_problems"].append(f"{post['author']}: {exc}")
        post["images"] = saved
        reason = stage1(post)
        conn.execute(
            """INSERT INTO posts (id, platform, source, author, author_kind, posted_at, posted_at_text, text, link,
                   is_sponsored, is_suggested, is_reshare, reshared_from, images, first_seen_at, run_id,
                   decision, left_out_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (post_id, doc["platform"], doc["source"], post["author"], post["author_kind"], post["posted_at"],
             post["posted_at_text"], post["text"], post["link"], int(post["is_sponsored"]),
             int(post["is_suggested"]), int(post["is_reshare"]), post["reshared_from"],
             json.dumps(post["images"]), now, run_id,
             "leave_out" if reason else None, reason),
        )
        store.add_keys(conn, post_id, keys)
        summary["new"] += 1
        if reason:
            summary["dropped"][reason] = summary["dropped"].get(reason, 0) + 1
        else:
            summary["waiting_for_label"] += 1
    conn.execute("UPDATE runs SET n_new = ? WHERE id = ?", (summary["new"], run_id))
    conn.commit()
    return summary

"""A full run on made-up friends, so you can see the email before connecting any account."""

import json
import shutil
import struct
import zlib
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from . import digest as digest_mod
from . import labels, mail, render, store
from .config import REPO_ROOT
from .ingest import ingest

FIXTURE = REPO_ROOT / "fixtures" / "sample-feed.json"
PREFERENCES = REPO_ROOT / "fixtures" / "sample-preferences.md"


def _png(path, width, height, top, bottom, sun):
    """A soft landscape-ish gradient with a sun, as a stand-in photo. Standard library only."""
    sx, sy, sr = int(width * sun[0]), int(height * sun[1]), int(height * 0.12)
    rows = []
    for y in range(height):
        t = y / (height - 1)
        base = bytes(int(a + (b - a) * t) for a, b in zip(top, bottom))
        row = bytearray(b"\x00" + base * width)
        dy = y - sy
        if abs(dy) < sr:
            half = int((sr * sr - dy * dy) ** 0.5)
            for x in range(max(sx - half, 0), min(sx + half, width)):
                row[1 + 3 * x:4 + 3 * x] = b"\xff\xf1\xd6"
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def run(out, send=False, cfg=None):
    out = Path(out).resolve()
    shutil.rmtree(out, ignore_errors=True)
    inbox = out / "inbox"
    inbox.mkdir(parents=True)
    demo_cfg = replace(cfg, home=out, preferences_path=PREFERENCES, cadence="weekly")

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    now = store.utcnow()
    for post in fixture["posts"]:
        hours = post.pop("_hours_ago", 24)
        post["posted_at"] = store.iso(now - timedelta(hours=hours))
        for im in post.get("images", []):
            spec = im.pop("_draw")
            _png(inbox / im["path"], 800, 533, tuple(spec["top"]), tuple(spec["bottom"]), spec["sun"])
    wanted = {(p["author"], p.get("text", "")): p.pop("_label", None) for p in fixture["posts"]}
    (inbox / "posts.json").write_text(json.dumps(fixture, indent=2), encoding="utf-8")

    conn = store.connect(demo_cfg)
    summary = ingest(conn, demo_cfg, fixture, inbox)
    todo = labels.pending(conn, demo_cfg)
    labelled = []
    for p in todo["posts"]:
        choice = wanted.get((p["author"], p["text"]))
        if choice:
            labelled.append({"id": p["id"], **choice})
    labels.apply_labels(conn, {
        "preferences": {"close_friends": ["Jen Park", "Marcus Obi", "Ruth Adler"], "max_per_person_per_week": 2},
        "labels": labelled,
    })

    d = digest_mod.build(conn, demo_cfg)
    preview = out / "preview.html"
    preview.write_text(render.render_html(d, lambda f: str(out / f), demo_cfg.tz), encoding="utf-8")
    msg, subject = mail.build_digest_message(demo_cfg, d)
    (out / "digest.eml").write_bytes(bytes(msg))
    print(f"Read {summary['seen']} made-up posts; {summary['new'] - summary['waiting_for_label']} dropped by the fixed rules.")
    print(f"Subject: {subject}")
    print(f"{render.opening_line(d)} {render.footer_lines(d)[0]}")
    print(f"Open {preview} in a browser to see it, or {out / 'digest.eml'} in a mail app.")
    if send:
        mail.send(cfg, msg)
        print(f"Sent the sample digest to {cfg.email_to}.")

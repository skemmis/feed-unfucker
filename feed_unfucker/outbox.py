"""Hand the email to the agent's own email tool (a Gmail or Outlook connector), so nobody needs a password.

`prepare` writes the email as JSON for the agent to send, and remembers which
posts it holds. Once the agent has sent it, `mark_sent` records that, so the
same posts never go out twice. Photos load from the platform's own links
rather than being attached, because an agent can't cheaply pass image bytes
to a tool; those links expire after some days.
"""

import json

from . import digest as digest_mod
from . import render, store

NO_ADDRESS = "FU_EMAIL_TO isn't set. Ask the user for their address, then run ./fu config set FU_EMAIL_TO <address>."


def _remote_src(im):
    return im.get("url") if (im.get("url") or "").startswith("https://") else None


def _write(conn, cfg, email_id, subject, text, html_body, record):
    if not cfg.email_to:
        raise SystemExit(NO_ADDRESS)
    payload = {"id": email_id, "to": cfg.email_to, "subject": subject, "html_body": html_body, "text_body": text}
    cfg.outbox_dir.mkdir(parents=True, exist_ok=True)
    path = cfg.outbox_dir / f"{email_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    store.set_kv(conn, "prepared:" + email_id, {"subject": subject, **record})
    conn.commit()
    return path


def prepare_alert(conn, cfg, reason, now):
    subject, text, html_body = render.render_broke(reason, now, cfg.tz)
    email_id = now.strftime("%Y-%m-%d-%H%M") + "-alert"
    return _write(conn, cfg, email_id, subject, text, html_body, {"kind": "alert", "sent_at": store.iso(now)})


def prepare(conn, cfg, d):
    if d.broke:
        reason = "no posts were read since the last email. The browser may be logged out, or the page may have changed."
        return prepare_alert(conn, cfg, reason, d.period_end)
    email_id = d.period_end.strftime("%Y-%m-%d-%H%M")
    return _write(conn, cfg, email_id, render.subject(d), render.render_text(d, cfg.tz),
                  render.render_html(d, _remote_src, cfg.tz),
                  {"kind": "digest", "sent_at": store.iso(d.period_end), "post_ids": d.post_ids,
                   "capped_ids": d.capped_ids, "n_friends": len(d.friends)})


def mark_sent(conn, email_id):
    key = "prepared:" + email_id
    info = store.get_kv(conn, key)
    if info is None:
        raise SystemExit(f"No prepared email {email_id!r}. It may already be marked as sent.")
    if info["kind"] == "digest":
        digest_mod.record_sent(conn, info["sent_at"], info["post_ids"], info["capped_ids"], info["subject"], info["n_friends"])
    else:
        conn.execute("INSERT INTO digests (sent_at, kind, n_posts, n_friends, subject) VALUES (?, 'alert', 0, 0, ?)",
                     (info["sent_at"], info["subject"]))
    conn.execute("DELETE FROM kv WHERE key = ?", (key,))
    conn.commit()
    return info

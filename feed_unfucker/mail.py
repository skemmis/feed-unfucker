"""Build the email with photos embedded, and send it from the user's own account to themselves."""

import mimetypes
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from . import render

# Gmail rejects messages over 25 MB, and encoding adds about a third.
IMAGE_BUDGET_BYTES = 16 * 1024 * 1024


def build_digest_message(cfg, digest):
    """Returns (EmailMessage, subject). Photos past the size budget are left as 'more photos on Facebook'."""
    subject = render.subject(digest)
    attached = {}  # stored file -> (cid, bytes, mime type)
    used = 0
    for friend in digest.friends:
        for post in friend.posts:
            for im in post.images:
                file = im.get("file")
                if not file or file in attached:
                    continue
                path = cfg.home / file
                if not path.exists():
                    continue
                size = path.stat().st_size
                if used + size > IMAGE_BUDGET_BYTES:
                    continue
                used += size
                mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
                attached[file] = (make_msgid(domain="feed-unfucker.local")[1:-1], path.read_bytes(), mime)

    html_body = render.render_html(
        digest, lambda im: f"cid:{attached[im['file']][0]}" if im.get("file") in attached else None, cfg.tz)
    msg = _base(cfg, subject)
    msg.set_content(render.render_text(digest, cfg.tz))
    msg.add_alternative(html_body, subtype="html")
    html_part = msg.get_payload()[1]
    for file, (cid, data, mime) in attached.items():
        maintype, subtype = mime.split("/", 1)
        html_part.add_related(data, maintype=maintype, subtype=subtype, cid=f"<{cid}>",
                              filename=file.replace("/", "-"), disposition="inline")
    return msg, subject


def build_broke_message(cfg, reason, now):
    subject, text, page = render.render_broke(reason, now, cfg.tz)
    msg = _base(cfg, subject)
    msg.set_content(text)
    msg.add_alternative(page, subtype="html")
    return msg, subject


def _base(cfg, subject):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"Feed Unfucker <{cfg.email_from}>" if cfg.email_from else "Feed Unfucker"
    if cfg.email_to:
        msg["To"] = cfg.email_to
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="feed-unfucker.local")
    return msg


def send(cfg, msg):
    if not cfg.email_ready():
        raise SystemExit(
            "Email isn't set up yet. Fill in FU_SMTP_HOST, FU_SMTP_USER and FU_SMTP_PASSWORD in "
            f"{cfg.home / 'config.env'} (see docs/setup.md), then run ./fu doctor."
        )
    context = ssl.create_default_context()
    if cfg.smtp_port == 465:
        with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, context=context, timeout=60) as smtp:
            smtp.login(cfg.smtp_user, cfg.smtp_password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=60) as smtp:
            smtp.starttls(context=context)
            smtp.login(cfg.smtp_user, cfg.smtp_password)
            smtp.send_message(msg)

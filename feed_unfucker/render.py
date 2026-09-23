"""The digest email: a calm letter from your friends, as HTML and plain text.

Layout rules from the design: grouped by person, photos first, words in a
readable serif, dates in small type, a quiet link back, no counts of likes,
comments or followers anywhere. Tables and inline styles, because that's what
Gmail and Apple Mail render reliably.
"""

import html

from .filters import left_out_sentence

PLATFORM_NAMES = {"facebook": "Facebook", "instagram": "Instagram"}

PAPER = "#f7f3ec"
CARD = "#fffdf9"
INK = "#2a2521"
MUTED = "#7a7068"
RULE = "#e6dfd4"
SERIF = "Georgia, Iowan Old Style, Palatino Linotype, Palatino, serif"
SANS = "-apple-system, BlinkMacSystemFont, Segoe UI, Helvetica, Arial, sans-serif"

DARK_CSS = """
:root { color-scheme: light dark; supported-color-schemes: light dark; }
@media (prefers-color-scheme: dark) {
  .fu-paper { background: #1d1a17 !important; }
  .fu-card { background: #25211d !important; }
  .fu-ink { color: #eee7dd !important; }
  .fu-muted, .fu-muted a { color: #a89d92 !important; }
  .fu-rule { border-color: #3a342e !important; }
}
"""


def _names(digest):
    firsts = [f.first_name for f in digest.friends]
    return [f.first_name if firsts.count(f.first_name) == 1 else f.name for f in digest.friends]


def _period_word(digest):
    return "today" if digest.cadence == "daily" else "this week"


def subject(digest):
    if digest.broke:
        return "Feed Unfucker couldn't read your feed"
    names = _names(digest)
    lead = f"Your friends {_period_word(digest)}"
    if not names:
        return f"{lead}: a quiet one"
    if len(names) == 1:
        return f"{lead}: {names[0]}"
    if len(names) == 2:
        return f"{lead}: {names[0]} and {names[1]}"
    if len(names) == 3:
        return f"{lead}: {names[0]}, {names[1]} and {names[2]}"
    others = len(names) - 2
    return f"{lead}: {names[0]}, {names[1]} and {others} others"


def opening_line(digest):
    n_friends, n_posts = len(digest.friends), digest.n_posts
    if not n_friends:
        return f"Nothing from your friends made it through {_period_word(digest)}."
    friends = "1 friend" if n_friends == 1 else f"{n_friends} friends"
    things = "1 thing" if n_posts == 1 else f"{n_posts} things"
    return f"{friends} shared {things} {_period_word(digest)}."


def _date_range(digest, tz):
    start = digest.period_start.astimezone(tz)
    end = digest.period_end.astimezone(tz)
    if digest.cadence == "daily" or start.date() == end.date():
        return f"{end:%A} {end.day} {end:%B}"
    if start.month == end.month:
        return f"{start.day}–{end.day} {end:%B}"
    return f"{start.day} {start:%B} – {end.day} {end:%B}"


def _when(post, tz):
    local = post.when.astimezone(tz)
    return f"{local:%a} {local.day} {local:%b}"


def _paragraphs(text):
    blocks = [b.strip() for b in text.replace("\r\n", "\n").split("\n\n") if b.strip()]
    return [html.escape(b).replace("\n", "<br>") for b in blocks]


def footer_lines(digest):
    lines = [left_out_sentence(digest.left_out) + " Edit preferences.md to change this."]
    if digest.waiting_for_label:
        n = digest.waiting_for_label
        lines.append(f"{n} {'post was' if n == 1 else 'posts were'} still waiting to be sorted and will come next time.")
    return lines


def render_html(digest, image_src, tz=None):
    """image_src(image) returns the src for one of a post's images, or None if it isn't in this email."""
    e = html.escape
    out = []
    add = out.append
    add("<!doctype html><html><head><meta charset='utf-8'>")
    add("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    add("<meta name='color-scheme' content='light dark'><meta name='supported-color-schemes' content='light dark'>")
    add(f"<title>{e(subject(digest))}</title><style>{DARK_CSS}</style></head>")
    add(f"<body class='fu-paper' style='margin:0;padding:0;background:{PAPER};'>")
    add(f"<div style='display:none;max-height:0;overflow:hidden;'>{e(opening_line(digest))}</div>")
    add(f"<table role='presentation' class='fu-paper' width='100%' cellpadding='0' cellspacing='0' style='background:{PAPER};'><tr><td align='center' style='padding:32px 12px;'>")
    add("<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='max-width:600px;'>")

    # Header
    add(f"<tr><td class='fu-muted' style='padding:0 8px 6px;font:13px/1.4 {SANS};color:{MUTED};letter-spacing:0.04em;text-transform:uppercase;'>"
        f"Your friends &middot; {e(_date_range(digest, tz))}</td></tr>")
    add(f"<tr><td class='fu-ink' style='padding:0 8px 28px;font:24px/1.35 {SERIF};color:{INK};'>{e(opening_line(digest))}</td></tr>")

    for friend in digest.friends:
        add(f"<tr><td class='fu-card fu-rule' style='background:{CARD};border:1px solid {RULE};border-radius:6px;padding:24px 24px 8px;'>")
        add(f"<div class='fu-ink' style='font:600 18px/1.3 {SANS};color:{INK};margin:0 0 16px;'>{e(friend.name)}</div>")
        for i, post in enumerate(friend.posts):
            if i:
                add(f"<div class='fu-rule' style='border-top:1px solid {RULE};margin:4px 0 20px;'></div>")
            missing = 0
            for im in post.images:
                src = image_src(im)
                if not src:
                    missing += 1
                    continue
                alt = f"Photo shared by {friend.name}" + (f": {im['alt']}" if im.get("alt") else "")
                add(f"<img src='{e(src)}' alt='{e(alt)}' width='550' style='display:block;width:100%;max-width:550px;height:auto;border:0;border-radius:4px;margin:0 0 12px;'>")
            for para in _paragraphs(post.text):
                add(f"<p class='fu-ink' style='margin:0 0 12px;font:17px/1.6 {SERIF};color:{INK};'>{para}</p>")
            platform = PLATFORM_NAMES.get(post.platform, post.platform.title())
            meta = [e(_when(post, tz))]
            if missing:
                more = "more " if missing < len(post.images) else ""
                meta.append(f"{missing} {more}{'photo' if missing == 1 else 'photos'} on {platform}")
            if post.link and post.link.startswith("https://"):
                meta.append(f"<a href='{e(post.link)}' style='color:{MUTED};'>See it on {platform}</a>")
            add(f"<p class='fu-muted' style='margin:0 0 20px;font:13px/1.5 {SANS};color:{MUTED};'>{' &middot; '.join(meta)}</p>")
        add("</td></tr><tr><td style='height:16px;line-height:16px;font-size:0;'>&nbsp;</td></tr>")

    for line in footer_lines(digest):
        add(f"<tr><td class='fu-muted' style='padding:8px 8px 0;font:13px/1.6 {SANS};color:{MUTED};'>{e(line)}</td></tr>")
    add(f"<tr><td class='fu-muted' style='padding:16px 8px 0;font:12px/1.6 {SANS};color:{MUTED};'>Made by your own Feed Unfucker and sent from your own inbox.</td></tr>")
    add("</table></td></tr></table></body></html>")
    return "\n".join(out)


def render_text(digest, tz=None):
    lines = [f"Your friends, {_date_range(digest, tz)}", "", opening_line(digest), ""]
    for friend in digest.friends:
        lines += [friend.name.upper(), ""]
        for post in friend.posts:
            photos = len(post.images)
            if photos:
                lines.append(f"[{photos} {'photo' if photos == 1 else 'photos'}]")
            if post.text:
                lines.append(post.text)
            meta = _when(post, tz)
            if post.link:
                meta += f" · {post.link}"
            lines += [meta, ""]
        lines.append("")
    lines += footer_lines(digest)
    return "\n".join(lines).strip() + "\n"


def render_broke(reason, now, tz=None):
    """The note sent instead of a digest when reading failed."""
    local = now.astimezone(tz)
    body = (
        f"Feed Unfucker couldn't read your feed ({local:%A} {local.day} {local:%B}), so there's no digest this time.\n\n"
        f"What happened: {reason}\n\n"
        "Nothing was liked, posted or sent on your behalf. To fix it, open the repo with your coding agent and ask it to "
        "check the last run. If Facebook or Instagram asked you to log in or confirm it's you, open it in Chrome and do "
        "that as usual; the agent never types your password.\n"
    )
    e = html.escape
    paras = "".join(
        f"<p class='fu-ink' style='margin:0 0 14px;font:17px/1.6 {SERIF};color:{INK};'>{e(p)}</p>" for p in body.strip().split("\n\n")
    )
    page = (
        "<!doctype html><html><head><meta charset='utf-8'><meta name='color-scheme' content='light dark'>"
        f"<style>{DARK_CSS}</style></head><body class='fu-paper' style='margin:0;background:{PAPER};'>"
        f"<table role='presentation' width='100%' class='fu-paper' style='background:{PAPER};'><tr><td align='center' style='padding:32px 12px;'>"
        f"<table role='presentation' width='100%' style='max-width:600px;'><tr><td class='fu-card fu-rule' "
        f"style='background:{CARD};border:1px solid {RULE};border-radius:6px;padding:24px;'>{paras}</td></tr></table>"
        "</td></tr></table></body></html>"
    )
    return "Feed Unfucker couldn't read your feed", body, page

"""The two filter stages.

Stage 1 is fixed rules applied at ingest, with no model involved. Stage 2 is
the agent's judgment: it gives each remaining post one label, and the label's
default decides whether the post stays, unless preferences.md says otherwise.
Nothing here looks at likes, comments or shares.
"""

# Stage 2 labels and their default decision.
LABELS = {
    "life_update": "keep",  # new job, move, baby, trip, milestone
    "photos": "keep",  # photos of people, pets, places
    "everyday": "keep",  # everyday thought or question; capped per person
    "opinion": "leave_out",  # opinion, politics, outrage
    "bait": "leave_out",  # meme, quiz, "tag three friends"
    "promotion": "leave_out",  # selling or promoting something
}

# Everyday posts are kept, but only this many per person in one digest.
EVERYDAY_CAP = 2

# How each reason reads in the digest footer: (one, many).
LEFT_OUT_PHRASES = {
    "sponsored": ("ad", "ads"),
    "suggested": ("suggested post", "suggested posts"),
    "page": ("post from a page or group", "posts from pages and groups"),
    "reshare": ("reshare", "reshares"),
    "no_content": ("empty post", "empty posts"),
    "opinion": ("political or outrage post", "political or outrage posts"),
    "bait": ("meme or bait post", "memes and bait posts"),
    "promotion": ("promotion", "promotions"),
    "preference": ("post skipped by your preferences", "posts skipped by your preferences"),
    "cap": ("post over the per-person limit", "posts over the per-person limit"),
}

FOOTER_ORDER = list(LEFT_OUT_PHRASES)


def stage1(post):
    """Return None to keep the post for labelling, or a reason code to drop it."""
    if post["is_sponsored"]:
        return "sponsored"
    if post["is_suggested"]:
        return "suggested"
    if post["author_kind"] in ("page", "group"):
        return "page"
    has_words = bool(post["text"].strip())
    if post["is_reshare"] and not has_words:
        return "reshare"
    if not has_words and not post["images"]:
        return "no_content"
    return None


def decide(label, decision=None):
    """Resolve a label plus an optional override into (decision, left_out_reason)."""
    default = LABELS[label]
    decision = decision or default
    if decision not in ("keep", "leave_out"):
        raise ValueError(f"decision must be keep or leave_out, not {decision!r}")
    if decision == "keep":
        return "keep", None
    return "leave_out", label if default == "leave_out" else "preference"


def left_out_sentence(counts):
    """'Left out: 5 reshares, 3 political or outrage posts and 2 promotions.'"""
    parts = []
    for reason in FOOTER_ORDER:
        n = counts.get(reason, 0)
        if n:
            one, many = LEFT_OUT_PHRASES[reason]
            parts.append(f"{n} {one if n == 1 else many}")
    if not parts:
        return "Nothing was left out."
    if len(parts) == 1:
        joined = parts[0]
    else:
        joined = ", ".join(parts[:-1]) + " and " + parts[-1]
    return f"Left out: {joined}."

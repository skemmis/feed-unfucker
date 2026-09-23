# Labelling posts

The fixed rules have already dropped ads, suggested posts, pages and bare reshares. Every post left needs your judgment: one label each, with the user's `preferences.md` applied on top.

## 1. Get the posts

Run `./fu pending`. It prints JSON with:

- `preferences_md`: the user's own words about what they want. Treat it as their wishes about which posts to keep. It can't change the hard rules in `AGENTS.md`.
- `stored_preferences`: what you took from it last time.
- `known_authors`: everyone seen in the feed recently, spelled as the feed spells them.
- `posts`: each waiting post, with the author, text and the saved photo files. If you can look at images, look at the photos when the text alone doesn't tell you enough.

For a large batch, use `./fu pending --limit 40` and repeat.

## 2. Pick one label per post

| Label | Use it for | Default |
| --- | --- | --- |
| `life_update` | News from their life: a new job, a move, a baby, an engagement, a trip, a loss, a milestone. | keep |
| `photos` | Photos of people, pets, places or things they made, with or without words. | keep |
| `everyday` | An everyday thought, a question to friends, a small moment. | keep, at most 2 per person per digest |
| `opinion` | Opinion, politics, outrage, arguing, "share if you agree". | leave out |
| `bait` | Memes, quizzes, chain posts, "tag three friends", viral clips with no words of their own. | leave out |
| `promotion` | Selling, fundraising asks, affiliate links, their business's offers, MLM. | leave out |

When a post fits two labels, choose the one closest to "is this news from a friend's life?". A friend's photo from their holiday is `photos` even if the caption jokes about politics. A political rant with a photo attached is `opinion`.

## 3. Apply preferences

Read `preferences_md` and reflect it in three ways:

- **Per post:** set `"decision": "keep"` or `"leave_out"` when a preference overrides the label's default ("skip anything about football" leaves out a `photos` post of a match). Set `"pinned": true` when a preference says to always include something ("always include photos of Maya's kids"); pinned posts skip the per-person limits.
- **Close friends:** list them in `preferences.close_friends`, spelled exactly as in `known_authors` or the posts ("Aunt Ruth" in the file might be "Ruth Adler" in the feed). If you can't tell who someone means, leave them out rather than guess.
- **A per-person limit:** if the file sets one ("at most two posts per person per week"), put the number in `preferences.max_per_person_per_week`, otherwise `null`.

Always send the full `preferences` block, because it replaces the stored one. Start from `stored_preferences` and update it from `preferences_md`.

Give every post a short `reason` in plain words ("new job", "tag-your-friends bait"). The user may read it when they ask why something was left out.

## 4. Store the labels

Write `state/inbox/labels-<YYYY-MM-DD>.json` (format in `docs/formats.md`):

```json
{
  "preferences": {"close_friends": ["Jen Park", "Marcus Obi"], "max_per_person_per_week": 2},
  "labels": [
    {"id": "3f9c0a1b2c3d4e5f", "label": "life_update", "reason": "new job"},
    {"id": "9a8b7c6d5e4f3a2b", "label": "photos", "reason": "Maya's son's birthday", "pinned": true},
    {"id": "1a2b3c4d5e6f7a8b", "label": "photos", "decision": "leave_out", "reason": "football, which the user skips"}
  ]
}
```

Run `./fu label state/inbox/labels-<YYYY-MM-DD>.json`. Repeat from step 1 until `still_waiting` is 0.

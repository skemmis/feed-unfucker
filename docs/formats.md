# File formats

Two JSON files pass from the agent to `./fu`. Both are checked on the way in, and every problem is listed at once so the agent can fix them in one go.

## Posts: `./fu ingest FILE`

One file per read of one feed.

| Field | Type | Notes |
| --- | --- | --- |
| `platform` | `"facebook"` or `"instagram"` | Required. |
| `source` | string | Which feed, like `friends_feed` or `following`. |
| `note` | string | Optional. What happened during the read, kept with the run. |
| `posts` | list | Required. Can be empty, which records a read that found nothing. |

Each post:

| Field | Type | Notes |
| --- | --- | --- |
| `author` | string | Required. The name as shown. |
| `author_kind` | `person`, `page`, `group` or `unknown` | Pages and groups are dropped by the fixed rules. Default `unknown`. |
| `posted_at` | ISO 8601 string or `null` | Converted to UTC. |
| `posted_at_text` | string | What the page said, like "Yesterday at 17:12". |
| `text` | string | The author's own words only. |
| `link` | string | The post's own address. Used to spot repeats and for the "See it on Facebook" link. |
| `images` | list of `{"url": ..., "alt": ...}` or `{"path": ..., "alt": ...}` | Up to 6. URLs must be https and are downloaded at ingest. Relative paths are read from the posts file's folder. |
| `is_sponsored`, `is_suggested`, `is_reshare` | true/false | Default false. |
| `reshared_from` | string or `null` | Who the reshared post is from. |

Output: JSON with `seen`, `new`, `repeats`, `dropped` (by reason), `waiting_for_label` and any `image_problems`.

Repeats are spotted by the post's link (tracking parameters removed), and by author plus the start of the text, so a post seen on two days is only stored once.

## Labels: `./fu label FILE`

| Field | Type | Notes |
| --- | --- | --- |
| `preferences.close_friends` | list of names | Spelled as in the feed. Shown first in the digest. Replaces the stored list. |
| `preferences.max_per_person_per_week` | whole number or `null` | Counted over the last 7 days of sent digests. |
| `labels` | list | One entry per post. |

Each label:

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | From `./fu pending`. |
| `label` | `life_update`, `photos`, `everyday`, `opinion`, `bait` or `promotion` | Required. |
| `decision` | `keep` or `leave_out` | Optional. Overrides the label's default when a preference says so. |
| `pinned` | true/false | Optional. Always include, ignoring per-person limits. |
| `reason` | string | A few plain words. |

Leave out `preferences` entirely to keep what's stored.

## What's kept, and where

Everything lives in `state/` (or `$FU_HOME`), which git ignores:

- `feed.sqlite`: posts, the keys used to spot repeats, runs and sent emails.
- `images/`: downloaded photos, one folder per post.
- `outbox/`: each built email, as a `.eml` file (SMTP) or a `.json` file for the agent's email tool.
- `config.env`: settings, changed with `./fu config set`.
- `browser-profile/`: only in pop-up window mode, the browser's saved login.

`./fu prune --days 30` (part of every run) blanks the text and deletes the photos of posts handled more than 30 days ago. Their keys stay, so they never come back.

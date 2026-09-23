# Reading the extension's captures

In extension mode you never open Facebook or Instagram yourself. The Feed Unfucker Chrome extension reads the feed in the user's own Chrome once a day and saves what was on screen to a **Feed Unfucker** folder in their Google Drive, one file per read, named like `capture-facebook-2026-09-23T0812Z.json`. Your job is the part that needs judgment: working out what each saved post is, and writing it in the format `./fu ingest` takes.

Use your Google Drive tool (a connector) for everything in Drive. Captures are friends' posts: never copy them anywhere except `state/inbox/`, and never change or delete the capture files; the extension deletes them after 14 days.

## 1. Find the captures to read

1. Run `./fu since`. It prints a time: the last digest, or three days ago if there hasn't been one.
2. Search Drive for files named `capture-` in the **Feed Unfucker** folder, and keep those whose name (or created time) is after that time. Only read platforms listed in `./fu doctor`'s "platforms to read".
3. If there are none, say so in your report. If the newest capture of a platform is more than two days old, note it too: Chrome may not have been open, or the extension may have been removed.

## 2. Read each capture

Download each file and save it as `state/inbox/<the same file name>`. It looks like this:

```json
{
  "format": "feed-unfucker-capture",
  "version": 1,
  "platform": "facebook",
  "source": "friends_feed",
  "captured_at": "2026-09-23T08:12:40Z",
  "status": "ok",
  "note": "Read 23 screens.",
  "items": [
    {
      "text": "Jen Park\n2h ·\nWe did it! Keys in hand…\nLike\nComment\nShare",
      "links": ["https://www.facebook.com/jenpark/posts/1001"],
      "images": [{"url": "https://scontent.xx.fbcdn.net/…", "alt": "May be an image of a living room"}]
    }
  ]
}
```

- **status `needs_login`**: the user was logged out, or Meta showed a security check. Send a "something broke" note (see "When something goes wrong" in `AGENTS.md`) saying which site, and skip that capture.
- **status `no_posts` or `error`**: nothing to read. Mention it in your report. If it's the only capture and a digest is due, `./fu digest` builds a "something broke" note by itself.
- **status `ok`**: each item is one post as it appeared on screen, the page's own text top to bottom. Turn it into a post as described in `prompts/read-feed.md` step 3.2, with these notes:
  - **author** is usually the first line. A line like "Chris shared a post" or "Jen is with Sam" names the author too.
  - **Sponsored / Suggested**: look for "Sponsored", "Suggested for you", "Follow" next to a name, "Paid partnership", "Reels for you" and similar. Record those posts with the flags set; the fixed rules drop them.
  - **text**: the author's own words only. Leave out the name, the time, "Like", "Comment", "Share", "Reply", reaction and comment counts, "See translation", the reshared post's text and link previews.
  - **posted_at**: turn relative times ("2h", "Yesterday at 18:40", "3d") into UTC using `captured_at`, not the current time.
  - **link**: the link in `links` that's the post's own address; the first one usually is.
  - **images**: copy the `url`s. Improve each `alt` to a short plain description if the saved one is empty or unhelpful, going by the post's text; don't guess details you can't know.

  Skip items that aren't posts (a "People you may know" row, a stories strip, a "Create post" box).

Write one posts file per capture, `state/inbox/posts-<the capture's name>`, in the format in `docs/formats.md`, with `platform` and `source` from the capture and `note` naming the capture file. Then run `./fu ingest` on it. Repeats across captures are fine; `./fu ingest` drops them.

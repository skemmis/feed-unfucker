# Reading a feed

You read the feed the way a person would: open it, look, scroll, look again. Use the Playwright MCP browser tools (`browser_navigate`, `browser_snapshot`, `browser_take_screenshot`, `browser_evaluate`, `browser_press_key`, `browser_wait_for`, `browser_click`). Don't write fixed CSS selectors for Facebook's or Instagram's layout; they change often. Understand the page from snapshots and screenshots instead, and use the ARIA roles described below only to collect image and link addresses.

The hard rules in `AGENTS.md` apply throughout. Above all: the only thing you may click is "See more".

## 1. Open the feed

| Platform | Open | You should see |
| --- | --- | --- |
| facebook | `https://www.facebook.com/?filter=friends&sk=h_chr` | The friends-only feed ("Friends" under Feeds), newest first. If you land on the normal home feed, look in the left menu for **Feeds**, then the **Friends** tab, and open that. |
| instagram | `https://www.instagram.com/?variant=following` | Posts only from accounts the user follows, newest first. |

Wait 3–5 seconds for it to settle, then take a snapshot. If what you see is a login form, a checkpoint, a captcha, "confirm it's you" or any security notice, **stop now** and follow "When something goes wrong" in `AGENTS.md`.

## 2. Decide where to stop

Stop reading when the first of these happens:

- you reach posts older than the last read of this platform (see `./fu status`, `recent_reads`), or older than 3 days if there's no earlier read;
- 3 screens in a row show nothing new;
- you've scrolled 40 screens, or collected 80 posts.

## 3. Read, a screen at a time

Repeat until a stop condition is met:

1. Take a snapshot (and a screenshot when the snapshot alone doesn't make a post clear).
2. For every post you can see, note:
   - **author**: the name as shown. For a post that's a friend sharing something, the author is the friend.
   - **author_kind**: `person` for an individual; `page` for a business, brand, public figure, publication or meme page; `group` for a group post; `unknown` if you can't tell. On Instagram, verified brand and celebrity accounts are `page`.
   - **is_sponsored**: labelled "Sponsored", "Ad" or "Paid partnership".
   - **is_suggested**: labelled "Suggested for you", "Suggested post", "Because you follow…", "Reels for you", "People you may know", or anything else the platform picked rather than the author.
   - **is_reshare** and **reshared_from**: the friend is sharing someone else's post. Their own words go in `text`; if they added none, leave `text` empty.
   - **text**: the author's own words, in full. If it ends in "See more", click that "See more" (and nothing else) and read the rest. Leave out the reshared post's text, link previews, and any counts.
   - **posted_at**: the post time as ISO 8601 in UTC. Convert relative times ("3h", "Yesterday at 17:12", "2d") using the current time. If you can only guess the day, use midday. Keep what the page said in **posted_at_text**.
   - **link**: the post's own address, usually the link on its timestamp.
   - **images**: the post's own photos (not avatars, icons, emoji or ad images), with a short plain **alt** describing each one, like "Two kids on a beach".
3. Collect photo and link addresses. This small script uses ARIA roles, not layout classes, so it survives most redesigns. Run it with `browser_evaluate`:

   ```js
   () => [...document.querySelectorAll('[role="article"], article')]
     .filter(el => !el.parentElement.closest('[role="article"], article'))
     .map(el => ({
       starts_with: el.innerText.slice(0, 160),
       photos: [...el.querySelectorAll('img')]
         .filter(im => im.naturalWidth >= 300 && im.naturalHeight >= 200)
         .map(im => im.currentSrc || im.src),
       links: [...el.querySelectorAll('a[href]')].map(a => a.href)
         .filter(h => /\/posts\/|story_fbid|\/permalink|\/photo|\/p\/|\/reel\//.test(h))
         .slice(0, 5),
     }))
   ```

   Match each result to a post you noted by its opening text. If the script finds nothing (the page may use other roles), take a screenshot of each photo instead with `browser_take_screenshot` on that element, and use the saved file's path in `images` (`{"path": "...", "alt": "..."}`; relative paths are read from `state/inbox/`).
4. Scroll one screen with `browser_press_key` `PageDown`, then wait 2–5 seconds with `browser_wait_for`, varying the pause a little.

Don't worry about recording a post twice across screens or runs; `./fu ingest` drops repeats. Record ads and suggested posts too, flagged as such. The fixed rules drop them, and the digest footer counts them so the user can see the filter working.

## 4. Save the file

Write everything to `state/inbox/<platform>-<YYYY-MM-DD>.json` in the format in `docs/formats.md`:

```json
{
  "platform": "facebook",
  "source": "friends_feed",
  "note": "Read 23 screens; stopped at posts from 3 days ago.",
  "posts": [
    {
      "author": "Jen Park",
      "author_kind": "person",
      "posted_at": "2026-09-22T17:12:00Z",
      "posted_at_text": "Yesterday at 18:12",
      "text": "We did it! Keys in hand…",
      "link": "https://www.facebook.com/jenpark/posts/1001",
      "images": [{"url": "https://scontent.xx.fbcdn.net/…", "alt": "A sunny living room full of boxes"}],
      "is_sponsored": false,
      "is_suggested": false,
      "is_reshare": false,
      "reshared_from": null
    }
  ]
}
```

Then run `./fu ingest` on it. It downloads the photos straight away, because Meta's photo links stop working after a while.

# Agent instructions for Feed Unfucker

These instructions work with any coding agent that can read files, run scripts and use MCP tools. Don't rely on features specific to one harness.

## What you're doing

You're building a digest of the user's friends' posts from the feeds they're logged into, then emailing it to them.

## Hard rules

- Read-only: never like, comment, post, follow, unfollow or message anyone.
- Only visit the user's own feeds (Facebook Friends tab, Instagram Following feed). Don't crawl profiles or search.
- Run at most once per scheduled run. Don't retry in loops if a page fails to load; report it instead.
- Never read, print or store the user's password or 2FA codes. If a login or security check appears, stop and tell the user.
- Keep friends' posts out of git. State lives in the paths listed in `.gitignore`.

## Steps (to be filled in as the v0 spike lands)

1. Open the feed in the logged-in browser profile (Playwright MCP).
2. Scroll and snapshot. Extract posts as JSON: author, time, text, images, link.
3. Deduplicate against posts already seen.
4. Filter using the rules in the design doc and the user's `preferences.md`.
5. Render the email and send it with the provided script.

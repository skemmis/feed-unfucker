# Feed Unfucker

A calm email of what your actual friends are up to, and nothing else.

Social feeds now show you strangers, brands and outrage, tuned for addiction. Your friends' posts are still in there, buried. Feed Unfucker is a set of instructions for your own coding agent (Claude Code, Codex or similar). The agent reads *your* feed with *your* login, keeps the real updates from people you know, and emails you a digest.

**Status:** v0, pre-alpha. It works end to end on test data and a fake feed page, but it hasn't read a live Facebook or Instagram account yet.

## How it works

1. Your agent reads Facebook and Instagram in the Chrome you already use, where you're already logged in, through Playwright's Chrome extension. It never sees your password.
2. Once a day, it opens your Friends and Following feeds and reads them the way you would: scrolling, looking, never clicking anything but "See more".
3. Fixed rules drop ads, suggestions, pages and bare reshares. Then the agent sorts what's left, keeping life updates and photos and leaving out politics, bait and selling. Your plain-English `preferences.md` steers it.
4. Daily or weekly, it emails you the digest from your own account, through your agent's Gmail or Outlook connector. It's grouped by friend, photos first, with no like or comment counts anywhere. The footer says what was left out, so you can see the filter working.

Nothing runs on a server we operate. It runs on your own computer, in your own browser.

## Try it

On your computer, open this repo in your coding agent (the Claude desktop app, Claude Code, Codex or similar) and say:

> Set me up.

The agent does the rest. Along the way you'll add Playwright's extension to Chrome, allow it to connect, connect your email if your agent doesn't have it yet, and answer a couple of questions about who you want to hear from. Your first digest arrives straight away.

## Ground rules

- **Read-only.** The agent never likes, comments, posts or messages anyone.
- **Your account, your call.** Automated reading breaks Meta's terms of service and can get an account restricted. Use it only on an account whose owner accepts that risk.
- **No engagement metrics.** Digests never show or rank by likes, comments or follower counts.
- **Your friends' posts stay yours.** Posts and photos live in `state/` on your computer, ignored by git, and are deleted after 30 days.

## What's in here

- `AGENTS.md`: the instructions every agent reads. `CLAUDE.md` points Claude Code at it.
- `prompts/`: a full run, reading a feed, labelling posts.
- `fu` and `feed_unfucker/`: the fixed steps, in Python with no dependencies. `./fu --help` lists them.
- `docs/`: setup, cloud mode and file formats.
- `schedule/` and `scripts/scheduled-run.sh`: running it every morning.

Run the tests with `python3 -m unittest`.

## License

Copyright (C) 2026 Sam (skemmis) and contributors.

Feed Unfucker is free software under the GNU Affero General Public License v3.0. See `LICENSE`. If you change it and run it as a service for other people, you have to share your changes under the same license.

# Feed Unfucker

A calm email of what your actual friends are up to, and nothing else.

Social feeds now show you strangers, brands and outrage, tuned for addiction. Your friends' posts are still in there, buried. Feed Unfucker is a small Chrome extension plus a set of instructions for your own coding agent (Claude Code, Codex or similar). The extension reads *your* feed in *your* browser, the agent keeps the real updates from people you know, and emails you a digest.

**Status:** v0, pre-alpha. It works end to end on test data and a fake feed page, but it hasn't read a live Facebook or Instagram account yet, and the extension isn't in the Chrome Web Store yet.

## How it works

1. The Feed Unfucker extension reads Facebook and Instagram in the Chrome you already use, where you're already logged in. Nothing ever sees your password.
2. Once a day, it opens your Friends and Following feeds and reads them the way you would: scrolling, looking, never clicking anything but "See more". It saves what it saw to a folder in your own Google Drive.
3. Your agent picks that up, from wherever it runs: your computer or a cloud container. Fixed rules drop ads, suggestions, pages and bare reshares. Then the agent sorts what's left, keeping life updates and photos and leaving out politics, bait and selling. Your plain-English `preferences.md` steers it.
4. Daily or weekly, it emails you the digest from your own account, through your agent's Gmail or Outlook connector. It's grouped by friend, photos first, with no like or comment counts anywhere. The footer says what was left out, so you can see the filter working.

Nothing runs on a server we operate. The reading happens in your own browser, the posts sit in your own Drive, and the email comes from your own account.

## Try it

Open this repo in your coding agent, anywhere (the Claude app, Claude Code on the web or your computer, Codex or similar), and say:

> Set up Feed Unfucker for me.

The agent does the rest. Along the way you'll connect Google Drive and your email to the agent if it doesn't have them yet, add the Feed Unfucker extension to Chrome and click Connect and Read now, and answer a couple of questions about who you want to hear from. Your first digest arrives straight away.

## Ground rules

- **Read-only.** The agent never likes, comments, posts or messages anyone.
- **Your account, your call.** Automated reading breaks Meta's terms of service and can get an account restricted. Use it only on an account whose owner accepts that risk.
- **No engagement metrics.** Digests never show or rank by likes, comments or follower counts.
- **Your friends' posts stay yours.** They live in your own Google Drive (deleted after 14 days) and in the agent's `state/` folder, ignored by git (deleted after 30 days).

## What's in here

- `AGENTS.md`: the instructions every agent reads. `CLAUDE.md` points Claude Code at it.
- `extension/`: the Chrome extension that reads the feed.
- `prompts/`: a full run, reading the extension's captures, labelling posts.
- `fu` and `feed_unfucker/`: the fixed steps, in Python with no dependencies. `./fu --help` lists them.
- `docs/`: setup, file formats and testing.
- `schedule/` and `scripts/scheduled-run.sh`: running it every morning.

Run the tests with `python3 -m unittest`, and the extension's with `node extension/test/run.mjs`.

## License

Copyright (C) 2026 Sam (skemmis) and contributors.

Feed Unfucker is free software under the GNU Affero General Public License v3.0. See `LICENSE`. If you change it and run it as a service for other people, you have to share your changes under the same license.

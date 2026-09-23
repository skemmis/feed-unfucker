# Feed Unfucker

A calm email of what your actual friends are up to, and nothing else.

Social feeds now show you strangers, brands and outrage. Your friends' posts are still in there, buried. Feed Unfucker is a set of instructions for your own coding agent (Claude Code, Codex or similar). The agent reads *your* feed with *your* login, keeps the real updates from people you know, and emails you a digest.

**Status:** pre-alpha. Nothing works yet. See the design notes in `docs/` once they land.

## How it works (planned)

1. You log into Facebook and Instagram once, in a browser profile the agent can use.
2. On a schedule, your agent opens your Friends and Following feeds and reads them the way you would.
3. It drops ads, suggestions, reshares and engagement bait. Your plain-English `preferences.md` steers what stays.
4. It emails the digest to you, from your own inbox.

Nothing runs on a server we operate. It runs on your laptop, or as a scheduled job in your own cloud agent account.

## Ground rules

- **Read-only.** The agent never likes, comments, posts or messages anyone.
- **Your account, your call.** Automated reading breaks Meta's terms of service and can get an account restricted. Use it only on an account where you accept that risk.
- **No engagement metrics.** Digests never show or rank by likes, comments or follower counts.

## Getting started

Not yet. The first milestone is reading one day of the Facebook Friends tab into structured posts.

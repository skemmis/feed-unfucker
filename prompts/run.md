# One Feed Unfucker run

This is the whole job for a scheduled run. Work from the repo root, follow the hard rules in `AGENTS.md`, and don't ask the user anything: nobody is watching a scheduled run. Keep going past a failure on one platform, but never retry reading it.

1. **Check setup.** Run `./fu doctor`. If a line about email says `todo`, stop and say which setting is missing; don't try to fix `state/config.env` yourself. The "browser profile" line may say `todo` before the first login; that's fine.

2. **Read each feed.** For each platform listed under "platforms to read":
   1. Run `./fu can-read <platform>`. If it exits non-zero, skip that platform.
   2. Read it by following `prompts/read-feed.md`. Save what you find to `state/inbox/<platform>-<YYYY-MM-DD>.json`.
   3. Run `./fu ingest state/inbox/<platform>-<YYYY-MM-DD>.json`. If it reports a validation error, fix the file and run it once more.
   4. If you hit a login or security check, run `./fu alert --send --reason "..."` and skip the rest of the reading.

3. **Label.** Follow `prompts/label.md` until `./fu pending` shows no posts.

4. **Send if due.** Run `./fu due`. If it prints `due`, run `./fu digest --send`. If it prints `not due`, don't send.

5. **Tidy up.** Run `./fu prune --days 30`. Delete the `state/inbox/*.json` and screenshot files you made in this run; the posts are in the store now.

6. **Report.** Finish with at most five short lines: what you read (platform and number of posts), how many were kept, whether an email went out, and anything that went wrong. Don't quote friends' posts in the report.

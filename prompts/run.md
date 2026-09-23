# One Feed Unfucker run

This is the whole job for a scheduled run. Work from the repo root, follow the hard rules in `AGENTS.md`, and don't ask the user anything: nobody is watching a scheduled run. Keep going past a failure on one platform, but never retry reading it.

1. **Check setup.** Run `./fu doctor`. If `FU_EMAIL_TO` is missing, stop and say so. Note which way email goes (the "email:" line).

2. **Read each feed.** For each platform listed under "platforms to read":
   1. Run `./fu can-read <platform>`. If it exits non-zero, skip that platform.
   2. Read it by following `prompts/read-feed.md`. Save what you find to `state/inbox/<platform>-<YYYY-MM-DD>.json`.
   3. Run `./fu ingest state/inbox/<platform>-<YYYY-MM-DD>.json`. If it reports a validation error, fix the file and run it once more.
   4. If you hit a login or security check, send a "something broke" note (step 4 explains how, using `./fu alert` with `--reason "..."`) and skip the rest of the reading. If the browser can't be reached at all (Chrome closed, the extension not connected), say so in your report and skip reading; don't send a note for that.

3. **Label.** Follow `prompts/label.md` until `./fu pending` shows no posts.

4. **Send if due.** Run `./fu due`. If it prints `not due`, don't send. If it prints `due`:
   - If doctor said email goes through your email tool: run `./fu digest --prepare`. It writes a JSON file with `to`, `subject`, `html_body` and `text_body`. Send exactly that with your email tool (the HTML as the HTML body, the text as the plain-text body; don't edit either), then run `./fu sent <id>` with the id it printed. If sending fails, don't run `./fu sent`; the same email goes out next time.
   - If doctor said SMTP: run `./fu digest --send`.

5. **Tidy up.** Run `./fu prune --days 30`. Delete the `state/inbox/*.json` and screenshot files you made in this run; the posts are in the store now.

6. **Report.** Finish with at most five short lines: what you read (platform and number of posts), how many were kept, whether an email went out, and anything that went wrong. Don't quote friends' posts in the report.

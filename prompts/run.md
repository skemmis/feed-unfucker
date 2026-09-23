# One Feed Unfucker run

This is the whole job for a scheduled run. Work from the repo root, follow the hard rules in `AGENTS.md`, and don't ask the user anything: nobody is watching a scheduled run. Keep going past a failure on one platform, but never retry reading it.

The machine you're on may be brand new (a cloud container) or the same one as last time. Steps 1 and 7 make both work: the small state file in the user's Google Drive carries what has to survive between runs.

1. **Restore.** Run `./fu init` quietly. Then look in the user's Google Drive, in the **Feed Unfucker** folder, for `feed-unfucker-state.json`. If it's there, download it to `state/inbox/state.json` and run `./fu state import state/inbox/state.json`. If you have no Google Drive tool, skip this; the machine's own `state/` is all there is.

2. **Check setup.** Run `./fu doctor`. If `FU_EMAIL_TO` is missing, stop and say so. Note how the feed is read (the "reads the feed" line) and which way email goes (the "email" line).

3. **Is a digest due?** Run `./fu due`.
   - **Extension mode:** if it prints `not due`, stop here with a one-line report. There's nothing to read; the extension does the reading.
   - **Browser mode:** read anyway (the reading is spread over the week), but remember the answer for step 5.

4. **Read.**
   - **Extension mode:** follow `prompts/read-capture.md`.
   - **Browser mode:** for each platform under "platforms to read":
     1. Run `./fu can-read <platform>`. If it exits non-zero, skip that platform.
     2. Read it by following `prompts/read-feed.md`. Save what you find to `state/inbox/<platform>-<YYYY-MM-DD>.json`.
     3. Run `./fu ingest state/inbox/<platform>-<YYYY-MM-DD>.json`. If it reports a validation error, fix the file and run it once more.
     4. If you hit a login or security check, send a "something broke" note (see "When something goes wrong" in `AGENTS.md`) and skip the rest of the reading. If the browser can't be reached at all (Chrome closed, the extension not connected), say so in your report and skip reading; don't send a note for that.

   Then follow `prompts/label.md` until `./fu pending` shows no posts.

5. **Send, if due.**
   - If doctor said email goes through your email tool: run `./fu digest --prepare`. It writes a JSON file with `to`, `subject`, `html_body` and `text_body`. Send exactly that with your email tool (the HTML as the HTML body, the text as the plain-text body; don't edit either), then run `./fu sent <id>` with the id it printed. If sending fails, don't run `./fu sent`; the same email goes out next time.
   - If doctor said SMTP: run `./fu digest --send`.

6. **Tidy up.** Run `./fu prune --days 30`. Delete the files you made in `state/inbox/` this run (captures, posts files, screenshots); the posts are in the store now.

7. **Save.** If you have a Google Drive tool, run `./fu state export state/inbox/state.json` and save it to the **Feed Unfucker** folder as `feed-unfucker-state.json`, replacing the old one. It holds no post text or photos, and no passwords. Then delete `state/inbox/state.json`.

8. **Report.** Finish with at most five short lines: what you read (platform and number of posts), how many were kept, whether an email went out, and anything that went wrong. Don't quote friends' posts in the report.

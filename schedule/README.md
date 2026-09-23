# Scheduling

A run reads each feed at most once a day (`./fu can-read` enforces it) and sends the digest when it's due, so scheduling one run a day is right for both daily and weekly digests. A weekly digest goes out on `FU_WEEKLY_DAY`; if the machine was asleep that day, it goes out on the next run.

Test the run by hand first:

```sh
scripts/scheduled-run.sh claude   # or codex
```

Then check the log in `state/logs/`.

## macOS (launchd)

1. Copy `com.feedunfucker.run.plist` to `~/Library/LaunchAgents/`.
2. Edit the two paths in it to point at this repo, and `claude` to `codex` if you use Codex.
3. `launchctl load ~/Library/LaunchAgents/com.feedunfucker.run.plist`

launchd runs a missed job when the Mac wakes up, which is what you want here.

## Linux (cron)

Run `crontab -e` and add the line from `cron.example`, with the path changed. cron skips runs while the machine is off; the next day's run catches up on the digest.

## In the cloud

Most coding agents can run a prompt on a schedule in their cloud. See `docs/cloud.md` first, because the login and state work differently there.

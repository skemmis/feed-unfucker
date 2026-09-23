# Setting up

Agent: you do every step yourself. The user never edits a file, runs a command or copies anything technical. Their only actions are clicks in their own browser, plus a few plain answers in chat. Ask one thing at a time, keep each message short and friendly, and don't show them commands or file names unless they ask.

## 0. Check where you are running

Run `./fu init`, then `./fu doctor`, quietly. Don't tell the user what they printed.

**If doctor's "this machine" line says there's no screen**, you're on a cloud machine and can't reach the user's Chrome. Don't list what you ran, which files were made or the state of the branch. Tell them, in your own words and in about this many lines:

> Setup has to happen on your own computer, because I read your feed in your own Chrome. It takes a few clicks:
> 1. Download Feed Unfucker from https://github.com/skemmis/feed-unfucker/archive/refs/heads/main.zip and unzip it.
> 2. Open the Claude desktop app (https://claude.ai/download), go to **Code**, choose **Local**, and pick the unzipped folder.
> 3. Say "Set up Feed Unfucker for me" there.

If they use Codex or another agent instead, say the same with that app. Then stop; there's nothing else to do here.

**If doctor says npx is missing**, Node.js isn't installed, and the browser connection needs it. Ask the user to download and run the installer from https://nodejs.org (the "LTS" button, then click through it), then restart this session. On a Mac with Homebrew, or on Linux, you can install it yourself instead.

## 1. One sentence about the risk

Say this in your own words and wait for a yes: reading your feed automatically breaks Meta's terms, and Meta could restrict an account that looks automated. Feed Unfucker keeps that risk low (it only reads, once a day, in your own browser), but it isn't zero.

## 2. Connect their Chrome

Feed Unfucker reads the feed in the Chrome the user already uses, where they're already logged in, through Playwright's Chrome extension. The repo's `.mcp.json` already registers it for Claude Code, which may ask the user to allow the "playwright" server the first time; tell them to allow it. For Codex or another agent, register it yourself with the command `./fu mcp` prints, and restart if your harness needs that.

1. Ask the user to open https://chromewebstore.google.com/detail/playwright-extension/mmlmfjhmonkocbjadbfplnigmagldckm in Chrome and click **Add to Chrome**.
2. Open `https://www.facebook.com/?filter=friends&sk=h_chr` with `browser_navigate`. Chrome shows a Playwright page asking which tab to share, or asking to allow the connection. Tell the user to click to allow it.
3. Take a snapshot. If it shows their Friends feed, you're connected. If it shows a login page, ask them to log in to Facebook in that tab as they normally would, then check again. Never type anything into a login form yourself.
4. Ask whether they use Instagram too. If they do, check `https://www.instagram.com/?variant=following` the same way. If they don't, run `./fu config set FU_PLATFORMS facebook`.

If they don't use Chrome or Edge, use the pop-up window instead: register the server with `./fu mcp --window`, open facebook.com, and ask them to log in once in the window that appears. The login is saved for later runs.

## 3. Email

The digest goes out from the user's own email account, sent by you.

- **If you have an email tool** (a Gmail or Outlook connector): ask which address the digest should go to, and run `./fu config set FU_EMAIL_TO <address>`.
- **If you don't have one:** ask the user to connect their email in your connector settings. It's a normal "sign in with Google" or Microsoft page, done in their browser. Then continue as above.

Only if neither works, fall back to SMTP with an app password (see "Sending over SMTP" below). That's the one route that needs the user to handle a password, so don't offer it first.

## 4. What they want to see

Ask two or three short questions and write the answers into `preferences.md` in plain English:

- Who are your closest friends? They'll come first.
- Anything you'd rather never see, even from friends? (Politics is already left out.)
- Weekly or daily? Weekly is the default. For daily, run `./fu config set FU_CADENCE daily`.

Also set their timezone if you can tell it, like `./fu config set FU_TIMEZONE Europe/London`.

## 5. The first digest, now

Don't wait for the schedule. Follow `prompts/read-feed.md` for each platform, `prompts/label.md`, then `./fu digest --prepare`, send it with your email tool, and run `./fu sent <id>`. Tell the user it's in their inbox, and ask them to reply here if something is missing or shouldn't be there. Turn anything they say into a line in `preferences.md`.

## 6. Schedule it

Set it up yourself, then tell the user it's done and when it will run:

- **macOS:** write `~/Library/LaunchAgents/com.feedunfucker.run.plist` from `schedule/com.feedunfucker.run.plist` with this repo's real path and this agent (`claude` or `codex`), then run `launchctl load` on it.
- **Linux:** add the line from `schedule/cron.example` to the user's crontab, with the real path.
- **Windows:** create a daily Task Scheduler task that runs `scripts/scheduled-run.sh` through Git Bash or WSL.
- Or use your harness's own scheduled tasks, if it has them, pointed at `prompts/run.md`.

Morning runs happen without anyone watching, so Chrome would otherwise ask to allow the connection each time. Ask the user to click the Playwright extension's icon in Chrome and paste the token it shows. Then run `./fu config set PLAYWRIGHT_MCP_EXTENSION_TOKEN <token>`. If they'd rather not, runs still work, but Chrome asks them to click allow each morning.

If Chrome isn't running at that time, the run may not reach the feed. It reports that and tries again the next day.

## Sending over SMTP

For agents without an email tool. It embeds the photos in the email, so they never expire, but the user has to create an app password. For Gmail: turn on 2-Step Verification, create one at https://myaccount.google.com/apppasswords, and put it in `state/config.env` as `FU_SMTP_PASSWORD` in their own editor. Never ask them to paste it to you. Set `FU_SMTP_HOST`, `FU_SMTP_PORT` and `FU_SMTP_USER` with `./fu config set`. After that, `./fu digest --send` sends it directly.

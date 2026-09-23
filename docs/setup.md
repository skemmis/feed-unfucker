# Setting up

Agent: you do every step yourself. The user never edits a file, runs a command or copies anything technical. Their only actions are clicks in their own browser, plus a few plain answers in chat. Ask one thing at a time, keep each message short and friendly, and don't show them commands or file names unless they ask.

It doesn't matter where you're running: the user's computer, a cloud container or anything else. You never open Facebook or Instagram yourself. The Feed Unfucker Chrome extension reads the feed in the user's own Chrome and saves it to their Google Drive, and you turn that into the digest with your Google Drive and email tools.

## 0. Get ready, quietly

Run `./fu init`, then `./fu doctor`. Don't tell the user what they printed.

If the user is a developer who wants you to read the feed yourself with a browser instead, see "Reading with a browser instead" at the end.

## 1. One sentence about the risk

Say this in your own words and wait for a yes: reading your feed automatically breaks Meta's terms, and Meta could restrict an account that looks automated. Feed Unfucker keeps that risk low (it only reads, once a day, in your own browser), but it isn't zero.

## 2. Your tools

You need a **Google Drive** tool and an **email** tool (Gmail or Outlook), both usually connectors. Check which you have. For each one that's missing, ask the user to connect it in your connector settings: it's a normal "sign in with Google" page in their browser. Say which you need and why in one sentence ("so I can pick up your feed from your Drive and email you the digest"). Wait until they're connected.

## 3. The Chrome extension

1. Ask the user to add **Feed Unfucker** to Chrome from the link in `extension/README.md` ("Install"), and to make sure they're logged in to Facebook (and Instagram, if they use it) in Chrome as usual.
2. When it's added, a Feed Unfucker page opens. Ask them to click **Connect** next to Google Drive and sign in, untick Instagram if they don't use it, then click **Read now**. A small window opens, scrolls their feed for a minute or two and closes by itself.
3. Look in their Google Drive for a **Feed Unfucker** folder with a `capture-` file in it. If it's there, carry on. If a capture's status is `needs_login`, ask them to log in to that site in Chrome and click **Read now** again. If nothing shows up after a few minutes, ask them what the extension's page says.
4. If they untick Instagram, run `./fu config set FU_PLATFORMS facebook` (or `instagram` for the opposite).

## 4. Email

Ask which address the digest should go to, and run `./fu config set FU_EMAIL_TO <address>`. It's sent from their own account by your email tool.

Only if they can't connect an email tool, fall back to SMTP with an app password (see "Sending over SMTP" below). That's the one route that needs the user to handle a password, so don't offer it first.

## 5. What they want to see

Ask two or three short questions and write the answers into `preferences.md` in plain English:

- Who are your closest friends? They'll come first.
- Anything you'd rather never see, even from friends? (Politics is already left out.)
- Weekly or daily? Weekly is the default. For daily, run `./fu config set FU_CADENCE daily`.

Also set their timezone if you can tell it, like `./fu config set FU_TIMEZONE Europe/London`.

## 6. The first digest, now

Don't wait for the schedule. Follow `prompts/read-capture.md`, then `prompts/label.md`, then `./fu digest --prepare`, send it with your email tool, and run `./fu sent <id>`. Then save the state to Drive as in `prompts/run.md` step 7, so the next run can pick up from here on any machine.

Tell the user it's in their inbox, and ask them to reply here if something is missing or shouldn't be there. Turn anything they say into a line in `preferences.md`, and save the state to Drive again.

## 7. Schedule it

The run needs only this repo and your Drive and email tools, so it can run anywhere. Set up a daily run yourself, in the morning in the user's timezone, with the prompt "Follow prompts/run.md in the Feed Unfucker repo". Use whichever your harness has:

- **Its own scheduled tasks or routines** (most cloud agents have them). Point it at this repo, and make sure the scheduled run has the same Google Drive and email tools.
- **The user's computer**, if you're running there and the harness has no scheduler: see `schedule/README.md` (launchd on macOS, cron on Linux, Task Scheduler on Windows).

A run on a day with no digest due stops straight away, so daily runs are cheap. Tell the user it's done and when the next digest will arrive. The extension keeps reading by itself whenever Chrome is open during the day.

## Sending over SMTP

For agents without an email tool. It embeds the photos in the email, so they never expire, but the user has to create an app password. For Gmail: turn on 2-Step Verification, create one at https://myaccount.google.com/apppasswords, and put it in `state/config.env` as `FU_SMTP_PASSWORD` in their own editor. Never ask them to paste it to you. Set `FU_SMTP_HOST`, `FU_SMTP_PORT` and `FU_SMTP_USER` with `./fu config set`. After that, `./fu digest --send` sends it directly. SMTP settings stay on this machine, so this only suits a machine that runs every time, like the user's own computer.

## Reading with a browser instead

For developers testing the reading prompts, on their own computer. Run `./fu config set FU_READ_VIA browser`. You then read the feed yourself with the Playwright MCP server, in the user's own Chrome through Playwright's Chrome extension (https://chromewebstore.google.com/detail/playwright-extension/mmlmfjhmonkocbjadbfplnigmagldckm). The repo's `.mcp.json` registers it for Claude Code; for other agents, `./fu mcp` prints the command. Open `https://www.facebook.com/?filter=friends&sk=h_chr`, have the user allow the connection, and follow `prompts/read-feed.md`. For unattended runs, ask for the token shown in the Playwright extension and run `./fu config set PLAYWRIGHT_MCP_EXTENSION_TOKEN <token>`. `./fu mcp --window` uses a separate browser window instead of their Chrome.

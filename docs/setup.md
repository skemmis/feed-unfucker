# Setting up

Agent: walk the user through these steps one at a time, and check each one works before moving on. The user does anything involving passwords themselves; you never see them.

Before starting, make sure the user knows: automated reading breaks Meta's terms of service, and Meta can restrict an account that seems automated. Feed Unfucker keeps the risk low (read-only, once a day, a real browser, a person's pace), but it's not zero. Only use it on an account whose owner accepts that.

## 1. Check the tools

- Python 3.9 or newer (`python3 --version`). No packages to install.
- Node.js 18 or newer, for `npx` (`npx --version`). It runs the Playwright MCP browser server.
- Google Chrome. The Playwright MCP server drives it by default. Without Chrome, run `npx playwright install chromium` and add `--browser chromium` to the MCP command below. A real Chrome is better: it looks like the user's normal browser.

Then run `./fu init`. It creates `state/` (ignored by git), `state/config.env` and `preferences.md`.

## 2. Email

Ask the user to open `state/config.env` in their own editor and fill in the email settings. Don't read the file, and don't ask them to paste a password to you.

For Gmail they need an app password: turn on 2-Step Verification, then create one at https://myaccount.google.com/apppasswords and paste it into `FU_SMTP_PASSWORD`. Other providers are listed in the file.

Check it with `./fu doctor`, then send a sample digest built from made-up friends:

```sh
./fu demo --send
```

Ask the user to find it in their inbox and look at it on their phone too. If it went to spam, marking it "not spam" once usually fixes that.

## 3. The browser

The agent reads feeds through the Playwright MCP server, using a browser profile kept in `state/browser-profile/`. Run `./fu mcp` to print the exact command for this machine, with full paths, and the line to register it:

- **Claude Code:** the repo's `.mcp.json` already registers it, with paths relative to the repo, so start Claude Code from the repo folder. Approve the `playwright` server when asked, then restart the session.
- **Codex:** run the `codex mcp add playwright -- …` line that `./fu mcp` printed, then restart Codex.
- **Any other agent:** register an MCP server named `playwright` that runs the printed command.

Check it works by opening `https://example.com` with `browser_navigate`. A browser window should appear.

## 4. Log in, by hand

1. Open `https://www.facebook.com/` with `browser_navigate`.
2. Tell the user to log in in that browser window themselves, including any 2FA, and to say when they're done. Don't take snapshots or screenshots while they type.
3. Do the same for `https://www.instagram.com/` if they want Instagram too.
4. If they only want one platform, set `FU_PLATFORMS` in `state/config.env` (the user can do this, or you can edit just that line).

The login stays in `state/browser-profile/`, like a normal browser remembering them.

## 5. Preferences

Open `preferences.md` with the user and help them write what they want in plain English: close friends, topics to skip, people whose photos to always include, a per-person limit. It's read on every run.

## 6. The first read

Follow `prompts/read-feed.md` for each platform, then `prompts/label.md`. Then build a preview without sending:

```sh
./fu digest --preview state/preview.html
```

Go through it with the user. Ask them to scroll their feed by hand for a minute and say if an important post is missing, or if something slipped through that shouldn't have. Suggest `preferences.md` lines for anything they want changed.

When they're happy, send it: `./fu digest --send`.

## 7. Schedule it

See `schedule/README.md` to run every morning on this machine, or `docs/cloud.md` to run it in a cloud agent session.

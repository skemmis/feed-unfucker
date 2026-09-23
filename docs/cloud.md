# Running in the cloud

This is an advanced alternative to the normal setup, which reads the feed in your own Chrome on your computer. It needs technical steps, so it's for people who want runs to happen while their computer is off.

Many coding agents can run a scheduled job in the cloud, which fixes "my laptop was asleep". It also moves the Meta login and the posts off the user's device, so it's the riskier mode. Get local mode working first, then try cloud mode on one account and watch for security checks.

**Status: written but not yet tested on a real account.**

## What changes

| | Local | Cloud |
| --- | --- | --- |
| Login | A browser profile on the laptop | A saved login file, stored as a secret in the user's cloud agent account |
| Browser | Chrome window, visible | Headless, from a datacenter IP (more likely to trigger Meta's checks) |
| Posts and photos | Kept in `state/` for 30 days | Only for the length of the run |
| What survives between runs | Everything in `state/` | A small state file: keys of posts already seen, recent sends per friend, close friends, `preferences.md` |

Because posts don't survive between cloud runs, cloud mode needs `FU_CADENCE=daily`: each run reads and sends in one go. A weekly digest in the cloud would need the posts kept somewhere private between runs, which v0 doesn't do.

The login file can act as the user on Facebook and Instagram. Treat it like a password: keep it only in the cloud account's secrets, never in a repo.

## Set it up

1. **Make a login file, on the laptop.** This opens a fresh browser; log in to Facebook (and Instagram, in a new tab), then close the window:

   ```sh
   npx playwright open --save-storage=state/meta.storage-state.json https://www.facebook.com/
   ```

2. **Store it as a secret** in the cloud environment, as `FU_META_STORAGE_STATE`, with the file's contents base64-encoded (`base64 < state/meta.storage-state.json`). Add the email settings as secrets too: `FU_SMTP_HOST`, `FU_SMTP_USER`, `FU_SMTP_PASSWORD`, `FU_TIMEZONE` (cloud machines run on UTC) and `FU_CADENCE=daily`.

3. **Pick a private place for the state file**, such as a private GitHub repo the cloud session can push to. Set `FU_STATE_REPO` to its clone URL. Never use the public Feed Unfucker repo.

4. **Allow the network** in the cloud environment's settings: `facebook.com`, `instagram.com`, `fbcdn.net`, `cdninstagram.com`, `registry.npmjs.org` (for the MCP server) and your SMTP host.

5. **Add a setup step** that runs before the agent starts, so the MCP server can find the login file:

   ```sh
   printf '%s' "$FU_META_STORAGE_STATE" | base64 -d > state/meta.storage-state.json
   chmod 600 state/meta.storage-state.json
   ```

6. **Register the browser** with `./fu mcp --cloud`, which prints a headless command that loads the login file instead of a profile.

7. **Schedule** the job daily with this prompt:

   > Follow docs/cloud.md "Each run", then prompts/run.md.

## Each run

1. `git clone "$FU_STATE_REPO" state/private` and, if `state/private/state.json` exists, `./fu state import state/private/state.json`.
2. Follow `prompts/run.md`.
3. `./fu prune --days 0`, so no post text or photos outlive the run.
4. `./fu state export state/private/state.json`, then commit and push `state/private` with the message "Update state". That repo must stay private.

## Hybrid (fallback, not built yet)

If cloud logins get flagged, the fallback is to read on the laptop whenever it's awake and let the cloud job only filter and send. That's not in v0.

# The Feed Unfucker Chrome extension

It reads the user's Facebook Friends feed and Instagram Following feed in their own Chrome, where they're already logged in, and saves what was on screen to a **Feed Unfucker** folder in their own Google Drive. Their coding agent, running anywhere, turns those captures into the digest (`prompts/read-capture.md`).

## Install

**Not in the Chrome Web Store yet.** Until it is, use "Trying it before it's listed" below. Once it's listed, this line becomes the link and setup needs nothing else.

## What it does, and doesn't

- Once an hour it checks whether a feed is due: at most once every 20 hours per site, only between 8am and 10pm, and only while Chrome is open.
- It opens the feed in a small unfocused window, scrolls a screen at a time with pauses of 2 to 5 seconds, and closes the window. It stops after 3 screens with nothing new, 3 screens of posts it saw last time, 40 screens or 80 posts.
- The only thing it clicks is "See more" (Instagram: "more") inside a post, to read the whole text. It never likes, comments, follows or opens anything else.
- It saves the page's own text for each post, the post's links, and the addresses of its photos. It doesn't try to understand the posts; the agent does that.
- It stops at once on a login page or security check, and saves a capture with status `needs_login` so the agent can tell the user.
- Google Drive access is `drive.file`, the narrowest scope: it can only see files it made. Captures older than 14 days are deleted.
- Nothing is sent anywhere else. There's no server.

The code is small: `background.js` (when to read, and saving), `capture.js` (reading the page), `drive.js` (Google Drive) and `popup.html`/`popup.js` (the page with the buttons).

## Trying it before it's listed

For developers, and for testing with a real account. Google sign-in needs an OAuth client, so do "Before listing" steps 1 and 2 first.

1. In Chrome, open `chrome://extensions`, turn on **Developer mode**, click **Load unpacked** and pick this `extension` folder.
2. The Feed Unfucker page opens. Click **Connect**, then **Read now**.

## Before listing (project owner, once)

1. **A stable extension ID.** Done: `manifest.json` has a public `"key"`, so the extension always loads as `eadolnijhnlehcohaagfipanahcnlklo`. The Web Store may assign its own ID when it's listed; if so, add that ID to the OAuth client too.
2. **A Google OAuth client.** In Google Cloud: create a project, enable the Google Drive API, set up the OAuth consent screen (app name Feed Unfucker, scope `drive.file`), then create an OAuth client of type **Chrome extension** with the extension's ID. Put its client ID in `manifest.json` under `oauth2.client_id`. `drive.file` isn't a sensitive scope, so Google's verification is light.
3. **The Web Store listing.** A Chrome Web Store developer account (one-time fee), a short description, a privacy policy page (what's above is most of it), and the permission justifications: `scripting` and the Facebook and Instagram host permissions to read the feed, `identity` for Google Drive, `alarms` to read once a day, `storage` for the extension's own settings.
4. Put the listing's link in "Install" above and in `docs/setup.md` step 3.

## Testing

`node extension/test/run.mjs` loads the extension into Chromium with Playwright, points it at `fixtures/fake-feed/` instead of Facebook, and swaps Google Drive for local storage. It checks that a read finds all eight posts on the fake page (including the one that appears only after scrolling, and Lee's full text after "See more"), that the window closes, that a second "Read now" within the hour doesn't read again, and that a logged-out site stops at once with status `needs_login`. It needs Node and the `playwright` package.

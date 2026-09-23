# Testing without a real account

Three levels, from quickest to closest to real use.

## 1. Unit tests

```sh
python3 -m unittest
```

They cover repeats, the fixed rules, labels, per-person limits, ordering, the email's structure, state export and pruning. No network, no browser.

## 2. The demo (for developers)

```sh
./fu demo
```

Builds a digest from `fixtures/sample-feed.json` (made-up friends, generated photos), with labels already chosen. Open `state/demo/preview.html`. It's a quick check that the email looks right after changing the renderer; it isn't part of setup.

## 3. A real agent on a fake feed

`fixtures/fake-feed/` is a small made-up feed page with the things a real one has: friends' posts, an ad, a suggested post, a bare reshare, a political rant, a "See more" link, like counts to ignore, and a post that only appears after scrolling. It tests the reading and labelling prompts with your actual agent and browser.

```sh
python3 -m http.server 8765 --directory fixtures/fake-feed &
export FU_HOME=/tmp/fu-fake FU_PREFERENCES=fixtures/sample-preferences.md
./fu init
```

Register the Playwright MCP server in its own-window mode for this (`./fu mcp --window` prints the command), so the test doesn't touch your everyday Chrome. Then ask your agent:

> Follow prompts/read-feed.md, but open http://localhost:8765/ instead of the Facebook address and treat it as platform facebook. The state folder is $FU_HOME. Then follow prompts/label.md, then run ./fu digest --preview $FU_HOME/preview.html.

A good result keeps Sam, Lee (with both photos and the full text after "See more"), Robin and Alex; drops the ad, the suggested post and Chris's bare reshare by rule; and leaves out Pat's rant as `opinion`. No like or comment counts appear anywhere.

Do this in each harness you want to support (Claude Code and Codex at least) before calling a change to the prompts done.

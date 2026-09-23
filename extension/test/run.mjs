// Loads the extension into Chromium, points it at fixtures/fake-feed instead of Facebook,
// swaps Google Drive for local storage, and checks one full read.
//   node extension/test/run.mjs
// Needs the playwright package (npm i -g playwright, or NODE_PATH pointing at it).

import assert from "node:assert/strict";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const here = path.dirname(fileURLToPath(import.meta.url));
const extDir = path.resolve(here, "..");
const feedDir = path.resolve(extDir, "..", "fixtures", "fake-feed");
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "fu-ext-"));
const testExt = path.join(tmp, "extension");

// A test copy: the fake feed instead of Facebook, local storage instead of Drive, short pauses.
fs.cpSync(extDir, testExt, { recursive: true, filter: (p) => !p.includes(`${path.sep}test`) });
let gate = "password";
const server = http.createServer((req, res) => {
  if (req.url.startsWith("/gate")) {
    const pages = {
      password: '<form><input name="u"><input type="password"></form>',
      code: '<h2>Check your phone</h2><p>Enter the code we sent to your number.</p><input type="text" name="c"><button>Continue</button>',
    };
    return res.writeHead(200, { "Content-Type": "text/html" }).end(pages[gate]);
  }
  const file = path.join(feedDir, req.url === "/" ? "index.html" : path.normalize(req.url).replace(/^[/\\]+/, ""));
  if (!file.startsWith(feedDir) || !fs.existsSync(file)) return res.writeHead(404).end();
  res.writeHead(200, { "Content-Type": file.endsWith(".png") ? "image/png" : "text/html" }).end(fs.readFileSync(file));
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const feedUrl = `http://localhost:${server.address().port}/`;

const edit = (name, fn) => fs.writeFileSync(path.join(testExt, name), fn(fs.readFileSync(path.join(testExt, name), "utf8")));
edit("manifest.json", (s) => {
  const m = JSON.parse(s);
  m.host_permissions.push("http://localhost/*");
  return JSON.stringify(m);
});
edit("background.js", (s) =>
  s
    .replace("https://www.facebook.com/?filter=friends&sk=h_chr", feedUrl)
    .replace("https://www.instagram.com/?variant=following", `${feedUrl}gate`)
    .replace("minPauseMs: 2000, maxPauseMs: 5000", "minPauseMs: 300, maxPauseMs: 600")
);
edit("capture.js", (s) => s.replace('startsWith("https://")', 'startsWith("http")'));
fs.writeFileSync(
  path.join(testExt, "drive.js"),
  `export const getToken = async () => "test";
export async function saveCapture(name, record) {
  const { saved = [] } = await chrome.storage.local.get("saved");
  saved.push({ name, record });
  await chrome.storage.local.set({ saved });
}
export async function pruneCaptures() {}
`
);

const ctx = await chromium.launchPersistentContext(path.join(tmp, "profile"), {
  headless: true,
  channel: "chromium",
  executablePath: process.env.CHROMIUM_PATH || undefined,
  args: [`--disable-extensions-except=${testExt}`, `--load-extension=${testExt}`],
});
try {
  let [sw] = ctx.serviceWorkers();
  if (!sw) sw = await ctx.waitForEvent("serviceworker");
  const id = new URL(sw.url()).host;
  const page = await ctx.newPage();
  await page.goto(`chrome-extension://${id}/popup.html`);
  await page.evaluate(() => chrome.storage.local.set({ platforms: ["facebook"] }));

  const reply = await page.evaluate(() => chrome.runtime.sendMessage({ type: "fu-read-now" }));
  assert.deepEqual(reply, { ok: true });
  const { saved, runs } = await page.evaluate(() => chrome.storage.local.get(["saved", "runs"]));
  assert.equal(saved.length, 1);
  const rec = saved[0].record;
  assert.match(saved[0].name, /^capture-facebook-\d{4}-\d\d-\d\dT\d{4}Z\.json$/);
  assert.equal(rec.format, "feed-unfucker-capture");
  assert.equal(rec.status, "ok");
  const texts = rec.items.map((i) => i.text);
  assert.equal(rec.items.length, 8, `expected 8 posts, got:\n${texts.join("\n---\n")}`);
  for (const who of ["Sam Ortiz", "Lee Nakamura", "Robin Hale", "Alex Kim", "Pat Morgan", "Chris Dunn", "Glow Serum Co.", "Daily Laughs"]) {
    assert.ok(texts.some((t) => t.includes(who)), `missing ${who}`);
  }
  const lee = rec.items.find((i) => i.text.includes("Lee Nakamura"));
  assert.ok(lee.text.includes("Come and visit soon"), "See more wasn't expanded");
  assert.equal(lee.images.length, 2);
  assert.ok(!texts.join(" ").includes("undefined"));
  assert.equal(runs.facebook.status, "ok");

  const pagesLeft = ctx.pages().filter((p) => p.url().startsWith(feedUrl));
  assert.equal(pagesLeft.length, 0, "the reading window was left open");

  await page.evaluate(() => chrome.runtime.sendMessage({ type: "fu-read-now" }));
  const again = await page.evaluate(() => chrome.storage.local.get("saved"));
  assert.equal(again.saved.length, 1, "read the feed twice within an hour");

  // A logged-out site: stop at once and say so.
  await page.evaluate(() => chrome.storage.local.set({ platforms: ["instagram"] }));
  await page.evaluate(() => chrome.runtime.sendMessage({ type: "fu-read-now" }));
  const out = await page.evaluate(() => chrome.storage.local.get(["saved", "runs"]));
  assert.equal(out.saved.length, 2);
  assert.equal(out.saved[1].record.status, "needs_login");
  assert.equal(out.saved[1].record.items.length, 0);
  assert.equal(out.runs.instagram.status, "needs_login");
  assert.equal(await page.isVisible("#instagram-login"), false);  // the page shown before the read
  await page.reload();
  assert.equal(await page.isVisible("#instagram-login"), true, "no log-in link after a logged-out read");

  // After a logged-out read, Read now tries again straight away.
  await page.evaluate(() => chrome.runtime.sendMessage({ type: "fu-read-now" }));
  const retry = await page.evaluate(() => chrome.storage.local.get("saved"));
  assert.equal(retry.saved.length, 3, "couldn't retry after a logged-out read");

  // A "we sent you a code" page counts as logged out too, not as an empty feed.
  gate = "code";
  await page.evaluate(() => chrome.runtime.sendMessage({ type: "fu-read-now" }));
  const coded = await page.evaluate(() => chrome.storage.local.get("saved"));
  assert.equal(coded.saved.length, 4);
  assert.equal(coded.saved[3].record.status, "needs_login", "a code check wasn't treated as logged out");

  console.log(`ok: ${rec.items.length} posts, ${rec.items.reduce((a, i) => a + i.images.length, 0)} photos, ${rec.note}`);
} finally {
  await ctx.close();
  server.close();
  fs.rmSync(tmp, { recursive: true, force: true });
}

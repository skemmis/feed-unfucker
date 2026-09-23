// Once an hour, check whether a feed is due (at most once a day, during the day), read it
// in a small unfocused window, and save what was on screen to the user's Google Drive.

import { capturePage } from "./capture.js";
import { getToken, pruneCaptures, saveCapture } from "./drive.js";

export const FEEDS = {
  facebook: { url: "https://www.facebook.com/?filter=friends&sk=h_chr", source: "friends_feed" },
  instagram: { url: "https://www.instagram.com/?variant=following", source: "following" },
};

const MIN_HOURS_BETWEEN_READS = 20;
const DAY_START_HOUR = 8;
const DAY_END_HOUR = 22;
const KEEP_DAYS = 14;
const LIMITS = { maxScreens: 40, maxItems: 80, minPauseMs: 2000, maxPauseMs: 5000 };

let running = false;
const waiting = new Map();

chrome.runtime.onInstalled.addListener(async ({ reason }) => {
  chrome.alarms.create("fu-tick", { periodInMinutes: 60, delayInMinutes: 5 });
  if (reason === "install") chrome.tabs.create({ url: "popup.html?welcome=1" });
});
chrome.runtime.onStartup.addListener(() => chrome.alarms.create("fu-tick", { periodInMinutes: 60, delayInMinutes: 5 }));
chrome.alarms.onAlarm.addListener((a) => a.name === "fu-tick" && readDue(false));

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  if (msg.type === "fu-capture" && waiting.has(msg.runId)) {
    waiting.get(msg.runId)(msg.result);
    waiting.delete(msg.runId);
  } else if (msg.type === "fu-read-now") {
    readDue(true).then(() => reply({ ok: true }), (e) => reply({ ok: false, error: String(e) }));
    return true;
  } else if (msg.type === "fu-connect-drive") {
    getToken(true).then((t) => reply({ ok: !!t }), (e) => reply({ ok: false, error: String(e) }));
    return true;
  }
});

export async function settings() {
  const s = await chrome.storage.local.get(["platforms", "runs", "known"]);
  return { platforms: s.platforms || ["facebook", "instagram"], runs: s.runs || {}, known: s.known || {} };
}

async function readDue(now) {
  if (running) return;
  running = true;
  try {
    const { platforms, runs } = await settings();
    const hour = new Date().getHours();
    if (!now && (hour < DAY_START_HOUR || hour >= DAY_END_HOUR)) return;
    if (!(await getToken(false).catch(() => null))) return setBadge("!");
    for (const platform of platforms) {
      const last = runs[platform];
      const hoursSince = last ? (Date.now() - Date.parse(last.at)) / 3600000 : Infinity;
      if (!now && hoursSince < MIN_HOURS_BETWEEN_READS) continue;
      // Even "Read now" never reads a feed twice within an hour.
      if (now && hoursSince < 1) continue;
      await readOne(platform);
    }
    await pruneCaptures(KEEP_DAYS);
  } finally {
    running = false;
  }
}

async function readOne(platform) {
  const feed = FEEDS[platform];
  const { known, runs } = await settings();
  const runId = `${platform}-${Date.now()}`;
  const keepAlive = setInterval(() => chrome.runtime.getPlatformInfo(), 20000);
  let win;
  let result;
  try {
    win = await chrome.windows.create({ url: feed.url, type: "popup", focused: false, width: 520, height: 900 });
    const tabId = win.tabs[0].id;
    await loaded(tabId, 45000);
    const done = new Promise((resolve) => waiting.set(runId, resolve));
    await chrome.scripting.executeScript({
      target: { tabId },
      func: capturePage,
      args: [{ ...LIMITS, platform, runId, known: known[platform] || [] }],
    });
    result = await withTimeout(done, 8 * 60000, { status: "error", error: "timed out", items: [] });
  } catch (e) {
    result = { status: "error", error: String(e), items: [] };
  } finally {
    clearInterval(keepAlive);
    waiting.delete(runId);
    if (win) chrome.windows.remove(win.id).catch(() => {});
  }

  const at = new Date().toISOString();
  const record = {
    format: "feed-unfucker-capture",
    version: 1,
    platform,
    source: feed.source,
    captured_at: at,
    status: result.status,
    note: result.error || `Read ${result.screens || 0} screens.`,
    items: result.items || [],
  };
  const name = `capture-${platform}-${at.slice(0, 16).replace(/:/g, "")}Z.json`;
  await saveCapture(name, record);

  if (result.fingerprints) known[platform] = result.fingerprints.slice(0, 300);
  runs[platform] = { at, status: result.status, count: record.items.length, file: name };
  await chrome.storage.local.set({ known, runs });
  setBadge(Object.values(runs).some((r) => r.status === "needs_login" || r.status === "error") ? "!" : "");
}

function loaded(tabId, ms) {
  return withTimeout(
    new Promise((resolve) => {
      chrome.tabs.get(tabId).then((t) => t.status === "complete" && resolve(), () => {});
      const listener = (id, info) => {
        if (id === tabId && info.status === "complete") {
          chrome.tabs.onUpdated.removeListener(listener);
          resolve();
        }
      };
      chrome.tabs.onUpdated.addListener(listener);
    }),
    ms,
    undefined
  );
}

function withTimeout(promise, ms, fallback) {
  return Promise.race([promise, new Promise((r) => setTimeout(() => r(fallback), ms))]);
}

function setBadge(text) {
  chrome.action.setBadgeText({ text });
  if (text) chrome.action.setBadgeBackgroundColor({ color: "#b3261e" });
}

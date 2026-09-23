const $ = (id) => document.getElementById(id);
const PLATFORMS = ["facebook", "instagram"];

if (new URLSearchParams(location.search).has("welcome")) document.body.classList.add("welcome");

const ago = (iso) => {
  const h = Math.round((Date.now() - Date.parse(iso)) / 3600000);
  return h < 1 ? "just now" : h < 24 ? `${h}h ago` : `${Math.round(h / 24)}d ago`;
};

const describe = (run) => {
  if (!run) return { text: "Not read yet", bad: false };
  if (run.status === "ok") return { text: `${run.count} posts, ${ago(run.at)}`, bad: false };
  if (run.status === "no_posts") return { text: `No posts found, ${ago(run.at)}`, bad: true };
  if (run.status === "needs_login") return { text: "Log in to this site in Chrome", bad: true };
  return { text: `Couldn't read it, ${ago(run.at)}`, bad: true };
};

async function driveConnected() {
  try {
    const r = await chrome.identity.getAuthToken({ interactive: false });
    return !!(typeof r === "string" ? r : r && r.token);
  } catch (e) {
    return false;
  }
}

async function render() {
  const { platforms = PLATFORMS, runs = {} } = await chrome.storage.local.get(["platforms", "runs"]);
  const connected = await driveConnected();
  $("drive-status").textContent = connected ? "Connected. Saves go to a \"Feed Unfucker\" folder." : "Not connected yet";
  $("connect").hidden = connected;
  $("read-now").disabled = !connected;
  for (const p of PLATFORMS) {
    $(p).checked = platforms.includes(p);
    const d = describe(runs[p]);
    $(`${p}-status`).textContent = platforms.includes(p) ? d.text : "Off";
    $(`${p}-status`).classList.toggle("bad", platforms.includes(p) && d.bad);
  }
  $("next").hidden = !(connected && Object.values(runs).some((r) => r.status === "ok"));
}

$("connect").addEventListener("click", async () => {
  $("drive-status").textContent = "Opening Google sign-in…";
  await chrome.runtime.sendMessage({ type: "fu-connect-drive" });
  render();
});

$("read-now").addEventListener("click", async () => {
  $("read-now").disabled = true;
  $("read-status").textContent = "Reading… a small window opens and closes by itself.";
  const r = await chrome.runtime.sendMessage({ type: "fu-read-now" });
  $("read-status").textContent = r && r.ok ? "Done." : "Something went wrong. Try again in a while.";
  render();
});

for (const p of PLATFORMS) {
  $(p).addEventListener("change", async () => {
    const platforms = PLATFORMS.filter((x) => $(x).checked);
    await chrome.storage.local.set({ platforms });
    render();
  });
}

render();

// Runs inside the feed page, injected by background.js. It reads the page the way a
// person would: look, expand "See more", scroll a screen, pause, look again. It never
// clicks anything else. Posts are found by ARIA role, not by layout classes, and the
// agent works out what each one is later, so a redesign rarely breaks this.
//
// This function is serialized into the page, so it must not use anything from outside it.

export async function capturePage(opts) {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const pause = () => sleep(opts.minPauseMs + Math.random() * (opts.maxPauseMs - opts.minPauseMs));
  const known = new Set(opts.known || []);
  const seen = new Map();
  const report = (result) =>
    chrome.runtime.sendMessage({ type: "fu-capture", runId: opts.runId, result: { ...result, url: location.href } });

  const fingerprint = (text) => text.replace(/\s+/g, " ").trim().slice(0, 120);

  const blocked = () =>
    /\/login|\/checkpoint|\/challenge|two_step|accounts\/login/.test(location.href) ||
    !!document.querySelector('input[type="password"]');

  const topLevelPosts = () =>
    [...document.querySelectorAll('[role="article"], article')].filter(
      (el) => !el.parentElement || !el.parentElement.closest('[role="article"], article')
    );

  // The only click allowed anywhere: the link that expands a post's own text.
  const expandLabels = opts.platform === "instagram" ? ["more", "… more"] : ["See more"];
  const expandSeeMore = async (post) => {
    for (const b of post.querySelectorAll('[role="button"], button')) {
      if (b.closest("a[href]")) continue;
      if (expandLabels.includes((b.innerText || "").trim()) && b.offsetParent !== null) {
        b.click();
        await sleep(400 + Math.random() * 400);
      }
    }
  };

  const readPost = (post) => ({
    text: post.innerText.slice(0, 6000),
    links: [...new Set([...post.querySelectorAll("a[href]")].map((a) => a.href))]
      .filter((h) => /\/posts\/|story_fbid|\/permalink|\/photo|\/p\/|\/reel\/|\/videos\//.test(h))
      .slice(0, 6),
    images: [...post.querySelectorAll("img")]
      .filter((im) => im.naturalWidth >= 300 && im.naturalHeight >= 200)
      .map((im) => ({ url: im.currentSrc || im.src, alt: im.alt || "" }))
      .filter((im) => im.url.startsWith("https://"))
      .slice(0, 6),
  });

  try {
    await sleep(3000 + Math.random() * 2000);
    if (blocked()) return report({ status: "needs_login", items: [] });

    let quiet = 0;
    let onlyKnown = 0;
    let screens = 0;
    while (screens < opts.maxScreens && seen.size < opts.maxItems) {
      screens += 1;
      let added = 0;
      let addedNew = 0;
      for (const post of topLevelPosts()) {
        const rect = post.getBoundingClientRect();
        if (rect.bottom < 0 || rect.top > window.innerHeight * 1.5) continue;
        await expandSeeMore(post);
        const item = readPost(post);
        const fp = fingerprint(item.text);
        if (!fp || seen.has(fp)) continue;
        seen.set(fp, item);
        added += 1;
        if (!known.has(fp)) addedNew += 1;
      }
      // Stop after 3 screens with nothing new, or 3 screens of posts the last read already saw.
      quiet = added ? 0 : quiet + 1;
      onlyKnown = added && !addedNew ? onlyKnown + 1 : 0;
      if (quiet >= 3 || onlyKnown >= 3) break;
      if (blocked()) return report({ status: "needs_login", items: [...seen.values()] });
      window.scrollBy({ top: Math.round(window.innerHeight * 0.85), behavior: "smooth" });
      await pause();
    }
    const items = [...seen.values()];
    report({ status: items.length ? "ok" : "no_posts", screens, items, fingerprints: [...seen.keys()] });
  } catch (e) {
    report({ status: "error", error: String(e), items: [...seen.values()] });
  }
}

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

  // A login page, a code check or any other "confirm it's you" screen. The user deals with
  // those themselves, in a normal tab; this never types anything or clicks through them.
  const gateWords = /\b(enter (the|your) code|security code|confirmation code|we sent|code (was )?sent|verify|verification|confirm (it'?s|that it'?s) you|security check|two-factor|authentication|log in|log into|sign in)\b/i;
  const blocked = () => {
    if (/\/login|\/checkpoint|\/challenge|two_step|two_factor|auth_platform|\/recover|\/suspended|confirmemail|accounts\/login/.test(location.href)) return true;
    if (document.querySelector('input[type="password"], input[autocomplete="one-time-code"]')) return true;
    // A big dialog over the feed (not a small chat window), or a page with no posts at all.
    const bigDialogs = [...document.querySelectorAll('[role="dialog"]')].filter(
      (d) => d.getBoundingClientRect().width > window.innerWidth * 0.5
    );
    for (const box of [...bigDialogs, topLevelPosts().length ? null : document.body]) {
      if (box && box.querySelector('input:not([type="hidden"]):not([type="search"])') && gateWords.test(box.innerText || "")) return true;
    }
    return false;
  };

  // Posts, found by accessibility roles and attributes rather than layout classes. Facebook
  // and Instagram change which ones they use, so try several, then the feed's own children.
  const POST = '[role="article"], article, [aria-posinset], [data-pagelet^="FeedUnit"]';
  const topLevelPosts = () => {
    const posts = [...document.querySelectorAll(POST)].filter(
      (el) => !el.parentElement || !el.parentElement.closest(POST)
    );
    if (posts.length) return posts;
    const feed = document.querySelector('[role="feed"]');
    return feed ? [...feed.children].filter((c) => (c.innerText || "").trim().length > 40) : [];
  };

  // What the page offered, as counts only, so a read that finds nothing says why.
  const diagnose = () => ({
    title: document.title.slice(0, 80),
    role_article: document.querySelectorAll('[role="article"]').length,
    article: document.querySelectorAll("article").length,
    aria_posinset: document.querySelectorAll("[aria-posinset]").length,
    feed_unit: document.querySelectorAll('[data-pagelet^="FeedUnit"]').length,
    role_feed: document.querySelectorAll('[role="feed"]').length,
    role_main: document.querySelectorAll('[role="main"]').length,
    text_length: (document.body.innerText || "").length,
    scroll_height: document.documentElement.scrollHeight,
  });

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

  // Last resort when no post can be told apart: keep the new lines of text on each screen,
  // and the photos and links on it. The agent can still find the posts in that.
  const seenLines = new Set();
  const readScreen = () => {
    const root = document.querySelector('[role="main"]') || document.querySelector("main") || document.body;
    const lines = (root.innerText || "").split("\n").map((l) => l.trim()).filter(Boolean);
    const fresh = lines.filter((l) => !seenLines.has(l));
    fresh.forEach((l) => seenLines.add(l));
    const onScreen = (el) => {
      const r = el.getBoundingClientRect();
      return r.bottom > 0 && r.top < window.innerHeight;
    };
    const item = readPost(root);
    return {
      kind: "screen",
      text: fresh.join("\n").slice(0, 8000),
      links: item.links,
      images: [...root.querySelectorAll("img")]
        .filter((im) => onScreen(im) && im.naturalWidth >= 300 && im.naturalHeight >= 200)
        .map((im) => ({ url: im.currentSrc || im.src, alt: im.alt || "" }))
        .filter((im) => im.url.startsWith("https://"))
        .slice(0, 8),
    };
  };

  try {
    // Wait for the feed to fill in (it loads after the page does), up to about 15 seconds.
    await sleep(3000 + Math.random() * 2000);
    for (let i = 0; i < 10 && !topLevelPosts().length && !blocked(); i++) await sleep(1000);
    if (blocked()) return report({ status: "needs_login", items: [], diagnosis: diagnose() });

    if (!topLevelPosts().length) {
      const screensToRead = Math.min(opts.maxScreens, 15);
      let screens = 0;
      const items = [];
      while (screens < screensToRead) {
        screens += 1;
        const item = readScreen();
        if (item.text) items.push(item);
        if (blocked()) return report({ status: "needs_login", items, diagnosis: diagnose() });
        window.scrollBy({ top: Math.round(window.innerHeight * 0.85), behavior: "smooth" });
        await pause();
      }
      return report({ status: items.length ? "ok" : "no_posts", mode: "screens", screens, items, diagnosis: diagnose() });
    }

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
    report({ status: items.length ? "ok" : "no_posts", mode: "posts", screens, items, fingerprints: [...seen.keys()], diagnosis: items.length ? undefined : diagnose() });
  } catch (e) {
    report({ status: "error", error: String(e), items: [...seen.values()], diagnosis: diagnose() });
  }
}

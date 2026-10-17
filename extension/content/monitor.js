// Xairex Bridge content script — Facebook / Messenger / Instagram / Discord.
//
// Reports two things to the service worker:
//   * "unread"  — the unread counter from the tab title (robust primary signal:
//                 "(3) Messenger", "(1) • Instagram", "(2) Discord | #chan");
//   * "message" — best-effort observation of newly appearing conversation
//                 rows / chat lines (defensive: every heuristics path is
//                 wrapped; the DOM here is obfuscated and changes often).
//
// Privacy: everything stays local. The owner can switch any platform off in
// the extension options; nothing is read at all while a platform is off.

(() => {
  const HOST = location.hostname.replace(/^www\./, "");
  const PLATFORM = HOST.includes("messenger.com")
    ? "messenger"
    : HOST.includes("instagram.com")
      ? "instagram"
      : HOST.includes("discord.com")
        ? "discord"
        : HOST.includes("facebook.com")
          ? "facebook"
          : "";
  if (!PLATFORM) return;

  const SEND_INTERVAL_MS = 500;  // Reduced from 1500ms for real-time updates (user request 2026-10-17)
  const SCAN_DEBOUNCE_MS = 200;  // Reduced from 400ms for faster detection
  const lastSentAt = {}; // kind -> timestamp
  let lastTitleCount = -1;
  let primed = false;
  let seenRows = new Set();
  let scanTimer = null;

  function send(event) {
    const now = Date.now();
    if (now - (lastSentAt[event.kind] || 0) < SEND_INTERVAL_MS) return;
    lastSentAt[event.kind] = now;
    event.platform = PLATFORM;
    event.ts = now;
    try {
      chrome.runtime.sendMessage({ type: "xairex-content-event", event }, () => {
        void chrome.runtime.lastError; // service worker asleep — dropped, fine
      });
    } catch (error) {
      // extension context invalidated (reload) — stop quietly
    }
  }

  // ------------------------------------------------------------- unread count

  function parseCount(title) {
    const match = title.match(/^\((\d+)\)/);
    if (match) return parseInt(match[1], 10);
    if (title.startsWith("•") || title.startsWith("\u2022")) return 1;
    return 0;
  }

  function checkTitle() {
    try {
      const title = document.title || "";
      const count = Number.isFinite(parseCount(title)) ? parseCount(title) : 0;
      if (count !== lastTitleCount) {
        lastTitleCount = count;
        send({ kind: "unread", count, title });
      }
    } catch (error) {
      // never let heuristics break the page
    }
  }

  setInterval(checkTitle, 2000);  // Check every 2s instead of 4s for real-time updates
  document.addEventListener("visibilitychange", checkTitle);

  // -------------------------------------------------------- message observers

  const ROW_SELECTORS = {
    facebook: ['[role="row"]', 'a[href*="/messages/t/"]'],
    messenger: ['[role="row"]', '[role="listitem"]', 'a[href*="/t/"]'],
    instagram: ['a[href^="/direct/t/"]', '[role="listitem"]'],
    discord: ['[id^="chat-messages-"]', '[class*="messageListItem"]'],
  };

  function textOf(element) {
    return element && element.innerText ? element.innerText.trim().replace(/\s+/g, " ") : "";
  }

  function isOutgoing(text) {
    return /^(you|you sent|you:)\b/i.test(text) || /^you\b/i.test(text);
  }

  function guessSender(text) {
    // Inbox-style rows read "Name · preview · time" (or "Name\npreview").
    const first = text.split(/[·\n]/)[0].trim();
    if (first && first.length >= 2 && first.length <= 40 && !/\d{1,2}:\d{2}/.test(first)) return first;
    return "";
  }

  function scanRows() {
    try {
      const selectors = ROW_SELECTORS[PLATFORM] || [];
      let nodes = [];
      for (const selector of selectors) {
        const found = document.querySelectorAll(selector);
        if (found.length) {
          nodes = Array.from(found).slice(-10);
          break;
        }
      }
      const texts = nodes
        .map(textOf)
        .filter((text) => text.length >= 3 && text.length <= 240);
      if (!primed) {
        // First pass is the baseline: never report history as new messages.
        texts.forEach((text) => seenRows.add(text));
        primed = true;
        return;
      }
      const fresh = texts.filter((text) => !seenRows.has(text));
      if (!fresh.length) return;
      fresh.forEach((text) => seenRows.add(text));
      if (seenRows.size > 400) {
        seenRows = new Set(Array.from(seenRows).slice(-200));
      }
      const newest = fresh[fresh.length - 1];
      if (isOutgoing(newest)) return;
      if (PLATFORM === "discord" && lastTitleCount <= 0) return; // own messages never raise the badge
      send({
        kind: "message",
        sender: guessSender(newest),
        preview: newest.slice(0, 160),
        url: location.href,
        title: document.title || "",
      });
    } catch (error) {
      // defensive: DOM changed under us
    }
  }

  function attach() {
    try {
      const observer = new MutationObserver(() => {
        if (scanTimer) return;
        scanTimer = setTimeout(() => {
          scanTimer = null;
          scanRows();
        }, SCAN_DEBOUNCE_MS);
      });
      observer.observe(document.body, { childList: true, subtree: true });
      scanRows();
    } catch (error) {
      // body not ready; the title counter still works
    }
  }

  if (document.body) attach();
  else document.addEventListener("DOMContentLoaded", attach);

  checkTitle();
})();

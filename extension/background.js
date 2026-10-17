// Xairex Bridge — MV3 service worker.
//
// Talks to the local Xairex assistant over ws://127.0.0.1:<port> (loopback
// only; nothing ever leaves this machine). Facts verified 2026-10-16 against
// the official docs: WebSockets in extension service workers need Chrome
// 116+, and a message every 20 s keeps the worker (and the socket) alive —
// https://developer.chrome.com/docs/extensions/how-to/web-platform/websockets

const DEFAULTS = {
  enabled: true,
  port: 8769,
  logActivity: true,
  monitor: { facebook: true, instagram: true, messenger: true, discord: true },
};

const RECONNECT_DELAY_MS = 5000;
const KEEPALIVE_MS = 20000;
//: A "connecting" socket older than this never reported anything (machine slept
//: mid-handshake, or the peer went silent) - treat it as dead and replace it.
const CONNECT_STALE_MS = 15000;
const OUTBOX_LIMIT = 400;
const ACTIVITY_DEDUP_MS = 5000;

let socket = null;
let socketState = "idle"; // idle | connecting | connected
let connectStartedAt = 0;
let keepAliveTimer = null;
let reconnectTimer = null;
let outbox = [];
let outboxLoaded = false;
const lastLoggedTab = new Map(); // tabId -> { url, at }

// ------------------------------------------------------------------ settings

async function getSettings() {
  const stored = await chrome.storage.local.get("settings");
  const saved = stored.settings || {};
  return {
    ...DEFAULTS,
    ...saved,
    monitor: { ...DEFAULTS.monitor, ...(saved.monitor || {}) },
  };
}

async function setStatus(state, detail) {
  try {
    await chrome.storage.local.set({
      status: { state, detail: detail || "", at: Date.now() },
    });
  } catch (error) {
    // status is best effort only
  }
}

// -------------------------------------------------------------------- outbox

async function loadOutbox() {
  if (outboxLoaded) return;
  outboxLoaded = true;
  try {
    const stored = await chrome.storage.local.get("outbox");
    if (Array.isArray(stored.outbox)) outbox = stored.outbox.slice(-OUTBOX_LIMIT);
  } catch (error) {
    outbox = [];
  }
}

async function persistOutbox() {
  try {
    await chrome.storage.local.set({ outbox: outbox.slice(-OUTBOX_LIMIT) });
  } catch (error) {
    // best effort
  }
}

async function sendEvent(event) {
  const payload = { ...event, ts: event.ts || Date.now() };
  if (socket && socketState === "connected") {
    try {
      socket.send(JSON.stringify({ v: 1, type: "event", event: payload }));
      return;
    } catch (error) {
      // fall through to buffering
    }
  }
  await loadOutbox();
  outbox.push(payload);
  if (outbox.length > OUTBOX_LIMIT) outbox = outbox.slice(-OUTBOX_LIMIT);
  await persistOutbox();
}

async function flushOutbox() {
  if (!outbox.length || !socket || socketState !== "connected") return;
  const pending = outbox.slice();
  outbox = [];
  await persistOutbox();
  for (const event of pending) {
    try {
      socket.send(JSON.stringify({ v: 1, type: "event", event }));
    } catch (error) {
      outbox.push(event);
      break;
    }
  }
  if (outbox.length) await persistOutbox();
}

// --------------------------------------------------------------- connection

async function connect() {
  const settings = await getSettings();
  if (!settings.enabled) {
    await setStatus("disabled", "");
    return;
  }
  if (socket) {
    const open = socket.readyState === WebSocket.OPEN && socketState === "connected";
    const pending = socket.readyState === WebSocket.CONNECTING && Date.now() - connectStartedAt < CONNECT_STALE_MS;
    if (open || pending) return;
    // Zombie socket: no event ever fired for it (machine slept mid-handshake,
    // or the peer went silent), so socketState lies. Replace it instead of
    // blocking reconnection forever.
    try {
      socket.close();
    } catch (error) {
      // ignore
    }
    socket = null;
    socketState = "idle";
    stopKeepAlive();
  }
  await loadOutbox();
  socketState = "connecting";
  connectStartedAt = Date.now();
  let ws;
  try {
    ws = new WebSocket(`ws://127.0.0.1:${settings.port}/xairex`);
  } catch (error) {
    socketState = "idle";
    scheduleReconnect();
    return;
  }
  socket = ws;

  ws.onopen = async () => {
    socketState = "connected";
    await setStatus("connected", `127.0.0.1:${settings.port}`);
    try {
      ws.send(
        JSON.stringify({
          v: 1,
          type: "hello",
          client: "xairex-bridge",
          ext_version: chrome.runtime.getManifest().version,
          platforms: settings.monitor,
        }),
      );
    } catch (error) {
      // keepalive will retry
    }
    await flushOutbox();
    startKeepAlive();
  };
  ws.onmessage = (event) => {
    void handleMessage(event.data);
  };
  ws.onclose = () => {
    handleDown("closed");
  };
  ws.onerror = () => {
    // onclose fires right after; nothing to do here
  };
}

function handleDown(reason) {
  const wasConnected = socketState === "connected";
  socketState = "idle";
  socket = null;
  stopKeepAlive();
  if (wasConnected || reason === "closed") setStatus("offline", reason);
  scheduleReconnect();
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    void connect();
  }, RECONNECT_DELAY_MS);
}

function resetConnection() {
  stopKeepAlive();
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (socket) {
    try {
      socket.close();
    } catch (error) {
      // ignore
    }
    socket = null;
  }
  socketState = "idle";
  void connect();
}

function startKeepAlive() {
  stopKeepAlive();
  keepAliveTimer = setInterval(() => {
    if (socket && socketState === "connected" && socket.readyState === WebSocket.OPEN) {
      try {
        socket.send("keepalive");
      } catch (error) {
        handleDown("send-failed");
      }
    } else if (socket && socketState === "connected") {
      // The socket quietly died (sleep/wake). Full teardown, not just the
      // timer - otherwise the connect() guard would treat it as alive forever.
      handleDown("stale");
    } else {
      stopKeepAlive();
    }
  }, KEEPALIVE_MS);
}

function stopKeepAlive() {
  if (keepAliveTimer) {
    clearInterval(keepAliveTimer);
    keepAliveTimer = null;
  }
}

// ----------------------------------------------------------------- commands

async function handleMessage(raw) {
  if (typeof raw !== "string") return;
  let message;
  try {
    message = JSON.parse(raw);
  } catch (error) {
    return; // "keepalive" and other plain text
  }
  if (!message || message.type !== "command") return;
  const id = String(message.id || "");
  const name = String(message.name || "");
  const args = message.args || {};
  let result;
  try {
    result = await runCommand(name, args);
  } catch (error) {
    result = { ok: false, error: String((error && error.message) || error) };
  }
  if (socket && socketState === "connected") {
    try {
      socket.send(
        JSON.stringify({
          v: 1,
          type: "result",
          id,
          ok: !!result.ok,
          data: result.data || {},
          error: result.error || null,
        }),
      );
    } catch (error) {
      // connection died; the host will report a timeout
    }
  }
}

async function runCommand(name, args) {
  if (name === "get_status") {
    const settings = await getSettings();
    const unread = await getUnread();
    return {
      ok: true,
      data: {
        platforms: settings.monitor,
        unread,
        port: settings.port,
        logActivity: settings.logActivity,
        version: chrome.runtime.getManifest().version,
      },
    };
  }
  if (name === "get_unread") {
    return { ok: true, data: { unread: await getUnread() } };
  }
  if (name === "youtube") {
    return youtubeCommand(String(args.op || "title"));
  }
  if (name === "tabs") {
    return tabsCommand();
  }
  return { ok: false, error: `unknown command ${name}` };
}

// ------------------------------------------------------------------- unread

async function getUnread() {
  try {
    const stored = await chrome.storage.local.get("unread");
    return stored.unread || {};
  } catch (error) {
    return {};
  }
}

async function setUnread(platform, count) {
  const unread = await getUnread();
  unread[platform] = count;
  try {
    await chrome.storage.local.set({ unread });
  } catch (error) {
    // best effort
  }
}

// ------------------------------------------------------------------ youtube

async function youtubeCommand(op) {
  const tabs = await chrome.tabs.query({ url: ["*://www.youtube.com/*"] });
  if (!tabs.length) return { ok: false, error: "no-youtube-tab" };
  const target = tabs.find((tab) => tab.audible) || tabs.find((tab) => tab.active) || tabs[0];
  try {
    const [injection] = await chrome.scripting.executeScript({
      target: { tabId: target.id },
      func: ytControl,
      args: [op],
    });
    return injection && injection.result ? injection.result : { ok: false, error: "no-result" };
  } catch (error) {
    return { ok: false, error: "cannot-access-tab" };
  }
}

// Runs inside the YouTube page (must stay self-contained — Chrome serializes it).
function ytControl(op) {
  const video = document.querySelector("video");
  if (!video) return { ok: false, error: "no-video" };
  try {
    if (op === "play") video.play();
    else if (op === "pause") video.pause();
    else if (op === "toggle") {
      if (video.paused) video.play();
      else video.pause();
    } else if (op === "restart") {
      video.currentTime = 0;
      video.play();
    } else if (op === "next") {
      const next = document.querySelector(".ytp-next-button");
      if (next) next.click();
      else video.currentTime = video.duration;
    }
  } catch (error) {
    return { ok: false, error: String((error && error.message) || error) };
  }
  const title = (document.title || "")
    .replace(/^\(\d+\)\s*/, "")
    .replace(/\s*-\s*YouTube$/, "");
  return { ok: true, data: { title, state: video.paused ? "paused" : "playing", url: location.href } };
}

// --------------------------------------------------------------------- tabs

async function tabsCommand() {
  const tabs = await chrome.tabs.query({});
  const list = tabs
    .filter((tab) => tab.url && /^https?:/.test(tab.url))
    .slice(0, 60)
    .map((tab) => ({
      title: tab.title || "",
      url: tab.url,
      active: !!tab.active,
      audible: !!tab.audible,
    }));
  return { ok: true, data: { count: list.length, tabs: list } };
}

// ------------------------------------------------- content script plumbing

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && message.type === "xairex-content-event" && message.event && sender.tab) {
    handleContentEvent(message.event).then(
      () => sendResponse({ ok: true }),
      () => sendResponse({ ok: false }),
    );
    return true; // async response
  }
  if (message && message.type === "xairex-reconnect") {
    resetConnection();
    sendResponse({ ok: true });
    return false;
  }
  return false;
});

async function handleContentEvent(event) {
  const settings = await getSettings();
  if (!settings.enabled) return;
  const platform = String(event.platform || "");
  if (event.kind !== "activity" && !settings.monitor[platform]) return;
  if (event.kind === "unread") await setUnread(platform, Number(event.count || 0));
  await sendEvent(event);
}

// ------------------------------------------------------------ tab activity

async function logActivity(tabId, url, title) {
  const settings = await getSettings();
  if (!settings.logActivity) return;
  const now = Date.now();
  const previous = lastLoggedTab.get(tabId);
  if (previous && previous.url === url && now - previous.at < ACTIVITY_DEDUP_MS) return;
  lastLoggedTab.set(tabId, { url, at: now });
  if (lastLoggedTab.size > 200) {
    const keep = Array.from(lastLoggedTab.entries()).slice(-100);
    lastLoggedTab.clear();
    keep.forEach(([key, value]) => lastLoggedTab.set(key, value));
  }
  await sendEvent({ kind: "activity", platform: "web", url, title: title || "" });
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  const url = changeInfo.url || (changeInfo.status === "complete" ? tab.url : "");
  if (!url || !/^https?:/.test(url)) return;
  void logActivity(tabId, url, changeInfo.url ? tab.title : tab.title);
});

chrome.tabs.onActivated.addListener(async (info) => {
  try {
    const tab = await chrome.tabs.get(info.tabId);
    if (tab && tab.url && /^https?:/.test(tab.url)) {
      void logActivity(tab.tabId, tab.url, tab.title);
    }
  } catch (error) {
    // tab vanished; nothing to log
  }
});

// ---------------------------------------------------------------- lifecycle

chrome.action.onClicked.addListener(() => {
  void chrome.runtime.openOptionsPage();
});

chrome.alarms.create("xairex-reconnect", { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "xairex-reconnect") void connect();
});

chrome.runtime.onStartup.addListener(() => {
  void connect();
});

chrome.runtime.onInstalled.addListener(async () => {
  const stored = await chrome.storage.local.get("settings");
  if (!stored.settings) await chrome.storage.local.set({ settings: DEFAULTS });
  void connect();
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.settings) resetConnection();
});

// Service worker boots (fresh install, browser start, or wake-up): try to link up.
void connect();

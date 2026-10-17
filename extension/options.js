// Xairex Bridge — options page logic.

const DEFAULTS = {
  enabled: true,
  port: 8769,
  logActivity: true,
  monitor: { facebook: true, instagram: true, messenger: true, discord: true },
};

const PLATFORMS = ["facebook", "instagram", "messenger", "discord"];

const $ = (id) => document.getElementById(id);

async function load() {
  const stored = await chrome.storage.local.get("settings");
  const settings = {
    ...DEFAULTS,
    ...(stored.settings || {}),
    monitor: { ...DEFAULTS.monitor, ...((stored.settings || {}).monitor || {}) },
  };
  $("enabled").checked = !!settings.enabled;
  $("port").value = settings.port;
  $("logActivity").checked = !!settings.logActivity;
  for (const platform of PLATFORMS) {
    $(`mon-${platform}`).checked = !!settings.monitor[platform];
  }
}

async function save() {
  const settings = {
    enabled: $("enabled").checked,
    port: Math.min(65535, Math.max(1024, parseInt($("port").value, 10) || DEFAULTS.port)),
    logActivity: $("logActivity").checked,
    monitor: {},
  };
  for (const platform of PLATFORMS) {
    settings.monitor[platform] = $(`mon-${platform}`).checked;
  }
  await chrome.storage.local.set({ settings });
  $("port").value = settings.port;
  $("save-result").textContent = "saved — reconnecting…";
  try {
    chrome.runtime.sendMessage({ type: "xairex-reconnect" }, () => void chrome.runtime.lastError);
  } catch (error) {
    // service worker asleep; the 1-minute alarm will pick the settings up
  }
  setTimeout(() => {
    $("save-result").textContent = "";
  }, 2500);
}

function renderStatus(status) {
  const dot = $("status-dot");
  dot.className = "";
  const state = (status && status.state) || "offline";
  if (state === "connected") {
    dot.classList.add("dot-connected");
    $("status-text").textContent = `connected to Xairex (${status.detail || "127.0.0.1"})`;
  } else if (state === "disabled") {
    dot.classList.add("dot-disabled");
    $("status-text").textContent = "disabled — switch it on and save";
  } else {
    dot.classList.add("dot-offline");
    $("status-text").textContent = "offline — waiting for Xairex to run";
  }
}

async function refreshStatus() {
  try {
    const stored = await chrome.storage.local.get("status");
    renderStatus(stored.status);
  } catch (error) {
    renderStatus(null);
  }
}

$("save").addEventListener("click", () => void save());
$("reconnect").addEventListener("click", () => {
  try {
    chrome.runtime.sendMessage({ type: "xairex-reconnect" }, () => void chrome.runtime.lastError);
  } catch (error) {
    // ignore
  }
  refreshStatus();
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.status) refreshStatus();
});

void load();
void refreshStatus();
setInterval(refreshStatus, 2000);

# Xairex Bridge — browser extension

Connects Chrome/Edge to the local **Xairex** assistant over `ws://127.0.0.1:8769`
(loopback only — nothing ever leaves this machine, no cloud, no telemetry).

What it does while Xairex is running:

| Feature | Details |
|---|---|
| Rolling activity log | Pages you visit (URL + title) are streamed to Xairex and kept in hourly files under `data/browser/`, auto-cycled after **7 hours** (configurable in Xairex settings → Browser bridge). |
| Message watching | Facebook, Messenger, Instagram, Discord — unread counts from tab titles plus best-effort new-message observations. Switch any platform off in the options; default on. |
| New-message notes | Xairex can speak a short note when a new message arrives ("New message on Facebook from Sofia.") — ratelimited, and only while she is idle. Toggle in Xairex settings. |
| YouTube control | "skip this video", "pause youtube", "what's playing on youtube" — controls the real player even when the tab is not focused. |
| Tab list | "what tabs do I have open" answers with the active tab and count. |

## Install (one time)

1. Make sure Xairex is installed and can run (`.\scripts\start.ps1 --gui`).
2. Open `chrome://extensions` (or `edge://extensions`).
3. Switch **Developer mode** on (top right).
4. Click **Load unpacked** and select this `extension/` folder.
5. The extension appears. Click its toolbar icon to open the settings page —
   the status line should turn green: *connected to Xairex*.

That's it. The extension reconnects by itself; if Xairex is closed it simply
stays offline and buffers recent events.

## Notes & troubleshooting

- **Status stays orange ("offline")?** Xairex is not running (or the bridge is
  off / on another port in Xairex settings) → start Xairex, then click
  *RECONNECT NOW* on this page.
- **DOM heuristics** for message previews depend on Facebook/Instagram/Discord
  markup, which changes over time. The unread-count signal (tab title) is the
  robust one; the person names in message notes are best-effort.
- **Discord**: reports unread counts and channel changes; own messages are
  filtered (they never raise the badge).
- The service worker is kept alive by a 20-second keepalive while connected
  (Chrome 116+ requirement; see
  https://developer.chrome.com/docs/extensions/how-to/web-platform/websockets).
- To remove everything: `chrome://extensions` → Xairex Bridge → Remove.
  The local log in `data/browser/` self-deletes after the retention window.

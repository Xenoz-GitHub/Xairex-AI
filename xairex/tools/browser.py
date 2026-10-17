"""Browser tools (G23, D42/D43): the rolling activity log and the live extension link.

``browser_activity`` reads the 7-hour rolling log (works even when Chrome is
closed — the log outlives the browser) and narrates what is going on:
messages, unread counts, top sites. ``browser_command`` talks to the loaded
extension over the loopback bridge: connection status, unread counts, YouTube
player control and the open-tab list. Everything fails soft with an honest
sentence when the extension is not connected.
"""

from __future__ import annotations

import logging
from typing import Any

from xairex.bridge.store import ActivityStore
from xairex.tools.registry import ToolRegistry, ToolResult, ToolSpec

logger = logging.getLogger("xairex.tools")

_PLATFORM_LABELS = {
    "facebook": "Facebook",
    "messenger": "Messenger",
    "instagram": "Instagram",
    "discord": "Discord",
    "youtube": "YouTube",
    "web": "the browser",
}

_YOUTUBE_OPS = ("play", "pause", "toggle", "next", "restart", "title")


def _label(platform: str) -> str:
    return _PLATFORM_LABELS.get(str(platform), str(platform).title() or "the browser")


def _store(settings: Any) -> ActivityStore:
    return ActivityStore(
        settings.resolve_path(settings.bridge.log_dir),
        retention_hours=settings.bridge.retention_hours,
    )


def _window_label(minutes: int) -> str:
    if minutes < 60:
        return "the last minute" if minutes == 1 else f"the last {minutes} minutes"
    hours = minutes // 60
    if minutes % 60 == 0:
        return "the last hour" if hours == 1 else f"the last {hours} hours"
    return f"the last {minutes} minutes"


def _time_of(record: dict[str, Any]) -> str:
    iso = str(record.get("iso", ""))
    return iso[11:16] if len(iso) >= 16 else "?"


def _flatten(text: str, cap: int = 90) -> str:
    flat = " ".join(str(text).split())
    return flat if len(flat) <= cap else flat[: cap - 1] + "…"


def _messages_sentence(summary: dict[str, Any]) -> str | None:
    messages: dict[str, int] = summary["messages"]
    if not messages:
        return None
    total = sum(messages.values())
    bits: list[str] = []
    for platform, count in sorted(messages.items(), key=lambda item: -item[1])[:3]:
        last = summary["last_message"].get(platform, {})
        sender = str(last.get("sender", "")).strip()
        bits.append(f"{count} on {_label(platform)}" + (f" (last from {sender})" if sender else ""))
    return f"{total} new message{'s' if total != 1 else ''} — " + ", ".join(bits)


def _unread_sentence(unread: dict[str, int]) -> str | None:
    active = {platform: count for platform, count in unread.items() if count > 0}
    if not active:
        return None
    bits = [f"{count} on {_label(platform)}" for platform, count in sorted(active.items(), key=lambda item: -item[1])]
    return "unread right now: " + ", ".join(bits)


# ------------------------------------------------------------- browser_activity


def browser_activity_tool(settings: Any) -> ToolSpec:
    def handler(args: dict) -> ToolResult:
        scope = str(args.get("scope", "summary")).strip().lower()
        # Default to 15 minutes for real-time activity (user feedback: seeing old 2-17h messages)
        minutes = int(args.get("minutes", 15))
        limit = int(args.get("limit", 20))
        platform = args.get("platform")
        platform = str(platform).strip().lower() if platform else None
        store = _store(settings)
        window = _window_label(minutes)

        if scope == "summary":
            summary = store.summary(minutes=float(minutes))
            if summary["events"] == 0:
                return ToolResult(
                    True,
                    f"I don't see any browser activity in {window}. If that is unexpected, check that Chrome is "
                    "open and the Xairex Bridge extension is loaded.",
                    data=summary,
                )
            parts: list[str] = []
            messages_sentence = _messages_sentence(summary)
            if messages_sentence:
                parts.append(messages_sentence)
            domains = summary["domains"]
            if domains:
                top = ", ".join(f"{name} ({count})" for name, count in list(domains.items())[:3])
                parts.append(f"browsing mostly {top}")
            unread_sentence = _unread_sentence(summary["unread"])
            if unread_sentence:
                parts.append(unread_sentence)
            if not parts:
                parts.append(f"{summary['events']} browser events")
            return ToolResult(True, f"In {window}: " + "; ".join(parts) + ".", data=summary)

        if scope == "messages":
            records = store.read(minutes=float(minutes), platform=platform, kind="message", limit=limit)
            if not records:
                where = f" on {_label(platform)}" if platform else ""
                return ToolResult(True, f"No new messages{where} in {window}.", data={"messages": []})
            lines = []
            for record in records:
                sender = str(record.get("sender", "")).strip() or "someone"
                preview = _flatten(str(record.get("preview", "")))
                stamp = _time_of(record)
                piece = f"{stamp} {sender} on {_label(record.get('platform', 'web'))}"
                if preview:
                    piece += f": {preview}"
                lines.append(piece)
            spoken = "; ".join(lines[-4:])
            more = f" (+{len(lines) - 4} more)" if len(lines) > 4 else ""
            return ToolResult(True, f"Latest messages — {spoken}{more}.", data={"messages": records})

        if scope == "sites":
            summary = store.summary(minutes=float(minutes))
            domains = summary["domains"]
            if not domains:
                return ToolResult(True, f"No browsing history in {window}.", data=summary)
            top = ", ".join(f"{name} ({count})" for name, count in domains.items())
            total = sum(domains.values())
            return ToolResult(True, f"In {window} you visited {total} pages — top sites: {top}.", data=summary)

        # raw
        records = store.read(minutes=float(minutes), platform=platform, limit=limit)
        if not records:
            return ToolResult(True, f"No browser events in {window}.", data={"events": []})
        lines = []
        for record in records[-10:]:
            kind = str(record.get("kind", "activity"))
            piece = f"{_time_of(record)} [{kind}] {_label(record.get('platform', 'web'))}"
            title = _flatten(str(record.get("title", "")), 60)
            if title:
                piece += f" — {title}"
            lines.append(piece)
        return ToolResult(True, "Recent browser events: " + " | ".join(lines), data={"events": records})

    return ToolSpec(
        name="browser_activity",
        description=(
            "What has been happening in the browser (Facebook/Messenger/Instagram/Discord messages and "
            "browsing). Reads the rolling log kept by the Xairex browser extension (auto-cycles after "
            "several hours). Use for 'what's going on', 'any new messages', 'who messaged me', 'what "
            "have I been browsing'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["summary", "messages", "sites", "raw"],
                    "description": "summary = overview; messages = individual message lines; sites = top domains; raw = event list.",
                },
                "minutes": {
                    "type": "integer",
                    "minimum": 5,
                    "maximum": 420,
                    "description": "Look-back window in minutes (default 15 for real-time, max 420 = retention cap).",
                },
                "platform": {
                    "type": "string",
                    "description": "Optional filter: facebook, messenger, instagram, discord, youtube, web.",
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 500, "description": "Max records (default 20)."},
            },
        },
        handler=handler,
        timeout_seconds=10.0,
    )


# -------------------------------------------------------------- browser_command


def _bridge_off_message(bridge: Any) -> str:
    """Honest sentence for a bridge that is not listening on this instance."""
    if getattr(bridge, "refused_reason", None) == "already-served":
        return (
            "Another Xairex window already serves the browser bridge, so the extension is connected there. "
            "Ask in that window, or close it and restart me."
        )
    return (
        "The browser bridge is off — bridge.enabled is false or the port is busy. Turn it on in settings, "
        "then restart Xairex."
    )


def _relay(bridge: Any, name: str, args: dict[str, Any], timeout: float = 10.0) -> ToolResult | dict[str, Any]:
    if bridge is None:
        return ToolResult(
            False,
            "The browser bridge is not running. Start Xairex (the bridge listens on loopback) and load the "
            "Xairex Bridge extension in Chrome.",
        )
    if not bridge.running:
        return ToolResult(False, _bridge_off_message(bridge))
    result = bridge.send_command(name, args, timeout=timeout)
    if result is None:
        return ToolResult(
            False,
            "The Xairex Bridge extension is not connected. Open Chrome/Edge with the extension loaded — it "
            "connects automatically while Xairex is running.",
        )
    if not result.get("ok"):
        error = str(result.get("error") or "unknown error")
        if error == "timeout":
            return ToolResult(False, "The browser extension did not answer in time. Is Chrome responsive?")
        if error == "no-youtube-tab":
            return ToolResult(False, "There is no YouTube tab open right now.")
        if error == "no-video":
            return ToolResult(False, "The YouTube tab has no video playing right now.")
        return ToolResult(False, f"The browser extension reported: {error}.")
    return result


def browser_command_tool(settings: Any, bridge: Any = None) -> ToolSpec:
    def handler(args: dict) -> ToolResult:
        action = str(args.get("action", "status")).strip().lower()

        if action == "status":
            if bridge is None:
                return ToolResult(
                    False,
                    "The browser bridge is not running. Start Xairex (the bridge listens on loopback) and load "
                    "the Xairex Bridge extension in Chrome.",
                )
            status = bridge.status()
            if not status["running"]:
                return ToolResult(False, _bridge_off_message(bridge), data=status)
            if not status["connected"]:
                return ToolResult(
                    True,
                    "The bridge is listening, but the Xairex Bridge extension is not connected. Load it in "
                    "Chrome (chrome://extensions → Developer mode → Load unpacked).",
                    data=status,
                )
            unread = _unread_sentence({k: int(v.get("count", 0)) for k, v in status["unread"].items()})
            suffix = f" {unread[0].upper() + unread[1:]}." if unread else " Nothing unread."
            return ToolResult(
                True,
                f"The browser bridge is connected on port {status['port']} — {status['events_seen']} events seen."
                + suffix,
                data=status,
            )

        if action == "unread":
            live = _relay(bridge, "get_status", {}, timeout=8.0)
            if isinstance(live, ToolResult):
                # Extension not connected: fall back to the last-known counts from the log.
                snapshot = bridge.unread_report() if bridge is not None else {}
                if snapshot:
                    counts = {platform: int(values.get("count", 0)) for platform, values in snapshot.items()}
                    active = {platform: count for platform, count in counts.items() if count > 0}
                    if active:
                        bits = ", ".join(
                            f"{count} on {_label(platform)}"
                            for platform, count in sorted(active.items(), key=lambda item: -item[1])
                        )
                        return ToolResult(
                            True,
                            f"The extension is not connected right now. Last known unread: {bits}.",
                            data={"source": "log", "unread": snapshot},
                        )
                return live
            unread = live.get("data", {}).get("unread", {})
            counts = {str(platform): int(value) for platform, value in unread.items()} if isinstance(unread, dict) else {}
            sentence = _unread_sentence(counts)
            if sentence is None:
                return ToolResult(True, "Nothing unread anywhere.", data=live.get("data", {}))
            return ToolResult(True, f"In your browser, {sentence}.", data=live.get("data", {}))

        if action == "youtube":
            op = str(args.get("op", "toggle")).strip().lower()
            if op not in _YOUTUBE_OPS:
                return ToolResult(False, f"I don't know the YouTube action '{op}'.")
            relay = _relay(bridge, "youtube", {"op": op})
            if isinstance(relay, ToolResult):
                return relay
            data = relay.get("data", {})
            title = str(data.get("title", "")).strip()
            state = str(data.get("state", ""))
            if op == "title":
                if not title:
                    return ToolResult(True, "The YouTube tab is open but I can't read the video title.", data=data)
                verb = "is paused" if state == "paused" else "is playing"
                return ToolResult(True, f"On YouTube, '{title}' {verb}.", data=data)
            if op == "next":
                extra = f" Now playing: '{title}'." if title else ""
                return ToolResult(True, "Skipped to the next video." + extra, data=data)
            if op == "play":
                text = f"Playing '{title}' on YouTube." if title else "Playing on YouTube."
                return ToolResult(True, text, data=data)
            if op == "pause":
                return ToolResult(True, "Paused the YouTube video.", data=data)
            if op == "restart":
                return ToolResult(True, "Restarted the YouTube video.", data=data)
            # toggle
            if state == "paused":
                return ToolResult(True, "Paused the YouTube video.", data=data)
            if state == "playing":
                return ToolResult(True, "The YouTube video is playing.", data=data)
            return ToolResult(True, "Toggled playback on YouTube.", data=data)

        if action == "tabs":
            relay = _relay(bridge, "tabs", {})
            if isinstance(relay, ToolResult):
                return relay
            data = relay.get("data", {})
            tabs = data.get("tabs", [])
            if not isinstance(tabs, list) or not tabs:
                return ToolResult(True, "No browser tabs are open.", data=data)
            active = next((tab for tab in tabs if tab.get("active")), None)
            active_title = _flatten(str(active.get("title", ""))) if active else ""
            spoken = f"You have {len(tabs)} tabs open"
            if active_title:
                spoken += f"; the active one is '{active_title}'"
            return ToolResult(True, spoken + ".", data=data)

        return ToolResult(False, f"I don't know the browser action '{action}'.")

    return ToolSpec(
        name="browser_command",
        description=(
            "Talk to the browser through the Xairex Bridge extension: connection status, unread message "
            "counts, YouTube video control (play/pause/toggle/next/restart/title), and the open-tab list. "
            "Requires the extension to be loaded in Chrome and Xairex to be running."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "unread", "youtube", "tabs"],
                    "description": "What to do in the browser.",
                },
                "op": {
                    "type": "string",
                    "enum": list(_YOUTUBE_OPS),
                    "description": "YouTube operation (only with action='youtube'): play, pause, toggle, next, restart, title.",
                },
            },
            "required": ["action"],
        },
        handler=handler,
        timeout_seconds=20.0,
    )


def register_browser_tools(registry: ToolRegistry, settings: Any, bridge: Any = None) -> None:
    """Register both browser tools (kept together so callers import one helper)."""
    registry.register(browser_activity_tool(settings))
    registry.register(browser_command_tool(settings, bridge))

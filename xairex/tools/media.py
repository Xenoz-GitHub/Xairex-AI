"""media_control: play/pause/next/previous via virtual media keys (ctypes)."""

from __future__ import annotations

import ctypes

from xairex.tools.registry import ToolResult, ToolSpec

_VK = {
    "play_pause": 0xB3,
    "next": 0xB0,
    "previous": 0xB1,
    "stop": 0xB2,
}

_LABELS = {
    "play_pause": "play/pause",
    "next": "next track",
    "previous": "previous track",
    "stop": "stop",
}


def _press(code: int) -> None:
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    user32.keybd_event(code, 0, 0, 0)
    user32.keybd_event(code, 0, 2, 0)


def media_control_tool() -> ToolSpec:
    def handler(args: dict) -> ToolResult:
        action = str(args.get("action", "")).strip().lower()
        code = _VK.get(action)
        if code is None:
            return ToolResult(False, f"I don't know the media action '{action}'.")
        _press(code)
        return ToolResult(True, f"Sent {_LABELS[action]} to the media player.")

    return ToolSpec(
        name="media_control",
        description="Control media playback in the active player (play/pause, next, previous, stop).",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": list(_VK),
                    "description": "Media key to send.",
                }
            },
            "required": ["action"],
        },
        handler=handler,
        timeout_seconds=5.0,
    )

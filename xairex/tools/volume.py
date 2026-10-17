"""set_volume: absolute volume control via pycaw (SAC-probed on this machine).

pycaw (pure Python + comtypes) passed the Smart App Control import probe on
2026-10-16 and can read/write the master volume endpoint. When pycaw is
unavailable the tool degrades to virtual volume keys (up/down/mute only);
"set" and "status" need the endpoint.
"""

from __future__ import annotations

import ctypes
import logging
from typing import Any

from xairex.config import Settings
from xairex.tools.registry import ToolResult, ToolSpec

logger = logging.getLogger("xairex.tools.volume")

_VK_VOLUME_UP = 0xAF
_VK_VOLUME_DOWN = 0xAE
_VK_VOLUME_MUTE = 0xAD


def _press_vk(code: int) -> None:
    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    user32.keybd_event(code, 0, 0, 0)
    user32.keybd_event(code, 0, 2, 0)


def _endpoint() -> Any | None:
    """The pycaw master-volume endpoint, or None when pycaw is unavailable."""
    try:
        from ctypes import POINTER, cast

        from comtypes import CLSCTX_ALL, CoInitialize
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    except Exception:
        logger.debug("pycaw not available; using virtual volume keys", exc_info=True)
        return None
    try:
        CoInitialize()
        device = AudioUtilities.GetSpeakers()
        existing = getattr(device, "EndpointVolume", None)
        if existing is not None:  # older pycaw returns the interface directly
            return existing
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))
    except Exception:
        logger.exception("Could not open the volume endpoint")
        return None


def set_volume_tool(settings: Settings) -> ToolSpec:
    step = settings.tools.volume_step_percent / 100.0

    def handler(args: dict) -> ToolResult:
        action = str(args.get("action", "")).strip().lower()
        endpoint = _endpoint()

        if action == "status":
            if endpoint is None:
                return ToolResult(False, "I can't read the exact volume on this machine (pycaw is missing).")
            percent = round(float(endpoint.GetMasterVolumeLevelScalar()) * 100)
            muted = bool(endpoint.GetMute())
            suffix = " (muted)" if muted and percent > 0 else ""
            return ToolResult(True, f"Volume is {percent} percent{suffix}.", data={"percent": percent})

        if action == "set":
            percent = args.get("percent")
            if percent is None:
                return ToolResult(False, "Tell me a percentage between 0 and 100 to set the volume.")
            if endpoint is None:
                return ToolResult(
                    False, "Setting an exact volume needs pycaw; I can only go up, down or mute right now."
                )
            endpoint.SetMasterVolumeLevelScalar(float(percent) / 100.0, None)
            return ToolResult(True, f"Volume set to {int(percent)} percent.", data={"percent": int(percent)})

        if action in ("up", "down"):
            if endpoint is not None:
                current = float(endpoint.GetMasterVolumeLevelScalar())
                new_value = max(0.0, min(1.0, current + (step if action == "up" else -step)))
                endpoint.SetMasterVolumeLevelScalar(new_value, None)
                return ToolResult(
                    True,
                    f"Volume {'up' if action == 'up' else 'down'} to {round(new_value * 100)} percent.",
                    data={"percent": round(new_value * 100)},
                )
            presses = max(1, round(settings.tools.volume_step_percent / 2))
            for _ in range(presses):
                _press_vk(_VK_VOLUME_UP if action == "up" else _VK_VOLUME_DOWN)
            return ToolResult(True, f"Volume {action}.")

        if action in ("mute", "unmute"):
            mute = action == "mute"
            if endpoint is not None:
                endpoint.SetMute(mute, None)
                return ToolResult(True, "Muted." if mute else "Unmuted.")
            _press_vk(_VK_VOLUME_MUTE)  # virtual key toggles
            return ToolResult(True, "Toggled the mute key.")

        return ToolResult(False, f"I don't know the volume action '{action}'.")

    return ToolSpec(
        name="set_volume",
        description="Control the system volume: up, down, set an exact percentage, mute or read the current level.",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["up", "down", "set", "mute", "unmute", "status"],
                    "description": "What to do with the volume.",
                },
                "percent": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Target percentage for action 'set'.",
                },
            },
            "required": ["action"],
        },
        handler=handler,
        timeout_seconds=5.0,
    )

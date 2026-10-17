"""wifi_control: best-effort adapter toggle with settings fallback (D24).

Turning the adapter on/off needs administrator rights; when Windows refuses,
the tool reports why and asks the runtime to open the Wi-Fi settings pane
(``data["open"]``) instead of trying to elevate behind the user's back.
"""

from __future__ import annotations

import logging
import subprocess

from xairex.config import Settings
from xairex.tools.registry import ToolResult, ToolSpec

logger = logging.getLogger("xairex.tools.wifi")

WIFI_SETTINGS_URI = "ms-settings:network-wifi"


def _run_netsh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["netsh", *args],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=15,
        check=False,
    )


def _parse_interfaces(output: str) -> list[tuple[str, str]]:
    """[(name, state)] parsed from ``netsh wlan show interfaces`` output."""
    interfaces: list[tuple[str, str]] = []
    name: str | None = None
    state: str | None = None
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "name":
            if name and state:
                interfaces.append((name, state))
            name, state = value, None
        elif key == "state" and name:
            state = value
    if name and state:
        interfaces.append((name, state))
    return interfaces


def _pick_interface(settings: Settings) -> tuple[str | None, str | None]:
    configured = settings.tools.wifi_interface.strip()
    if configured:
        try:
            result = _run_netsh(["wlan", "show", "interfaces"])
        except (OSError, subprocess.SubprocessError):
            return configured, None
        for name, state in _parse_interfaces(result.stdout or ""):
            if name.lower() == configured.lower():
                return name, state
        return configured, None
    try:
        result = _run_netsh(["wlan", "show", "interfaces"])
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("netsh wlan show interfaces failed: %s", exc)
        return None, None
    interfaces = _parse_interfaces(result.stdout or "")
    if not interfaces:
        return None, None
    return interfaces[0]


def _looks_like_refusal(output: str) -> bool:
    lowered = output.lower()
    return any(marker in lowered for marker in ("elevation", "access is denied", "denied", "administrator"))


def wifi_control_tool(settings: Settings) -> ToolSpec:
    def handler(args: dict) -> ToolResult:
        action = str(args.get("action", "")).strip().lower()
        name, state = _pick_interface(settings)

        if action == "status":
            if name is None:
                return ToolResult(False, "I couldn't find a Wi-Fi adapter on this machine.")
            if state is None:
                return ToolResult(True, f"Wi-Fi adapter '{name}' is present (state unknown).")
            return ToolResult(True, f"Wi-Fi is {state}.")

        if action not in ("on", "off"):
            return ToolResult(False, f"I don't know the wifi action '{action}'.")

        if name is None:
            return ToolResult(False, "I couldn't find a Wi-Fi adapter to switch.")

        desired = "enabled" if action == "on" else "disabled"
        try:
            result = _run_netsh(["interface", "set", "interface", f"name={name}", f"admin={desired}"])
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug("netsh set interface failed: %s", exc)
            return ToolResult(
                False,
                f"I can't switch Wi-Fi {action} right now. I opened the Wi-Fi settings so you can do it there.",
                data={"open": WIFI_SETTINGS_URI},
            )

        output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
        if result.returncode != 0 or _looks_like_refusal(output):
            reason = output.splitlines()[0] if output else "Windows refused the change"
            return ToolResult(
                False,
                f"I can't switch Wi-Fi {action} without administrator rights ({reason}). "
                "I opened the Wi-Fi settings so you can do it there.",
                data={"open": WIFI_SETTINGS_URI},
            )
        return ToolResult(True, f"Wi-Fi turned {action}.")

    return ToolSpec(
        name="wifi_control",
        description=(
            "Check or change the Wi-Fi adapter (on/off). Needs administrator rights to switch; "
            "without them the settings app is opened instead."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["on", "off", "status"],
                    "description": "What to do with Wi-Fi.",
                }
            },
            "required": ["action"],
        },
        handler=handler,
        timeout_seconds=20.0,
    )

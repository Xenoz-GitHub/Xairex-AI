"""system_info: local date/time and machine status (read-only, CPU-only)."""

from __future__ import annotations

import datetime as _dt
import os

from xairex.tools.registry import ToolResult, ToolSpec


def _time_text() -> str:
    now = _dt.datetime.now()
    return "It is " + now.strftime("%I:%M %p").lstrip("0") + "."


def _date_text() -> str:
    now = _dt.datetime.now()
    return f"Today is {now:%A, %B} {now.day}, {now:%Y}."


def _cpu_text() -> str:
    import psutil

    percent = psutil.cpu_percent(interval=0.3)
    return f"CPU usage is {percent:.0f} percent."


def _memory_text() -> str:
    import psutil

    mem = psutil.virtual_memory()
    used_gb = mem.used / 1024**3
    total_gb = mem.total / 1024**3
    return f"Memory usage is {mem.percent:.0f} percent ({used_gb:.1f} of {total_gb:.1f} GB in use)."


def _disk_text() -> str:
    import psutil

    root = (os.environ.get("SystemDrive") or "C:") + "\\"
    usage = psutil.disk_usage(root)
    letter = root.rstrip("\\")
    return f"Disk {letter} is {usage.percent:.0f} percent used, with {usage.free / 1024**3:.0f} GB free."


def _battery_text() -> str:
    import psutil

    battery = psutil.sensors_battery()
    if battery is None:
        return "This machine doesn't report a battery."
    state = "plugged in" if battery.power_plugged else "on battery"
    return f"Battery is at {battery.percent:.0f} percent, {state}."


_ACTIONS = {
    "time": _time_text,
    "date": _date_text,
    "cpu": _cpu_text,
    "memory": _memory_text,
    "disk": _disk_text,
    "battery": _battery_text,
}


def system_info_tool() -> ToolSpec:
    def handler(args: dict) -> ToolResult:
        action = str(args.get("action", "")).strip().lower()
        func = _ACTIONS.get(action)
        if func is None:
            return ToolResult(False, f"I can't answer '{action}'. Try time, date, cpu, memory, disk or battery.")
        try:
            return ToolResult(True, func())
        except Exception as exc:  # noqa: BLE001 - psutil quirks must not crash the engine
            return ToolResult(False, f"I couldn't read that system value ({type(exc).__name__}).")

    return ToolSpec(
        name="system_info",
        description="Read local machine status: time, date, CPU usage, memory, disk, battery.",
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["time", "date", "cpu", "memory", "disk", "battery"],
                    "description": "Which value to read.",
                }
            },
            "required": ["action"],
        },
        handler=handler,
        timeout_seconds=5.0,
    )

"""Typed tool registry and the safe OS-control tool set (Phase G, spec section 6).

Every tool call goes through :meth:`xairex.tools.registry.ToolRegistry.execute` —
schema-validated, time-bounded and audited. Model output never executes
directly: only registered tools run, and no tool accepts shell command text
(golden rule 5, amended by D37–D39).
"""

from __future__ import annotations

from typing import Any

from xairex.config import Settings
from xairex.tools.registry import AuditHook, ToolRegistry, ToolResult, ToolSpec, validate_arguments

__all__ = [
    "AuditHook",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "register_default_tools",
    "validate_arguments",
]


def register_default_tools(registry: ToolRegistry, settings: Settings, *, bridge: Any = None, db: Any = None) -> ToolRegistry:
    """Register the built-in tool set (local imports keep this module light).

    *bridge* is the live :class:`~xairex.bridge.server.BridgeServer` when one is
    running; ``browser_command`` degrades to an honest sentence without it.
    
    *db* is the Database instance for memory tools (G14).
    """
    from xairex.tools.admin import admin_command_tool
    from xairex.tools.applications import find_app_tool, open_app_tool
    from xairex.tools.browser import browser_activity_tool, browser_command_tool
    from xairex.tools.defender import defender_scan_tool
    from xairex.tools.files import (
        append_file_tool,
        copy_file_tool,
        edit_file_tool,
        find_files_tool,
        make_directory_tool,
        move_file_tool,
        organize_folder_tool,
        write_file_tool,
    )
    from xairex.tools.keyboard import press_keys_tool, type_text_tool
    from xairex.tools.media import media_control_tool
    from xairex.tools.memory import recall_tool, remember_tool
    from xairex.tools.shell_command import shell_command_tool
    from xairex.tools.system_info import system_info_tool
    from xairex.tools.turbo_cpp import turbo_write_code_tool
    from xairex.tools.volume import set_volume_tool
    from xairex.tools.vscode import vscode_control_tool
    from xairex.tools.websites import open_website_tool, search_web_tool
    from xairex.tools.wifi import wifi_control_tool

    registry.register(open_app_tool(settings))
    registry.register(find_app_tool(settings))
    registry.register(open_website_tool(settings))
    registry.register(search_web_tool(settings))
    registry.register(type_text_tool())
    registry.register(press_keys_tool())
    registry.register(set_volume_tool(settings))
    registry.register(media_control_tool())
    registry.register(wifi_control_tool(settings))
    registry.register(system_info_tool())
    registry.register(find_files_tool(settings))
    registry.register(write_file_tool(settings))
    registry.register(append_file_tool(settings))
    registry.register(edit_file_tool(settings))
    registry.register(move_file_tool(settings))
    registry.register(copy_file_tool(settings))
    registry.register(make_directory_tool(settings))
    registry.register(organize_folder_tool(settings))
    registry.register(defender_scan_tool(settings))
    registry.register(turbo_write_code_tool(settings))
    registry.register(vscode_control_tool())
    registry.register(browser_activity_tool(settings))
    registry.register(browser_command_tool(settings, bridge))
    registry.register(admin_command_tool(settings))
    registry.register(shell_command_tool())  # General-purpose command execution (user request 2026-10-17)
    
    # Memory tools (G14 - persistent memory, no amnesia)
    if db is not None:
        registry.register(remember_tool(settings, db))
        registry.register(recall_tool(settings, db))
    
    return registry

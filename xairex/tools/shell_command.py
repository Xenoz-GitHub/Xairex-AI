"""General-purpose shell command execution tool (user request 2026-10-17).

Allows Xairex to run ANY command-line tool for penetration testing:
nmap, gobuster, sqlmap, curl, etc. ONLY for the owner's authorized testing.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Any

from xairex.tools.registry import ToolResult, ToolSpec

logger = logging.getLogger("xairex.tools")


def shell_command_tool() -> ToolSpec:
    """Execute any shell command (AUTHORIZED USERS ONLY - owner's testing)."""

    def handler(args: dict) -> ToolResult:
        command = str(args.get("command", "")).strip()
        if not command:
            return ToolResult(False, "Tell me what command to run.")

        # Parse command (split by spaces, handle quotes)
        import shlex

        try:
            cmd_parts = shlex.split(command)
        except ValueError as exc:
            return ToolResult(False, f"Invalid command syntax: {exc}")

        # Safety: Don't allow certain dangerous operations without explicit user confirmation
        dangerous_patterns = ["rm -rf /", "format", "del /f /s /q C:\\"]
        if any(pattern in command.lower() for pattern in dangerous_patterns):
            return ToolResult(
                False,
                "That command looks destructive. If you really want to run it, use the admin_command tool instead.",
            )

        try:
            # Run with timeout
            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                timeout=args.get("timeout", 60),
                check=False,
            )

            success = result.returncode == 0
            output = result.stdout.strip() if result.stdout else ""
            error = result.stderr.strip() if result.stderr else ""

            # Format output for display
            if success:
                message = f"Command completed (exit code {result.returncode})"
                if output:
                    # Truncate very long output
                    display_output = output if len(output) <= 2000 else output[:2000] + "... (truncated)"
                    message += f"\n\nOutput:\n{display_output}"
            else:
                message = f"Command failed (exit code {result.returncode})"
                if error:
                    message += f"\n\nError:\n{error}"
                if output:
                    message += f"\n\nOutput:\n{output}"

            return ToolResult(success, message, data={"exit_code": result.returncode, "stdout": output, "stderr": error})

        except subprocess.TimeoutExpired:
            return ToolResult(False, f"Command timed out after {args.get('timeout', 60)} seconds.")
        except FileNotFoundError:
            return ToolResult(False, f"Command not found: {cmd_parts[0]}. Make sure it's installed and in PATH.")
        except Exception as exc:  # noqa: BLE001
            return ToolResult(False, f"Failed to run command: {exc}")

    return ToolSpec(
        name="shell_command",
        description=(
            "Execute any shell/command-line tool for penetration testing: nmap, gobuster, sqlmap, nikto, "
            "curl, wget, netcat, etc. Use for reconnaissance, scanning, and exploitation when specific tools "
            "aren't available. Examples: 'nmap -sV example.com', 'curl -X POST http://site.com/login', "
            "'gobuster dir -u http://site.com -w wordlist.txt'. ONLY use for authorized security testing."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The complete shell command to execute (e.g., 'nmap -sV 192.168.1.1')",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 60, max 300 for long scans)",
                    "minimum": 1,
                    "maximum": 300,
                },
            },
            "required": ["command"],
        },
        handler=handler,
        timeout_seconds=310.0,  # Allow up to 5 minutes for long scans
    )

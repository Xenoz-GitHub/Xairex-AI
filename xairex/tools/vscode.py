"""VS Code workflow (G24, D44): open folders/files and drive the integrated terminal.

The owner asked for full Visual Studio Code support: open it, create a folder,
create a file, write code, and run commands in the terminal "flawlessly".

Opening a path needs no keystrokes at all — VS Code ships its own launcher
(``code`` / ``code.cmd`` / ``Code.exe``) which reuses the last window (``-r``)
or opens a new one (``-n``). The integrated terminal has no such switch, so
that action uses the same live-verified Win32 foreground machinery as the Turbo
C++ flow (:mod:`xairex.tools.winfocus`, G22): bring the main window to the
front, open a terminal through the command palette (Ctrl+Shift+P →
"Terminal: Create New Terminal"), then type the command through
:mod:`xairex.tools.keyboard` and press Enter.

Two hazards, both measured live 2026-10-16:

* VS Code's stock "new terminal" keybinding is Ctrl+Shift+` — and **Shift+` is
  Discord's global overlay toggle**. The overlay popped up, took keyboard
  focus, and the typed commands ("g++ hello.cpp …") went into a Discord chat
  instead of the terminal. Hence: the command palette route (no backtick
  anywhere), a focus guard that Esc-dismisses foreign foreground windows and
  re-focuses VS Code *immediately before typing*, and an honest failure
  instead of typing blind.
* VS Code's terminal is Electron/Chromium and ignores ``KEYEVENTF_UNICODE``
  injection, so all typing here uses scan-code (``mode="vk"``) events.

Keystrokes only ever go to a VS Code window this tool has just verified is in
the foreground — never to whatever window happens to be busy.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import time
from pathlib import Path

from xairex.tools import keyboard
from xairex.tools.registry import ToolResult, ToolSpec
from xairex.tools.winfocus import focus, pids, windows_of

#: Settle times (module-level so tests can zero them).
_SETTLE_AFTER_OPEN = 1.2
_SETTLE_AFTER_FOCUS = 0.5
_SETTLE_PALETTE = 0.6
_SETTLE_TERMINAL = 1.6

#: Terminal creation goes through the command palette on purpose: the stock
#: "new terminal" keybinding is Ctrl+Shift+`, and Shift+` toggles Discord's
#: overlay (live 2026-10-16 — the overlay stole the typing).
_PALETTE_COMBO = "ctrl+shift+p"
_PALETTE_TERMINAL = "Terminal: Create New Terminal"

#: Longest terminal command this tool will type (safety rail).
_MAX_COMMAND = 500

#: VS Code's Electron main-window class.
_WINDOW_CLASS = "Chrome_WidgetWin_1"

_sleep = time.sleep


def find_code_cli() -> str | None:
    """Path to VS Code's launcher: ``code`` on PATH, else the standard install."""
    found = shutil.which("code")
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        root = Path(local) / "Programs" / "Microsoft VS Code"
        for candidate in (root / "bin" / "code.cmd", root / "Code.exe"):
            if candidate.is_file():
                return str(candidate)
    return None


def launch_code(args: list[str]) -> tuple[bool, str]:
    """Fire-and-forget the VS Code launcher with *args*; returns ``(ok, detail)``.

    The launcher may either hand the request to a running instance or become
    the app process itself, so the call must never wait for it to exit.
    """
    cli = find_code_cli()
    if cli is None:
        return False, "VS Code does not seem to be installed — I couldn't find its 'code' launcher."
    if cli.lower().endswith((".cmd", ".bat")):
        cmdline = ["cmd", "/c", cli, *args]
    else:
        cmdline = [cli, *args]
    try:
        subprocess.Popen(
            cmdline,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
        )
    except OSError as exc:
        return False, f"I couldn't start VS Code: {exc}"
    return True, cli


def resolve_path(raw: str) -> Path:
    """Expand variables and ``~`` in a user-spoken path."""
    text = os.path.expandvars(str(raw or "").strip().strip('"'))
    return Path(text).expanduser()


def main_window() -> int:
    """A visible VS Code main window: the foreground one when possible, else topmost."""
    foreground = int(ctypes.windll.user32.GetForegroundWindow())
    fallback = 0
    for pid_value in pids("Code.exe"):
        for hwnd, title, cls in windows_of(pid_value):
            if cls != _WINDOW_CLASS or not title.strip():
                continue
            if hwnd == foreground:
                return hwnd
            if not fallback:
                fallback = hwnd
    return fallback


def _open(path_raw: str, new_window: bool) -> ToolResult:
    if not str(path_raw or "").strip():
        # "open vs code" / "open VS Code" — no path, just bring up the editor.
        ok, detail = launch_code(["-n"] if new_window else [])
        if not ok:
            return ToolResult(False, detail)
        _sleep(_SETTLE_AFTER_OPEN)
        return ToolResult(True, "Opened VS Code.", data={"launcher": detail})
    target = resolve_path(path_raw)
    fresh_file = False
    if not target.exists():
        if target.parent.is_dir() and target.suffix:
            fresh_file = True  # VS Code shows a not-yet-saved buffer for this
        else:
            return ToolResult(
                False,
                f"I couldn't open {target} in VS Code — that path does not exist yet. "
                "Ask me to create the folder or file first.",
            )
    ok, detail = launch_code(["-n" if new_window else "-r", str(target)])
    if not ok:
        return ToolResult(False, detail)
    _sleep(_SETTLE_AFTER_OPEN)
    if fresh_file:
        return ToolResult(
            True,
            f"Opened a new file {target.name} in VS Code — tell me the code to write and I'll fill it in.",
            data={"path": str(target), "new": True},
        )
    return ToolResult(True, f"Opened {target} in VS Code.", data={"path": str(target)})


def _foreground() -> int:
    return int(ctypes.windll.user32.GetForegroundWindow())


def _ensure_foreground(hwnd: int, attempts: int = 3) -> bool:
    """True once *hwnd* really owns the keyboard focus.

    Anything else in front means keystrokes would go to the wrong window —
    overlays like Discord's pop up over VS Code and swallow typing (measured
    live 2026-10-16). Esc dismisses such overlays; then the foreground is
    taken back and re-checked. Never type without this returning True.
    """
    for _ in range(attempts):
        if _foreground() == hwnd:
            return True
        keyboard.press_combo("esc")  # overlay windows (Discord) close on Esc
        _sleep(0.4)
        focus(hwnd)
        _sleep(0.3)
    return _foreground() == hwnd


def _terminal(command: str) -> ToolResult:
    text = " ".join(str(command or "").split())
    if not text:
        return ToolResult(False, "I need the command you want to run in VS Code's terminal.")
    if len(text) > _MAX_COMMAND:
        return ToolResult(False, f"That command is too long for me to type safely (over {_MAX_COMMAND} characters).")
    hwnd = main_window()
    if not hwnd:
        return ToolResult(
            False,
            "I don't see an open VS Code window — open VS Code first, or ask me to open a folder in it.",
        )
    if not focus(hwnd):
        return ToolResult(
            False,
            "VS Code is open, but I couldn't bring it to the front — click it once and ask me again.",
        )
    _sleep(_SETTLE_AFTER_FOCUS)
    guard_failed = ToolResult(
        False,
        "Something else keeps taking the keyboard focus over VS Code (a chat or game overlay?), "
        "so I stopped before typing anything. Dismiss it and ask me again.",
    )
    if not _ensure_foreground(hwnd):
        return guard_failed
    keyboard.press_combo(_PALETTE_COMBO)  # command palette — never Ctrl+Shift+`
    _sleep(_SETTLE_PALETTE)
    if not _ensure_foreground(hwnd):
        return guard_failed
    # Text goes in with scan-code (vk) injection: Electron's terminal ignores
    # Unicode injection; the palette fuzzy-matches "Terminal: Create New
    # Terminal" and Enter runs it.
    keyboard.type_text(_PALETTE_TERMINAL + "\n", mode="vk")
    _sleep(_SETTLE_TERMINAL)
    if not _ensure_foreground(hwnd):
        return ToolResult(
            False,
            "VS Code lost the keyboard focus right before I could type the command — nothing was typed. Try again.",
        )
    keyboard.type_text(text + "\n", mode="vk")
    return ToolResult(
        True,
        f"I typed this into VS Code's terminal and pressed Enter: {text}",
        data={"command": text, "window": hwnd},
    )


def _status() -> ToolResult:
    cli = find_code_cli()
    hwnd = main_window()
    if cli and hwnd:
        return ToolResult(True, "VS Code is ready: I found the launcher and an open window.")
    if cli:
        return ToolResult(True, "VS Code is installed, but no window is open right now.")
    return ToolResult(False, "I couldn't find the VS Code launcher ('code') on this machine.")


def vscode_control_tool() -> ToolSpec:
    """The ``vscode_control`` tool: open paths and run terminal commands in VS Code."""

    def handler(args: dict) -> ToolResult:
        action = str(args.get("action", "")).strip().lower()
        if action == "open":
            try:
                return _open(str(args.get("path", "")).strip(), bool(args.get("new_window", False)))
            except Exception as exc:  # noqa: BLE001 - honest sentence instead of a crash
                return ToolResult(False, f"I couldn't open that in VS Code: {exc}")
        if action == "terminal":
            try:
                return _terminal(str(args.get("command", "")))
            except ValueError as exc:
                return ToolResult(False, f"I couldn't type that into the terminal: {exc}")
            except Exception as exc:  # noqa: BLE001
                return ToolResult(False, f"The VS Code terminal action failed: {exc}")
        if action == "status":
            return _status()
        return ToolResult(False, "Unknown VS Code action — use 'open', 'terminal' or 'status'.")

    return ToolSpec(
        name="vscode_control",
        description=(
            "Work with Visual Studio Code (VS Code): open a folder or file in the editor "
            "(action='open', path='C:/...'), or run a command in its integrated terminal "
            "(action='terminal', command='g++ main.cpp -o main && ./main'). Use this whenever the "
            "user asks to open something in VS Code / work in VS Code / run or compile something "
            "in the VS Code terminal. To create files first, use write_file, then open or run them here."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["open", "terminal", "status"],
                    "description": "open = show a folder or file in VS Code; terminal = run a command in its integrated terminal; status = check whether VS Code is ready.",
                },
                "path": {
                    "type": "string",
                    "description": "Folder or file for the 'open' action (absolute, or ~ for the user's home folder); omit it to just open VS Code.",
                },
                "new_window": {
                    "type": "boolean",
                    "description": "Open in a new VS Code window instead of the last active one.",
                },
                "command": {
                    "type": "string",
                    "description": "Shell command for the 'terminal' action, e.g. 'g++ main.cpp -o main' or 'python app.py'.",
                },
            },
            "required": ["action"],
        },
        handler=handler,
        timeout_seconds=90.0,
    )

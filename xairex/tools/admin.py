"""admin_command: the owner's elevated command runner (G12, D27).

"Run any command with my admin permission" is implemented the only safe way:

* the command text is **owner-authored** in ``settings.json`` (``admin.commands``:
  name -> exact command line) — the model/router can only name a command, never
  invent one (golden rule 5: no eval/exec of model text);
* one run = one UAC prompt. Elevation uses the shell's ``runas`` verb through
  ``ShellExecuteExW`` — the same mechanism as ``Start-Process -Verb RunAs`` —
  so the owner always consents, and dismissing the prompt runs nothing;
* the exact command line is part of the transcript message, the output is kept
  under ``data/admin/`` and every run is audited in ``tool_runs``.

Implementation detail: the command runs inside a tiny generated ``.cmd``
wrapper that redirects the output to a file and appends the command's
``%errorlevel%`` as a trailing ``XAIRX_CODE=<n>`` marker — an elevated process
is started through the shell, which has no stdout pipe to give back. The
marker line needs the space before ``>>`` (``echo X=0>>file`` would be parsed
as a *stdin* append-redirect of stream 0 in cmd, silently losing the marker —
found live, 2026-10-16).
"""

from __future__ import annotations

import ctypes
import logging
import os
import re
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from xairex.config import Settings
from xairex.tools.registry import ToolResult, ToolSpec

logger = logging.getLogger("xairex.tools.admin")

#: ShellExecuteExW: hand back the process handle so we can wait for the end.
_SEE_MASK_NOCLOSEPROCESS = 0x00000040
#: Suppress shell error boxes; the UAC consent UI is unaffected.
_SEE_MASK_FLAG_NO_UI = 0x00000400
_SW_HIDE = 0
_ERROR_CANCELLED = 1223
_WAIT_TIMEOUT = 258
_WAIT_OBJECT_0 = 0

#: How much of a command's output is quoted in the spoken/printed message
#: (the full text stays in the run file under data/admin).
_OUTPUT_PREVIEW = 400
#: How many recent run files are kept (pairs of .cmd + .txt).
_MAX_RUNS = 12
#: Cap for reading one run's output file.
_READ_LIMIT = 262_144


class _SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", ctypes.c_ulong),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", ctypes.c_void_p),
        ("dwHotKey", wintypes.DWORD),
        ("hIcon", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


@dataclass(frozen=True)
class LaunchOutcome:
    """Result of one elevated launch attempt."""

    status: str  # "completed" | "cancelled" | "timeout" | "failed"
    exit_code: int | None = None
    winerror: int = 0


def normalize_admin_name(raw: str) -> str:
    """Fold 'Flush  DNS' / 'flush-dns' / 'flush_dns' to one comparable form."""
    return re.sub(r"[\s_-]+", " ", str(raw or "").strip().lower())


def resolve_command(settings: Settings, raw: str) -> tuple[str, str] | None:
    """The configured ``(name, command line)`` *raw* refers to, if any."""
    wanted = normalize_admin_name(raw)
    if not wanted:
        return None
    for name, line in settings.admin.commands.items():
        if normalize_admin_name(name) == wanted:
            return str(name), str(line)
    return None


def _command_names(settings: Settings) -> list[str]:
    return [str(name) for name in settings.admin.commands]


def _cmd_exe() -> str:
    root = os.environ.get("SystemRoot") or r"C:\Windows"
    return str(Path(root) / "System32" / "cmd.exe")


def _run_dir(settings: Settings) -> Path:
    """Where run wrappers and outputs live (tests point this at tmp)."""
    return settings.resolve_path("data/admin")


# --------------------------------------------------------------- wrapper files


def _write_wrapper(run_dir: Path, name: str, line: str) -> tuple[Path, Path]:
    """The .cmd that runs *line* and records its exit code; returns (cmd, out).

    Raises :class:`ValueError` when the command cannot be written as a plain
    ASCII batch file (refused rather than mangled).
    """
    if not line.isascii():
        raise ValueError("non-ascii command")
    run_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "command"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    counter = 0
    while True:
        suffix = f"-{counter}" if counter else ""
        wrapper = run_dir / f"{slug}-{stamp}{suffix}.cmd"
        output = run_dir / f"{slug}-{stamp}{suffix}.txt"
        if not wrapper.exists():
            break
        counter += 1
    script = (
        "@echo off\r\n"
        f"{line} 1> \"{output}\" 2>&1\r\n"
        f"echo XAIRX_CODE=%errorlevel% >>\"{output}\"\r\n"
    )
    wrapper.write_text(script, encoding="ascii", newline="")
    return wrapper, output


#: The wrapper appends this on its own line (or glued to the command output's
#: last line when that line has no newline) — anchored to the file's end.
_MARKER_RE = re.compile(r"XAIRX_CODE=(-?\d+)[ \t]*\r?\n?\Z")


def _read_outcome(output: Path) -> tuple[int | None, str]:
    """``(exit code, output text)`` parsed from a run's output file."""
    try:
        raw = output.read_bytes()[:_READ_LIMIT]
    except OSError:
        return None, ""
    text = raw.decode("utf-8", "replace").replace("\x00", "")
    match = _MARKER_RE.search(text)
    if match:
        return int(match.group(1)), text[: match.start()].rstrip("\r\n")
    return None, text.strip()


def _prune_runs(run_dir: Path, keep: int = _MAX_RUNS) -> None:
    """Keep only the newest *keep* runs (each run = .cmd + .txt pair)."""
    try:
        outputs = sorted(run_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return
    for stale in outputs[keep:]:
        for path in (stale, stale.with_suffix(".cmd")):
            try:
                path.unlink()
            except OSError:
                pass


def _preview(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= _OUTPUT_PREVIEW:
        return collapsed
    return collapsed[: _OUTPUT_PREVIEW - 1] + "…"


# ------------------------------------------------------------------- launching


def _launch_elevated(executable: str, parameters: str, wait_seconds: float) -> LaunchOutcome:
    """Run *executable* with the UAC ``runas`` verb and wait for it to finish.

    Tests monkeypatch this; the real path is a thin ShellExecuteExW wrapper.
    """
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(_SHELLEXECUTEINFOW)]
    shell32.ShellExecuteExW.restype = wintypes.BOOL

    info = _SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = _SEE_MASK_NOCLOSEPROCESS | _SEE_MASK_FLAG_NO_UI
    info.lpVerb = "runas"
    info.lpFile = executable
    info.lpParameters = parameters
    info.nShow = _SW_HIDE

    if not shell32.ShellExecuteExW(ctypes.byref(info)):
        return LaunchOutcome("cancelled" if ctypes.get_last_error() == _ERROR_CANCELLED else "failed",
                             winerror=ctypes.get_last_error())
    handle = info.hProcess
    try:
        waited = kernel32.WaitForSingleObject(wintypes.HANDLE(handle), wintypes.DWORD(int(wait_seconds * 1000)))
        if waited == _WAIT_OBJECT_0:
            code = wintypes.DWORD()
            kernel32.GetExitCodeProcess(wintypes.HANDLE(handle), ctypes.byref(code))
            return LaunchOutcome("completed", exit_code=int(code.value))
        return LaunchOutcome("timeout", winerror=_WAIT_TIMEOUT)
    finally:
        kernel32.CloseHandle(wintypes.HANDLE(handle))


# --------------------------------------------------------------------- tool


def _describe_available(settings: Settings) -> str:
    names = _command_names(settings)
    listed = "; ".join(f"'{name}' ({settings.admin.commands[name]})" for name in names)
    return f"Your admin commands: {listed}."


def _empty_commands_result() -> ToolResult:
    return ToolResult(
        False,
        "No admin commands are configured yet. Add them under admin.commands in settings.json "
        '(name and exact command line, for example: "flush dns": "ipconfig /flushdns").',
    )


def admin_command_tool(settings: Settings) -> ToolSpec:
    def handler(args: dict[str, Any]) -> ToolResult:
        action = str(args.get("action", "") or "").strip().lower()
        if action == "list":
            if not settings.admin.commands:
                return _empty_commands_result()
            return ToolResult(True, _describe_available(settings), data={"commands": dict(settings.admin.commands)})
        if action != "run":
            return ToolResult(False, f"I don't know the admin action '{action}'.")

        raw_name = str(args.get("command", "") or "").strip()
        if not raw_name:
            if not settings.admin.commands:
                return _empty_commands_result()
            return ToolResult(False, f"Tell me which admin command to run. {_describe_available(settings)}")
        resolved = resolve_command(settings, raw_name)
        if resolved is None:
            if not settings.admin.commands:
                return _empty_commands_result()
            return ToolResult(
                False,
                f"I don't know an admin command called '{raw_name}'. {_describe_available(settings)}",
                data={"unknown": raw_name},
            )
        name, line = resolved

        run_dir = _run_dir(settings)
        try:
            wrapper, output = _write_wrapper(run_dir, name, line)
        except ValueError:
            return ToolResult(
                False,
                "That admin command contains characters I can't run safely, so I left it alone. "
                "Keep the command line to plain ASCII text.",
            )
        except OSError as exc:
            logger.debug("admin: cannot write run files: %s", exc)
            return ToolResult(False, "I couldn't prepare the admin run (writing to data/admin failed). See the log.")

        logger.info("admin: running %r — exact line: %s", name, line)
        try:
            # ``cmd /d /s /c ""script""`` is the canonical form for a quoted
            # batch path (survives spaces in the project directory).
            outcome = _launch_elevated(_cmd_exe(), f'/d /s /c ""{wrapper}""', float(settings.admin.timeout_seconds))
        except OSError as exc:
            logger.error("admin: launch failed: %s", exc)
            return ToolResult(False, f"The elevated launch failed ({exc}). Nothing ran. The exact command: {line}")

        if outcome.status == "cancelled":
            return ToolResult(
                False,
                f"I was ready to run it, but the UAC prompt was dismissed — nothing ran. The exact command: {line}.",
                data={"command_line": line, "cancelled": True},
            )
        if outcome.status == "timeout":
            return ToolResult(
                False,
                f"I started it with administrator rights, but it was still running after "
                f"{settings.admin.timeout_seconds} seconds — I stopped waiting. The exact command: {line}.",
                data={"command_line": line, "output_path": str(output), "still_running": True},
            )
        if outcome.status != "completed":
            return ToolResult(
                False,
                f"The elevated launch failed (Windows error {outcome.winerror}). Nothing ran. "
                f"The exact command: {line}.",
                data={"command_line": line, "winerror": outcome.winerror},
            )

        _prune_runs(run_dir)
        file_code, text = _read_outcome(output)
        if file_code is None:
            # The marker is written by our wrapper right after the command —
            # missing means we genuinely don't know, so say that.
            logger.warning("admin: %r ran but %s has no exit marker", name, output)
            message = (
                f"The exact command: {line} — it ran as administrator, but the run file "
                "did not record an exit code, so I can't tell whether it succeeded."
            )
            if text:
                message += f" Output: {_preview(text)}"
            return ToolResult(
                False,
                message,
                data={"command_line": line, "exit_code": None, "output_path": str(output)},
            )
        if file_code == 0:
            verdict = "it ran as administrator (exit code 0)"
        else:
            verdict = f"it ran as administrator and reported a failure (exit code {file_code})"
        message = f"The exact command: {line} — {verdict}."
        if text:
            message += f" Output: {_preview(text)}"
        logger.info("admin: %r finished exit_code=%s", name, file_code)
        return ToolResult(
            file_code == 0,
            message,
            data={"command_line": line, "exit_code": file_code, "output_path": str(output)},
        )

    names = _command_names(settings)
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["run", "list"],
                "description": "run one configured admin command, or list what is configured",
            },
            "command": {
                "type": "string",
                "description": "Exact configured command name, e.g. 'flush dns'. Required for action 'run'.",
            },
        },
        "required": ["action"],
    }
    if names:
        # Typed allowlist: the model can only name one of the owner's commands.
        parameters["properties"]["command"]["enum"] = names

    return ToolSpec(
        name="admin_command",
        description=(
            "Run one of the owner's pre-approved administrator commands (or list them). "
            "Only the exact names configured in settings under admin.commands exist — never invent "
            "a name or command text. Every run shows the exact command line and asks for the owner's "
            "consent with one UAC prompt; if the prompt is dismissed, nothing runs."
        ),
        parameters=parameters,
        handler=handler,
        timeout_seconds=float(settings.admin.timeout_seconds + 30),
    )

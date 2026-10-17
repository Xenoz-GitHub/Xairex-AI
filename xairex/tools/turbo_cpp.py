"""Turbo C++ workflow (G22, D41): create a source file, type code into the IDE, save it.

The owner asked Xairex to open Turbo C++ and write + save Borland (MS-DOS)
code hands-free. The verified live flow (2026-10-16, notes/04 section L):

1. the Turbo C++ shortcut opens a WPF launcher window that waits for a click;
   we UI-Automate its "New Source File..." button (no focus needed),
2. the launcher shows a Windows save dialog (default ``C:\\TURBOC3\\Projects``)
   -> set the file name field through UI Automation (keystroke typing is only
   a fallback: a stray keypress from other software once turned FIBO into
   TFIBO during the live smoke), press Enter — the launcher creates the file
   and starts DOSBox with ``TC <file>`` on the command line,
3. steal the DOSBox window's foreground (AttachThreadInput + Alt-tap: plain
   SetForegroundWindow is blocked while another app holds focus),
4. type the code with scancode (VK) injection — DOSBox translates scancodes
   into DOS keys and ignores Unicode injection (probe 2026-10-16),
5. press F2 (the named buffer saves straight to disk) and read the file back
   to confirm exactly what was typed landed on disk.

Rails: code is only ever typed as keystrokes (never executed); the file name
is validated to a short safe form; an existing file is never replaced unless
``overwrite=true`` (golden rules 5 + file rails, D37–D39).
"""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
import time
from pathlib import Path

from xairex.config import Settings
from xairex.tools import keyboard
from xairex.tools.applications import launch, resolve_app
from xairex.tools.registry import ToolResult, ToolSpec
from xairex.tools.winfocus import focus as _focus
from xairex.tools.winfocus import pids as _pids
from xairex.tools.winfocus import windows_of as _windows_of

logger = logging.getLogger("xairex.tools.turbo")

_MAX_CODE = 8000
#: DOS 8.3 file names only — longer stems may come back truncated from the DOS
#: side of the mount (probe 2026-10-16 used exactly this shape).
_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,7}$")

#: Where Turbo C++ installs and where the launcher's dialog creates files.
_ROOTS: tuple[Path, ...] = (Path(r"C:\TURBOC3"),)
_PROJECTS = Path(r"C:\TURBOC3\Projects")

#: Settle times (seconds) between the IDE steps; module-level so tests can zero them.
_WAIT_LAUNCHER = 90.0
_WAIT_DIALOG = 20.0
_WAIT_DOSBOX = 90.0
_SETTLE_TC_LOAD = 2.5
_SETTLE_AFTER_NAME = 0.5
_SETTLE_AFTER_SAVE = 1.8
_KEY_INTERVAL = 0.03

_SAVE_DIALOG_TITLE = "Create a source code file..."

_sleep = time.sleep  # seam


def _type_text(text: str, **kwargs) -> None:
    keyboard.type_text(text, **kwargs)


def _press_combo(combo: str) -> None:
    keyboard.press_combo(combo)


def _find_dosbox_window() -> int:
    for pid_value in _pids("DOSBox.exe"):
        windows = _windows_of(pid_value)
        if windows:
            return windows[0][0]
    return 0


# ------------------------------------------------------------------ UIA helper


UIA_INVOKE_PS = r"""
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
try {
    $pidValue = [int]$args[0]
    $buttonName = [string]$args[1]
    $windowName = [string]$args[2]
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $winCond = New-Object System.Windows.Automation.AndCondition(
        (New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $pidValue)),
        (New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::NameProperty, $windowName)))
    $win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $winCond)
    if ($null -eq $win) { Write-Output "window '$windowName' not found"; exit 2 }
    $btnCond = New-Object System.Windows.Automation.AndCondition(
        (New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::Button)),
        (New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::NameProperty, $buttonName)))
    $btn = $win.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $btnCond)
    if ($null -eq $btn) { Write-Output "button '$buttonName' not found"; exit 3 }
    $btn.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    Write-Output "invoked '$buttonName'"
} catch {
    Write-Output ("ERROR: " + $_.Exception.Message)
    exit 1
}
"""


def _run_ps(script: str, *args: str) -> str:
    """Run a fixed PowerShell helper (written to a temp file) and return stdout."""
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as handle:
        handle.write(script)
        path = handle.name
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path, *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return (result.stdout or "").strip()
    finally:
        Path(path).unlink(missing_ok=True)


UIA_SET_FILENAME_PS = r"""
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
try {
    $pidValue = [int]$args[0]
    $name = [string]$args[1]
    $windowName = [string]$args[2]
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $winCond = New-Object System.Windows.Automation.AndCondition(
        (New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $pidValue)),
        (New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::NameProperty, $windowName)))
    $win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $winCond)
    if ($null -eq $win) { Write-Output "window not found"; exit 2 }

    $edit = $null
    $hostCond = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::AutomationIdProperty, "FileNameControlHost")
    $host = $win.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $hostCond)
    $editCond = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        [System.Windows.Automation.ControlType]::Edit)
    if ($null -ne $host) { $edit = $host.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $editCond) }
    if ($null -eq $edit) {
        $nameCond = New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::NameProperty, "File name:")
        $edit = $win.FindFirst([System.Windows.Automation.TreeScope]::Descendants,
            (New-Object System.Windows.Automation.AndCondition($editCond, $nameCond)))
    }
    if ($null -eq $edit) {
        $idCond = New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::AutomationIdProperty, "1001")
        $edit = $win.FindFirst([System.Windows.Automation.TreeScope]::Descendants,
            (New-Object System.Windows.Automation.AndCondition($editCond, $idCond)))
    }
    if ($null -eq $edit) { Write-Output "file name edit not found"; exit 3 }

    $value = $edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
    $value.SetValue($name)
    Write-Output ("value=" + $value.Current.Value)
} catch {
    Write-Output ("ERROR: " + $_.Exception.Message)
    exit 1
}
"""


def _set_dialog_filename(pid_value: int, name: str) -> str:
    """Set the save dialog's file-name field via UI Automation; returns the field.

    Keystrokes are only a fallback — a stray keypress from another active
    process once turned FIBO into TFIBO (live smoke 2026-10-16); the value
    pattern cannot be corrupted like that.
    """
    out = _run_ps(UIA_SET_FILENAME_PS, str(pid_value), name, _SAVE_DIALOG_TITLE)
    for line in out.splitlines():
        if line.startswith("value="):
            return line[len("value=") :].strip()
    return ""


def _cmdline_of_dosbox() -> str:
    out = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "(Get-CimInstance Win32_Process -Filter \"name='dosbox.exe'\" | Select-Object -First 1).CommandLine",
        ],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return out.strip()


# ------------------------------------------------------------------ flow steps


def _search_existing(stem: str) -> Path | None:
    """Find ``<stem>.cpp`` (any case) under the known roots."""
    wanted = stem.upper()
    for root in _ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            try:
                if path.is_file() and path.stem.upper() == wanted and path.suffix.lower() == ".cpp":
                    return path
            except OSError:
                continue
    return None


def _existing_launcher() -> tuple[int, int] | None:
    for pid_value in _pids("Turbo C++.exe"):
        windows = _windows_of(pid_value)
        if windows:
            return pid_value, windows[0][0]
    return None


def _wait_launcher(before: set[int], timeout: float) -> tuple[int, int] | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for pid_value in _pids("Turbo C++.exe") - before:
            windows = _windows_of(pid_value)
            if windows:
                return pid_value, windows[0][0]
        _sleep(0.5)
    return None


def _find_save_dialog(pid_value: int) -> int:
    for hwnd, title, cls in _windows_of(pid_value):
        if cls == "#32770" and title.startswith("Create a source"):
            return hwnd
    return 0


def _dismiss_overwrite_prompt(pid_value: int) -> None:
    """If the save dialog triggered a 'Confirm Save As' prompt, accept it."""
    for hwnd, title, cls in _windows_of(pid_value):
        if cls == "#32770" and "confirm" in title.lower():
            if _focus(hwnd, attempts=4):
                _press_combo("enter")  # the default button is Yes
            return


def _verify_saved(stem: str, started: float) -> Path | None:
    """Newest fresh ``<stem>.cpp`` (any case) under the roots, or None."""
    wanted = stem.upper()
    candidates: list[Path] = []
    for root in _ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            try:
                if (
                    path.is_file()
                    and path.stem.upper() == wanted
                    and path.suffix.lower() == ".cpp"
                    and path.stat().st_mtime >= started - 60
                ):
                    candidates.append(path)
            except OSError:
                continue
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _content_matches(path: Path, code: str) -> bool:
    expected = [line.strip() for line in code.strip().splitlines() if line.strip()]
    try:
        raw = path.read_bytes()
    except OSError:
        return False
    text = raw.decode("ascii", "replace").replace("\r\n", "\n").replace("\x1a", "")
    actual = [line.strip() for line in text.strip().splitlines() if line.strip()]
    return actual == expected


# ------------------------------------------------------------------ naming


#: Words that describe the *job* rather than the program — never used as a name.
_NAME_STOPWORDS = frozenset(
    {
        "and",
        "borland",
        "build",
        "can",
        "code",
        "coding",
        "could",
        "cpp",
        "create",
        "dosbox",
        "file",
        "for",
        "ide",
        "inside",
        "into",
        "like",
        "little",
        "make",
        "need",
        "new",
        "open",
        "please",
        "problem",
        "program",
        "programme",
        "project",
        "quick",
        "save",
        "saved",
        "simple",
        "small",
        "some",
        "source",
        "tab",
        "that",
        "the",
        "then",
        "this",
        "turbo",
        "want",
        "with",
        "write",
        "writes",
        "xairex",
        "you",
        "your",
    }
)


def existing_project_names() -> set[str]:
    """Uppercase stems of the files already in the Turbo projects folder."""
    try:
        return {path.stem.upper() for path in _PROJECTS.iterdir() if path.is_file()}
    except OSError:
        return set()


def pick_project_filename(request: str, taken: set[str]) -> str:
    """An 8.3-safe program name derived from the ask, avoiding existing files."""
    words = [word for word in re.findall(r"[a-z0-9]+", str(request).lower()) if len(word) >= 3]
    base = next((word for word in words if word not in _NAME_STOPWORDS and not word.isdigit()), "prog")
    base = re.sub(r"[^A-Z0-9]", "", base.upper())[:8] or "PROG"
    if base not in taken:
        return base
    for suffix in range(2, 10):
        candidate = f"{base[:7]}{suffix}"
        if candidate not in taken:
            return candidate
    for suffix in range(10, 100):
        candidate = f"{base[:6]}{suffix}"
        if candidate not in taken:
            return candidate
    return base  # practically unreachable; the tool's overwrite guard stays as the last line


def flatten_for_editor(code: str) -> str:
    """Strip per-line leading whitespace before typing into the DOS editor.

    The Turbo C++ editor auto-indents: after Enter it pre-fills the next line
    with the previous line's leading whitespace, so typed indentation stacks
    deeper line after line (live 2026-10-16: a 37-line program landed on disk
    as a cascade up to ~60 columns deep). C does not care about leading
    whitespace, so every line is typed flush-left and the saved file stays
    exactly equal to the source. Blank lines stay blank.
    """
    return "\n".join(line.lstrip(" \t") for line in code.splitlines())


# ------------------------------------------------------------------ tool


def turbo_write_code_tool(settings: Settings) -> ToolSpec:
    def handler(args: dict) -> ToolResult:
        code = str(args.get("code", ""))
        stem = str(args.get("filename", "")).strip()
        overwrite = bool(args.get("overwrite", False))

        if not code.strip():
            return ToolResult(False, "There is no code to write.")
        if len(code) > _MAX_CODE:
            return ToolResult(False, f"That program is too long for the Turbo editor ({len(code)} characters).")
        if not _FILENAME_RE.match(stem):
            return ToolResult(
                False,
                "Turbo file names must be short: up to 8 letters, digits, dashes or underscores, like 'fibo'.",
            )
        stem = stem.upper()

        existing = _search_existing(stem)
        if existing is not None and not overwrite:
            return ToolResult(
                False,
                f"{existing.name} already exists at {existing}. Pick another name, or say it with overwrite.",
                data={"path": str(existing)},
            )

        if _pids("DOSBox.exe"):
            cmdline = _cmdline_of_dosbox()
            where = "Turbo C++" if "TC " in cmdline.upper() or "TC." in cmdline.upper() else "another DOS program"
            return ToolResult(
                False,
                f"{where} is already open in DOSBox. Close that window first and ask me again — "
                f"then I'll create the file cleanly from the launcher.",
            )

        launcher = _existing_launcher()
        if launcher is None:
            resolved = resolve_app(settings, "turbo c++")
            if resolved.error or not resolved.target:
                return ToolResult(False, resolved.error or "I can't find Turbo C++ on this machine.")
            logger.info("turbo: launching %s", resolved.target)
            before = _pids("Turbo C++.exe")
            try:
                launch(resolved.target)
            except OSError as exc:
                return ToolResult(False, f"I couldn't start Turbo C++: {exc}")
            launcher = _wait_launcher(before, _WAIT_LAUNCHER)
            if launcher is None:
                return ToolResult(
                    False,
                    "The Turbo C++ launcher didn't show its window (it may be waiting on its own network check). "
                    "Please open Turbo C++ once by hand, then ask me again.",
                )
        launcher_pid, _launcher_hwnd = launcher
        logger.info("turbo: launcher pid=%s", launcher_pid)

        dialog = _find_save_dialog(launcher_pid)
        if not dialog:
            out = _run_ps(UIA_INVOKE_PS, str(launcher_pid), "New Source File...", "Turbo C++")
            logger.info("turbo: UIA invoke -> %s", out)
            if "invoked" not in out:
                return ToolResult(
                    False,
                    "I couldn't click New Source File in the Turbo C++ launcher. "
                    "Click it once by hand, then ask me again.",
                )
            deadline = time.monotonic() + _WAIT_DIALOG
            while time.monotonic() < deadline and not dialog:
                dialog = _find_save_dialog(launcher_pid)
                _sleep(0.4)
        if not dialog:
            return ToolResult(False, "The Turbo C++ save dialog didn't appear. Nothing was typed.")

        if not _focus(dialog):
            return ToolResult(False, "I couldn't focus the Turbo C++ save dialog — nothing was typed.")
        field = _set_dialog_filename(launcher_pid, stem)
        logger.info("turbo: save dialog field=%r (want %r)", field, stem)
        if field.strip().upper() != stem.upper():
            logger.info("turbo: falling back to keystroke typing for the file name")
            _type_text(stem)
            _sleep(_SETTLE_AFTER_NAME)
        _press_combo("enter")
        _sleep(_SETTLE_AFTER_NAME)
        _dismiss_overwrite_prompt(launcher_pid)

        deadline = time.monotonic() + _WAIT_DOSBOX
        dosbox_hwnd = 0
        while time.monotonic() < deadline and not dosbox_hwnd:
            dosbox_hwnd = _find_dosbox_window()
            if not dosbox_hwnd:
                _sleep(0.5)
        if not dosbox_hwnd:
            return ToolResult(
                False,
                "Turbo C++ didn't open in DOSBox after saving the file name. Check the screen — nothing was typed.",
            )

        if not _focus(dosbox_hwnd):
            return ToolResult(False, "I couldn't focus the Turbo C++ window to type in it — nothing was typed.")
        typed_code = flatten_for_editor(code)
        logger.info("turbo: typing %s characters into the IDE", len(typed_code))
        _sleep(_SETTLE_TC_LOAD)
        started = time.time()
        _type_text(typed_code, mode="vk", interval=_KEY_INTERVAL)
        _sleep(0.8)
        _press_combo("f2")
        _sleep(_SETTLE_AFTER_SAVE)

        path = _verify_saved(stem, started)
        if path is None:
            return ToolResult(
                False,
                "I typed the program and pressed save, but I can't find the file on disk. Check the Turbo C++ screen.",
                data={"filename": stem},
            )
        if not _content_matches(path, typed_code):
            return ToolResult(
                False,
                f"I saved {path.name} at {path.parent}, but the text on disk differs from what I typed. Check the screen.",
                data={"path": str(path)},
            )
        logger.info("turbo: saved %s (%s bytes)", path, path.stat().st_size)
        return ToolResult(
            True,
            f"Done — I created {path.name} in Turbo C++, typed your program and saved it at {path.parent}.",
            data={"path": str(path), "filename": path.name},
        )

    return ToolSpec(
        name="turbo_write_code",
        description=(
            "Create a new Turbo C++ (Borland, MS-DOS) source file, type the given code into the Turbo C++ IDE "
            "and save it. Use this for Turbo C++/Borland/DOS C or C++ work (Borland dialect: iostream.h, conio.h "
            "or stdio.h, void main, clrscr, getch; no modern headers, no namespaces). Call it ONCE with the "
            "complete program — it launches the IDE, creates, types, saves and verifies the file by itself. "
            "Filename: short, 1-8 letters/digits/dashes/underscores, no extension ('.cpp' is added)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "The complete Borland-dialect C/C++ program to type in."},
                "filename": {"type": "string", "description": "Short file name without extension, e.g. 'fibo'."},
                "overwrite": {"type": "boolean", "description": "Replace the file if it already exists (default false)."},
            },
            "required": ["code", "filename"],
        },
        handler=handler,
        timeout_seconds=300.0,
    )

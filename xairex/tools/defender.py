"""Windows Defender scan and status tools (G13, owner: "detect viruses / automatically scan files").

Everything here stays local (golden rule 1): the tool drives Windows' own
Defender service through ``MpCmdRun.exe`` and PowerShell's Defender cmdlets —
no network, no third-party engine, no telemetry. Fixed command shapes only:
the model picks an action and a path, never a command line (golden rule 5).

Facts verified live on this machine (2026-10-17, notes/04 section Q):

- ``MpCmdRun.exe -Scan -ScanType 1`` = quick scan (~46 s here), ``2`` = full,
  ``3 -File <path>`` = targeted scan of one file/folder (0.3 s on a folder).
- Exit code 0 = no threats; 2 = threats found — but a failed request also
  surfaces as code 2 with a ``Failed with hr = 0x...`` line, so the HRESULT
  marker is checked before the "found something" wording.
- ``Get-MpComputerStatus`` and ``Get-MpThreatDetection`` both answer from a
  plain (non-elevated) prompt.
- ``-Scan -Cancel`` needs elevation (hr 0x80070005 as a plain user), so a
  cancel refusal is reported honestly instead of silently failing.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

from xairex.config import Settings
from xairex.tools.files import resolve_known_location
from xairex.tools.registry import ToolResult, ToolSpec

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

#: Blocking scan cap. Quick/targeted scans take seconds to a couple of minutes;
#: anything past this is cut off with an honest "I stopped waiting".
_SCAN_CAP_SECONDS = 480.0
_CANCEL_SECONDS = 30.0
_QUERY_TIMEOUT = 60.0
_THREAT_NAMES_SHOWN = 3

#: "CmdTool: Failed with hr = 0x..." — language-neutral HRESULT marker.
_HR_FAILURE_RE = re.compile(r"hr\s*=\s*0x[0-9A-Fa-f]+", re.IGNORECASE)

_STATUS_SCRIPT = (
    "$s = Get-MpComputerStatus\n"
    '"av=" + [int]$s.AntivirusEnabled\n'
    '"rt=" + [int]$s.RealTimeProtectionEnabled\n'
    '"tamper=" + [int]$s.IsTamperProtected\n'
    '"sig=" + $s.AntivirusSignatureVersion\n'
    '"sigage=" + $s.AntivirusSignatureAge\n'
    "\"quick=\" + $(if ($s.QuickScanEndTime) { $s.QuickScanEndTime.ToString('yyyy-MM-dd HH:mm') } else { '' })\n"
    "\"full=\" + $(if ($s.FullScanEndTime) { $s.FullScanEndTime.ToString('yyyy-MM-dd HH:mm') } else { '' })\n"
)

_THREATS_SCRIPT = (
    "$d = @(Get-MpThreatDetection | Sort-Object InitialDetectionTime -Descending | Select-Object -First 5)\n"
    "foreach ($x in $d) { $r = @($x.Resources)[0]; "
    "\"threat=\" + $x.ThreatID + \"|\" + $x.InitialDetectionTime.ToString('yyyy-MM-dd HH:mm') + \"|\" + $r }\n"
)


# ------------------------------------------------------------------- plumbing


def _mpcmdrun_path() -> Path | None:
    """Locate ``MpCmdRun.exe`` (Program Files first, then versioned platform dirs)."""
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    candidates = [program_files / "Windows Defender" / "MpCmdRun.exe"]
    platform_root = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Microsoft" / "Windows Defender" / "Platform"
    try:
        versions = sorted((entry for entry in platform_root.iterdir() if entry.is_dir()), reverse=True)
    except OSError:
        versions = []
    candidates.extend(version / "MpCmdRun.exe" for version in versions)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _run_mp(executable: Path, args: list[str], timeout: float) -> tuple[int | None, bool, str]:
    """Run MpCmdRun; returns ``(exit_code, timed_out, output)``.

    On timeout ``subprocess.run`` kills the client process we launched. The
    service-side scan may keep going — callers word their messages accordingly.
    """
    try:
        completed = subprocess.run(
            [str(executable), *args],
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
            creationflags=_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        return None, True, ""
    except OSError:
        return None, False, ""
    return completed.returncode, False, (completed.stdout or "") + (completed.stderr or "")


def _popen_mp(executable: Path, args: list[str]):
    """Start MpCmdRun detached (used for the background full scan)."""
    try:
        return subprocess.Popen(
            [str(executable), *args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=_NO_WINDOW,
        )
    except OSError:
        return None


def _powershell(script: str) -> str | None:
    """One hidden PowerShell pass; None means the query itself failed."""
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            check=False,
            text=True,
            timeout=_QUERY_TIMEOUT,
            creationflags=_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return (completed.stdout or "").strip()


def _parse_markers(output: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in output.splitlines():
        key, _, value = line.partition("=")
        key = key.strip().lower()
        if key:
            fields[key] = value.strip()
    return fields


def _threat_rows() -> list[tuple[str, str, str]] | None:
    """Recent detections as ``(name, when, first resource)``.

    An empty list means "none on record"; None means the query itself failed.
    """
    output = _powershell(_THREATS_SCRIPT)
    if output is None:
        return None
    rows: list[tuple[str, str, str]] = []
    for line in output.splitlines():
        if not line.startswith("threat="):
            continue
        parts = line[len("threat=") :].split("|")
        name = parts[0].strip()
        when = parts[1].strip() if len(parts) > 1 else ""
        where = parts[2].strip() if len(parts) > 2 else ""
        if name:
            rows.append((name, when, where))
    return rows


def _threat_names(rows: list[tuple[str, str, str]] | None) -> str:
    if not rows:
        return ""
    return ", ".join(name for name, _when, _where in rows[:_THREAT_NAMES_SHOWN])


def _last_meaningful_line(output: str, cap: int = 140) -> str:
    for line in reversed(output.splitlines()):
        text = line.strip()
        if text:
            return text[:cap]
    return ""


# -------------------------------------------------------------------- actions


def _scan_result(executable: Path, scan_args: list[str], scope: str, extra: dict | None = None) -> ToolResult:
    started = time.monotonic()
    code, timed_out, output = _run_mp(executable, scan_args, _SCAN_CAP_SECONDS)
    elapsed = time.monotonic() - started

    if timed_out:
        # Best effort: ask Defender itself to stop (needs elevation — may refuse).
        _run_mp(executable, ["-Scan", "-Cancel"], _CANCEL_SECONDS)
        minutes = _SCAN_CAP_SECONDS / 60
        return ToolResult(
            False,
            f"The {scope} scan didn't finish within {minutes:.0f} minutes, so I stopped waiting for it. "
            "It may still be running in the background — ask me for the scan status in a bit.",
        )
    if code is None:
        return ToolResult(False, "Windows Defender didn't answer that request — try again, or open Windows Security to check manually.")
    if code == 0:
        return ToolResult(
            True,
            f"No threats found — the {scope} scan finished in {elapsed:.0f} seconds. Defender keeps watching in the background.",
            data={"action": "scan", "scope": scope, "exit_code": 0, **(extra or {})},
        )
    if code != 2 or _HR_FAILURE_RE.search(output):
        tail = _last_meaningful_line(output)
        detail = f" — its tool said: {tail}" if tail else ""
        return ToolResult(False, f"The {scope} scan couldn't run{detail} (code {code}).")

    rows = _threat_rows()
    names = _threat_names(rows)
    if names:
        message = f"The {scope} scan found something: {names}. Defender is handling it — open Windows Security to see the details."
    else:
        message = f"The {scope} scan reported a threat. Defender is handling it — open Windows Security for the details."
    return ToolResult(
        True,
        message,
        data={"action": "scan", "scope": scope, "exit_code": 2, "threats": [name for name, _when, _where in rows or []], **(extra or {})},
    )


def _background_note(background: dict) -> str:
    process = background.get("process")
    if process is None:
        return ""
    code = process.poll()
    if code is None:
        return "The full scan I started earlier is still running."
    background["process"] = None
    if code == 0:
        return "The full scan I started earlier has finished — no threats."
    if code == 2:
        names = _threat_names(_threat_rows())
        if names:
            return f"The full scan I started earlier finished and found something: {names} — check Windows Security."
        return "The full scan I started earlier finished and reported a threat — check Windows Security."
    return f"The full scan I started earlier ended with code {code}."


def _status_result(background: dict) -> ToolResult:
    output = _powershell(_STATUS_SCRIPT)
    if output is None:
        return ToolResult(False, "I couldn't read Windows Defender's status just now — try again in a moment.")
    fields = _parse_markers(output)
    if "av" not in fields:
        return ToolResult(False, "Windows Defender didn't report its status — is it installed on this machine?")

    parts: list[str] = []
    if fields.get("av") == "1":
        line = "Windows Defender is on"
        if fields.get("rt") == "1":
            line += " with real-time protection"
        if fields.get("tamper") == "1":
            line += " and tamper protection"
        parts.append(line + ".")
    else:
        parts.append("Windows Defender looks switched off on this machine — that's worth checking in Windows Security.")

    signature = fields.get("sig", "unknown")
    age = fields.get("sigage", "")
    if age != "":
        age_text = f", {age} day{'s' if age != '1' else ''} old"
    else:
        age_text = ""
    parts.append(f"Signatures {signature}{age_text}.")
    parts.append(f"Last quick scan: {fields.get('quick') or 'never'}. Last full scan: {fields.get('full') or 'never'}.")

    note = _background_note(background)
    if note:
        parts.append(note)
    return ToolResult(True, " ".join(parts), data={"status": fields})


def _threats_result() -> ToolResult:
    rows = _threat_rows()
    if rows is None:
        return ToolResult(False, "I couldn't read Defender's threat history just now — try again in a moment.")
    if not rows:
        return ToolResult(True, "No threats in Defender's history — nothing has been detected on this machine.")
    described = "; ".join(
        f"{name} ({when})" + (f" in {where}" if where else "") for name, when, where in rows
    )
    return ToolResult(
        True,
        f"Recent Defender detections ({len(rows)}): {described}.",
        data={"threats": [name for name, _when, _where in rows]},
    )


def _cancel_result(executable: Path, background: dict) -> ToolResult:
    code, timed_out, _output = _run_mp(executable, ["-Scan", "-Cancel"], _CANCEL_SECONDS)
    background["process"] = None
    if timed_out or code is None:
        return ToolResult(False, "I couldn't reach Windows Defender to cancel the scan.")
    if code == 0:
        return ToolResult(True, "Okay — I asked Defender to stop the running scan.")
    return ToolResult(
        False,
        "Windows Defender wouldn't cancel it from my side — that request needs an elevated prompt, "
        "and there may simply be no scan running. If one is, you can stop it from Windows Security.",
    )


def _start_full_scan(executable: Path, background: dict) -> ToolResult:
    process = background.get("process")
    if process is not None and process.poll() is None:
        return ToolResult(True, "A full scan is already running — ask me for the scan status whenever you like.")
    process = _popen_mp(executable, ["-Scan", "-ScanType", "2"])
    if process is None:
        return ToolResult(False, "I couldn't start the full scan — try again, or open Windows Security.")
    background["process"] = process
    background["started"] = time.monotonic()
    return ToolResult(
        True,
        "Started a full scan in the background. Full scans can take an hour or more — "
        "ask me for the scan status whenever you like.",
        data={"action": "full"},
    )


# ----------------------------------------------------------------------- tool


def defender_scan_tool(settings: Settings) -> ToolSpec:
    """Windows Defender scans, status and threat history through fixed actions (G13)."""
    background: dict = {"process": None, "started": 0.0}

    def handler(args: dict) -> ToolResult:
        action = str(args.get("action", "status")).strip().lower()
        executable = _mpcmdrun_path()
        if executable is None:
            return ToolResult(False, "I can't find Windows Defender's command-line tool on this machine — is Defender installed?")
        if action == "status":
            return _status_result(background)
        if action == "threats":
            return _threats_result()
        if action == "cancel":
            return _cancel_result(executable, background)
        if action == "full":
            return _start_full_scan(executable, background)
        if action == "quick":
            return _scan_result(executable, ["-Scan", "-ScanType", "1"], "quick", {"action": "quick"})
        if action == "path":
            raw = str(args.get("path", "")).strip()
            if not raw:
                return ToolResult(False, "Tell me which file or folder to scan.")
            target = resolve_known_location(settings, raw)
            if target is None:
                return ToolResult(False, f"I can't find a file or folder called '{raw}' — give me the full path if it lives somewhere else.")
            scope = target.name or str(target)
            return _scan_result(
                executable,
                ["-Scan", "-ScanType", "3", "-File", str(target)],
                scope,
                {"action": "path", "path": str(target)},
            )
        return ToolResult(False, f"I don't know the defender action {action!r}.")

    return ToolSpec(
        name="defender_scan",
        description=(
            "Windows Defender (the built-in virus protection), all local: action 'quick' runs a quick scan of "
            "the whole machine, 'path' scans one file or folder (needs the 'path' argument), 'full' starts a full "
            "scan in the background, 'status' reports protection state and last scan times, 'threats' lists "
            "recent detections, 'cancel' asks Defender to stop a running scan."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["quick", "path", "full", "status", "threats", "cancel"],
                    "description": "What to do.",
                },
                "path": {
                    "type": "string",
                    "description": "File or folder to scan (required for action 'path').",
                },
            },
            "required": ["action"],
        },
        handler=handler,
        timeout_seconds=600.0,
    )

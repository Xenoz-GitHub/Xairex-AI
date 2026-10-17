"""App discovery (G19, D37–D38): find installed programs by name.

Sources, cheapest first:

1. learned/custom mappings in ``tools.apps`` — instant, and the normal path
   after the first successful find (results are learned back);
2. Start Menu + Desktop shortcuts — one hidden PowerShell pass that resolves
   the ``.lnk`` targets, cached for a few minutes;
3. the registry ``App Paths`` keys — every app that registers its exe;
4. a bounded scan of the common install roots (Program Files, per-user
   Programs, Desktop/Documents/Downloads, and system-drive folders whose name
   matches the query — the ``C:\\TURBOC3`` case), depth- and time-capped;
5. a whole-disk PowerShell search — only on explicit request ("search
   everywhere for X"), optionally elevated with one UAC prompt ("use admin
   powershell … search for X").

Everything returns :class:`AppCandidate` records ranked by how well the name
matches the query; nothing is launched here. All PowerShell runs use fixed
templates with a sanitized token — the query text never becomes a command.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xairex.config import Settings

logger = logging.getLogger("xairex.tools.discovery")

#: Where a hit came from — lower is better when scores tie.
SOURCE_PRIORITY = {
    "learned": -1,
    "start menu": 0,
    "desktop": 1,
    "app paths": 2,
    "scan": 3,
    "deep search": 4,
}

_SHORTCUT_TTL = 300.0  # seconds a resolved shortcut list stays fresh
_SHORTCUT_TIMEOUT = 15.0
_SCAN_SECONDS = 4.0
_SCAN_MAX_EXES = 1500
_DEEP_TIMEOUT = 90.0
_ELEVATED_TIMEOUT = 300.0

_NOISE_STEM = re.compile(r"^(?:unins|setup|install|update|updater|vc_redist|vcredist|dotnet|dxsetup)", re.IGNORECASE)
_SKIP_DIRS = {
    "windows",
    "$recycle.bin",
    "system volume information",
    "perflogs",
    "recovery",
    "windowsapps",
    "appdata",
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "site-packages",
}
_TOKEN_SAFE = re.compile(r"[^A-Za-z0-9._+-]")

#: module-level shortcut cache: (timestamp, entries)
_SHORTCUT_CACHE: tuple[float, list[tuple[str, str]]] | None = None


@dataclass(frozen=True)
class AppCandidate:
    """One plausible app match: what to open, where it came from, how good."""

    name: str  # display name (shortcut stem or exe stem)
    path: str  # what to open (.lnk, .exe or URI)
    source: str  # "learned" | "start menu" | "desktop" | "app paths" | "scan" | "deep search"
    score: float  # summed token match quality
    penalty: int  # display words that matched nothing (fewer = better)
    kind: str  # "shortcut" | "exe" | "uri"

    @property
    def order(self) -> tuple[float, int, int, int]:
        """Sort key: best score, fewest extra words, best source, shortest path."""
        return (-self.score, self.penalty, SOURCE_PRIORITY.get(self.source, 9), len(self.path))


def same_rank(first: AppCandidate, second: AppCandidate) -> bool:
    """True when two candidates are indistinguishable — the user must pick."""
    return first.order[:3] == second.order[:3]


# --------------------------------------------------------------------- scoring


def _words(text: str) -> list[str]:
    return [word for word in re.split(r"[^a-z0-9]+", str(text).lower()) if word]


def _token_score(token: str, words: list[str]) -> float:
    """How well one query token matches a word list (0 = no match)."""
    for word in words:
        if word == token:
            return 1.0
    for word in words:
        if len(token) >= 3 and word.startswith(token):
            return 0.8
    if len(token) >= 4:
        joined = "".join(words)
        if token in joined:
            return 0.6
    return 0.0


def query_tokens(query: str) -> list[str]:
    """Significant search tokens for *query* (aliases included, noise dropped)."""
    from xairex.tools.applications import normalize_app_name  # lazy: avoids an import cycle

    tokens: list[str] = []
    for word in _words(f"{query} {normalize_app_name(query)}"):
        if len(word) >= 3 and word not in ("app", "application", "program", "the", "for") and word not in tokens:
            tokens.append(word)
    if not tokens:
        fallback = " ".join(_words(query))
        if fallback:
            tokens = [fallback]
    return tokens


@dataclass(frozen=True)
class _RawHit:
    """A candidate before scoring: display name, open path, match fields."""

    name: str
    path: str
    source: str
    folders: tuple[str, ...] = ()
    target_stem: str = ""
    kind: str = "exe"


def _score(tokens: list[str], hit: _RawHit) -> tuple[float, int] | None:
    """Total match score and display-word penalty, or None when nothing hits."""
    name_words = _words(hit.name)
    folder_words = _words(" ".join(hit.folders))
    target_words = _words(hit.target_stem)

    total = 0.0
    matched_any = False
    for token in tokens:
        part = max(
            1.0 * _token_score(token, name_words),
            0.7 * _token_score(token, folder_words),
            0.4 * _token_score(token, target_words),
        )
        if part > 0:
            matched_any = True
        total += part
    if not matched_any:
        return None

    unmatched = 0
    for word in name_words:
        if not any(word == token or (len(token) >= 3 and word.startswith(token)) for token in tokens):
            unmatched += 1
    return total, unmatched


# ------------------------------------------------------------------- PowerShell


def _run_powershell(script: str, timeout: float) -> str | None:
    """Run one fixed PowerShell script hidden; None on failure/timeout."""
    if sys.platform != "win32":
        return None
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed.stdout


def _run_powershell_partial(script: str, timeout: float) -> str | None:
    """Like :func:`_run_powershell`, but keeps partial output on timeout."""
    if sys.platform != "win32":
        return None
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return completed.stdout
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout
        if isinstance(output, bytes):
            output = output.decode("utf-8", "replace")
        return output or None
    except OSError:
        return None


# ------------------------------------------------------------------- shortcuts


def _shortcut_roots() -> list[Path]:
    roots: list[Path] = []
    appdata = os.environ.get("APPDATA")
    programdata = os.environ.get("ProgramData")
    profile = os.environ.get("USERPROFILE")
    public = os.environ.get("PUBLIC")
    if appdata:
        roots.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if programdata:
        roots.append(Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if profile:
        roots.append(Path(profile) / "Desktop")
    if public:
        roots.append(Path(public) / "Desktop")
    return [root for root in roots if root.is_dir()]


def _shortcut_script(roots: list[Path]) -> str:
    quoted = ", ".join("'" + str(root).replace("'", "''") + "'" for root in roots)
    return (
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
        "$ErrorActionPreference='SilentlyContinue';"
        "$sh = New-Object -ComObject WScript.Shell;"
        f"Get-ChildItem -LiteralPath @({quoted}) -Recurse -Filter *.lnk -File | ForEach-Object {{"
        " $t = $sh.CreateShortcut($_.FullName).TargetPath;"
        " Write-Output ($_.FullName + [char]9 + $t) }"
    )


def _shortcut_entries() -> list[tuple[str, str]]:
    """(lnk path, target path) for every Start Menu / Desktop shortcut."""
    global _SHORTCUT_CACHE
    roots = _shortcut_roots()
    if not roots:
        return []
    now = time.monotonic()
    if _SHORTCUT_CACHE is not None and now - _SHORTCUT_CACHE[0] < _SHORTCUT_TTL:
        return _SHORTCUT_CACHE[1]
    output = _run_powershell(_shortcut_script(roots), _SHORTCUT_TIMEOUT)
    entries: list[tuple[str, str]] = []
    for line in (output or "").splitlines():
        line = line.strip()
        if not line or "\t" not in line:
            continue
        lnk, _, target = line.partition("\t")
        if lnk.lower().endswith(".lnk"):
            entries.append((lnk, target.strip()))
    _SHORTCUT_CACHE = (now, entries)
    return entries


def _raw_from_shortcut(lnk: str, target: str) -> _RawHit:
    path = Path(lnk)
    source = "start menu" if "start menu" in lnk.lower() else "desktop"
    folders = tuple(part for part in (path.parent.name, path.parent.parent.name) if part)
    return _RawHit(
        name=path.stem,
        path=lnk,
        source=source,
        folders=folders,
        target_stem=Path(target).stem if target else "",
        kind="shortcut",
    )


# ------------------------------------------------------------------- app paths


def _app_path_entries() -> list[tuple[str, str]]:
    """(exe name, full path) from every registry ``App Paths`` key."""
    try:
        import winreg
    except ImportError:
        return []
    entries: list[tuple[str, str]] = []
    locations = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    )
    for root, subkey in locations:
        try:
            key = winreg.OpenKey(root, subkey)
        except OSError:
            continue
        try:
            count = winreg.QueryInfoKey(key)[0]
            for index in range(count):
                try:
                    name = winreg.EnumKey(key, index)
                    with winreg.OpenKey(key, name) as child:
                        value, _ = winreg.QueryValueEx(child, "")
                except OSError:
                    continue
                if isinstance(value, str) and value.strip():
                    entries.append((name, value.strip()))
        finally:
            winreg.CloseKey(key)
    return entries


# ------------------------------------------------------------------ bounded scan


def _scan_roots(tokens: list[str]) -> list[tuple[Path, int]]:
    roots: list[tuple[Path, int]] = []
    program_files = os.environ.get("ProgramFiles")
    program_files_x86 = os.environ.get("ProgramFiles(x86)")
    local = os.environ.get("LOCALAPPDATA")
    profile = os.environ.get("USERPROFILE")
    if program_files:
        roots.append((Path(program_files), 3))
    if program_files_x86:
        roots.append((Path(program_files_x86), 3))
    if local:
        roots.append((Path(local) / "Programs", 4))
    if profile:
        for sub in ("Desktop", "Documents", "Downloads"):
            candidate = Path(profile) / sub
            if candidate.is_dir():
                roots.append((candidate, 2))
    system_drive = Path(os.environ.get("SystemDrive", "C:") + os.sep)
    try:
        for child in system_drive.iterdir():
            try:
                if not child.is_dir() or child.name.lower() in _SKIP_DIRS:
                    continue
            except OSError:
                continue
            if any(_token_score(token, _words(child.name)) > 0 for token in tokens):
                roots.append((child, 4))
    except OSError:
        pass
    return roots


def _scan_entries(
    tokens: list[str],
    *,
    budget_seconds: float = _SCAN_SECONDS,
    max_exes: int = _SCAN_MAX_EXES,
) -> list[tuple[str, tuple[str, ...]]]:
    """(exe path, parent folder names) from a depth/time-capped walk."""
    entries: list[tuple[str, tuple[str, ...]]] = []
    deadline = time.monotonic() + budget_seconds
    for root, max_depth in _scan_roots(tokens):
        if not root.is_dir():
            continue
        base_depth = len(root.parts)
        stack = [root]
        while stack:
            if time.monotonic() > deadline or len(entries) >= max_exes:
                return entries
            current = stack.pop()
            try:
                with os.scandir(current) as scan:
                    for item in scan:
                        try:
                            if item.is_dir(follow_symlinks=False):
                                depth = len(Path(item.path).parts) - base_depth
                                if depth >= max_depth or item.name.lower() in _SKIP_DIRS:
                                    continue
                                stack.append(Path(item.path))
                            elif item.is_file(follow_symlinks=False) and item.name.lower().endswith(".exe"):
                                if _NOISE_STEM.match(item.name[:-4]):
                                    continue
                                parent = Path(item.path).parent
                                folders = tuple(part for part in (parent.name, parent.parent.name) if part)
                                entries.append((item.path, folders))
                        except OSError:
                            continue
            except OSError:
                continue
    return entries


# ------------------------------------------------------------------ deep search


def _deep_token(query: str) -> str | None:
    """One sanitized search token for the whole-disk sweep (never a command)."""
    candidates = [word for word in _words(query) if len(word) >= 3]
    token = max(candidates, key=len) if candidates else " ".join(_words(query))
    token = _TOKEN_SAFE.sub("", token)
    return token if len(token) >= 2 else None


def _deep_script(token: str, out_file: str | None = None) -> str:
    system_drive = os.environ.get("SystemDrive", "C:") + os.sep
    script = (
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
        "$ErrorActionPreference='SilentlyContinue';"
        f"Get-ChildItem -LiteralPath '{system_drive}' -Recurse -File -Filter '*{token}*' -ErrorAction SilentlyContinue"
        " | Where-Object { $_.Extension -in '.exe', '.lnk' }"
        " | Select-Object -First 60 -ExpandProperty FullName"
    )
    if out_file is not None:
        script += f" | Out-File -LiteralPath '{out_file}' -Encoding utf8"
    return script


def _deep_entries(query: str, *, elevated: bool = False, timeout: float = _DEEP_TIMEOUT) -> list[str]:
    """Whole-disk PowerShell sweep for files matching the query token."""
    token = _deep_token(query)
    if not token:
        return []
    if elevated:
        return _deep_entries_elevated(token, timeout=timeout)
    output = _run_powershell_partial(_deep_script(token), timeout)
    return [line.strip() for line in (output or "").splitlines() if line.strip()]


def _deep_entries_elevated(token: str, *, timeout: float = _ELEVATED_TIMEOUT) -> list[str]:
    """Same sweep, run as administrator — one UAC prompt, owner decides."""
    out_fd, out_path = tempfile.mkstemp(prefix="xairex-find-", suffix=".txt")
    os.close(out_fd)
    script_fd, script_path = tempfile.mkstemp(prefix="xairex-find-", suffix=".ps1")
    try:
        os.write(script_fd, _deep_script(token, out_file=out_path).encode("utf-8"))
        os.close(script_fd)
        wrapper = (
            "$p = Start-Process -FilePath 'powershell.exe' -Verb RunAs -Wait -PassThru "
            f"-ArgumentList @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File','{script_path}'); "
            "exit $p.ExitCode"
        )
        try:
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", wrapper],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        try:
            text = Path(out_path).read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            return []
        return [line.strip() for line in text.splitlines() if line.strip()]
    finally:
        for leftover in (out_path, script_path):
            try:
                Path(leftover).unlink(missing_ok=True)
            except OSError:
                pass


# --------------------------------------------------------------------- finder


def _learned_candidate(settings: Settings, normalized: str) -> AppCandidate | None:
    from xairex.tools.applications import normalize_app_name  # lazy: avoids an import cycle

    for key, value in settings.tools.apps.items():
        key_norm = normalize_app_name(key)
        if not key_norm:
            continue
        if key_norm != normalized and not (len(normalized) >= 3 and (normalized in key_norm or key_norm in normalized)):
            continue
        try:
            if value.endswith(":"):
                return AppCandidate(name=key, path=value, source="learned", score=10.0, penalty=0, kind="uri")
            if Path(value).is_file():
                kind = "shortcut" if value.lower().endswith(".lnk") else "exe"
                return AppCandidate(name=key, path=value, source="learned", score=10.0, penalty=0, kind=kind)
        except OSError:
            continue
    return None


def _raw_hits(tokens: list[str]) -> list[_RawHit]:
    hits: list[_RawHit] = []
    for lnk, target in _shortcut_entries():
        if "uninstall" in Path(lnk).stem.lower():
            continue
        hits.append(_raw_from_shortcut(lnk, target))
    for name, path in _app_path_entries():
        try:
            if not Path(path).is_file():
                continue
        except OSError:
            continue
        hits.append(_RawHit(name=Path(name).stem, path=path, source="app paths"))
    for path, folders in _scan_entries(tokens):
        hits.append(_RawHit(name=Path(path).stem, path=path, source="scan", folders=folders))
    return hits


def find_apps(
    settings: Settings,
    query: str,
    *,
    deep: bool = False,
    elevated: bool = False,
) -> list[AppCandidate]:
    """Ranked app candidates for *query* (best first, at most ten)."""
    text = str(query or "").strip()
    if not text:
        return []

    from xairex.tools.applications import normalize_app_name  # lazy: avoids an import cycle

    learned = _learned_candidate(settings, normalize_app_name(text))
    if learned is not None:
        return [learned]

    tokens = query_tokens(text)
    if not tokens:
        return []

    scored: list[AppCandidate] = []
    for raw in _raw_hits(tokens):
        result = _score(tokens, raw)
        if result is None:
            continue
        score, penalty = result
        scored.append(
            AppCandidate(name=raw.name, path=raw.path, source=raw.source, score=score, penalty=penalty, kind=raw.kind)
        )
    if deep or elevated:
        for path in _deep_entries(text, elevated=elevated):
            if path.lower().endswith(".lnk"):
                parent = Path(path).parent
                folders = tuple(part for part in (parent.name, parent.parent.name) if part)
                hit = _RawHit(name=Path(path).stem, path=path, source="deep search", folders=folders, kind="shortcut")
            else:
                hit = _RawHit(name=Path(path).stem, path=path, source="deep search")
            result = _score(tokens, hit)
            if result is None:
                continue
            score, penalty = result
            scored.append(
                AppCandidate(
                    name=hit.name, path=path, source="deep search", score=score, penalty=penalty, kind=hit.kind
                )
            )

    scored.sort(key=lambda candidate: candidate.order)
    unique: list[AppCandidate] = []
    seen: set[str] = set()
    for candidate in scored:
        key = candidate.path.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
        if len(unique) >= 10:
            break
    return unique

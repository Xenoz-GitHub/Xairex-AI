"""open_app / find_app: launch any application on this PC (G19, D37–D38).

Resolution order: learned/custom mappings (``tools.apps``) → built-in table of
common Windows apps → live discovery (:mod:`xairex.tools.discovery`: Start
Menu/Desktop shortcuts, registry app paths, bounded scan; optional PowerShell
deep search). A discovered app is learned back into ``tools.apps`` so the next
request resolves instantly.

The name allowlist is gone (owner decision 2026-10-16: "it must allow all").
The rails that stay: every call goes through the typed tool registry, model
text never becomes a shell command, and only existing ``.exe``/``.lnk`` files
(or the known ``ms-settings:`` URI) are ever handed to the shell.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from xairex.config import Settings, save_settings
from xairex.tools.discovery import AppCandidate, find_apps, same_rank
from xairex.tools.registry import ToolResult, ToolSpec

logger = logging.getLogger("xairex.tools.apps")

#: Spelling variants mapped onto the canonical table keys.
_ALIASES = {
    "taskmgr": "task manager",
    "task-manager": "task manager",
    "vs code": "vscode",
    "visual studio code": "vscode",
    "google chrome": "chrome",
    "ms edge": "edge",
    "microsoft edge": "edge",
    "ms paint": "paint",
    "file explorer": "explorer",
    "files": "explorer",
    "windows settings": "settings",
    "settings app": "settings",
    "turboc": "turbo c++",
}

#: Trailing noise words dropped when learning a second alias for an app.
_LEARN_SUFFIX = re.compile(r"\s+(?:ide|app|application|program|editor|suite|studio)$")


def normalize_app_name(name: str) -> str:
    cleaned = " ".join(str(name or "").strip().lower().replace("_", " ").split())
    return _ALIASES.get(cleaned, cleaned)


def _join(base: str | None, *parts: str) -> str | None:
    return str(Path(base).joinpath(*parts)) if base else None


def _candidate_targets() -> dict[str, tuple[str, ...]]:
    """Canonical app name -> candidate targets (exe name, path or URI)."""
    pf = os.environ.get("ProgramFiles")
    pfx86 = os.environ.get("ProgramFiles(x86)")
    local = os.environ.get("LOCALAPPDATA")
    roaming = os.environ.get("APPDATA")
    table: dict[str, tuple[str, ...]] = {
        "calculator": ("calc.exe",),
        "notepad": ("notepad.exe",),
        "paint": ("mspaint.exe",),
        "explorer": ("explorer.exe",),
        "task manager": ("taskmgr.exe",),
        "settings": ("ms-settings:",),
        "terminal": ("wt.exe",),
        "chrome": tuple(
            path
            for path in (
                _join(pf, "Google", "Chrome", "Application", "chrome.exe"),
                _join(pfx86, "Google", "Chrome", "Application", "chrome.exe"),
                _join(local, "Google", "Chrome", "Application", "chrome.exe"),
            )
            if path
        ),
        "edge": tuple(
            path
            for path in (
                _join(pfx86, "Microsoft", "Edge", "Application", "msedge.exe"),
                _join(pf, "Microsoft", "Edge", "Application", "msedge.exe"),
            )
            if path
        ),
        "firefox": tuple(
            path
            for path in (
                _join(pf, "Mozilla Firefox", "firefox.exe"),
                _join(pfx86, "Mozilla Firefox", "firefox.exe"),
            )
            if path
        ),
        "vscode": tuple(
            path
            for path in (
                _join(local, "Programs", "Microsoft VS Code", "Code.exe"),
                _join(pf, "Microsoft VS Code", "Code.exe"),
            )
            if path
        ),
        "spotify": tuple(
            path
            for path in (
                _join(roaming, "Spotify", "Spotify.exe"),
                _join(local, "Microsoft", "WindowsApps", "Spotify.exe"),
            )
            if path
        ),
    }
    return table


def _candidate_exists(candidate: str) -> bool:
    if candidate.endswith(":"):  # URI scheme like ms-settings:
        return True
    if os.sep in candidate or (os.altsep and os.altsep in candidate):
        return Path(candidate).is_file()
    return shutil.which(candidate) is not None


@dataclass(frozen=True)
class ResolvedApp:
    """Result of resolving an app name: target, or a speakable error."""

    label: str
    target: str | None = None
    error: str | None = None


def known_app_names(settings: Settings) -> set[str]:
    """Every canonical app name the assistant knows about (built-ins + learned)."""
    return set(_candidate_targets()) | {normalize_app_name(key) for key in settings.tools.apps}


def resolve_app(settings: Settings, name: str) -> ResolvedApp:
    """Resolve *name* to an executable target or a speakable error.

    Unknown names are not an error here — callers hand those to live discovery.
    """
    normalized = normalize_app_name(name)
    if not normalized:
        return ResolvedApp(label=str(name), error="No application name was given.")

    custom = {normalize_app_name(key): value for key, value in settings.tools.apps.items()}
    if normalized in custom:
        return ResolvedApp(label=normalized, target=custom[normalized])

    table = _candidate_targets()
    if normalized not in table:
        return ResolvedApp(label=normalized, error=f"I don't know an app called '{normalized}' yet.")

    for candidate in table[normalized]:
        if _candidate_exists(candidate):
            if os.sep in candidate or (os.altsep and os.altsep in candidate):
                return ResolvedApp(label=normalized, target=candidate)
            found = shutil.which(candidate)
            if found:
                return ResolvedApp(label=normalized, target=found)
    return ResolvedApp(label=normalized, error=f"I couldn't find {normalized} on this machine.")


def launch(target: str) -> None:
    """Start a resolved target (exe path or URI). Kept small for tests."""
    os.startfile(target)  # type: ignore[attr-defined]  # Windows-only by design


def _looks_like_path(text: str) -> bool:
    return "\\" in text or "/" in text or text.lower().endswith(".exe") or (len(text) > 1 and text[1] == ":")


def _open_problem(target: str) -> str | None:
    """Speakable reason a target may not be opened, or None when it is fine."""
    text = str(target or "").strip()
    if not text:
        return "No target was given."
    if text.endswith(":"):
        if text == "ms-settings:":
            return None
        return f"I can't open the '{text}' link."
    path = Path(text)
    try:
        if not path.is_file():
            return f"I can't find that file any more: {text}"
    except OSError:
        return f"I can't check that path: {text}"
    suffix = path.suffix.lower()
    if suffix not in (".exe", ".lnk"):
        return f"For safety I only open .exe and .lnk files directly (got '{suffix or 'no extension'}')."
    return None


def _open_target(target: str, label: str) -> ToolResult:
    problem = _open_problem(target)
    if problem:
        return ToolResult(False, problem)
    try:
        launch(target)
    except OSError as exc:
        return ToolResult(False, f"Could not launch {label}: {exc}")
    return ToolResult(True, f"Opening {label}.", data={"target": target})


def _learn(settings: Settings, query: str, candidate: AppCandidate) -> None:
    """Remember a discovered app (in memory and in settings.json when possible)."""
    key = normalize_app_name(query)
    keys = [key]
    compact = _LEARN_SUFFIX.sub("", key).strip()
    if compact and compact != key:
        keys.append(compact)
    for alias in keys:
        if alias and alias not in settings.tools.apps:
            settings.tools.apps[alias] = candidate.path
    if settings.config_path is None:
        return
    try:
        save_settings(settings)
    except OSError as exc:
        logger.warning("Could not persist learned app %r: %s", key, exc)


def _candidates_line(candidates: list[AppCandidate], limit: int = 4) -> str:
    return "; ".join(
        f"{index + 1}) {candidate.name} — {candidate.path}" for index, candidate in enumerate(candidates[:limit])
    )


def open_app_tool(settings: Settings) -> ToolSpec:
    def handler(args: dict) -> ToolResult:
        requested = str(args.get("app", "")).strip().strip('"')
        if not requested:
            return ToolResult(False, "No application name was given.")

        if _looks_like_path(requested) or requested.endswith(":"):
            return _open_target(requested, Path(requested).stem or requested)

        resolved = resolve_app(settings, requested)
        if resolved.error is None and resolved.target is not None:
            return _open_target(resolved.target, resolved.label)

        candidates = find_apps(settings, requested)
        if not candidates:
            return ToolResult(
                False,
                f"I couldn't find '{requested}' on this machine. "
                f"Say 'search everywhere for {requested}' and I'll sweep the whole disk.",
                data={"query": requested},
            )
        if len(candidates) > 1 and same_rank(candidates[0], candidates[1]):
            return ToolResult(
                False,
                f"I found several matches for '{requested}': {_candidates_line(candidates)}. Which one?",
                data={"candidates": [candidate.path for candidate in candidates]},
            )
        best = candidates[0]
        _learn(settings, requested, best)
        return _open_target(best.path, best.name)

    return ToolSpec(
        name="open_app",
        description=(
            "Open an application installed on this PC, e.g. 'chrome', 'notepad', 'turbo c++ ide'. "
            "Unknown apps are found on disk automatically; a full .exe or .lnk path also works."
        ),
        parameters={
            "type": "object",
            "properties": {
                "app": {
                    "type": "string",
                    "description": "App name as the user said it (e.g. 'turbo c++ ide'), or a full .exe/.lnk path.",
                }
            },
            "required": ["app"],
        },
        handler=handler,
        timeout_seconds=30.0,
    )


def find_app_tool(settings: Settings) -> ToolSpec:
    def handler(args: dict) -> ToolResult:
        query = str(args.get("query", "")).strip()
        if not query:
            return ToolResult(False, "Tell me what app to find, like 'turbo c++ ide'.")
        elevated = bool(args.get("elevated", False))
        deep = bool(args.get("deep", False)) or elevated

        candidates = find_apps(settings, query, deep=deep, elevated=elevated)
        if not candidates:
            where = "the whole disk" if deep else "the Start Menu, the registry and the common folders"
            hint = (
                ""
                if deep
                else " I can sweep the whole disk with PowerShell if you say 'search everywhere for " + query + "'."
            )
            return ToolResult(False, f"I searched {where} and found no app matching '{query}'.{hint}")
        if len(candidates) > 1 and same_rank(candidates[0], candidates[1]):
            return ToolResult(
                False,
                f"I found several apps matching '{query}': {_candidates_line(candidates)}. Which one?",
                data={"candidates": [candidate.path for candidate in candidates]},
            )
        best = candidates[0]
        _learn(settings, query, best)
        return ToolResult(
            True,
            f"I found {best.name} at {best.path}. Say 'open {best.name}' and I'll launch it.",
            data={
                "candidates": [
                    {"name": candidate.name, "path": candidate.path, "source": candidate.source}
                    for candidate in candidates
                ]
            },
        )

    return ToolSpec(
        name="find_app",
        description=(
            "Find any application installed on this PC by name (Start Menu, registry, common folders). "
            "deep=true sweeps the whole disk with PowerShell; elevated=true asks for admin via UAC first. "
            "Use before open_app when the app may not be known."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "App name to find, e.g. 'turbo c++ ide'."},
                "deep": {"type": "boolean", "description": "Also sweep the whole disk with PowerShell (slower)."},
                "elevated": {"type": "boolean", "description": "Run the disk sweep as administrator (one UAC prompt)."},
            },
            "required": ["query"],
        },
        handler=handler,
        timeout_seconds=320.0,
    )

"""File management tools (G6 + G11, D28 amended by D39).

``find_files`` searches the approved roots (read-only). The management tools —
``write_file``, ``append_file``, ``edit_file``, ``move_file``, ``copy_file``,
``make_directory`` — accept any owner path (absolute or project-relative,
``~`` expanded). Rails that stay: existing files are never overwritten unless
the caller explicitly passes ``overwrite=true``, there is no delete tool, and
all text is written UTF-8.
"""

from __future__ import annotations

import fnmatch
import os
import re
import shutil
import time
from pathlib import Path

from xairex.config import Settings
from xairex.tools.registry import ToolResult, ToolSpec

_MAX_RESULTS = 15
_SEARCH_SECONDS = 12.0
_MAX_DEPTH = 6
_MAX_CONTENT_CHARS = 500_000


def approved_roots(settings: Settings) -> list[Path]:
    return [settings.resolve_path(raw) for raw in settings.tools.approved_directories]


def _within(path: Path, roots: list[Path]) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def find_files_tool(settings: Settings) -> ToolSpec:
    roots = approved_roots(settings)

    def handler(args: dict) -> ToolResult:
        pattern = str(args.get("pattern", "")).strip()
        if not pattern:
            return ToolResult(False, "Tell me what to search for, like 'taxes' or '*.pdf'.")

        search_roots = roots
        root_arg = str(args.get("root", "") or "").strip()
        if root_arg:
            requested = settings.resolve_path(root_arg)
            if not _within(requested, roots):
                allowed = ", ".join(str(root) for root in roots) or "none configured"
                return ToolResult(False, f"That folder is outside my approved folders ({allowed}).")
            search_roots = [requested]

        wildcard = any(char in pattern for char in "*?[")
        needle = pattern.lower()
        matches: list[str] = []
        truncated = False
        deadline = time.monotonic() + _SEARCH_SECONDS

        for base in search_roots:
            if not base.is_dir():
                continue
            base_depth = len(base.parts)
            for dirpath, dirnames, filenames in os.walk(base):
                if time.monotonic() > deadline:
                    truncated = True
                    break
                depth = len(Path(dirpath).parts) - base_depth
                if depth >= _MAX_DEPTH:
                    dirnames[:] = []
                dirnames[:] = [name for name in dirnames if not name.startswith(".")]
                for filename in filenames:
                    hit = fnmatch.fnmatch(filename.lower(), needle) if wildcard else needle in filename.lower()
                    if hit:
                        matches.append(os.path.join(dirpath, filename))
                        if len(matches) >= _MAX_RESULTS:
                            truncated = True
                            break
                if len(matches) >= _MAX_RESULTS or truncated:
                    break
            if len(matches) >= _MAX_RESULTS or truncated:
                break

        if not matches:
            where = ", ".join(root.name for root in search_roots) or "the approved folders"
            return ToolResult(False, f"I found no files matching '{pattern}' in {where}.")

        names = [Path(match).name for match in matches[:4]]
        listing = ", ".join(names)
        more = f", and {len(matches) - 4} more" if len(matches) > 4 else ""
        note = " I stopped early — there are more." if truncated else ""
        return ToolResult(
            True,
            f"I found {len(matches)} files: {listing}{more}.{note}",
            data={"matches": matches},
        )

    return ToolSpec(
        name="find_files",
        description=(
            "Search the user's approved folders for files by name. "
            "Use wildcards like '*.pdf' or a plain word like 'budget'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "File name pattern, e.g. '*.pdf' or 'budget'."},
                "root": {"type": "string", "description": "Optional folder to search inside (must be approved)."},
            },
            "required": ["pattern"],
        },
        handler=handler,
        timeout_seconds=15.0,
    )


# ----------------------------------------------------- file management (G11)


def _target_path(settings: Settings, raw: str) -> Path:
    return settings.resolve_path(str(raw).strip())


def _write_problem(path: Path) -> str | None:
    if path.exists() and path.is_dir():
        return f"{path} is a folder, not a file."
    return None


def write_file_tool(settings: Settings) -> ToolSpec:
    def handler(args: dict) -> ToolResult:
        raw_path = str(args.get("path", "")).strip()
        if not raw_path:
            return ToolResult(False, "I need a file path to save to.")
        content = str(args.get("content", ""))
        if len(content) > _MAX_CONTENT_CHARS:
            return ToolResult(
                False, f"That is more text than I can write in one go (max {_MAX_CONTENT_CHARS} characters)."
            )
        path = _target_path(settings, raw_path)
        problem = _write_problem(path)
        if problem:
            return ToolResult(False, problem)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            return ToolResult(False, f"Could not write {path}: {exc}")
        size = path.stat().st_size
        return ToolResult(True, f"Saved {path} ({size} bytes).", data={"path": str(path), "bytes": size})

    return ToolSpec(
        name="write_file",
        description="Create a text file (or replace its contents) at any path. Parent folders are created automatically.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path, e.g. '~/Desktop/notes.txt'."},
                "content": {"type": "string", "description": "Full text to save (UTF-8)."},
            },
            "required": ["path", "content"],
        },
        handler=handler,
        timeout_seconds=15.0,
    )


def append_file_tool(settings: Settings) -> ToolSpec:
    def handler(args: dict) -> ToolResult:
        raw_path = str(args.get("path", "")).strip()
        if not raw_path:
            return ToolResult(False, "I need a file path to append to.")
        content = str(args.get("content", ""))
        if len(content) > _MAX_CONTENT_CHARS:
            return ToolResult(
                False, f"That is more text than I can append in one go (max {_MAX_CONTENT_CHARS} characters)."
            )
        path = _target_path(settings, raw_path)
        problem = _write_problem(path)
        if problem:
            return ToolResult(False, problem)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(content)
        except OSError as exc:
            return ToolResult(False, f"Could not append to {path}: {exc}")
        size = path.stat().st_size
        return ToolResult(True, f"Appended to {path} ({size} bytes total).", data={"path": str(path), "bytes": size})

    return ToolSpec(
        name="append_file",
        description="Append text to a file (creates it if it does not exist yet).",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to append to."},
                "content": {"type": "string", "description": "Text to append (UTF-8)."},
            },
            "required": ["path", "content"],
        },
        handler=handler,
        timeout_seconds=15.0,
    )


def edit_file_tool(settings: Settings) -> ToolSpec:
    def handler(args: dict) -> ToolResult:
        raw_path = str(args.get("path", "")).strip()
        find = str(args.get("find", ""))
        replace = str(args.get("replace", ""))
        if not raw_path:
            return ToolResult(False, "I need a file path to edit.")
        if not find:
            return ToolResult(False, "Tell me the exact text to find and what to replace it with.")
        path = _target_path(settings, raw_path)
        if not path.is_file():
            return ToolResult(False, f"Could not find the file {path}.")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ToolResult(False, f"{path} does not look like a text file I can edit.")
        except OSError as exc:
            return ToolResult(False, f"Could not read {path}: {exc}")
        occurrences = text.count(find)
        if occurrences == 0:
            return ToolResult(False, f"I couldn't find that text in {path.name}.")
        replaced = occurrences if bool(args.get("all", False)) else 1
        try:
            path.write_text(text.replace(find, replace, replaced), encoding="utf-8")
        except OSError as exc:
            return ToolResult(False, f"Could not write {path}: {exc}")
        note = f"{replaced} of {occurrences} occurrences" if replaced < occurrences else f"{replaced} occurrence(s)"
        return ToolResult(True, f"Replaced {note} in {path.name}.", data={"path": str(path), "replaced": replaced})

    return ToolSpec(
        name="edit_file",
        description=(
            "Replace exact text inside a file (first occurrence, or every occurrence with all=true). "
            "Read the file first if you are not sure of the exact text."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to edit."},
                "find": {"type": "string", "description": "Exact text to find."},
                "replace": {"type": "string", "description": "Replacement text."},
                "all": {"type": "boolean", "description": "Replace every occurrence instead of the first."},
            },
            "required": ["path", "find", "replace"],
        },
        handler=handler,
        timeout_seconds=15.0,
    )


def _move_or_copy(args: dict, settings: Settings, *, copy: bool) -> ToolResult:
    raw_source = str(args.get("source", "")).strip()
    raw_destination = str(args.get("destination", "")).strip()
    if not raw_source or not raw_destination:
        return ToolResult(False, "I need both a source and a destination path.")
    source = _target_path(settings, raw_source)
    if not source.exists():
        return ToolResult(False, f"I can't find {source}.")
    destination = _target_path(settings, raw_destination)
    final = destination / source.name if destination.is_dir() else destination
    if final.exists() and not bool(args.get("overwrite", False)):
        return ToolResult(False, f"{final} already exists — ask me again with 'overwrite' if you want it replaced.")
    verb = "copy" if copy else "move"
    try:
        final.parent.mkdir(parents=True, exist_ok=True)
        if copy:
            if source.is_dir():
                shutil.copytree(str(source), str(final), dirs_exist_ok=bool(args.get("overwrite", False)))
            else:
                shutil.copy2(str(source), str(final))
        else:
            shutil.move(str(source), str(final))
    except OSError as exc:
        return ToolResult(False, f"Could not {verb} {source.name}: {exc}")
    return ToolResult(
        True,
        f"{'Copied' if copy else 'Moved'} {source.name} to {final}.",
        data={"source": str(source), "destination": str(final)},
    )


def move_file_tool(settings: Settings) -> ToolSpec:
    def handler(args: dict) -> ToolResult:
        return _move_or_copy(args, settings, copy=False)

    return ToolSpec(
        name="move_file",
        description=(
            "Move or rename a file or folder. If the destination is an existing folder the item moves inside it; "
            "an existing target is only replaced with overwrite=true."
        ),
        parameters={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "File or folder to move."},
                "destination": {"type": "string", "description": "Target path or target folder."},
                "overwrite": {"type": "boolean", "description": "Replace an existing file with the same name."},
            },
            "required": ["source", "destination"],
        },
        handler=handler,
        timeout_seconds=60.0,
    )


def copy_file_tool(settings: Settings) -> ToolSpec:
    def handler(args: dict) -> ToolResult:
        return _move_or_copy(args, settings, copy=True)

    return ToolSpec(
        name="copy_file",
        description=(
            "Copy a file or folder. If the destination is an existing folder the item is copied inside it; "
            "an existing target is only replaced with overwrite=true."
        ),
        parameters={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "File or folder to copy."},
                "destination": {"type": "string", "description": "Target path or target folder."},
                "overwrite": {"type": "boolean", "description": "Replace an existing file with the same name."},
            },
            "required": ["source", "destination"],
        },
        handler=handler,
        timeout_seconds=120.0,
    )


def make_directory_tool(settings: Settings) -> ToolSpec:
    def handler(args: dict) -> ToolResult:
        raw_path = str(args.get("path", "")).strip()
        if not raw_path:
            return ToolResult(False, "I need a folder path to create.")
        path = _target_path(settings, raw_path)
        if path.is_dir():
            return ToolResult(True, f"The folder {path} already exists.", data={"path": str(path), "created": False})
        if path.exists():
            return ToolResult(False, f"{path} exists and is a file, so I can't create a folder there.")
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return ToolResult(False, f"Could not create {path}: {exc}")
        return ToolResult(True, f"Created folder {path}.", data={"path": str(path), "created": True})

    return ToolSpec(
        name="make_directory",
        description="Create a folder (parent folders included).",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Folder path to create."}},
            "required": ["path"],
        },
        handler=handler,
        timeout_seconds=15.0,
    )


# ------------------------------------------------------- folder organizer (G11)

#: Category key -> (target folder name, extensions). The target folder is
#: created *inside* the organized folder, so "organize Downloads" stays
#: self-contained and trivially reversible — nothing is deleted, ever.
_ORGANIZE_CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("images", "Images", "jpg jpeg jfif png gif bmp webp heic heif svg ico tif tiff avif psd cr2 nef arw dng"),
    ("videos", "Videos", "mp4 mkv avi mov wmv flv webm m4v mpg mpeg 3gp"),
    ("music", "Music", "mp3 wav flac m4a aac ogg oga wma opus mid midi"),
    ("documents", "Documents", "pdf doc docx txt rtf odt ods xls xlsx csv ppt pptx odp md markdown epub mobi"),
    ("archives", "Archives", "zip rar 7z tar gz tgz bz2 xz iso jar"),
    ("installers", "Installers", "exe msi msix appx deb rpm dmg pkg apk"),
    (
        "code",
        "Code",
        (
            "py pyw js mjs cjs ts tsx jsx html htm css scss c cpp cc cxx h hpp hh cs java go rs rb php sql "
            "json jsonl yaml yml toml ini cfg xml sh ps1 bat cmd ipynb lua pl r kt swift dart vue svelte"
        ),
    ),
    ("fonts", "Fonts", "ttf otf woff woff2"),
)

_EXT_TO_CATEGORY: dict[str, tuple[str, str]] = {
    ext: (key, folder_name) for key, folder_name, exts in _ORGANIZE_CATEGORIES for ext in exts.split()
}

#: Loose files that are never moved: Windows bookkeeping, Office lock files
#: and dotfiles.
_ORGANIZE_SKIP_NAMES = frozenset({"desktop.ini", "thumbs.db", "iconcache.db"})

_MAX_NAMES_IN_MESSAGE = 5

#: Bare folder names the organizer knows by heart (resolved under the user's
#: home). Anything else must be a real path.
_KNOWN_FOLDER_NAMES = {
    "downloads": "Downloads",
    "download": "Downloads",
    "documents": "Documents",
    "document": "Documents",
    "docs": "Documents",
    "desktop": "Desktop",
    "pictures": "Pictures",
    "photos": "Pictures",
    "videos": "Videos",
    "video": "Videos",
    "music": "Music",
    "songs": "Music",
}


def resolve_known_location(settings: Settings, raw: str) -> Path | None:
    """Resolve a known folder name ("downloads") or any path to an existing location.

    Shared by the folder organizer (G11) and the Defender scanner (G13).
    Accepts conversational forms too ("my downloads folder", "the documents
    directory"), paths (``~`` expanded, project-relative) and bare names
    under the user's home. Returns None when nothing exists at the target.
    """
    text = str(raw).strip().strip("\"'")
    if not text:
        return None
    if any(sep in text for sep in ("\\", "/", "~", ":")):
        candidate = _target_path(settings, text)
        return candidate if candidate.exists() else None
    text = re.sub(r"^(?:(?:the|my|of)\s+)+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+(?:folder|directory)$", "", text, flags=re.IGNORECASE)
    if not text:
        return None
    known = _KNOWN_FOLDER_NAMES.get(" ".join(text.lower().split()))
    if known is not None:
        candidate = Path.home() / known
        return candidate if candidate.exists() else None
    candidate = Path.home() / text
    return candidate if candidate.exists() else None


def _organize_folder(settings: Settings, raw: str) -> Path | None:
    """Resolve a known folder name ("downloads") or any folder path to a real folder."""
    candidate = resolve_known_location(settings, raw)
    return candidate if candidate is not None and candidate.is_dir() else None


def _is_organize_skippable(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith((".", "~$")) or lowered in _ORGANIZE_SKIP_NAMES


def _organize_plan(folder: Path) -> tuple[dict[str, list[Path]], list[str]]:
    """Group the loose files in *folder* by category.

    Returns ``(plan, leftovers)``: *plan* maps category keys to the files that
    would move, *leftovers* are the names of unrecognized files (they stay).
    """
    plan: dict[str, list[Path]] = {}
    leftovers: list[str] = []
    for entry in sorted(folder.iterdir(), key=lambda path: path.name.lower()):
        if not entry.is_file() or _is_organize_skippable(entry.name):
            continue
        category = _EXT_TO_CATEGORY.get(entry.suffix.lower().lstrip("."))
        if category is None:
            leftovers.append(entry.name)
            continue
        plan.setdefault(category[0], []).append(entry)
    return plan, leftovers


def _files_word(count: int) -> str:
    return f"{count} file" if count == 1 else f"{count} files"


def _describe_counts(counts: dict[str, int]) -> str:
    return ", ".join(
        f"{folder_name.lower()} {counts[key]}" for key, folder_name, _exts in _ORGANIZE_CATEGORIES if counts.get(key)
    )


def _name_note(count: int, names: list[str], template: str) -> str:
    shown = ", ".join(names[:_MAX_NAMES_IN_MESSAGE])
    more = " and more" if count > _MAX_NAMES_IN_MESSAGE else ""
    return template.format(count=count, names=f"{shown}{more}")


def _organize_apply(folder: Path, plan: dict[str, list[Path]]) -> ToolResult:
    label = folder.name or str(folder)
    total = sum(len(files) for files in plan.values())
    if total == 0:
        return ToolResult(
            True,
            f"Your {label} folder is already tidy — no files to organize.",
            data={"action": "apply", "folder": str(folder), "moved": 0, "total": 0, "skipped": [], "failed": []},
        )

    moved = 0
    moved_counts: dict[str, int] = {}
    skipped: list[str] = []
    failed: list[str] = []
    # Deterministic order (category table order) keeps behavior testable.
    for key, folder_name, _exts in _ORGANIZE_CATEGORIES:
        files = plan.get(key)
        if not files:
            continue
        target_dir = folder / folder_name
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            failed.extend(source.name for source in files)
            continue
        for source in files:
            destination = target_dir / source.name
            if destination.exists():
                skipped.append(source.name)  # never overwrite
                continue
            try:
                shutil.move(str(source), str(destination))
            except OSError:
                failed.append(source.name)
                continue
            moved += 1
            moved_counts[key] = moved_counts.get(key, 0) + 1

    if moved:
        head = f"Done — {moved} of {total} files organized in your {label} folder: {_describe_counts(moved_counts)}."
    else:
        head = f"Nothing moved in your {label} folder."
    notes: list[str] = []
    if skipped:
        notes.append(
            _name_note(
                len(skipped),
                skipped,
                "{count} stayed put because a file with the same name is already there: {names}.",
            )
        )
    if failed:
        notes.append(
            _name_note(
                len(failed),
                failed,
                "{count} could not be moved (they may be open in another app): {names}.",
            )
        )
    return ToolResult(
        True,
        " ".join([head, *notes]),
        data={
            "action": "apply",
            "folder": str(folder),
            "moved": moved,
            "total": total,
            "skipped": skipped[:8],
            "failed": failed[:8],
        },
    )


def organize_folder_tool(settings: Settings) -> ToolSpec:
    """Preview -> confirm -> move sorting of one folder by file type (G11).

    ``preview`` only counts; the runtime speaks the plan and arms a pending
    yes/no (a bare "yes" then calls this tool with ``apply``). ``apply``
    re-plans from the files on disk, so the plan is always fresh; same-name
    targets are skipped, never overwritten.
    """

    def handler(args: dict) -> ToolResult:
        raw_folder = str(args.get("folder", "")).strip()
        action = str(args.get("action", "preview")).strip().lower()
        folder = _organize_folder(settings, raw_folder)
        if folder is None:
            return ToolResult(
                False,
                f"I can't find a folder called '{raw_folder or '(none)'}' — give me the full path if it lives somewhere else.",
            )
        try:
            plan, leftovers = _organize_plan(folder)
        except OSError as exc:
            return ToolResult(False, f"I couldn't read the folder {folder}: {exc}")
        if action == "apply":
            return _organize_apply(folder, plan)

        label = folder.name or str(folder)
        counts = {key: len(files) for key, files in plan.items()}
        total = sum(counts.values())
        if total == 0:
            return ToolResult(
                True,
                f"Your {label} folder is already tidy — no files to organize.",
                data={"action": "preview", "folder": str(folder), "total": 0, "plan": {}},
            )
        described = _describe_counts(counts)
        if leftovers:
            stays = "stays" if len(leftovers) == 1 else "stay"
            plan_line = (
                f"Here's the plan for your {label} folder: I can sort {_files_word(total)} — {described}. "
                f"{_files_word(len(leftovers))} {stays} in place (unrecognized type)."
            )
        else:
            plan_line = f"Here's the plan for your {label} folder: {_files_word(total)} — {described}."
        message = (
            f"{plan_line} I'll create one folder per type and move each file in. "
            f"Nothing has moved yet — say yes and I'll do it."
        )
        return ToolResult(
            True,
            message,
            data={"action": "preview", "folder": str(folder), "total": total, "plan": counts},
        )

    return ToolSpec(
        name="organize_folder",
        description=(
            "Sort the loose files in a folder by type (images, videos, music, documents, archives, installers, "
            "code, fonts) into matching subfolders inside the same folder. action 'preview' describes the plan "
            "without moving anything; action 'apply' moves the files (never overwrites — same-name files stay put). "
            "apply only after the user clearly says yes."
        ),
        parameters={
            "type": "object",
            "properties": {
                "folder": {
                    "type": "string",
                    "description": (
                        "Known folder name (downloads, documents, desktop, pictures, videos, music) or any folder path."
                    ),
                },
                "action": {
                    "type": "string",
                    "enum": ["preview", "apply"],
                    "description": "preview describes the plan; apply moves the files.",
                },
            },
            "required": ["folder", "action"],
        },
        handler=handler,
        timeout_seconds=120.0,
    )

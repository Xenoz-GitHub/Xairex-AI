"""Deterministic no-LLM command router (G7, D23).

The common operating commands are matched with fixed patterns, so the whole
"speak -> confirmation" round trip stays fast and predictable; anything
ambiguous returns ``None`` and the language model takes over (with the same
tool registry attached). The router can only produce typed tool calls — free
text is never executed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from xairex.config import Settings
from xairex.tools.applications import known_app_names, normalize_app_name
from xairex.tools.websites import site_aliases, validate_web_url


@dataclass(frozen=True)
class RoutedCommand:
    """One deterministic tool call parsed from the user's words."""

    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)


def _normalize(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split()).strip(" .!?;,")


#: Conversational padding that must not stop a spoken command from matching.
#: Spoken input arrives with interjections and politeness typed input never has
#: ("yo, can you please turn the volume up"); these are stripped so both hit the
#: same patterns. Observed 2026-10-16: the owner's natural phrasing missed the
#: router, fell through to the LLM, and the small model narrated fake actions.
_WRAPPER_PATTERNS = (
    re.compile(r"^(?:yo|hey|hi|hello|ok|okay|so|then|now|um|uh|xairex|please|pls)[,\s]+"),
    re.compile(r"^(?:can|could|would|will)\s+(?:you|u)\s+(?:please\s+)?"),
    re.compile(r"^do\s+you\s+mind\s+"),
    re.compile(
        r"^(?:i\s+want\s+you\s+to|i\s+need\s+you\s+to|i\s+would\s+like\s+you\s+to|i'd\s+like\s+you\s+to|i\s+want\s+to)\s+"
    ),
    re.compile(r"\s+(?:please|now|for\s+me|thanks|thank\s+you|ok|okay|buddy|xairex)$"),
    re.compile(r"\s+(?:a\s+bit|a\s+little|a\s+notch|a\s+tad|some)\s*$"),
)


def _strip_wrappers(text: str) -> str:
    """Remove conversational padding so spoken commands match typed patterns."""
    for _ in range(6):
        changed = False
        for pattern in _WRAPPER_PATTERNS:
            stripped = pattern.sub("", text, count=1).strip(" ,.!?;:")
            if stripped != text:
                text = stripped
                changed = True
        if not changed:
            break
    return text


_OPEN_IN_RE = re.compile(
    r"^(?:open|launch|start|go\s+to)\s+(?:the\s+)?(?P<site>.+?)\s+in\s+"
    r"(?P<browser>chrome|edge|firefox|the\s+browser|a\s+browser|browser)$"
)
_OPEN_RE = re.compile(
    r"^(?:open|launch|start|run|go\s+to|pull\s+up|bring\s+up)\s+(?:up\s+)?(?:the\s+)?(?P<target>.+?)"
    r"(?:\s+(?:app|application|for\s+me|please))?$"
)

#: VS Code (G24): opening a folder/file in the editor is deterministic — the
#: installed launcher takes the path directly. "open vs code" alone reuses the
#: last window (the tool runs the launcher without a path).
_VSCODE_NAME = r"(?:vs\s?code|vscode|visual\s+studio\s+code)"
_VSCODE_OPEN_RE = re.compile(
    r"^(?:open|launch|start|show(?:\s+me)?)\s+(?:up\s+)?(?:the\s+)?(?P<path>.+?)\s+in\s+" + _VSCODE_NAME + r"$"
)
_VSCODE_LAUNCH_RE = re.compile(r"^(?:open|launch|start)\s+(?:up\s+)?(?:the\s+)?" + _VSCODE_NAME + r"$")

#: "a folder C:\dev", "my old project X" — conversational padding before paths.
_PATH_FILLER_RE = re.compile(
    r"^(?:(?:a|an|the|my)\s+)?(?:new\s+|old\s+)?"
    r"(?:folder|directory|file|project|workspace|repo|repository|script)\s+(?P<rest>.+)$"
)

#: Organizing a folder by file type (G11): "organize my downloads", "sort out
#: my downloads folder", "clean up the files in my documents". Known folder
#: names only — other targets stay with the LLM (which can pass any path to
#: the organize_folder tool). The runtime arms a pending yes/no after the
#: preview, so the router always routes the *preview*, never the apply.
_ORGANIZE_RE = re.compile(
    r"^(?:organize|organise|sort|tidy(?:\s+up)?|arrange|declutter|clean(?:\s+up)?)\s+"
    r"(?:up\s+|out\s+)?"
    r"(?:the\s+|my\s+|a\s+)?"
    r"(?:files\s+(?:in|inside|from)\s+)?"
    r"(?:the\s+|my\s+)?"
    r"(?P<folder>downloads?|documents?|docs|desktop|pictures|photos|videos?|music|songs)"
    r"(?:\s+(?:folder|directory|files))?$"
)
_ORGANIZE_CANONICAL = {
    "download": "downloads",
    "document": "documents",
    "docs": "documents",
    "photos": "pictures",
    "video": "videos",
    "songs": "music",
}

#: Windows Defender asks (G13): "scan my computer for viruses", "run a quick
#: scan", "start a full scan", "scan my downloads for viruses". Anything that
#: is not a whole-machine word becomes a targeted path — the tool resolves
#: known folder names itself, so the router stays free of path logic.
_DEFENDER_SCAN_RE = re.compile(
    r"^(?:run\s+|start\s+|do\s+|perform\s+|begin\s+)?(?:a\s+|the\s+)?"
    r"(?:(?P<kind>quick|full|complete|deep|antivirus|anti-virus|virus|malware|defender|windows\s+defender|security)\s+)*"
    r"scan"
    r"(?:\s+(?:my\s+|the\s+|this\s+)?(?P<target>(?:(?!\bfor\b).)+?))??"
    r"(?:\s+for\s+(?:viruses|malware|threats|anything\s+(?:bad|suspicious)))?$"
)
_DEFENDER_CHECK_RE = re.compile(
    r"^(?:check|scan)\s+(?:my\s+|the\s+|this\s+)?"
    r"(?P<target>.+?)\s+for\s+(?:viruses|malware|threats|anything\s+(?:bad|suspicious))$"
)
#: Whole-machine words never become a path scan.
_SYSTEM_SCAN_WORDS = frozenset(
    {"computer", "pc", "laptop", "system", "machine", "files", "file", "everything", "windows"}
)
_DEFENDER_STATUS_RE = re.compile(
    r"^(?:(?:what|what's|whats)\s+(?:is|s)\s+)?(?:the\s+|my\s+)?"
    r"(?:windows\s+defender|defender|antivirus|anti-virus|virus\s+protection|protection|security)\s+"
    r"(?:status|state|report)$"
    r"|^am\s+i\s+(?:safe|protected)$"
    r"|^is\s+(?:my\s+|the\s+)?(?:windows\s+defender|defender|antivirus|anti-virus|virus\s+protection|protection|real-?time\s+protection)\s+"
    r"(?:on|running|enabled|working|ok|okay)$"
)
_DEFENDER_THREATS_RE = re.compile(
    r"^(?:(?:show|list|any|recent|new|last)\s+)*(?:threats?|viruses|virus|malware|detections)\s*"
    r"(?:history|report|found|detected|so\s+far)?$"
)
_DEFENDER_CANCEL_RE = re.compile(
    r"^(?:cancel|stop|abort)\s+(?:the\s+)?"
    r"(?:quick\s+|full\s+|virus\s+|defender\s+|windows\s+defender\s+|antivirus\s+)?scan$"
)

#: Writing code FOR the Turbo C++ workflow (G24): any ask that mentions
#: Turbo/Borland/DOSBox together with a creation-flavored verb ("write",
#: "create", "code", "program", "problem", "new file", ...) is one work order
#: for the purpose-built flow. The runtime generates the program with a
#: Borland-locked prompt and calls ``turbo_write_code`` directly, instead of
#: letting the small model improvise a plan from raw keystroke tools (live
#: failure 2026-10-16: ``open_app`` + duplicated ``type_text`` + a stray
#: ``open_website('wikipedia')``, uncompilable modern C++, empty answer after
#: 60 s). Wording and word order stay free; explain/debug/fix asks and plain
#: "save" asks stay with the LLM.
_TURBO_CODE_RE = re.compile(
    r"^(?!\s*(?:find|locate|search|where)\b)"  # discovery asks stay discovery
    r"(?=.*(?:turbo|borland|dosbox))"
    r"(?!.*\b(?:explain|debug|fix|review|understand|teach)\b)"
    r"(?=.*\b(?:write|create|code|program|programme|problem)\b"
    r"|\bnew\s+(?:file|tab|source|program|project)\b)"
    r".+$"
)


def _strip_path_filler(raw: str) -> str:
    """Drop conversational padding before a path ("a folder C:\\dev" -> "C:\\dev")."""
    match = _PATH_FILLER_RE.match(raw)
    return (match.group("rest") if match else raw).strip()

#: App discovery (G19): "search everywhere for X" sweeps the whole disk with
#: PowerShell; "use admin powershell … for X" does it elevated (one UAC popup).
_SEARCH_EVERYWHERE_RE = re.compile(
    r"^search\s+everywhere\s+for\s+(?P<query>.+)$"
    r"|^search\s+(?:the\s+)?whole\s+(?:computer|disk|system)\s+for\s+(?P<query2>.+)$"
)
_ADMIN_SEARCH_RE = re.compile(
    r"^(?:use\s+)?(?:the\s+)?(?:admin|administrator|elevated)\s+powershell\s+to\s+"
    r"(?:search|find|locate)(?:\s+(?:everywhere|all))?\s+for\s+(?P<query>.+)$"
    r"|^(?:search|find|locate)(?:\s+(?:everywhere|all))?\s+for\s+(?P<query2>.+?)"
    r"\s+as\s+(?:an?\s+)?admin(?:istrator)?$"
)
_FIND_APP_RE = re.compile(
    r"^(?:find|locate|search\s+for)\s+(?:the\s+|an?\s+)?(?:app|application|program)\s+"
    r"(?:called\s+|named\s+)?(?P<query>.+)$"
)
_WHERE_IS_RE = re.compile(r"^where\s+is\s+(?P<query>.+?)(?:\s+(?:installed|located))?$")

#: Web search (G20): "search YouTube for mr beast", "search for mr beast on
#: youtube", "google X", "play X on youtube" — all open a results page. The
#: colon forms ("search: \"mr beast video\"") are the owner's exact idiom.
_SEARCH_SITE_NAMES = (
    r"youtube|yt|google|bing|duckduckgo|ddg|github|wikipedia|wiki|reddit|amazon|"
    r"stack\s*overflow|spotify|netflix|twitter"
)
_WEB_SEARCH_RE = re.compile(
    r"^(?:search|look\s+up)\s+(?:for\s+)?(?P<q1>.+?)\s+(?:on|in)\s+(?P<site1>" + _SEARCH_SITE_NAMES + r")$"
    r"|^(?:search|look\s+up)\s+(?P<site2>" + _SEARCH_SITE_NAMES + r")\s+for\s+(?P<q2>.+)$"
    r"|^(?:play|watch)\s+(?P<q3>.+?)\s+on\s+(?P<site3>youtube)$"
    r"|^google\s+(?P<q4>.+)$"
    r"|^(?:search|look\s+up)\s+for\s+(?P<q5>.+)$"
    r"|^search\s*:\s*(?P<q6>.+?)\s+(?:on|in)\s+(?P<site4>youtube|yt)$"
    r"|^search\s*:\s*(?P<q7>.+)$"
)

#: Explicit typing form: "type: hello world", optionally "... and press
#: enter". Mirrors the owner's "search: …" idiom; natural phrasing like
#: "write a poem in notepad" stays with the LLM, which chains open_app +
#: type_text through the same typed registry.
_TYPE_TEXT_RE = re.compile(r"^type\s*:\s*(?P<text>.+?)(?:\s+and\s+(?:press\s+)?(?P<enter>enter))?$")

#: Browser bridge (G23): the rolling extension log ("what's going on in my
#: browser", "any new messages") and live YouTube control / tab queries.
#: The trailing pad tolerates conversational time filler. Note the generic
#: wrapper stripper eats a trailing "now", so "…like now" / "…right now" reach
#: these patterns as "…like" / "…right" (owner's live ask 2026-10-17: "is
#: there any new message like now?" missed everything and the small model
#: flailed through write_file/system_info for 110 s).
_BROWSER_TAIL = r"(?:\s+(?:(?:like|right|just)\s*)?(?:now|today|currently)?)?$"
_BROWSER_ACTIVITY_RE = re.compile(
    r"^(?:what(?:'s| is)\s+(?:going\s+on|happening)\s+(?:in\s+)?(?:my\s+|the\s+)?browser"
    r"|browser\s+activity"
    r"|what\s+have\s+i\s+been\s+(?:doing|up\s+to)\s+(?:online|in\s+the\s+browser|on\s+the\s+browser))"
    + _BROWSER_TAIL
)
# "what am I doing today" / "check what I am doing" - real-time activity queries
_WHAT_DOING_RE = re.compile(
    r"^(?:what\s+(?:am|have)\s+i\s+(?:been\s+)?(?:doing|up\s+to)"
    r"|check\s+(?:what\s+)?i\s+(?:am|have\s+been)\s+doing"
    r"|what(?:'s|s| is)\s+my\s+(?:activity|status)"
    r"|show\s+(?:me\s+)?(?:my\s+)?(?:activity|status|what\s+i'?m\s+doing))"
    r"(?:\s+(?:today|now|right\s+now|currently|recently|lately))?$"
)
_BROWSER_MESSAGES_RE = re.compile(
    r"^(?:"
    r"(?:(?:is|are)\s+there|do\s+i\s+have|did\s+i\s+get)\s+(?:any\s+|a\s+)?(?:new\s+)?messages?"
    r"|(?:any\s+)?new\s+messages?"
    r"|any\s+messages?"
    r"|check\s+(?:my\s+|the\s+)?messages?"
    r"|who\s+(?:messaged|texted|dm'?d|dmed)\s+me"
    r"|(?:has|did)\s+anyone\s+(?:messaged?|texted|dm'?d|dmed)\s+me"
    r")"
    r"(?:\s+(?:on\s+)?(?P<platform>facebook|messenger|instagram|discord|ig))?"
    + _BROWSER_TAIL
)
_BROWSER_UNREAD_RE = re.compile(
    r"^(?:what(?:'s| is)\s+unread|anything\s+unread|any\s+unread(?:\s+messages?)?"
    r"|check\s+(?:my\s+|the\s+)?unread(?:\s+messages?)?"
    r"|unread\s+(?:messages?|counts?|anything)"
    r"|how\s+many\s+unread(?:\s+messages?)?"
    r"|what\s+messages?\s+are\s+unread)"
    + _BROWSER_TAIL
)
_YOUTUBE_CONTROL_RE = re.compile(
    r"^(?:(?P<action>pause|resume|stop|skip)\s+(?:the\s+)?youtube(?:\s+(?:video|song|music))?"
    r"|(?P<action2>play)\s+(?:the\s+)?youtube\s+(?:video|song|music))$"
)
_YOUTUBE_SKIP_RE = re.compile(r"^(?:skip|next)\s+(?:this\s+|the\s+current\s+|the\s+)?video(?:\s+on\s+youtube)?$")
_YOUTUBE_STATUS_RE = re.compile(
    r"^(?:what(?:'s| is)\s+playing\s+on\s+youtube"
    r"|what\s+video\s+is\s+(?:this|playing|on\s+youtube)"
    r"|youtube\s+status)$"
)
_BROWSER_TABS_RE = re.compile(
    r"^(?:what\s+tabs\s+(?:do\s+i\s+have|are)\s+open|list\s+(?:my\s+)?tabs"
    r"|how\s+many\s+tabs\s+are\s+open)$"
)

#: Admin command runner (G12, D27): only explicit elevation phrasings route
#: here ("run X as administrator", "run the admin command X", "admin: X") —
#: normal asks are never hijacked. The name is checked against the owner's
#: configured commands by the tool itself, which answers honestly (with the
#: configured list) for unknown names — never inventing or running anything.
_ADMIN_RUN_RE = re.compile(
    r"^(?:run|execute)\s+(?:the\s+)?(?P<name1>.+?)(?:\s+command)?\s+"
    r"(?:as\s+(?:an?\s+)?(?:admin|administrator)|with\s+(?:my\s+|the\s+)?admin\s+(?:rights|permission))$"
    r"|^(?:run|execute)\s+(?:the\s+)?admin\s+command\s+(?P<name2>.+)$"
    r"|^admin\s*:\s*(?P<name3>.+)$"
)
_ADMIN_LIST_RE = re.compile(
    r"^(?:list|show)\s+(?:me\s+)?(?:my\s+|the\s+)?admin\s+commands$"
    r"|^what\s+admin\s+commands(?:\s+(?:do\s+i\s+have|are\s+(?:there|available)))?$"
)

#: A spoken volume target: "50", "50 percent", "50%", "max", "the maximum",
#: "full", and combinations like "max 100 percent" (heard live 2026-10-16:
#: "then you see the volume to max 100%" — speech-to-text heard "set" as
#: "see", and the old patterns matched none of it).
_VOLUME_LEVEL = r"(?:(?:max(?:imum)?|full)\s+)?(?:the\s+)?(?:\d{1,3}\s*(?:percent|%)?|max(?:imum)?|full)"

#: "set/turn/put the volume to X". "see" is deliberate: only an order like
#: this puts a level after "volume", so tolerating the common mishearing is
#: harmless (an open question never has a trailing target level).
_VOLUME_SET_RE = re.compile(
    rf"^(?:set|see|turn|put|bring|crank|adjust|change|raise|lower|increase|decrease)\s+"
    rf"(?:the\s+|my\s+)?(?:volume|sound|audio)\s+(?:to|at|up\s+to|down\s+to)\s+(?P<pct1>{_VOLUME_LEVEL})$"
    rf"|^(?:you\s+)?(?:set|see)\s+(?:the\s+)?volume\s+(?:to|at)\s+(?P<pct2>{_VOLUME_LEVEL})$"
    rf"|^(?:the\s+)?volume\s+(?:to|at|up\s+to|down\s+to)\s+(?P<pct3>{_VOLUME_LEVEL})$"
    rf"|^(?:turn|put|bring|crank|set|take)\s+it\s+(?:up|down)\s+to\s+(?P<pct4>{_VOLUME_LEVEL})$"
    rf"|^(?:turn|put|bring|crank)\s+(?:up|down)\s+(?:the\s+|my\s+)?(?:volume|sound|audio)\s+to\s+(?P<pct5>{_VOLUME_LEVEL})$"
    rf"|^(?:the\s+)?volume\s+(?P<pct6>\d{{1,3}}\s*(?:percent|%))$"
)
_VOLUME_MAX_RE = re.compile(r"^(?:max(?:imize)?)\s+(?:the\s+|my\s+)?(?:volume|sound|audio)$")


def _parse_volume_target(raw: str) -> int | None:
    """Turn a matched level ('50', '50 percent', 'max', 'max 100%') into 0-100."""
    number: int | None = None
    worded_max = False
    for token in str(raw).replace("%", " % ").split():
        if token in ("the", "percent"):
            continue
        if token in ("%", "max", "maximum", "full"):
            worded_max = True
            continue
        if not token.isdigit():
            return None
        number = int(token)
    if number is None:
        return 100 if worded_max else None
    return number if 0 <= number <= 100 else None


_VOLUME_STEP_RE = re.compile(
    r"^(?:turn\s+|put\s+|bring\s+|crank\s+)?(?:the\s+)?volume\s+(?:all\s+the\s+way\s+)?(?P<direction>up|down)$"
    r"|^(?:turn|bring|crank)\s+(?:it|that)\s+(?:all\s+the\s+way\s+)?(?P<direction2>up|down)$"
    r"|^(?P<direction3>up|down)\s+(?:the\s+)?volume$"
    r"|^(?:turn|put|bring|crank)\s+(?P<direction4>up|down)\s+(?:the\s+|my\s+)?(?:volume|sound|audio|music)$"
    r"|^(?:turn\s+it\s+|make\s+it\s+)?(?P<louder>louder|quieter)$"
    r"|^(?P<change>increase|raise|decrease|lower)\s+(?:the\s+)?volume$"
)
_VOLUME_MUTE_RE = re.compile(r"^(?P<action>mute|unmute)(?:\s+(?:the\s+)?(?:sound|audio|volume|it|everything))?$")
_VOLUME_STATUS_RE = re.compile(
    r"^(?:what(?:'s| is)\s+(?:the\s+|my\s+)?|check\s+(?:the\s+|my\s+)?)?volume(?:\s+(?:status|level))?$"
)

_MEDIA_RE = re.compile(
    r"^(?P<action>pause|resume|play|stop)\s+(?:the\s+)?(?:music|media|song|track|video|audio)$"
    r"|^(?P<next>next|skip)(?:\s+(?:the\s+)?(?:song|track|video))?$"
    r"|^(?P<previous>previous|last)\s+(?:song|track)$"
    r"|^(?P<bare>pause|resume|play)$"
)
_PLAY_OPEN_RE = re.compile(r"^play\s+(?P<target>.+)$")

_WIFI_STATE_RE = re.compile(
    r"^(?:turn\s+|switch\s+|put\s+)?(?:the\s+)?(?:wi-?fi|wireless)\s+(?P<state>on|off|enable|disable)$"
    r"|^(?:turn\s+|switch\s+|please\s+)*(?P<state2>on|off|enable|disable)\s+(?:the\s+)?(?:wi-?fi|wireless)$"
)
_WIFI_STATUS_RE = re.compile(
    r"^(?:what(?:'s| is)\s+(?:the\s+|my\s+)?|check\s+(?:the\s+|my\s+)?)?(?:wi-?fi|wireless)(?:\s+(?:status|state|connection))?$"
)

_TIME_RE = re.compile(r"^(?:what(?:'s| is)\s+the\s+time|what\s+time\s+is\s+it|tell\s+me\s+the\s+time|the\s+time|time)$")
_DATE_RE = re.compile(
    r"^(?:what(?:'s| is)\s+the\s+date|what\s+day\s+is\s+(?:it|today)"
    r"|what(?:'s| is)\s+today(?:'s)?\s+date|today(?:'s)?\s+date|the\s+date|date)$"
)

_SYSTEM_RE = re.compile(
    r"^(?P<cpu>cpu|processor)(?:\s+usage)?$"
    r"|^(?P<memory>memory|ram)(?:\s+usage)?$"
    r"|^(?P<disk>disk|storage)(?:\s+(?:space|usage))?$"
    r"|^(?P<battery>battery)(?:\s+(?:level|status|percentage))?$"
)


def _route_open(target: str, settings: Settings, browser: str | None = None) -> RoutedCommand | None:
    name = target.strip()
    if not name:
        return None
    chosen: dict[str, Any] | None = None
    if name in site_aliases(settings) or validate_web_url(name):
        chosen = {"site": name}
        if browser and browser not in ("the browser", "a browser", "browser"):
            chosen["browser"] = browser
        return RoutedCommand("open_website", chosen)
    if normalize_app_name(name) in known_app_names(settings):
        return RoutedCommand("open_app", {"app": name})
    lowered = name.lower()
    if lowered.endswith((" ide", " app", " application", " program", " editor", " suite", " studio")):
        # Clearly an app by phrasing ("open turbo c++ ide") — open_app itself
        # discovers unknown apps, so no need to know the name up front (G19).
        return RoutedCommand("open_app", {"app": name})
    return None


def route(text: str, settings: Settings) -> RoutedCommand | None:
    """Parse *text* into a typed tool call, or return None for the LLM."""
    normalized = _normalize(text)
    if not normalized:
        return None
    normalized = _strip_wrappers(normalized)
    if not normalized:
        return None

    match = _TURBO_CODE_RE.match(normalized)
    if match:
        return RoutedCommand("code_task", {"target": "turbo", "request": str(text).strip()})

    match = _VSCODE_OPEN_RE.match(normalized)
    if match:
        path = _strip_path_filler(match.group("path").strip().strip("\"'"))
        if path:
            return RoutedCommand("vscode_control", {"action": "open", "path": path})

    if _VSCODE_LAUNCH_RE.match(normalized):
        return RoutedCommand("vscode_control", {"action": "open"})

    match = _ADMIN_RUN_RE.match(normalized)
    if match:
        name = (match.group("name1") or match.group("name2") or match.group("name3") or "").strip().strip("\"'")
        if name:
            return RoutedCommand("admin_command", {"action": "run", "command": name})

    if _ADMIN_LIST_RE.match(normalized):
        return RoutedCommand("admin_command", {"action": "list"})

    match = _ORGANIZE_RE.match(normalized)
    if match:
        folder = match.group("folder")
        return RoutedCommand(
            "organize_folder",
            {"action": "preview", "folder": _ORGANIZE_CANONICAL.get(folder, folder)},
        )

    match = _DEFENDER_CHECK_RE.match(normalized) or _DEFENDER_SCAN_RE.match(normalized)
    if match:
        kind = (match.groupdict().get("kind") or "").strip()
        target = (match.group("target") or "").strip()
        if target and target.lower() not in _SYSTEM_SCAN_WORDS:
            return RoutedCommand("defender_scan", {"action": "path", "path": target})
        return RoutedCommand("defender_scan", {"action": "full" if kind in ("full", "complete") else "quick"})

    if _DEFENDER_STATUS_RE.match(normalized):
        return RoutedCommand("defender_scan", {"action": "status"})

    if _DEFENDER_THREATS_RE.match(normalized):
        return RoutedCommand("defender_scan", {"action": "threats"})

    if _DEFENDER_CANCEL_RE.match(normalized):
        return RoutedCommand("defender_scan", {"action": "cancel"})

    match = _OPEN_IN_RE.match(normalized)
    if match:
        routed = _route_open(match.group("site"), settings, browser=match.group("browser"))
        if routed is not None:
            return routed

    match = _OPEN_RE.match(normalized)
    if match:
        routed = _route_open(match.group("target"), settings)
        if routed is not None:
            return routed
        # not an app/site: fall through (e.g. "bring up the volume")

    match = _ADMIN_SEARCH_RE.match(normalized)
    if match:
        query = (match.group("query") or match.group("query2")).strip()
        return RoutedCommand("find_app", {"query": query, "deep": True, "elevated": True})

    match = _SEARCH_EVERYWHERE_RE.match(normalized)
    if match:
        query = (match.group("query") or match.group("query2")).strip()
        return RoutedCommand("find_app", {"query": query, "deep": True})

    match = _FIND_APP_RE.match(normalized)
    if match:
        return RoutedCommand("find_app", {"query": match.group("query").strip()})

    match = _WHERE_IS_RE.match(normalized)
    if match:
        return RoutedCommand("find_app", {"query": match.group("query").strip()})

    match = _WEB_SEARCH_RE.match(normalized)
    if match:
        groups = match.groupdict()
        query = next(value for key, value in groups.items() if key.startswith("q") and value)
        arguments: dict[str, Any] = {"query": query.strip().strip("\"'")}
        site = groups.get("site1") or groups.get("site2") or groups.get("site3") or groups.get("site4")
        if site:
            arguments["site"] = site
        return RoutedCommand("search_web", arguments)

    match = _TYPE_TEXT_RE.match(normalized)
    if match:
        text = match.group("text").strip().strip("\"'")
        if text:
            type_arguments: dict[str, Any] = {"text": text}
            if match.group("enter"):
                type_arguments["enter"] = True
            return RoutedCommand("type_text", type_arguments)

    if _BROWSER_ACTIVITY_RE.match(normalized) or _WHAT_DOING_RE.match(normalized):
        # Default to 15 minutes for real-time recent activity
        return RoutedCommand("browser_activity", {"scope": "summary", "minutes": 15})

    match = _BROWSER_MESSAGES_RE.match(normalized)
    if match:
        platform = match.group("platform")
        message_arguments: dict[str, Any] = {"scope": "messages", "minutes": 240}
        if platform:
            message_arguments["platform"] = "instagram" if platform == "ig" else platform
        return RoutedCommand("browser_activity", message_arguments)

    if _BROWSER_UNREAD_RE.match(normalized):
        return RoutedCommand("browser_command", {"action": "unread"})

    match = _YOUTUBE_CONTROL_RE.match(normalized)
    if match:
        action = match.group("action") or match.group("action2")
        op = {"pause": "pause", "play": "play", "resume": "play", "stop": "pause", "skip": "next"}[action]
        return RoutedCommand("browser_command", {"action": "youtube", "op": op})

    if _YOUTUBE_SKIP_RE.match(normalized):
        return RoutedCommand("browser_command", {"action": "youtube", "op": "next"})

    if _YOUTUBE_STATUS_RE.match(normalized):
        return RoutedCommand("browser_command", {"action": "youtube", "op": "title"})

    if _BROWSER_TABS_RE.match(normalized):
        return RoutedCommand("browser_command", {"action": "tabs"})

    match = _VOLUME_SET_RE.match(normalized)
    if match:
        raw = next(group for group in match.groups() if group)
        percent = _parse_volume_target(raw)
        if percent is not None:
            return RoutedCommand("set_volume", {"action": "set", "percent": percent})
        return None

    if _VOLUME_MAX_RE.match(normalized):
        return RoutedCommand("set_volume", {"action": "set", "percent": 100})

    match = _VOLUME_STEP_RE.match(normalized)
    if match:
        direction = (
            match.group("direction")
            or match.group("direction2")
            or match.group("direction3")
            or match.group("direction4")
        )
        if direction is None:
            louder = match.group("louder")
            if louder is not None:
                direction = "up" if louder == "louder" else "down"
            else:
                word = match.group("change") or ""
                direction = "up" if word in ("increase", "raise") else "down"
        return RoutedCommand("set_volume", {"action": direction})

    match = _VOLUME_MUTE_RE.match(normalized)
    if match:
        return RoutedCommand("set_volume", {"action": match.group("action")})

    if _VOLUME_STATUS_RE.match(normalized):
        return RoutedCommand("set_volume", {"action": "status"})

    match = _MEDIA_RE.match(normalized)
    if match:
        if match.group("action"):
            action = {"play": "play_pause", "pause": "play_pause", "resume": "play_pause", "stop": "stop"}[
                match.group("action")
            ]
        elif match.group("next"):
            action = "next"
        elif match.group("previous"):
            action = "previous"
        else:  # bare "pause" / "resume" / "play"
            action = "play_pause"
        return RoutedCommand("media_control", {"action": action})

    match = _PLAY_OPEN_RE.match(normalized)
    if match:
        routed = _route_open(match.group("target"), settings)
        if routed is not None:
            return routed

    match = _WIFI_STATE_RE.match(normalized)
    if match:
        state = str(match.group("state") or match.group("state2")).lower()
        return RoutedCommand("wifi_control", {"action": "on" if state in ("on", "enable") else "off"})

    if _WIFI_STATUS_RE.match(normalized):
        return RoutedCommand("wifi_control", {"action": "status"})

    if _TIME_RE.match(normalized):
        return RoutedCommand("system_info", {"action": "time"})
    if _DATE_RE.match(normalized):
        return RoutedCommand("system_info", {"action": "date"})

    match = _SYSTEM_RE.match(normalized)
    if match:
        action = match.group("cpu") or match.group("memory") or match.group("disk") or match.group("battery")
        action = {"processor": "cpu", "ram": "memory", "storage": "disk"}.get(action, action)
        return RoutedCommand("system_info", {"action": action})

    return None


# ------------------------------------------------------------ confirmations

#: Bare confirmations for a question the assistant just asked ("say yes and
#: I'll do it"). Only consulted while a flow actually waits for an answer —
#: see ``Runtime._answer`` — so a stray "yes" never triggers anything.
_CONFIRM_YES = frozenset(
    {
        "yes",
        "yeah",
        "yep",
        "yup",
        "ya",
        "yes please",
        "sure",
        "sure thing",
        "ok",
        "okay",
        "alright",
        "all right",
        "right",
        "fine",
        "go",
        "go ahead",
        "go for it",
        "do it",
        "do that",
        "do it please",
        "make it so",
        "proceed",
        "confirm",
        "confirmed",
        "yes do it",
        "sounds good",
        "why not",
        "let's do it",
        "lets do it",
        "absolutely",
        "of course",
        "you bet",
    }
)
_CONFIRM_NO = frozenset(
    {
        "no",
        "nope",
        "nah",
        "naw",
        "no thanks",
        "no thank you",
        "cancel",
        "cancel it",
        "don't",
        "dont",
        "do not",
        "do not do it",
        "don't do it",
        "dont do it",
        "not now",
        "not right now",
        "later",
        "maybe later",
        "never mind",
        "nevermind",
        "forget it",
        "leave it",
        "leave them",
        "leave it for now",
        "keep them",
        "keep it",
        "no do not",
    }
)


def classify_confirmation(text: str) -> str | None:
    """Return ``"yes"``/``"no"`` when *text* is a bare confirmation, else None."""
    normalized = _normalize(text)
    if not normalized:
        return None
    stripped = _strip_wrappers(normalized)
    # The wrapper stripper eats trailing "now"/"please" ("not now" -> "not"),
    # so both forms are checked.
    for candidate in (stripped, normalized):
        if candidate in _CONFIRM_YES:
            return "yes"
        if candidate in _CONFIRM_NO:
            return "no"
    if stripped.startswith("yes "):
        return "yes"
    if stripped.startswith("no "):
        return "no"
    return None

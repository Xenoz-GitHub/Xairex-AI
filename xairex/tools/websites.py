"""open_website: open aliased sites or validated URLs in the user's browser.

The browser fetches the page the *user* asked for — Xairex itself makes zero
external calls (the offline rule covers the assistant's own network use).
Only ``http``/``https`` URLs are accepted; ``javascript:``, ``file:`` and other
schemes are rejected outright.
"""

from __future__ import annotations

import logging
import os
import subprocess
from urllib.parse import quote_plus, urlsplit

from xairex.config import Settings
from xairex.tools.applications import resolve_app
from xairex.tools.registry import ToolResult, ToolSpec

logger = logging.getLogger("xairex.tools.web")

_BUILTIN_SITES: dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "yt": "https://www.youtube.com",  # observed spoken shorthand: "open yt"
    "facebook": "https://www.facebook.com",
    "fb": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "insta": "https://www.instagram.com",
    "tiktok": "https://www.tiktok.com",
    "twitch": "https://www.twitch.tv",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "maps": "https://www.google.com/maps",
    "wikipedia": "https://www.wikipedia.org",
    "reddit": "https://www.reddit.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "amazon": "https://www.amazon.com",
    "netflix": "https://www.netflix.com",
    "whatsapp": "https://web.whatsapp.com",
    "drive": "https://drive.google.com",
    "calendar": "https://calendar.google.com",
    "translate": "https://translate.google.com",
}

_BROWSER_CHOICES = ("chrome", "edge", "firefox")

#: Site key -> (spoken label, search URL template). The query is URL-encoded;
#: nothing here talks to the network — the browser does the fetching.
_SEARCH_SITES: dict[str, tuple[str, str]] = {
    "youtube": ("YouTube", "https://www.youtube.com/results?search_query={query}"),
    "google": ("Google", "https://www.google.com/search?q={query}"),
    "bing": ("Bing", "https://www.bing.com/search?q={query}"),
    "duckduckgo": ("DuckDuckGo", "https://duckduckgo.com/?q={query}"),
    "github": ("GitHub", "https://github.com/search?q={query}"),
    "wikipedia": ("Wikipedia", "https://en.wikipedia.org/w/index.php?search={query}"),
    "reddit": ("Reddit", "https://www.reddit.com/search/?q={query}"),
    "amazon": ("Amazon", "https://www.amazon.com/s?k={query}"),
    "stackoverflow": ("Stack Overflow", "https://stackoverflow.com/search?q={query}"),
    "spotify": ("Spotify", "https://open.spotify.com/search/{query}"),
    "netflix": ("Netflix", "https://www.netflix.com/search?q={query}"),
    "twitter": ("Twitter", "https://x.com/search?q={query}"),
}

_SEARCH_ALIASES = {
    "yt": "youtube",
    "ddg": "duckduckgo",
    "wiki": "wikipedia",
    "so": "stackoverflow",
    "stack overflow": "stackoverflow",
}


def site_aliases(settings: Settings) -> dict[str, str]:
    """Built-in site aliases merged with ``tools.website_aliases`` (validated)."""
    merged = dict(_BUILTIN_SITES)
    for key, value in settings.tools.website_aliases.items():
        if validate_web_url(value):
            merged[key.strip().lower()] = value
    return merged


def validate_web_url(candidate: str) -> str | None:
    """Return a safe http(s) URL for *candidate*, else None."""
    text = (candidate or "").strip()
    if not text or " " in text:
        return None
    if "://" not in text:
        if "." not in text:
            return None
        text = "https://" + text
    try:
        parts = urlsplit(text)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return text


def _spawn_browser(exe: str, url: str) -> None:
    subprocess.Popen(
        [exe, url],
        close_fds=True,
        creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
    )


def _launch_browser(settings: Settings, url: str, browser: str | None = None) -> str | None:
    """Open *url* in the requested/configured browser; returns error text or None."""
    tried: set[str] = set()
    for candidate in (browser, settings.tools.browser):
        name = (candidate or "").strip().lower()
        if not name or name in tried:
            continue
        tried.add(name)
        resolved = resolve_app(settings, name)
        if resolved.target and not resolved.target.endswith(":"):
            try:
                _spawn_browser(resolved.target, url)
            except OSError as exc:
                return f"Could not open the browser: {exc}"
            return None
    try:
        os.startfile(url)  # type: ignore[attr-defined]  # default browser
    except OSError as exc:
        return f"Could not open the browser: {exc}"
    return None


def open_website_tool(settings: Settings) -> ToolSpec:
    aliases = site_aliases(settings)
    alias_list = ", ".join(sorted(aliases))

    def handler(args: dict) -> ToolResult:
        raw = str(args.get("site", "")).strip()
        key = raw.lower().rstrip("/")
        url = aliases.get(key) or validate_web_url(raw)
        if not url:
            return ToolResult(False, f"I don't know the site '{raw}'. Try a full address like example.com.")
        browser = str(args.get("browser", "") or "").strip().lower()
        error = _launch_browser(settings, url, browser if browser in _BROWSER_CHOICES else None)
        if error:
            return ToolResult(False, error)
        label = key if key in aliases else url
        return ToolResult(True, f"Opening {label} in the browser.", data={"url": url})

    return ToolSpec(
        name="open_website",
        description=(
            "Open a website in the user's browser. Accepts a known alias "
            f"({alias_list}) or a full domain/URL like 'example.com'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "site": {"type": "string", "description": "Site alias or URL, e.g. 'youtube' or 'example.com'."},
                "browser": {
                    "type": "string",
                    "enum": list(_BROWSER_CHOICES),
                    "description": "Optional browser to use when the user named one.",
                },
            },
            "required": ["site"],
        },
        handler=handler,
        timeout_seconds=10.0,
    )


def search_web_tool(settings: Settings) -> ToolSpec:
    def handler(args: dict) -> ToolResult:
        query = str(args.get("query", "")).strip()
        if not query:
            return ToolResult(False, "Tell me what to search for.")
        raw_site = str(args.get("site", "") or "").strip().lower()
        site = _SEARCH_ALIASES.get(raw_site, raw_site) if raw_site else "google"
        fallback = ""
        if site not in _SEARCH_SITES:
            fallback = f"I don't have a built-in search for {raw_site} yet, so I searched Google for '{query}'."
            site = "google"
        label, template = _SEARCH_SITES[site]
        url = template.format(query=quote_plus(query))
        error = _launch_browser(settings, url, None)
        if error:
            return ToolResult(False, error)
        message = fallback or f"Searching {label} for '{query}'."
        return ToolResult(True, message, data={"url": url, "site": site, "query": query})

    return ToolSpec(
        name="search_web",
        description=(
            "Search a website in the user's browser and show the results: YouTube, Google, Bing, "
            "DuckDuckGo, GitHub, Wikipedia, Reddit, Amazon, Stack Overflow, Spotify, Netflix, Twitter. "
            "Use for 'search X on youtube' / 'google X' / 'play X on youtube' style requests."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for, e.g. 'mr beast video'."},
                "site": {
                    "type": "string",
                    "description": (
                        "Where to search: youtube, google (default), bing, duckduckgo, github, wikipedia, "
                        "reddit, amazon, stackoverflow, spotify, netflix, twitter."
                    ),
                },
            },
            "required": ["query"],
        },
        handler=handler,
        timeout_seconds=15.0,
    )

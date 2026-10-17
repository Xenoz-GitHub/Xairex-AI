"""Security policy helpers.

Everything here supports the project's hard offline rule: the runtime may only
talk to the local machine (loopback Ollama) plus local files and audio devices.
No side effects at import time.
"""

from __future__ import annotations

from urllib.parse import urlsplit

#: Hosts that resolve to the local machine and are therefore allowed.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

#: Model-name suffixes Ollama uses for hosted/cloud models — always prohibited.
_CLOUD_SUFFIX = "-cloud"


def is_loopback_host(host: str) -> bool:
    """Return True when *host* is an explicitly allowed loopback host."""
    normalized = (host or "").strip().strip("[]").lower()
    return normalized in LOOPBACK_HOSTS


def is_loopback_url(url: str) -> bool:
    """Return True when *url* is a plain HTTP(S) URL pointing at loopback."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme not in ("http", "https"):
        return False
    return is_loopback_host(parts.hostname or "")


def is_cloud_model_tag(model: str) -> bool:
    """Return True when *model* looks like an Ollama cloud model tag (…-cloud)."""
    return (model or "").strip().lower().endswith(_CLOUD_SUFFIX)

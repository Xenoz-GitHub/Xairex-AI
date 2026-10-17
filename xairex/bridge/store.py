"""Rolling browser-activity store (G23, D42): hourly JSONL segments, auto-cycled.

The extension streams small JSON events ("activity", "message", "unread") over
the loopback bridge; the bridge appends them here. Segments are one file per
local-time hour (``activity-YYYYMMDD-HH.jsonl``) and any segment that ended
more than ``retention_hours`` ago is deleted on the next maintenance pass —
the owner's "7 hours only, then auto-delete/cycle" requirement, bounded
forever by construction. Nothing here leaves the machine.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger("xairex.bridge")

#: Segment file name pattern (local time).
SEGMENT_PREFIX = "activity-"
SEGMENT_SUFFIX = ".jsonl"

#: Field caps so a hostile/buggy page cannot balloon the log.
_MAX_TITLE = 300
_MAX_URL = 500
_MAX_TEXT = 200

#: Minimum seconds between automatic cleanup scans.
_CLEANUP_EVERY_SECONDS = 60.0


def _hour_key(ts: float) -> datetime:
    return datetime.fromtimestamp(ts).replace(minute=0, second=0, microsecond=0)


def segment_name(ts: float) -> str:
    """File name of the hourly segment covering *ts* (local time)."""
    return _hour_key(ts).strftime(f"{SEGMENT_PREFIX}%Y%m%d-%H{SEGMENT_SUFFIX}")


def normalize_event(raw: dict[str, Any], *, now: float | None = None) -> dict[str, Any]:
    """Validate/cap one raw event from the extension; raises ``ValueError`` when unusable."""
    kind = str(raw.get("kind", "")).strip().lower()
    if kind not in ("activity", "message", "unread"):
        raise ValueError(f"unknown event kind {kind!r}")
    ts_ms = raw.get("ts")
    if not isinstance(ts_ms, (int, float)) or ts_ms <= 0:
        ts_ms = (now if now is not None else time.time()) * 1000.0
    ts_ms = float(ts_ms)
    if ts_ms > 10**14:  # microsecond timestamps (some pages report µs — 1.7e15 now, ms is ~1.7e12)
        ts_ms /= 1000.0
    record: dict[str, Any] = {
        "ts": int(ts_ms),
        "iso": datetime.fromtimestamp(ts_ms / 1000.0).isoformat(timespec="seconds"),
        "kind": kind,
        "platform": str(raw.get("platform", "web")).strip().lower()[:32] or "web",
    }
    for field, cap in (("title", _MAX_TITLE), ("url", _MAX_URL), ("sender", _MAX_TEXT), ("preview", _MAX_TEXT)):
        value = raw.get(field)
        if value:
            record[field] = str(value)[:cap]
    count = raw.get("count")
    if isinstance(count, (int, float)) and count >= 0:
        record["count"] = int(count)
    return record


def domain_of(url: str) -> str:
    """Best-effort visit domain for summaries: ``www.`` stripped, lowercase."""
    try:
        host = urlparse(str(url)).hostname or ""
    except ValueError:
        return ""
    host = host.lower()
    return host.removeprefix("www.")


class ActivityStore:
    """Append-only hourly JSONL segments with bounded retention."""

    def __init__(
        self,
        directory: Path,
        *,
        retention_hours: float = 7.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.directory = Path(directory)
        self.retention_hours = max(float(retention_hours), 0.0)
        self._clock = clock
        self._lock = threading.Lock()
        self._last_cleanup = 0.0

    # ------------------------------------------------------------------ write

    def append(self, record: dict[str, Any]) -> None:
        """Append one normalized record; runs retention cleanup when due."""
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            target = self.directory / segment_name(record["ts"] / 1000.0)
            try:
                with target.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
            except OSError as exc:  # disk problems must never kill the bridge
                logger.warning("activity log write failed (%s): %s", target.name, exc)
                return
            now = self._clock()
            if now - self._last_cleanup >= _CLEANUP_EVERY_SECONDS:
                self._last_cleanup = now
                self.cleanup(now=now)

    # --------------------------------------------------------------- retention

    def cleanup(self, *, now: float | None = None) -> list[str]:
        """Delete segments that ended before ``now - retention_hours``.

        Returns the deleted file names. A segment covers one hour, so a 7-hour
        retention keeps 7–8 hours of data — never more.
        """
        now = self._clock() if now is None else now
        cutoff = now - self.retention_hours * 3600.0
        deleted: list[str] = []
        if not self.directory.is_dir():
            return deleted
        for path in sorted(self.directory.glob(f"{SEGMENT_PREFIX}*{SEGMENT_SUFFIX}")):
            stamp = self._segment_start(path.name)
            if stamp is None:
                continue
            if stamp + 3600.0 < cutoff:  # the whole hour ended before the cutoff
                try:
                    path.unlink()
                    deleted.append(path.name)
                except OSError as exc:  # pragma: no cover - best effort
                    logger.warning("could not delete old segment %s: %s", path.name, exc)
        if deleted:
            logger.info("activity log cycled: removed %s", ", ".join(deleted))
        return deleted

    @staticmethod
    def _segment_start(name: str) -> float | None:
        if not (name.startswith(SEGMENT_PREFIX) and name.endswith(SEGMENT_SUFFIX)):
            return None
        stamp = name[len(SEGMENT_PREFIX) : -len(SEGMENT_SUFFIX)]
        try:
            parsed = datetime.strptime(stamp, "%Y%m%d-%H")
        except ValueError:
            return None
        return parsed.timestamp()

    def segments(self) -> list[Path]:
        if not self.directory.is_dir():
            return []
        return sorted(self.directory.glob(f"{SEGMENT_PREFIX}*{SEGMENT_SUFFIX}"))

    # ------------------------------------------------------------------ read

    def read(
        self,
        *,
        minutes: float | None = None,
        platform: str | None = None,
        kind: str | None = None,
        limit: int = 200,
        now: float | None = None,
    ) -> list[dict[str, Any]]:
        """Recent records (oldest first), filtered and capped to the newest *limit*."""
        now = self._clock() if now is None else now
        floor_ms = (now - minutes * 60.0) * 1000.0 if minutes is not None else 0.0
        wanted_platform = platform.strip().lower() if platform else None
        records: list[dict[str, Any]] = []
        for path in self.segments():
            start = self._segment_start(path.name)
            if start is not None and start + 3600.0 < floor_ms / 1000.0:
                continue  # segment ended before the window
            try:
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(record, dict) or "ts" not in record:
                            continue
                        if float(record["ts"]) < floor_ms:
                            continue
                        if wanted_platform and record.get("platform") != wanted_platform:
                            continue
                        if kind and record.get("kind") != kind:
                            continue
                        records.append(record)
            except OSError as exc:  # pragma: no cover - unreadable segment
                logger.warning("could not read segment %s: %s", path.name, exc)
        records.sort(key=lambda item: item.get("ts", 0))
        if limit > 0:
            records = records[-limit:]
        return records

    def summary(self, *, minutes: float = 60.0, now: float | None = None) -> dict[str, Any]:
        """Counts for narration: messages per platform, top domains, unread snapshot."""
        records = self.read(minutes=minutes, limit=0, now=now)
        messages = Counter()
        last_message: dict[str, dict[str, Any]] = {}
        domains: Counter = Counter()
        unread: dict[str, int] = {}
        for record in records:
            if record.get("kind") == "message":
                platform = str(record.get("platform", "web"))
                messages[platform] += 1
                last_message[platform] = record
            elif record.get("kind") == "activity":
                domain = domain_of(str(record.get("url", "")))
                if domain:
                    domains[domain] += 1
            elif record.get("kind") == "unread" and isinstance(record.get("count"), int):
                unread[str(record.get("platform", "web"))] = record["count"]
        return {
            "window_minutes": int(minutes),
            "events": len(records),
            "messages": dict(messages),
            "last_message": last_message,
            "domains": dict(domains.most_common(10)),
            "unread": unread,
        }

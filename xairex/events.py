"""Structured runtime events (Phase G — resolves note O6).

The engine thread never talks to a UI directly. In GUI mode the runtime emits
:class:`Event` objects into an :class:`EventBus` and the Tk main loop drains
them on a timer (``after()``); the terminal front end keeps its direct text
interface unchanged.

Design rules:

* emitting must never block, fail or leak audio data — the queue is unbounded
  and UI mistakes cannot reach the engine;
* events carry plain data (str/float/bool) so any front end can consume them;
* kinds are module-level strings, matched freely by consumers.
"""

from __future__ import annotations

import queue
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------- event kinds

STATE = "state"  # data: frm, to (XairexState values)
TRANSCRIPT = "transcript"  # data: text — what the user said (or typed)
ANSWER = "answer"  # data: text — the assistant's answer
STATUS = "status"  # data: text — muted informational line (metrics, notices)
TAG = "tag"  # data: name, text, color
ERROR = "error"  # data: text
WARN = "warn"  # data: text
BUSY = "busy"  # data: text
REPORT = "report"  # data: text — a health report block
SYSTEM = "system"  # data: text — banner / help / goodbye
MIC_LEVEL = "mic_level"  # data: level — dBFS float (-120 muted)


@dataclass(frozen=True)
class Event:
    """One runtime notification. ``data`` is always a plain dict."""

    kind: str
    data: dict[str, Any] = field(default_factory=dict)


class EventBus:
    """Thread-safe event queue between the engine thread and any UI.

    The queue is unbounded: a UI that falls behind simply drains the backlog
    on its next tick, and the engine can never stall on a slow consumer.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[Event] = queue.Queue()

    def emit(self, kind: str, /, **data: Any) -> None:
        """Publish one event (safe from any thread)."""
        self._queue.put_nowait(Event(kind=kind, data=data))

    def drain(self, limit: int = 256) -> list[Event]:
        """Return up to *limit* pending events, oldest first."""
        events: list[Event] = []
        while len(events) < limit:
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return events

    def __len__(self) -> int:
        return self._queue.qsize()

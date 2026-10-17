"""Lightweight per-request performance metrics (spec section 11).

No promises about latency are made anywhere: numbers are measured here and
reported in the logs (and later recorded in the notes' session log).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


def rss_mb() -> float | None:
    """Approximate resident memory of this process in MB, or None if unknown."""
    try:
        import psutil
    except ImportError:  # pragma: no cover - psutil is a declared dependency
        return None
    try:
        process = psutil.Process()
        return round(process.memory_info().rss / (1024 * 1024), 1)
    except Exception:  # noqa: BLE001  # pragma: no cover - metrics must never break a request
        return None


@dataclass
class RequestMetrics:
    """Timing marks for one user request, ending in a one-line summary."""

    label: str
    started: float = field(default_factory=time.perf_counter)
    marks: dict[str, float] = field(default_factory=dict)

    def mark(self, name: str) -> None:
        """Record a named point in time."""
        self.marks[name] = time.perf_counter()

    def elapsed_ms(self, name: str) -> float | None:
        """Milliseconds between request start and a named mark."""
        marked = self.marks.get(name)
        if marked is None:
            return None
        return round((marked - self.started) * 1000, 1)

    def total_ms(self) -> float:
        return round((time.perf_counter() - self.started) * 1000, 1)

    def summary(self) -> str:
        """One log-friendly line, e.g. ``ask: llm=3200.0ms tts=850.0ms total=4300.0ms rss=512.3MB``."""
        parts = [f"{name}={self.elapsed_ms(name)}ms" for name in self.marks]
        line = f"{self.label}: " + " ".join(parts) + f" total={self.total_ms()}ms"
        usage = rss_mb()
        if usage is not None:
            line += f" rss={usage}MB"
        return line

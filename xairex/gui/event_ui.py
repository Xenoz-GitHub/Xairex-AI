"""Runtime ``Ui`` that turns all display calls into event-bus messages (G2).

The Tkinter front end never lets the engine print to a terminal. Instead the
runtime is given one of these: every display call becomes a structured event
on the bus, and the GUI drains the bus on a Tk timer. This module is kept
tkinter-free so it can be imported and tested headless.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import numpy as np

from xairex import events
from xairex.events import EventBus
from xairex.state_machine import XairexState
from xairex.ui import Ui, frame_db


class EventMeter:
    """Input-level meter that reports frames as ``MIC_LEVEL`` events.

    Mirrors the CLI's one-line meter, but publishes the per-frame dBFS level
    instead of drawing, so the GUI can animate its status orb. ``update`` is
    called from the engine (recording) thread.
    """

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def update(self, chunk: np.ndarray) -> None:
        self._bus.emit(events.MIC_LEVEL, level=frame_db(chunk))

    def finish(self) -> None:
        self._bus.emit(events.MIC_LEVEL, level=-120.0)


class EventUi(Ui):
    """Headless ``Ui`` implementation: everything becomes a bus event."""

    def __init__(self, bus: EventBus) -> None:
        super().__init__(animations=False, colors="never")
        self.bus = bus

    # ------------------------------------------------------------ plain text

    def print_plain(self, text: str) -> None:
        self.bus.emit(events.SYSTEM, text=text)

    def print_banner(self) -> None:
        self.bus.emit(events.SYSTEM, text=self.banner())

    def print_report(self, text: str) -> None:
        self.bus.emit(events.REPORT, text=text)

    # -------------------------------------------------------- tagged messages

    def print_tag(self, name: str, message: str, color: str = "cyan") -> None:
        self.bus.emit(events.TAG, name=name, text=message, color=color)

    def print_warn(self, message: str) -> None:
        self.bus.emit(events.WARN, text=message)

    def print_error(self, message: str) -> None:
        self.bus.emit(events.ERROR, text=message)

    def print_busy(self, message: str) -> None:
        self.bus.emit(events.BUSY, text=message)

    def print_muted(self, text: str) -> None:
        self.bus.emit(events.STATUS, text=text)

    def print_answer(self, text: str) -> None:
        self.bus.emit(events.ANSWER, text=text)

    def print_user_echo(self, text: str) -> None:
        self.bus.emit(events.TRANSCRIPT, text=text)

    # ------------------------------------------------------------------ state

    def state_changed(self, frm: XairexState, to: XairexState) -> None:
        """``Runtime.on_state`` hook: publish one STATE event per transition."""
        self.bus.emit(events.STATE, frm=frm.value, to=to.value)

    # ------------------------------------------------------------- animations

    def listening_banner(self) -> None:
        self.bus.emit(
            events.TAG,
            name="ptt",
            text="listening — speak now; recording stops after silence",
            color="green",
        )

    def listening_meter(self) -> EventMeter:
        return EventMeter(self.bus)

    @contextmanager
    def spinner(
        self,
        label: str,
        detail: str | None = None,
        *,
        frames: str = "dots",
        interval: float = 0.09,
    ) -> Iterator[None]:
        """No-op: the GUI shows phases on the status orb, not as text."""
        yield

    # -------------------------------------------------------------------- misc

    def write_inline(self, text: str) -> None:
        pass

    def clear_line(self) -> None:
        pass

    def newline(self) -> None:
        pass

    def prompt(self) -> str:
        return ""

"""Explicit runtime state machine (spec section 3).

Only the runtime/engine thread moves the assistant through these states. The
transition table below is the single authoritative definition — see
notes/02-ARCHITECTURE.md section 3 for the rationale of each edge.

States must never overlap: this machine plus the single engine thread is what
prevents duplicate recordings, duplicate tool execution and overlapping speech.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import StrEnum

logger = logging.getLogger("xairex.state")


class XairexState(StrEnum):
    """All explicit assistant states."""

    STARTING = "starting"
    IDLE = "idle"
    LISTENING_FOR_WAKE_WORD = "listening_for_wake_word"
    RECORDING_COMMAND = "recording_command"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    EXECUTING_TOOL = "executing_tool"
    SPEAKING = "speaking"
    ERROR = "error"
    STOPPING = "stopping"


class IllegalTransitionError(RuntimeError):
    """Raised when code attempts a transition that is not in the table."""

    def __init__(self, frm: XairexState, to: XairexState) -> None:
        super().__init__(f"Illegal state transition: {frm.value} -> {to.value}")
        self.frm = frm
        self.to = to


#: Authoritative transition table. ``STOPPING`` is terminal.
TRANSITIONS: dict[XairexState, frozenset[XairexState]] = {
    XairexState.STARTING: frozenset(
        {
            XairexState.LISTENING_FOR_WAKE_WORD,
            XairexState.IDLE,
            XairexState.ERROR,
            XairexState.STOPPING,
        }
    ),
    XairexState.IDLE: frozenset(
        {
            XairexState.LISTENING_FOR_WAKE_WORD,
            XairexState.RECORDING_COMMAND,
            XairexState.THINKING,
            XairexState.EXECUTING_TOOL,
            XairexState.SPEAKING,
            XairexState.ERROR,
            XairexState.STOPPING,
        }
    ),
    XairexState.LISTENING_FOR_WAKE_WORD: frozenset(
        {
            XairexState.RECORDING_COMMAND,
            XairexState.IDLE,
            XairexState.ERROR,
            XairexState.STOPPING,
        }
    ),
    XairexState.RECORDING_COMMAND: frozenset(
        {
            XairexState.TRANSCRIBING,
            XairexState.LISTENING_FOR_WAKE_WORD,
            XairexState.IDLE,
            XairexState.ERROR,
            XairexState.STOPPING,
        }
    ),
    XairexState.TRANSCRIBING: frozenset(
        {
            XairexState.THINKING,
            XairexState.EXECUTING_TOOL,
            XairexState.LISTENING_FOR_WAKE_WORD,
            XairexState.IDLE,
            XairexState.ERROR,
            XairexState.STOPPING,
        }
    ),
    XairexState.THINKING: frozenset(
        {
            XairexState.EXECUTING_TOOL,
            XairexState.SPEAKING,
            XairexState.LISTENING_FOR_WAKE_WORD,
            XairexState.IDLE,
            XairexState.ERROR,
            XairexState.STOPPING,
        }
    ),
    XairexState.EXECUTING_TOOL: frozenset(
        {
            XairexState.THINKING,
            XairexState.SPEAKING,
            XairexState.IDLE,
            XairexState.ERROR,
            XairexState.STOPPING,
        }
    ),
    XairexState.SPEAKING: frozenset(
        {
            XairexState.LISTENING_FOR_WAKE_WORD,
            XairexState.IDLE,
            XairexState.ERROR,
            XairexState.STOPPING,
        }
    ),
    XairexState.ERROR: frozenset(
        {
            XairexState.IDLE,
            XairexState.LISTENING_FOR_WAKE_WORD,
            XairexState.STOPPING,
        }
    ),
    XairexState.STOPPING: frozenset(),
}


class StateMachine:
    """Small, explicit, hookable state machine."""

    def __init__(
        self,
        initial: XairexState = XairexState.STARTING,
        on_change: Callable[[XairexState, XairexState], None] | None = None,
    ) -> None:
        self._state = initial
        self._on_change = on_change

    @property
    def state(self) -> XairexState:
        return self._state

    def allowed_transitions(self) -> frozenset[XairexState]:
        """States reachable from the current state in one step."""
        return TRANSITIONS[self._state]

    def can_transition(self, to: XairexState) -> bool:
        return to in TRANSITIONS[self._state]

    def transition(self, to: XairexState) -> XairexState:
        """Move to *to*, or raise :class:`IllegalTransitionError`."""
        frm = self._state
        if to not in TRANSITIONS[frm]:
            raise IllegalTransitionError(frm, to)
        self._state = to
        logger.debug("state: %s -> %s", frm.value, to.value)
        if self._on_change is not None:
            try:
                self._on_change(frm, to)
            except Exception:  # callbacks must never break the machine
                logger.exception("State change callback failed (%s -> %s)", frm.value, to.value)
        return to

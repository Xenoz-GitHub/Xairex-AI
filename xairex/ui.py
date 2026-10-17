"""Cyber-styled console interface for the Xairex CLI (no new dependencies).

Design rules:

* **Graceful degradation** — colors are emitted only when the terminal supports
  ANSI (or the config forces them) and honour the ``NO_COLOR`` convention;
  animations (spinners, the live microphone meter) run only in an interactive
  terminal. Redirected output falls back to plain one-line status messages so
  logs, scripts and tests stay readable.
* **One-line widgets** — animated lines are drawn on a single line with ``\\r``
  and always erase themselves before other output continues.
* **Stdlib only** (plus numpy, already a dependency) — Xairex stays offline and
  install-light.

Configured through the ``ui`` section of ``config/settings.json``.
"""

from __future__ import annotations

import ctypes
import math
import os
import shutil
import sys
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import numpy as np

from xairex import __version__

# ------------------------------------------------------------------ ANSI codes

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
CYAN = "\x1b[38;5;51m"  # bright cyan
MAGENTA = "\x1b[38;5;201m"  # neon magenta
GREEN = "\x1b[38;5;48m"
YELLOW = "\x1b[38;5;226m"
RED = "\x1b[38;5;203m"
GRAY = "\x1b[38;5;245m"

_COLOR_CODES = {
    "cyan": CYAN,
    "magenta": MAGENTA,
    "green": GREEN,
    "yellow": YELLOW,
    "red": RED,
    "gray": GRAY,
}

#: Braille spinner (8 frames) for thinking / transcribing.
_SPIN_FRAMES = ("⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷")

#: Travelling wave for speaking (7 frames of 14 cells).
_WAVE_BASE = "▁▂▃▄▅▆▇█▇▆▅▄▃▂"
_WAVE_FRAMES = tuple(_WAVE_BASE[i:] + _WAVE_BASE[:i] for i in range(0, len(_WAVE_BASE), 2))

_METER_FULL = "▰"
_METER_EMPTY = "▱"

#: Windows console flag for ANSI escape processing.
_ENABLE_VT = 0x0004


def _enable_windows_vt() -> None:
    """Turn on ANSI escape processing in the Windows console (no-op elsewhere)."""
    if os.name != "nt":
        return
    try:  # pragma: no cover - depends on the host console
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | _ENABLE_VT)
    except Exception:  # noqa: BLE001, S110 - a console probe must never fail the app
        pass


def _is_tty(stream: Any) -> bool:
    try:
        return bool(stream is not None and stream.isatty())
    except Exception:  # noqa: BLE001 - exotic stream objects
        return False


def _clear_line(stream: Any) -> None:
    width = max(20, min(shutil.get_terminal_size(fallback=(80, 24)).columns - 1, 120))
    stream.write("\r" + " " * width + "\r")
    stream.flush()


def frame_db(chunk: np.ndarray) -> float:
    """RMS level of an int16 chunk in dBFS (-120 floor)."""
    if chunk.size == 0:
        return -120.0
    values = chunk.astype(np.float32, copy=False)
    rms = float(np.sqrt(np.mean(values * values)))
    if rms <= 1e-6:
        return -120.0
    return max(-120.0, 20.0 * math.log10(rms / 32768.0))


# ------------------------------------------------------------------ banner art

_X = ("██╗  ██╗", "╚██╗██╔╝", " ╚███╔╝ ", " ██╔██╗ ", "██╔╝ ██╗", "╚═╝  ╚═╝")
_A = (" █████╗ ", "██╔══██╗", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝")
_I = ("██╗", "██║", "██║", "██║", "██║", "╚═╝")
_R = ("██████╗ ", "██╔══██╗", "██████╔╝", "██╔══██╗", "██║  ██║", "╚═╝  ╚═╝")
_E = ("███████╗", "██╔════╝", "█████╗  ", "██╔══╝  ", "███████╗", "╚══════╝")

_ART_ROWS = tuple(" ".join(letter[row] for letter in (_X, _A, _I, _R, _E, _X)) for row in range(6))


# ------------------------------------------------------------------- listening


class ListeningMeter:
    """Live one-line input level meter drawn while push-to-talk records."""

    _CELLS = 14

    def __init__(self, ui: Ui) -> None:
        self._ui = ui
        self._active = False

    def update(self, chunk: np.ndarray) -> None:
        """Redraw the meter for one captured frame (no-op when animations are off)."""
        if not self._ui.animations:
            return
        self._active = True
        level = frame_db(chunk)
        fraction = min(max((level + 60.0) / 60.0, 0.0), 1.0)
        filled = round(fraction * self._CELLS)
        if level < -55.0:
            color = GRAY
        elif level < -38.0:
            color = GREEN
        elif level < -20.0:
            color = YELLOW
        else:
            color = RED
        bar = _METER_FULL * filled + _METER_EMPTY * (self._CELLS - filled)
        self._ui.write_inline(
            f"\r  {self._ui.cyan('◉')} {self._ui.style(color, bar)} {self._ui.muted(f'{level:6.1f} dBFS')}"
        )

    def finish(self) -> None:
        """Erase the meter line (safe to call more than once)."""
        if self._active:
            self._ui.clear_line()
            self._active = False


# ------------------------------------------------------------------------ UI


class Ui:
    """Color + animation facade used by the runtime.

    When colors/animations are off every method still prints its text — just
    plain — so output stays useful when redirected to a file or piped.
    """

    def __init__(self, *, animations: bool = True, colors: str = "auto", stream: Any | None = None) -> None:
        self._stream = stream if stream is not None else sys.stdout
        tty = _is_tty(self._stream)
        if colors == "never":
            self._color = False
        elif colors == "always":
            self._color = True
        else:
            self._color = tty and os.environ.get("NO_COLOR") is None and os.environ.get("TERM") != "dumb"
        self._animations = bool(animations) and tty
        _enable_windows_vt()

    @classmethod
    def from_settings(cls, settings: Any) -> Ui:
        return cls(animations=settings.ui.animations, colors=settings.ui.colors)

    @property
    def color(self) -> bool:
        """True when ANSI colors are emitted."""
        return self._color

    @property
    def animations(self) -> bool:
        """True when animated widgets are drawn."""
        return self._animations

    # ------------------------------------------------------------------ styling

    def style(self, code: str, text: str) -> str:
        return f"{code}{text}{RESET}" if self._color else text

    def bold(self, text: str) -> str:
        return self.style(BOLD, text)

    def cyan(self, text: str) -> str:
        return self.style(CYAN, text)

    def magenta(self, text: str) -> str:
        return self.style(MAGENTA, text)

    def green(self, text: str) -> str:
        return self.style(GREEN, text)

    def yellow(self, text: str) -> str:
        return self.style(YELLOW, text)

    def red(self, text: str) -> str:
        return self.style(RED, text)

    def muted(self, text: str) -> str:
        return self.style(GRAY, text)

    # --------------------------------------------------------------- printing

    def _can_encode(self, text: str) -> bool:
        encoding = getattr(self._stream, "encoding", None) or "utf-8"
        try:
            text.encode(encoding)
            return True
        except (UnicodeEncodeError, LookupError):
            return False

    def _ascii_safe(self, text: str) -> str:
        return text.encode("ascii", "replace").decode("ascii")

    def _print(self, text: str = "") -> None:
        if not self._can_encode(text):
            text = self._ascii_safe(text)
        try:
            print(text, file=self._stream)
        except UnicodeEncodeError:  # belt and braces when the stream mis-reports
            print(self._ascii_safe(text), file=self._stream)

    def print_plain(self, text: str) -> None:
        """Print *text* unchanged (encoding-safe)."""
        self._print(text)

    def write_inline(self, text: str) -> None:
        """Write *text* without a newline and flush (for animated lines)."""
        if not self._can_encode(text):
            text = self._ascii_safe(text)
        try:
            self._stream.write(text)
            self._stream.flush()
        except UnicodeEncodeError:  # pragma: no cover - belt and braces
            self._stream.write(self._ascii_safe(text))
            self._stream.flush()

    def clear_line(self) -> None:
        """Erase the current line."""
        _clear_line(self._stream)

    def newline(self) -> None:
        self._print("")

    def banner(self) -> str:
        lines = [f"  {self.cyan(row)}" for row in _ART_ROWS]
        lines.append("  " + self.muted("⟪ offline neural core ⟫ ⟪ cpu-only ⟫ ⟪ no cloud ⟫"))
        lines.append("  " + self.muted(f"v{__version__} · push-to-talk + typed mode · press Enter to talk"))
        lines.append("  " + self.muted("'help' for commands · Ctrl+C to exit"))
        return "\n".join(lines)

    def print_banner(self) -> None:
        banner = self.banner()
        if self._can_encode(banner):
            self._print(banner)
            return
        # Narrow console encodings (e.g. redirected cp1252 output): plain banner.
        self._print("=" * 60)
        self._print(f"Xairex v{__version__} - fully offline voice assistant")
        self._print("Brain: local Ollama | Ears: local Whisper | Voice: local Piper")
        self._print("=" * 60)

    def print_report(self, text: str) -> None:
        """Print a health report, coloring OK/FAIL lines when colors are on."""
        for line in text.splitlines():
            if line.startswith("[FAIL"):
                styled = self.red(line)
            elif line.startswith("[OK"):
                styled = self.green(line)
            elif line.startswith("       fix:"):
                styled = self.yellow(line)
            else:
                styled = line
            self._print(styled)

    def tag(self, name: str, message: str, color: str = "cyan") -> str:
        prefix = self.style(_COLOR_CODES[color], f"[{name}]")
        return f"{prefix} {message}".rstrip()

    def print_tag(self, name: str, message: str, color: str = "cyan") -> None:
        self._print(self.tag(name, message, color))

    def print_warn(self, message: str) -> None:
        self._print(self.tag("warn", message, "yellow"))

    def print_error(self, message: str) -> None:
        self._print(self.tag("error", message, "red"))

    def print_busy(self, message: str) -> None:
        self._print(self.tag("busy", message, "yellow"))

    def print_muted(self, text: str) -> None:
        self._print(self.muted(text))

    def print_answer(self, text: str) -> None:
        self._print(f"{self.magenta('xairex')}{self.magenta('>')} {text}")

    def print_user_echo(self, text: str) -> None:
        self._print(f"{self.cyan('you')}{self.cyan('>')} {text}")

    def prompt(self) -> str:
        return "\n" + self.cyan("you") + self.cyan("> ")

    def help_block(self) -> str:
        rows = (
            ("(Enter)  / ptt", "push-to-talk: press Enter on an empty line, then speak"),
            ("ask <text>", "ask Xairex a question (the answer is spoken and printed)"),
            ("say <text>", "speak the given text without asking the model"),
            ("health", "run local offline readiness checks"),
            ("stop", "stop the current answer immediately"),
            ("help", "show this help"),
            ("quit", "shut down (Ctrl+C works too)"),
        )
        width = max(len(command) for command, _ in rows)
        lines = [self.muted("── commands " + "─" * 44)]
        for command, text in rows:
            lines.append(f"  {self.cyan(command.ljust(width))}  {text}")
        lines.append("")
        lines.append(self.muted("tip: typing a sentence without a command counts as 'ask'"))
        return "\n".join(lines)

    # ------------------------------------------------------------- animations

    def listening_banner(self) -> None:
        if self._animations:
            line = f"  {self.cyan('◉')} {self.bold('listening')} {self.muted('— speak now; recording stops after silence')}"
            self._print(line)
        else:
            self._print(self.tag("ptt", "listening... (speak now; recording stops after silence)"))

    def listening_meter(self) -> ListeningMeter:
        return ListeningMeter(self)

    @contextmanager
    def spinner(
        self,
        label: str,
        detail: str | None = None,
        *,
        frames: str = "dots",
        interval: float = 0.09,
    ) -> Iterator[None]:
        """Animate a one-line status while the block runs.

        In non-interactive output the label is printed once (``label...``),
        which keeps redirected logs readable.
        """
        if not self._animations:
            self._print(f"{label}...")
            yield
            return

        glyphs: Sequence[str] = _WAVE_FRAMES if frames == "wave" else _SPIN_FRAMES
        suffix = f" {self.muted(detail)}" if detail else ""
        stop = threading.Event()

        def _spin() -> None:
            index = 0
            while not stop.wait(interval):
                glyph = self.style(MAGENTA, glyphs[index % len(glyphs)])
                self.write_inline(f"\r  {glyph} {self.style(DIM, label)}{suffix}")
                index += 1

        thread = threading.Thread(target=_spin, name="xairex-spinner", daemon=True)
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join(timeout=1.0)
            self.clear_line()

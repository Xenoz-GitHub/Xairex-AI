"""Shared Tk theme: palette, canvas-drawn widgets, small helpers (G4/G17).

The design system for the Xairex desktop UI. Everything is plain Tk + Canvas —
no ttk, one style source (D32/D33), standard library only, Smart-App-Control
safe.

Widgets:

* :class:`HoverButton` — rounded button with an always-on breathing glow that
  flares on hover and flashes on press;
* :class:`GlowBorder` — animated pulsing border for plain Tk inputs (Entry,
  Listbox, OptionMenu, Scale) so focus/idle glow covers every control;
* :class:`GlowStrip` — thin pulsing accent bar for section cards;
* :class:`FluidScrollbar` — thin canvas scrollbar with a draggable rounded
  thumb (drop-in for ``tk.Scrollbar`` in the common vertical case);
* :class:`ScanBar` — animated scan strip used under headers;
* :class:`Toggle` — rounded pill switch bound to a ``tk.BooleanVar`` with a
  breathing halo.

Animation ticks are deliberately cheap (60–110 ms, a few dozen canvas items,
skipped whenever a widget is unmapped), so the whole kit stays comfortably on
the CPU-only budget.
"""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import font as tkfont

# ------------------------------------------------------------------- palette

BG = "#070d13"  # window background (near-black blue)
BG_DEEP = "#04080d"  # recessed wells (troughs, listboxes)
PANEL = "#0c1520"  # cards / inputs / button background
PANEL_HI = "#122238"  # hover fill
EDGE = "#16324a"  # subtle borders
EDGE_HI = "#24557d"  # hover borders / HUD brackets
CYAN = "#3beaff"
MAGENTA = "#ff5fd7"
GREEN = "#69ffa0"
YELLOW = "#ffe25f"
RED = "#ff6f7d"
GRAY = "#7f8c9b"
DIM = "#3d4c5c"
TEXT = "#d7e6f2"

MONO = ("Consolas", 11)
MONO_SMALL = ("Consolas", 9)
MONO_TINY = ("Consolas", 8)
MONO_BOLD = ("Consolas", 11, "bold")
MONO_TITLE = ("Consolas", 22, "bold")


# ------------------------------------------------------------------- helpers


def mix(color_a: str, color_b: str, t: float) -> str:
    """Linear blend between two ``#rrggbb`` colors (``t`` clamped to 0..1)."""
    t = max(0.0, min(1.0, float(t)))
    channels = []
    for i in (1, 3, 5):
        a = int(color_a[i : i + 2], 16)
        b = int(color_b[i : i + 2], 16)
        channels.append(round(a + (b - a) * t))
    return "#{:02x}{:02x}{:02x}".format(*channels)


def _safe_bg(parent: tk.Misc, override: str | None = None) -> str:
    """Resolve a canvas background: explicit > parent bg if it is hex > ``BG``.

    Plain Tk roots hand out named system colours (``SystemButtonFace`` …) that
    cannot be blended with :func:`mix` — fall back to the theme background.
    """
    for candidate in (override, parent.cget("bg")):
        if isinstance(candidate, str) and len(candidate) == 7 and candidate.startswith("#"):
            try:
                int(candidate[1:], 16)
            except ValueError:
                continue
            return candidate
    return BG


def rounded_rect(canvas: tk.Canvas, x1, y1, x2, y2, radius: float = 8, **kwargs):
    """Draw a rounded rectangle as a smoothed polygon; returns the item id."""
    radius = max(0.0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


# ------------------------------------------------------------------- widgets


class HoverButton(tk.Canvas):
    """Rounded flat button with an always-on breathing glow (G17/G21).

    The border glow pulses slowly even when idle ("everything glows", owner
    request 2026-10-16), flares brighter on hover and flashes on press.
    Canvas-drawn on purpose (D33): rounded corners, accent bar and glow are
    impossible with plain ``tk.Button`` and would need a parallel ttk style
    system. The API stays tkinter-flavoured: ``command=``, ``set_text()``,
    ``set_enabled()``.
    """

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command=None,
        *,
        fg: str = CYAN,
        glyph: str = "",
        height: int = 36,
        width: int = 0,
        accent: bool = True,
        bg: str | None = None,
    ) -> None:
        super().__init__(
            parent,
            height=height,
            width=width or 120,
            bg=_safe_bg(parent, bg),
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._text = text
        self._glyph = glyph
        self._command = command
        self._fg = fg
        self._accent = accent
        self._radius = min(9, height // 2)
        self._hover = 0.0  # animated 0..1
        self._target = 0.0
        self._pressed = False
        self._enabled = True
        self._anim: str | None = None
        self._phase = 0.0
        self._pulse_id: str | None = None

        if not width:  # natural width from the label
            measure = tkfont.Font(root=self, font=MONO_BOLD)
            label = f"{glyph}  {text}".strip() if glyph else text
            self.configure(width=measure.measure(label) + 40)

        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._schedule_pulse()

    # ------------------------------------------------------------- public API

    def set_text(self, text: str) -> None:
        self._text = text
        self._draw()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        self.configure(cursor="hand2" if self._enabled else "arrow")
        if not self._enabled:
            self._pressed = False
            self._target = 0.0
        self._draw()

    def destroy(self) -> None:  # cancel pending tweens/pulses before tearing down
        for pending in (self._anim, self._pulse_id):
            if pending is not None:
                try:
                    self.after_cancel(pending)
                except tk.TclError:
                    pass
        self._anim = None
        self._pulse_id = None
        super().destroy()

    # -------------------------------------------------------------- behaviour

    def _schedule_pulse(self) -> None:
        try:
            self._pulse_id = self.after(80, self._pulse_tick)
        except tk.TclError:
            self._pulse_id = None

    def _pulse_tick(self) -> None:
        """Idle breathing glow — cheap, and skipped whenever unmapped."""
        self._pulse_id = None
        try:
            if not self.winfo_exists():
                return
            if self.winfo_ismapped() and self._enabled:
                self._phase += 0.16
                self._draw()
        except tk.TclError:
            return
        self._schedule_pulse()

    def _on_enter(self, _event) -> None:
        if self._enabled:
            self._target = 1.0
            self._tween()

    def _on_leave(self, _event) -> None:
        self._target = 0.0
        self._pressed = False
        self._tween()

    def _on_press(self, _event) -> None:
        if self._enabled:
            self._pressed = True
            self._draw()

    def _on_release(self, event) -> None:
        if not self._enabled:
            return
        was_pressed = self._pressed
        self._pressed = False
        self._draw()
        inside = 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
        if was_pressed and inside and callable(self._command):
            self._command()

    def _tween(self) -> None:
        if self._anim is None:
            self._step()

    def _step(self) -> None:
        self._anim = None
        if abs(self._hover - self._target) < 0.03:
            self._hover = self._target
            self._draw()
            return
        self._hover += (self._target - self._hover) * 0.35
        self._draw()
        try:
            self._anim = self.after(16, self._step)
        except tk.TclError:
            pass

    # --------------------------------------------------------------- painting

    def _draw(self) -> None:
        try:
            if not self.winfo_exists():
                return
            self.delete("all")
            width = self.winfo_width()
            if width <= 1:
                width = self.winfo_reqwidth()
            height = self.winfo_height()
            if height <= 1:
                height = self.winfo_reqheight()
            t = self._hover
            breathe = 0.5 + 0.5 * math.sin(self._phase)
            bg_fill = self.cget("bg")

            # outer glow ring: breathing while idle, flaring on hover
            if self._enabled:
                ring = 0.10 + 0.14 * breathe + 0.45 * t
                rounded_rect(
                    self,
                    1.0,
                    1.0,
                    width - 1.0,
                    height - 1.0,
                    self._radius + 1,
                    outline=mix(bg_fill, self._fg, ring),
                    width=2,
                )

            fill = mix(PANEL, PANEL_HI, t)
            if self._pressed:
                fill = mix(fill, self._fg, 0.14)
            border_strength = (0.16 + 0.14 * breathe) if self._enabled else 0.0
            border = mix(EDGE, self._fg, min(1.0, border_strength + 0.55 * t))
            rounded_rect(self, 4, 4, width - 4, height - 4, self._radius, fill=fill, outline=border, width=2)

            if self._accent and self._enabled:
                rounded_rect(
                    self,
                    8.5,
                    9,
                    11.5,
                    height - 9,
                    1.5,
                    fill=mix(EDGE_HI, self._fg, min(1.0, 0.30 + 0.25 * breathe + 0.55 * t)),
                    outline="",
                )

            label = f"{self._glyph}  {self._text}".strip() if self._glyph else self._text
            text_color = self._fg if self._enabled else DIM
            text_color = mix(text_color, "#ffffff", 0.18 * t) if self._enabled else text_color
            offset = 1 if (self._pressed and self._enabled) else 0
            start_x = 16 if self._accent else 8
            self.create_text(
                (start_x + width - 10) / 2,
                height / 2 + offset,
                text=label,
                font=MONO_BOLD,
                fill=text_color,
            )
        except tk.TclError:
            pass


class FluidScrollbar(tk.Canvas):
    """Thin canvas scrollbar (rounded thumb, drag + hover highlight).

    Drop-in for ``tk.Scrollbar`` in the common vertical case::

        bar = FluidScrollbar(parent, target=text)  # wires yscrollcommand

    ``command=`` may be supplied instead when there is no target widget to
    scroll (wheel support then needs ``target`` anyway).
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        target: tk.Misc | None = None,
        command=None,
        width: int = 13,
        thumb: str = CYAN,
    ) -> None:
        super().__init__(parent, width=width, bg=_safe_bg(parent), highlightthickness=0, bd=0)
        if target is not None:
            self._target: tk.Misc | None = target
            self._scroll = target.yview
            target.configure(yscrollcommand=self.set)
        elif command is not None:
            self._target = None
            self._scroll = command
        else:
            raise ValueError("FluidScrollbar needs a target widget or a command")
        self._thumb_color = thumb
        self._first = 0.0
        self._last = 1.0
        self._hover = False
        self._drag_grab: float | None = None

        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_motion)
        self.bind("<ButtonRelease-1>", self._on_release)

    # tk-style protocol -------------------------------------------------------

    def set(self, first, last) -> None:
        try:
            self._first, self._last = float(first), float(last)
        except (TypeError, ValueError):
            return
        self._draw()

    def bind_wheel(self, *widgets: tk.Misc) -> None:
        """Route the mouse wheel over *widgets* to the scrolled target."""
        for widget in widgets:
            widget.bind("<MouseWheel>", self._on_wheel)

    # behaviour ---------------------------------------------------------------

    def _on_enter(self, _event) -> None:
        self._hover = True
        self._draw()

    def _on_leave(self, _event) -> None:
        if self._drag_grab is None:
            self._hover = False
            self._draw()

    def _thumb_bounds(self) -> tuple[float, float]:
        height = max(self.winfo_height(), 40)
        return 4 + (height - 8) * self._first, 4 + (height - 8) * self._last

    def _on_press(self, event) -> None:
        y1, y2 = self._thumb_bounds()
        if y1 <= event.y <= y2:
            self._drag_grab = event.y - y1  # grabbed the thumb itself
        else:
            self._drag_grab = (y2 - y1) / 2  # jump: centre the thumb on the click
            self._on_motion(event)
        self._draw()

    def _on_motion(self, event) -> None:
        if self._drag_grab is None:
            return
        height = max(self.winfo_height(), 40)
        span = self._last - self._first
        fraction = (event.y - 4 - self._drag_grab) / (height - 8)
        fraction = max(0.0, min(1.0 - span, fraction))
        self._scroll("moveto", fraction)
        self._first, self._last = fraction, fraction + span  # optimistic redraw
        self._draw()

    def _on_release(self, _event) -> None:
        self._drag_grab = None
        self._draw()

    def _on_wheel(self, event) -> None:
        if self._target is None:
            return
        delta = getattr(event, "delta", 0)
        steps = -int(delta / 120) or (-1 if delta > 0 else 1)
        self._target.yview_scroll(steps, "units")

    # painting ----------------------------------------------------------------

    def _draw(self) -> None:
        try:
            if not self.winfo_exists():
                return
            self.delete("all")
            width = self.winfo_width() or 13
            height = self.winfo_height()
            if height < 30:
                return
            rounded_rect(self, width / 2 - 1, 6, width / 2 + 1, height - 6, 1, fill=EDGE, outline="")

            span = max(self._last - self._first, 0.02)
            y1, y2 = self._thumb_bounds()
            if y2 - y1 < 24:  # keep the thumb grabbable
                center = (y1 + y2) / 2
                y1 = max(4.0, center - 12)
                y2 = min(float(height) - 4.0, center + 12)

            color = self._thumb_color
            if self._drag_grab is not None:
                color = mix(color, "#ffffff", 0.25)
            elif self._hover:
                color = mix(color, "#ffffff", 0.12)
            elif span > 0.995:
                color = mix(color, EDGE, 0.55)  # everything visible — dim the thumb
            rounded_rect(self, width / 2 - 3.5, y1, width / 2 + 3.5, y2, 5, fill=color, outline="")
        except tk.TclError:
            pass


class ScanBar(tk.Canvas):
    """Animated scan strip: travelling pulses over a cyan→magenta sweep."""

    def __init__(self, parent: tk.Misc, *, height: int = 4, bg: str | None = None, interval: int = 45) -> None:
        super().__init__(parent, height=height, bg=_safe_bg(parent, bg), highlightthickness=0, bd=0)
        self._offset = 0
        self._interval = interval
        self._running = False
        self.bind("<Configure>", lambda _event: self._draw())

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._tick()

    def stop(self) -> None:
        self._running = False

    def _tick(self) -> None:
        if not self._running:
            return
        try:
            if not self.winfo_exists():
                self._running = False
                return
            self._offset = (self._offset + 1) % 240
            self._draw()
            self.after(self._interval, self._tick)
        except tk.TclError:
            self._running = False

    def _draw(self) -> None:
        try:
            self.delete("all")
            width = self.winfo_width()
            height = self.winfo_height()
        except tk.TclError:
            return
        if width < 12 or height < 1:
            return
        segments = max(12, min(width // 6, 150))
        step = width / segments
        for i in range(segments):
            position = i / segments
            pulse = math.exp(-(((position - self._offset / 240) % 1.0) ** 2) * 40)
            pulse2 = math.exp(-(((position - 0.4 - self._offset / 240) % 1.0) ** 2) * 40)
            wave = 0.5 + 0.5 * math.sin(2 * math.pi * (position * 2 - self._offset / 60))
            heat = max(pulse, pulse2, 0.35 * wave)
            color = mix(CYAN, MAGENTA, (position + self._offset / 240) % 1.0)
            x = i * step
            self.create_line(x, 0, x, height, fill=mix(BG_DEEP, color, 0.15 + 0.85 * heat), width=step + 1)


class Toggle(tk.Canvas):
    """Rounded pill switch bound to a ``tk.BooleanVar`` (settings cards)."""

    def __init__(
        self,
        parent: tk.Misc,
        variable: tk.BooleanVar,
        *,
        on: str = GREEN,
        width: int = 42,
        height: int = 21,
    ) -> None:
        super().__init__(
            parent, width=width, height=height, bg=_safe_bg(parent), highlightthickness=0, bd=0, cursor="hand2"
        )
        self._var = variable
        self._on_color = on
        self._size_w = width
        self._size_h = height
        self._pos = 1.0 if variable.get() else 0.0
        self._anim: str | None = None
        self._phase = 0.0
        self._pulse_id: str | None = None
        variable.trace_add("write", lambda *_args: self._tween())
        self.bind("<Button-1>", lambda _event: self._var.set(not self._var.get()))
        self.bind("<Configure>", lambda _event: self._draw())
        self._schedule_pulse()

    def destroy(self) -> None:
        for pending in (self._anim, self._pulse_id):
            if pending is not None:
                try:
                    self.after_cancel(pending)
                except tk.TclError:
                    pass
        self._anim = None
        self._pulse_id = None
        super().destroy()

    def _schedule_pulse(self) -> None:
        try:
            self._pulse_id = self.after(90, self._pulse_tick)
        except tk.TclError:
            self._pulse_id = None

    def _pulse_tick(self) -> None:
        self._pulse_id = None
        try:
            if not self.winfo_exists():
                return
            if self.winfo_ismapped():
                self._phase += 0.15
                self._draw()
        except tk.TclError:
            return
        self._schedule_pulse()

    def _tween(self) -> None:
        if self._anim is None:
            self._step()

    def _step(self) -> None:
        self._anim = None
        target = 1.0 if self._var.get() else 0.0
        if abs(self._pos - target) < 0.05:
            self._pos = target
            self._draw()
            return
        self._pos += (target - self._pos) * 0.4
        self._draw()
        try:
            self._anim = self.after(16, self._step)
        except tk.TclError:
            pass

    def _draw(self) -> None:
        try:
            if not self.winfo_exists():
                return
            self.delete("all")
            width, height = self._size_w, self._size_h
            t = self._pos
            breathe = 0.5 + 0.5 * math.sin(self._phase)
            track = mix(BG_DEEP, mix(EDGE, self._on_color, 0.30 * t), 0.7)
            lit = min(1.0, 0.14 + 0.12 * breathe + 0.65 * t)
            border = mix(EDGE_HI, self._on_color, lit)
            rounded_rect(self, 1, 1, width - 1, height - 1, height / 2 - 1, fill=track, outline=border, width=1)
            radius = height / 2 - 4
            center_x = 4 + radius + (width - 8 - 2 * radius) * t
            knob = mix(GRAY, self._on_color, t)
            self.create_oval(
                center_x - radius,
                height / 2 - radius,
                center_x + radius,
                height / 2 + radius,
                fill=knob,
                outline="",
            )
        except tk.TclError:
            pass


class GlowBorder:
    """Animated pulsing border for plain Tk inputs (G21).

    Wraps ``tk.Entry``, ``tk.Listbox``, ``tk.OptionMenu`` and ``tk.Scale`` —
    widgets that cannot be canvas-drawn — and breathes their highlight ring:
    a soft idle glow that flares while the widget holds keyboard focus. Cheap:
    two ``configure`` calls per tick, skipped whenever the widget is unmapped.
    """

    def __init__(
        self,
        widget: tk.Misc,
        *,
        color: str = CYAN,
        base: str = EDGE,
        interval: int = 90,
    ) -> None:
        self._widget = widget
        self._color = color
        self._base = base
        self._interval = interval
        self._phase = 0.0
        self._alive = True
        try:
            widget.configure(highlightthickness=max(1, int(widget.cget("highlightthickness"))))
        except (tk.TclError, ValueError):
            pass
        self._schedule()

    def stop(self) -> None:
        self._alive = False

    def _schedule(self) -> None:
        if not self._alive:
            return
        try:
            self._widget.after(self._interval, self._tick)
        except tk.TclError:
            self._alive = False

    def _tick(self) -> None:
        if not self._alive:
            return
        try:
            widget = self._widget
            if not widget.winfo_exists():
                self._alive = False
                return
            if widget.winfo_ismapped():
                self._phase += 0.18
                breathe = 0.5 + 0.5 * math.sin(self._phase)
                try:
                    focused = widget.focus_get() is widget
                except tk.TclError:
                    focused = False
                strength = (0.55 + 0.30 * breathe) if focused else (0.18 + 0.16 * breathe)
                edge = mix(self._base, self._color, strength)
                widget.configure(highlightbackground=edge, highlightcolor=edge)
        except tk.TclError:
            self._alive = False
            return
        self._schedule()


class GlowStrip(tk.Canvas):
    """Thin pulsing accent bar used as the section-card edge (G21)."""

    def __init__(self, parent: tk.Misc, *, color: str = CYAN, width: int = 3, interval: int = 110) -> None:
        super().__init__(parent, width=width, bg=_safe_bg(parent), highlightthickness=0, bd=0)
        self._color = color
        self._interval = interval
        self._phase = 0.0
        self._alive = True
        self.bind("<Configure>", lambda _event: self._draw())
        self._schedule()

    def destroy(self) -> None:
        self._alive = False
        super().destroy()

    def _schedule(self) -> None:
        if not self._alive:
            return
        try:
            self.after(self._interval, self._tick)
        except tk.TclError:
            self._alive = False

    def _tick(self) -> None:
        if not self._alive:
            return
        try:
            if not self.winfo_exists():
                self._alive = False
                return
            if self.winfo_ismapped():
                self._phase += 0.12
                self._draw()
        except tk.TclError:
            self._alive = False
            return
        self._schedule()

    def _draw(self) -> None:
        try:
            if not self.winfo_exists():
                return
            breathe = 0.5 + 0.5 * math.sin(self._phase)
            self.delete("all")
            width = max(self.winfo_width(), int(self.cget("width")))
            height = max(self.winfo_height(), 1)
            self.create_rectangle(0, 0, width, height, fill=mix(EDGE, self._color, 0.40 + 0.45 * breathe), outline="")
        except tk.TclError:
            pass

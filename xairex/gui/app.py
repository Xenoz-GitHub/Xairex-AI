"""Tkinter desktop application for Xairex (decision D22, Phase G; skin G17).

Architecture (G1/G2):

* the engine keeps running on its own thread inside ``Runtime``;
* ``EventUi`` turns all runtime output into events on an ``EventBus``;
* this module owns the Tk main loop only — it drains the bus on a timer
  (``after``), renders the transcript, animates the status orb and forwards
  button presses into the runtime's job queue. Health checks run on a helper
  thread so the window never freezes.

The look (G17): HUD-style transcript panel with corner brackets and a canvas
scrollbar, an animated scan bar under the header, canvas-drawn hover buttons
and a richer status orb — all from ``gui/theme.py`` (no ttk, no extra
packages). Standard library only; nothing here touches the network, models or
audio devices directly.
"""

from __future__ import annotations

import math
import threading
import tkinter as tk

from xairex import __version__, events
from xairex.config import Settings
from xairex.events import Event, EventBus
from xairex.gui import theme
from xairex.gui.event_ui import EventUi
from xairex.gui.settings_window import SettingsWindow
from xairex.runtime import Runtime
from xairex.state_machine import XairexState

# ------------------------------------------------------------------- palette
# The palette lives in gui/theme.py so every window shares one style source.

BG, PANEL, EDGE, EDGE_HI = theme.BG, theme.PANEL, theme.EDGE, theme.EDGE_HI
CYAN, MAGENTA, GREEN = theme.CYAN, theme.MAGENTA, theme.GREEN
YELLOW, RED, GRAY, TEXT, DIM = theme.YELLOW, theme.RED, theme.GRAY, theme.TEXT, theme.DIM

MONO, MONO_SMALL, MONO_TINY = theme.MONO, theme.MONO_SMALL, theme.MONO_TINY

mix = theme.mix

_ORB = 214  # status orb canvas size in pixels

_TAG_COLORS = {
    "cyan": CYAN,
    "magenta": MAGENTA,
    "green": GREEN,
    "yellow": YELLOW,
    "red": RED,
    "gray": GRAY,
}

_STATE_STYLE: dict[XairexState, tuple[str, str]] = {
    XairexState.STARTING: ("starting up", CYAN),
    XairexState.IDLE: ("idle — ready", CYAN),
    XairexState.LISTENING_FOR_WAKE_WORD: ('listening for "hey xairex"', GREEN),
    XairexState.RECORDING_COMMAND: ("listening — speak now", GREEN),
    XairexState.TRANSCRIBING: ("transcribing", YELLOW),
    XairexState.THINKING: ("thinking", MAGENTA),
    XairexState.EXECUTING_TOOL: ("running a tool", MAGENTA),
    XairexState.SPEAKING: ("speaking", CYAN),
    XairexState.ERROR: ("error", RED),
    XairexState.STOPPING: ("stopping", GRAY),
}


def state_label(state: XairexState) -> tuple[str, str]:
    """(label, color) for a state — pure so it can be tested without Tk."""
    return _STATE_STYLE.get(state, (state.value.replace("_", " "), GRAY))


class XairexApp:
    """The window: transcript, status orb, controls, metrics footer."""

    def __init__(self, settings: Settings, runtime: Runtime, bus: EventBus) -> None:
        self.settings = settings
        self.runtime = runtime
        self.bus = bus
        self.state = XairexState.STARTING
        self.level = -120.0
        self._frame = 0
        self._bridge_ticks = 0
        self._closing = False
        self._settings_window: SettingsWindow | None = None
        self._thinking_mark: str | None = None  # text mark for the thinking animation line

        self.root = tk.Tk()
        self.root.title(f"Xairex v{__version__} — offline neural core")
        self.root.configure(bg=BG)
        self.root.geometry("960x700")
        self.root.minsize(820, 580)

        self._build_header()
        self._build_body()
        self._build_input()
        self._build_footer()

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(50, self._drain_events)
        self.root.after(33, self._animate)

    # ---------------------------------------------------------------- layout

    def _build_header(self) -> None:
        frame = tk.Frame(self.root, bg=BG)
        frame.pack(fill="x", padx=18, pady=(14, 0))
        tk.Label(frame, text="XAIREX", bg=BG, fg=CYAN, font=theme.MONO_TITLE).pack(side="left")
        tk.Label(frame, text=f"v{__version__}", bg=BG, fg=DIM, font=MONO_TINY).pack(
            side="left", padx=(10, 0), pady=(10, 0)
        )
        # NOTIFICATIONS button (user request 2026-10-17)
        theme.HoverButton(
            frame, "NOTIFICATIONS", self._on_notifications, fg=YELLOW, glyph="◆", width=150, height=28
        ).pack(side="right", padx=(8, 0), pady=(6, 0))
        tk.Label(
            frame,
            text="⟪ offline neural core ⟫   ⟪ cpu-only ⟫   ⟪ no cloud ⟫",
            bg=BG,
            fg=GRAY,
            font=MONO_SMALL,
        ).pack(side="right", pady=(10, 0))

        self.scan = theme.ScanBar(self.root, height=3)
        self.scan.pack(fill="x", padx=18, pady=(8, 0))
        self.scan.start()

    def _build_body(self) -> None:
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=(12, 0))

        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        # The transcript sits inside a canvas so the HUD frame (corner
        # brackets) can be drawn in the margin around it.
        self._panel = tk.Canvas(left, bg=BG, highlightthickness=0, bd=0)
        self._panel.pack(fill="both", expand=True)
        self.text = tk.Text(
            self._panel,
            bg=PANEL,
            fg=TEXT,
            insertbackground=CYAN,
            font=MONO,
            wrap="word",
            relief="flat",
            highlightthickness=0,
            state="disabled",
            padx=14,
            pady=12,
            cursor="arrow",
            selectbackground=EDGE_HI,
            selectforeground=TEXT,
        )
        self.text.place(x=18, y=18, relwidth=1.0, relheight=1.0, width=-36, height=-36)
        self._scroll = theme.FluidScrollbar(self._panel, target=self.text)
        self._scroll.place(relx=1.0, x=-15, y=18, relheight=1.0, height=-36)
        self._scroll.bind_wheel(self._panel)
        self._panel.bind("<Configure>", self._draw_panel_frame)

        self.text.tag_configure("user", foreground=CYAN)
        self.text.tag_configure("xairex", foreground=MAGENTA)
        self.text.tag_configure("status", foreground=GRAY)
        self.text.tag_configure("warn", foreground=YELLOW)
        self.text.tag_configure("error", foreground=RED)
        self.text.tag_configure("ok", foreground=GREEN)
        self.text.tag_configure("system", foreground=CYAN)
        # Syntax highlighting tags (user request 2026-10-17)
        self.text.tag_configure("code", background=mix(BG, PANEL, 0.3), foreground=GREEN, font=("Consolas", 10))
        self.text.tag_configure("code_keyword", foreground=MAGENTA, font=("Consolas", 10, "bold"))
        self.text.tag_configure("code_string", foreground=YELLOW, font=("Consolas", 10))
        self.text.tag_configure("code_comment", foreground=GRAY, font=("Consolas", 10, "italic"))
        self.text.tag_configure("code_function", foreground=CYAN, font=("Consolas", 10))
        # Terminal execution tags (user request 2026-10-17: show commands like a coding agent)
        self.text.tag_configure("terminal_header", background=mix(BG, EDGE, 0.4), foreground=CYAN, font=("Consolas", 9, "bold"))
        self.text.tag_configure("terminal_command", background=mix(BG, PANEL, 0.2), foreground=GREEN, font=("Consolas", 9))
        self.text.tag_configure("terminal_output", background=mix(BG, PANEL, 0.1), foreground=TEXT, font=("Consolas", 9))

        right = tk.Frame(body, bg=BG, width=244)
        right.pack(side="right", fill="y", padx=(16, 0))
        right.pack_propagate(False)

        self.orb = tk.Canvas(right, width=_ORB, height=_ORB, bg=BG, highlightthickness=0)
        self.orb.pack(pady=(2, 4))

        self.state_text = tk.Label(right, text="starting up", bg=BG, fg=CYAN, font=("Consolas", 13, "bold"))
        self.state_text.pack(pady=(6, 0))

        self.metrics_text = tk.Label(right, text="", bg=BG, fg=GRAY, font=MONO_TINY, wraplength=228, justify="left")
        self.metrics_text.pack(pady=(8, 12))

        self.talk_button = theme.HoverButton(right, "TALK  (voice)", self._on_talk, fg=GREEN, glyph="◉")
        self.talk_button.pack(fill="x", pady=4)
        theme.HoverButton(right, "STOP", self._on_stop, fg=RED, glyph="■").pack(fill="x", pady=4)
        theme.HoverButton(right, "HEALTH", self._on_health, fg=YELLOW, glyph="+").pack(fill="x", pady=4)
        theme.HoverButton(right, "SETTINGS", self._on_settings, fg=CYAN, glyph="≡").pack(fill="x", pady=4)
        theme.HoverButton(right, "CLEAR", self._on_clear, fg=GRAY, glyph="×").pack(fill="x", pady=4)

    def _draw_panel_frame(self, _event: tk.Event | None = None) -> None:
        """HUD corner brackets around the transcript (redrawn on resize)."""
        canvas = self._panel
        canvas.delete("frame")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width < 90 or height < 90:
            return
        length = 22
        inset = 4
        corners = (
            (inset, inset, 1, 1),
            (width - inset, inset, -1, 1),
            (inset, height - inset, 1, -1),
            (width - inset, height - inset, -1, -1),
        )
        tick = mix(EDGE_HI, CYAN, 0.5)
        for x, y, dx, dy in corners:
            canvas.create_line(x, y, x + dx * length, y, fill=EDGE_HI, width=2, tags="frame")
            canvas.create_line(x, y, x, y + dy * length, fill=EDGE_HI, width=2, tags="frame")
            canvas.create_line(x + dx * (length + 5), y, x + dx * (length + 13), y, fill=tick, width=1, tags="frame")
            canvas.create_line(x, y + dy * (length + 5), x, y + dy * (length + 13), fill=tick, width=1, tags="frame")

    def _build_input(self) -> None:
        frame = tk.Frame(self.root, bg=BG)
        frame.pack(fill="x", padx=18, pady=(12, 0))
        self.entry = tk.Entry(
            frame,
            bg=PANEL,
            fg=TEXT,
            insertbackground=CYAN,
            font=MONO,
            relief="flat",
            highlightthickness=1,
            highlightbackground=EDGE,
            highlightcolor=CYAN,
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=5)
        theme.GlowBorder(self.entry, color=CYAN)
        self.entry.bind("<Return>", lambda _event: self._submit())
        self.entry.bind("<KP_Enter>", lambda _event: self._submit())
        theme.HoverButton(frame, "SEND", self._submit, fg=CYAN, glyph="→", width=104, height=30).pack(
            side="left", padx=(10, 0)
        )
        self.entry.focus_set()

    def _build_footer(self) -> None:
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=18, pady=(12, 14))
        self._dot = tk.Canvas(bar, width=16, height=16, bg=BG, highlightthickness=0)
        self._dot.pack(side="left")
        self._paint_dot(CYAN)
        tk.Label(
            bar,
            text=f"  v{__version__} · type a question or press TALK · runtime 100% offline",
            bg=BG,
            fg=GRAY,
            font=MONO_SMALL,
        ).pack(side="left")
        self.brain_label = tk.Label(
            bar,
            text=f"brain: {self.settings.brain.model}",
            bg=BG,
            fg=GRAY,
            font=MONO_SMALL,
        )
        self.brain_label.pack(side="right")
        self.bridge_label = tk.Label(bar, text="", bg=BG, fg=GRAY, font=MONO_SMALL)
        self.bridge_label.pack(side="right", padx=(0, 16))

    def _paint_dot(self, color: str) -> None:
        """Small state dot in the footer (also a glow ring)."""
        self._dot.delete("all")
        theme.rounded_rect(self._dot, 4.5, 4.5, 11.5, 11.5, 2.5, fill=color, outline="")
        theme.rounded_rect(self._dot, 1.5, 1.5, 14.5, 14.5, 5, outline=mix(BG, color, 0.45), width=1)

    # ------------------------------------------------------------- transcript

    def _append(self, tag: str, text: str) -> None:
        self.text.configure(state="normal")
        self.text.insert("end", text + "\n", (tag,))
        self.text.configure(state="disabled")
        self.text.see("end")

    def _append_with_syntax(self, tag: str, text: str) -> None:
        """Append text with syntax highlighting for code blocks (user request 2026-10-17)."""
        import re

        # Detect code blocks: ```language\ncode\n```
        code_block_pattern = r"```(\w+)?\n(.*?)\n```"
        inline_code_pattern = r"`([^`]+)`"

        self.text.configure(state="normal")
        
        # Split by code blocks
        parts = re.split(code_block_pattern, text, flags=re.DOTALL)
        
        for i, part in enumerate(parts):
            if i % 3 == 0:  # Regular text
                # Check for inline code
                inline_parts = re.split(inline_code_pattern, part)
                for j, inline_part in enumerate(inline_parts):
                    if j % 2 == 0:  # Regular text
                        if inline_part:
                            self.text.insert("end", inline_part, (tag,))
                    else:  # Inline code
                        self.text.insert("end", inline_part, ("code",))
            elif i % 3 == 1:  # Language identifier (skip)
                pass
            elif i % 3 == 2:  # Code block content
                language = parts[i-1] if i > 0 else ""
                self._insert_highlighted_code(part, language)
        
        self.text.insert("end", "\n")
        self.text.configure(state="disabled")
        self.text.see("end")

    def _insert_highlighted_code(self, code: str, language: str) -> None:
        """Insert code with basic syntax highlighting."""
        # Simple syntax highlighting for common patterns
        import re

        # Keywords for various languages
        keywords = {
            "python": r"\b(def|class|import|from|if|elif|else|for|while|return|try|except|with|as|pass|break|continue|yield|lambda|async|await)\b",
            "javascript": r"\b(function|const|let|var|if|else|for|while|return|class|import|export|from|async|await)\b",
            "bash": r"\b(if|then|else|fi|for|while|do|done|case|esac|function)\b",
            "sql": r"\b(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TABLE|DATABASE|INDEX)\b",
        }

        self.text.insert("end", "\n", ("code",))
        
        lines = code.split("\n")
        for line in lines:
            if not line.strip():
                self.text.insert("end", "\n", ("code",))
                continue

            # Comments
            if re.match(r"^\s*(#|//|--)", line):
                self.text.insert("end", line + "\n", ("code_comment",))
                continue

            # Apply keyword highlighting
            keyword_pattern = keywords.get(language.lower(), "")
            if keyword_pattern:
                parts = re.split(f"({keyword_pattern})", line)
                for part in parts:
                    if re.match(keyword_pattern, part):
                        self.text.insert("end", part, ("code_keyword",))
                    elif '"' in part or "'" in part:
                        # String highlighting
                        self.text.insert("end", part, ("code_string",))
                    else:
                        self.text.insert("end", part, ("code",))
                self.text.insert("end", "\n", ("code",))
            else:
                # No language-specific highlighting
                self.text.insert("end", line + "\n", ("code",))
        
        self.text.insert("end", "\n", ("code",))

    def _start_thinking_animation(self) -> None:
        """Start the Claude-style thinking animation."""
        self.text.configure(state="normal")
        self._thinking_mark = self.text.index("end-1c")
        self.text.insert("end", "xairex ▸ ", ("xairex",))
        self.text.insert("end", "thinking", ("status",))
        self.text.insert("end", "\n")
        self.text.configure(state="disabled")
        self.text.see("end")

    def _update_thinking_animation(self) -> None:
        """Update the thinking text with animated dots."""
        if self._thinking_mark is None or self.state != XairexState.THINKING:
            return
        # Cycle through "thinking", "thinking.", "thinking..", "thinking..."
        dots = ((self._frame // 10) % 4)
        thinking_text = "thinking" + "." * dots
        try:
            self.text.configure(state="normal")
            # Find the thinking line and update it
            mark_line = int(self._thinking_mark.split(".")[0])
            line_start = f"{mark_line}.0"
            line_end = f"{mark_line}.end"
            content = self.text.get(line_start, line_end)
            if "thinking" in content:
                # Replace everything after "xairex ▸ " with the animated thinking text
                prefix_end = content.find("thinking")
                if prefix_end > 0:
                    new_line = content[:prefix_end] + thinking_text
                    self.text.delete(line_start, line_end)
                    self.text.insert(line_start, new_line[:10], ("xairex",))
                    self.text.insert(f"{mark_line}.10", new_line[10:], ("status",))
            self.text.configure(state="disabled")
        except Exception:  # noqa: BLE001 - defensive; don't crash the animation loop
            pass

    def _stop_thinking_animation(self) -> None:
        """Remove the thinking animation line."""
        if self._thinking_mark is None:
            return
        try:
            self.text.configure(state="normal")
            mark_line = int(self._thinking_mark.split(".")[0])
            self.text.delete(f"{mark_line}.0", f"{mark_line+1}.0")
            self.text.configure(state="disabled")
        except Exception:  # noqa: BLE001 - defensive
            pass
        finally:
            self._thinking_mark = None

    def _append_tagged(self, name: str, text: str, color: str) -> None:
        tag = f"tag-{name}-{color}"
        self.text.tag_configure(tag, foreground=color)
        self._append(tag, f"[{name}] {text}")

    def _append_terminal_execution(self, text: str) -> None:
        """Display tool execution in terminal style (user request 2026-10-17)."""
        self.text.configure(state="normal")
        
        # Parse out command if present
        import re
        
        # Pattern: "typed this into X: command" or "ran: command" or "executed: command"
        command_match = re.search(r"(?:typed.*?:|ran:|executed:)\s*(.+)", text, re.IGNORECASE)
        
        if command_match:
            command = command_match.group(1).strip()
            # Terminal-style header
            self.text.insert("end", "┌─[ TERMINAL ]", ("terminal_header",))
            self.text.insert("end", "\n")
            # Command line
            self.text.insert("end", "│ $ ", ("terminal_header",))
            self.text.insert("end", command, ("terminal_command",))
            self.text.insert("end", "\n")
            # Footer
            self.text.insert("end", "└────────────\n", ("terminal_header",))
        else:
            # Fallback to regular tool display
            self.text.insert("end", f"[tool] {text}\n", ("status",))
        
        self.text.configure(state="disabled")
        self.text.see("end")

    def _append_report(self, text: str) -> None:
        for line in text.splitlines():
            if line.startswith("[FAIL"):
                self._append("error", line)
            elif line.startswith("[OK"):
                self._append("ok", line)
            elif line.startswith("       fix:"):
                self._append("warn", line)
            else:
                self._append("status", line)

    # ----------------------------------------------------------------- events

    def _drain_events(self) -> None:
        if self._closing:
            return
        for event in self.bus.drain():
            self._apply(event)
        self._drain_bridge()
        self.root.after(50, self._drain_events)

    def _drain_bridge(self) -> None:
        """Speak/show queued 'new message' notes; refresh the footer bridge state."""
        bridge = getattr(self.runtime, "bridge", None)
        if bridge is not None:
            for note in bridge.drain_announcements():
                text = str(note.get("text", "")).strip()
                if not text:
                    continue
                preview = " ".join(str(note.get("preview", "")).split())
                sender = str(note.get("sender", "")).strip()
                platform = str(note.get("platform", "")).strip()
                
                # Format with proper separation (user request 2026-10-17: fix "Namemessage" issue)
                if self.state is XairexState.IDLE and self.settings.bridge.announce_messages:
                    self._append("xairex", f"xairex ▸ {text}")
                    if sender and preview:
                        # Show sender and message on separate lines with proper spacing
                        self._append("status", f"    From: {sender}")
                        self._append("status", f"    Message: \"{preview}\"")
                    elif preview:
                        self._append("status", f'    "{preview}"')
                    self.runtime.submit_say(text)
                else:
                    # Condensed format for non-idle states
                    if sender and preview:
                        suffix = f" from {sender}: \"{preview}\""
                    elif preview:
                        suffix = f": \"{preview}\""
                    else:
                        suffix = ""
                    self._append("status", f"  · {text}{suffix}")
        self._bridge_ticks += 1
        if self._bridge_ticks % 20 == 1:
            self._refresh_bridge_label()

    def _refresh_bridge_label(self) -> None:
        bridge = getattr(self.runtime, "bridge", None)
        if bridge is None or not self.settings.bridge.enabled:
            self.bridge_label.configure(text="")
            return
        status = bridge.status()
        if status["connected"]:
            self.bridge_label.configure(text="bridge: connected", fg=GREEN)
        elif status["running"]:
            self.bridge_label.configure(text="bridge: waiting for extension", fg=GRAY)
        else:
            self.bridge_label.configure(text="bridge: off", fg=YELLOW)

    def _apply(self, event: Event) -> None:
        data = event.data
        if event.kind == events.STATE:
            old_state = self.state
            self.state = XairexState(data["to"])
            label, color = state_label(self.state)
            self.state_text.configure(text=label, fg=color)
            self._paint_dot(color)
            # Start thinking animation when entering THINKING state
            if self.state == XairexState.THINKING and old_state != XairexState.THINKING:
                self._start_thinking_animation()
            # Stop thinking animation when leaving THINKING state
            elif old_state == XairexState.THINKING and self.state != XairexState.THINKING:
                self._stop_thinking_animation()
        elif event.kind == events.TRANSCRIPT:
            self._append("user", f"you ▸ {data['text']}")
        elif event.kind == events.ANSWER:
            # Use syntax highlighting for answers that may contain code (user request 2026-10-17)
            answer_text = data['text']
            if "```" in answer_text or "`" in answer_text:
                self._append_with_syntax("xairex", f"xairex ▸ {answer_text}")
            else:
                self._append("xairex", f"xairex ▸ {answer_text}")
        elif event.kind == events.STATUS:
            text = str(data.get("text", ""))
            self._append("status", f"  · {text}")
            if "total=" in text:
                self.metrics_text.configure(text=text)
        elif event.kind == events.TAG:
            color = _TAG_COLORS.get(str(data.get("color")), GRAY)
            name = str(data.get("name", "info"))
            text = str(data.get("text", ""))
            
            # Enhanced terminal-style display for tool execution (user request 2026-10-17)
            if name == "tool" and any(keyword in text.lower() for keyword in ["typed", "command", "ran", "executed"]):
                self._append_terminal_execution(text)
            else:
                self._append_tagged(name, text, color)
        elif event.kind == events.ERROR:
            self._append("error", f"[error] {data.get('text', '')}")
        elif event.kind == events.WARN:
            self._append("warn", f"[warn] {data.get('text', '')}")
        elif event.kind == events.BUSY:
            self._append("warn", f"[busy] {data.get('text', '')}")
        elif event.kind == events.REPORT:
            self._append_report(str(data.get("text", "")))
        elif event.kind == events.SYSTEM:
            self._append("system", str(data.get("text", "")))
        elif event.kind == events.MIC_LEVEL:
            self.level = float(data.get("level", -120.0))

    # ---------------------------------------------------------------- actions

    def _submit(self) -> None:
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self._append("user", f"you ▸ {text}")
        self.runtime.submit_ask(text)

    def _on_talk(self) -> None:
        self.runtime.submit_ptt()

    def _on_stop(self) -> None:
        self.runtime.cancel_current()
        self._append("status", "  · stop requested")

    def _on_settings(self) -> None:
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._settings_window.lift()
            self._settings_window.focus_set()
            return
        self._settings_window = SettingsWindow(self.root, self.settings, on_saved=self._on_settings_saved)

    def _on_notifications(self) -> None:
        """Open the notifications/activity modal window."""
        try:
            from xairex.gui.notifications_window import NotificationsWindow

            bridge = getattr(self.runtime, "bridge", None)
            NotificationsWindow(self.root, bridge)
        except Exception as exc:  # noqa: BLE001
            self._append("error", f"[error] could not open notifications: {exc}")

    def _on_settings_saved(self, settings: Settings) -> None:
        # The engine keeps the settings it booted with (restart to apply); the
        # GUI updates what it displays so the two never disagree silently.
        self.settings = settings
        self.brain_label.configure(text=f"brain: {settings.brain.model}")
        self._append("status", "  · settings saved to config/settings.json — restart Xairex to apply")

    def _on_health(self) -> None:
        self._append("status", "  · running offline health checks…")

        def worker() -> None:
            try:
                text = self.runtime.health_report_text()
            except Exception as exc:  # noqa: BLE001 - surfaced as a report line, never a crash
                text = f"[FAIL] health checks crashed: {exc!r}"
            self.bus.emit(events.REPORT, text=text)

        threading.Thread(target=worker, name="xairex-health", daemon=True).start()

    def _on_clear(self) -> None:
        """CLEAR button: clear transcript and conversation history."""
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        # Also clear conversation history (user request)
        try:
            self.runtime.brain.conversation.clear_history()
        except Exception:
            pass  # Best effort

    # -------------------------------------------------------------- animation

    def _animate(self) -> None:
        if self._closing:
            return
        self._frame += 1
        self._draw_orb()
        # Update thinking animation if active
        if self.state == XairexState.THINKING:
            self._update_thinking_animation()
        self.root.after(33, self._animate)

    def _draw_orb(self) -> None:
        c = self.orb
        c.delete("all")
        _label, color = state_label(self.state)
        cx = cy = _ORB // 2
        frame = self._frame

        self._draw_orb_tickring(c, cx, cy, color, frame)

        if self.state is XairexState.RECORDING_COMMAND:
            self._draw_orb_recording(c, cx, cy, color, frame)
        elif self.state in (XairexState.THINKING, XairexState.TRANSCRIBING, XairexState.EXECUTING_TOOL):
            self._draw_orb_working(c, cx, cy, color, frame)
        elif self.state is XairexState.SPEAKING:
            self._draw_orb_speaking(c, cx, cy, color, frame)
        elif self.state is XairexState.ERROR:
            self._draw_orb_error(c, cx, cy, frame)
        else:  # idle / starting / stopping / wake-word standby
            self._draw_orb_idle(c, cx, cy, color, frame)

    @staticmethod
    def _draw_orb_tickring(c: tk.Canvas, cx: int, cy: int, color: str, frame: int) -> None:
        """Faint tick ring with a highlight spot travelling around it."""
        c.create_oval(cx - 94, cy - 94, cx + 94, cy + 94, outline=mix(BG, EDGE_HI, 0.5), width=1)
        ticks = 48
        lead = (frame * 2.5) % 360
        for i in range(ticks):
            angle = i * (360 / ticks)
            delta = abs(((angle - lead + 180) % 360) - 180)
            light = max(0.0, 1.0 - delta / 80) ** 2
            rad = math.radians(angle)
            outer = 90.0
            inner = 84.0 - 2.0 * light
            c.create_line(
                cx + inner * math.cos(rad),
                cy + inner * math.sin(rad),
                cx + outer * math.cos(rad),
                cy + outer * math.sin(rad),
                fill=mix(EDGE, color, 0.18 + 0.82 * light),
                width=2 if light > 0.35 else 1,
            )

    @staticmethod
    def _draw_orb_idle(c: tk.Canvas, cx: int, cy: int, color: str, frame: int) -> None:
        radius = 50 + 5 * math.sin(frame * 0.07)
        c.create_oval(cx - 76, cy - 76, cx + 76, cy + 76, outline=EDGE, width=1)
        c.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline=color, width=2)
        sweep = math.radians((frame * 1.1) % 360)
        c.create_line(
            cx,
            cy,
            cx + (radius + 20) * math.cos(sweep),
            cy + (radius + 20) * math.sin(sweep),
            fill=mix(BG, color, 0.55),
            width=1,
        )
        c.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, fill=color, outline="")

    def _draw_orb_recording(self, c: tk.Canvas, cx: int, cy: int, color: str, frame: int) -> None:
        fraction = min(max((self.level + 60.0) / 60.0, 0.0), 1.0)
        radius = 36 + 20 * fraction
        c.create_oval(cx - 70, cy - 70, cx + 70, cy + 70, outline=EDGE, width=1)
        c.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline=color, width=3)
        for i in range(36):  # level-reactive burst rays
            angle = i * 10 + frame * 1.5
            wobble = 0.5 + 0.5 * math.sin(frame * 0.35 + i * 1.1)
            length = 6 + 22 * fraction * wobble
            rad = math.radians(angle)
            start = radius + 10
            c.create_line(
                cx + start * math.cos(rad),
                cy + start * math.sin(rad),
                cx + (start + length) * math.cos(rad),
                cy + (start + length) * math.sin(rad),
                fill=mix(EDGE_HI, color, 0.3 + 0.7 * fraction),
                width=2,
            )
        c.create_oval(cx - 7, cy - 7, cx + 7, cy + 7, fill=color, outline="")

    @staticmethod
    def _draw_orb_working(c: tk.Canvas, cx: int, cy: int, color: str, frame: int) -> None:
        second = MAGENTA if color != MAGENTA else CYAN
        c.create_oval(cx - 74, cy - 74, cx + 74, cy + 74, outline=EDGE, width=1)
        start = (frame * 9) % 360
        c.create_arc(cx - 62, cy - 62, cx + 62, cy + 62, start=start, extent=120, style="arc", outline=color, width=4)
        c.create_arc(
            cx - 44,
            cy - 44,
            cx + 44,
            cy + 44,
            start=(-start * 1.6) % 360,
            extent=84,
            style="arc",
            outline=second,
            width=2,
        )
        for k in (0, 180):  # orbiting particles
            angle = math.radians(frame * 3.4 + k)
            px, py = cx + 72 * math.cos(angle), cy + 72 * math.sin(angle)
            c.create_oval(px - 3, py - 3, px + 3, py + 3, fill=color if k == 0 else second, outline="")
        points: list[float] = []
        for step in range(6):  # rotating core hexagon
            angle = math.radians(60 * step + frame * 2)
            points.extend((cx + 11 * math.cos(angle), cy + 11 * math.sin(angle)))
        c.create_polygon(points, fill="", outline=color, width=2)

    @staticmethod
    def _draw_orb_speaking(c: tk.Canvas, cx: int, cy: int, color: str, frame: int) -> None:
        c.create_oval(cx - 74, cy - 74, cx + 74, cy + 74, outline=EDGE, width=1)
        c.create_oval(cx - 58, cy - 58, cx + 58, cy + 58, outline=mix(EDGE, color, 0.35), width=1)
        for i in range(9):
            height = 12 + 40 * abs(math.sin(frame * 0.22 + i * 0.65))
            x = cx - 56 + i * 14
            c.create_line(
                x, cy - height, x, cy + height, fill=mix(color, MAGENTA, (i % 3) * 0.16), width=5, capstyle="round"
            )

    @staticmethod
    def _draw_orb_error(c: tk.Canvas, cx: int, cy: int, frame: int) -> None:
        flash = RED if (frame // 6) % 2 == 0 else "#5a1f2a"
        c.create_oval(cx - 66, cy - 66, cx + 66, cy + 66, outline=flash, width=4)
        c.create_text(cx, cy, text="!", fill=flash, font=("Consolas", 34, "bold"))

    # -------------------------------------------------------------- lifecycle

    def run(self) -> None:
        """Run the Tk main loop (blocking until the window closes)."""
        self.root.mainloop()

    def close(self) -> None:
        """Window close: stop the engine, clear conversation, then destroy (idempotent)."""
        if self._closing:
            return
        self._closing = True
        try:
            self.scan.stop()
        finally:
            try:
                # Clear conversation history on close (user request)
                try:
                    self.runtime.brain.conversation.clear_history()
                except Exception:
                    pass  # Best effort - don't block close
                self.runtime.shutdown()
            finally:
                self.root.destroy()


def run_gui(settings: Settings) -> int:
    """Boot the engine, build the window and run the Tk main loop (blocking)."""
    bus = EventBus()
    ui = EventUi(bus)
    runtime = Runtime(settings, ui=ui, on_state=ui.state_changed)
    runtime.prepare()  # banner/report/warnings land on the bus for the window
    runtime.start_engine()
    runtime.warm_up()
    app = XairexApp(settings, runtime, bus)
    try:
        app.run()
    finally:
        runtime.shutdown()
    return 0

"""Notifications/Activity modal window (user request 2026-10-17).

Shows all browser extension messages and activities in a separate modal with
animated scrollbar. Accessed via NOTIFICATIONS button in the main GUI header.
"""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

from xairex.gui import theme

if TYPE_CHECKING:
    from xairex.bridge.server import BridgeServer

BG, PANEL, EDGE, EDGE_HI = theme.BG, theme.PANEL, theme.EDGE, theme.EDGE_HI
CYAN, MAGENTA, GREEN, YELLOW, RED, GRAY, TEXT, DIM = (
    theme.CYAN,
    theme.MAGENTA,
    theme.GREEN,
    theme.YELLOW,
    theme.RED,
    theme.GRAY,
    theme.TEXT,
    theme.DIM,
)
MONO, MONO_SMALL, MONO_TINY = theme.MONO, theme.MONO_SMALL, theme.MONO_TINY


class NotificationsWindow(tk.Toplevel):
    """Modal window showing all browser extension activity and messages."""

    def __init__(self, parent: tk.Tk, bridge: BridgeServer | None) -> None:
        super().__init__(parent)
        self.bridge = bridge
        self.parent_window = parent

        self.title("Xairex — Browser Activity & Notifications")
        self.configure(bg=BG)
        self.geometry("720x600")
        self.minsize(600, 400)

        # Make it modal (stays on top of parent)
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self._load_activity()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

        # Poll for new activity
        self._poll_activity()

    def _build_ui(self) -> None:
        # Header
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=18, pady=(14, 0))
        tk.Label(
            header,
            text="BROWSER ACTIVITY & NOTIFICATIONS",
            bg=BG,
            fg=CYAN,
            font=theme.MONO_TITLE,
        ).pack(side="left")
        theme.HoverButton(header, "CLEAR", self._on_clear, fg=YELLOW, glyph="×", width=100, height=26).pack(
            side="right"
        )
        theme.HoverButton(header, "REFRESH", self._on_refresh, fg=GREEN, glyph="↻", width=100, height=26).pack(
            side="right", padx=(0, 8)
        )

        # Scan bar
        self.scan = theme.ScanBar(self, height=2)
        self.scan.pack(fill="x", padx=18, pady=(8, 0))
        self.scan.start()

        # Activity list with custom scrollbar
        list_frame = tk.Frame(self, bg=BG)
        list_frame.pack(fill="both", expand=True, padx=18, pady=12)

        self.text = tk.Text(
            list_frame,
            bg=PANEL,
            fg=TEXT,
            font=MONO_SMALL,
            wrap="word",
            relief="flat",
            highlightthickness=0,
            state="disabled",
            padx=12,
            pady=10,
            cursor="arrow",
            selectbackground=EDGE_HI,
            selectforeground=TEXT,
        )
        self.text.pack(side="left", fill="both", expand=True)

        self.scrollbar = theme.FluidScrollbar(list_frame, target=self.text)
        self.scrollbar.pack(side="right", fill="y", padx=(8, 0))
        self.scrollbar.bind_wheel(self.text)

        # Tags for coloring
        self.text.tag_configure("time", foreground=DIM)
        self.text.tag_configure("platform", foreground=CYAN)
        self.text.tag_configure("sender", foreground=MAGENTA, font=("Consolas", 10, "bold"))
        self.text.tag_configure("preview", foreground=TEXT)
        self.text.tag_configure("unread", foreground=YELLOW)
        self.text.tag_configure("activity", foreground=GRAY)

        # Footer
        footer = tk.Frame(self, bg=BG)
        footer.pack(fill="x", padx=18, pady=(0, 14))
        self.status_label = tk.Label(footer, text="", bg=BG, fg=GRAY, font=MONO_TINY)
        self.status_label.pack(side="left")
        theme.HoverButton(footer, "CLOSE", self.destroy, fg=RED, glyph="×", width=100, height=26).pack(side="right")

    def _append(self, text: str, *tags: str) -> None:
        """Append text with tags."""
        self.text.configure(state="normal")
        self.text.insert("end", text, tags)
        self.text.configure(state="disabled")
        self.text.see("end")

    def _load_activity(self) -> None:
        """Load all activity from the bridge store."""
        if self.bridge is None:
            self._append("Bridge is not running.\n", "activity")
            return

        try:
            from xairex.bridge.store import ActivityStore

            store = ActivityStore(
                self.bridge.settings.resolve_path(self.bridge.settings.bridge.log_dir),
                retention_hours=self.bridge.settings.bridge.retention_hours,
            )
            records = store.read(minutes=self.bridge.settings.bridge.retention_hours * 60, limit=500)

            if not records:
                self._append("No browser activity in the last ", "activity")
                self._append(f"{int(self.bridge.settings.bridge.retention_hours)} hours", "unread")
                self._append(".\n", "activity")
                self.status_label.configure(text="No activity")
                return

            # Group by kind
            messages = [r for r in records if r.get("kind") == "message"]
            unread_events = [r for r in records if r.get("kind") == "unread"]
            activity_events = [r for r in records if r.get("kind") == "activity"]

            # Show messages first
            if messages:
                self._append("═" * 80 + "\n", "activity")
                self._append("  MESSAGES\n", "platform")
                self._append("═" * 80 + "\n", "activity")
                for msg in messages[-100:]:  # Last 100 messages
                    self._render_message(msg)

            # Show unread counts
            if unread_events:
                self._append("\n" + "═" * 80 + "\n", "activity")
                self._append("  UNREAD COUNTS\n", "platform")
                self._append("═" * 80 + "\n", "activity")
                for event in unread_events[-20:]:
                    self._render_unread(event)

            # Show browsing activity
            if activity_events:
                self._append("\n" + "═" * 80 + "\n", "activity")
                self._append("  BROWSING ACTIVITY\n", "platform")
                self._append("═" * 80 + "\n", "activity")
                for event in activity_events[-50:]:
                    self._render_activity(event)

            self.status_label.configure(text=f"Showing {len(records)} events")

        except Exception as exc:  # noqa: BLE001
            self._append(f"Error loading activity: {exc}\n", "activity")

    def _render_message(self, msg: dict) -> None:
        """Render one message event with proper formatting."""
        iso = msg.get("iso", "")
        time_str = iso[11:16] if len(iso) >= 16 else "?"
        platform = msg.get("platform", "web")
        sender = msg.get("sender", "").strip() or "someone"
        preview = msg.get("preview", "").strip()

        self._append(f"[{time_str}] ", "time")
        self._append(f"{platform.upper()}", "platform")
        self._append(" • ", "activity")
        self._append(f"{sender}", "sender")
        if preview:
            self._append("\n    ", "activity")
            self._append(f'"{preview}"\n', "preview")
        else:
            self._append("\n", "activity")

    def _render_unread(self, event: dict) -> None:
        """Render unread count event."""
        iso = event.get("iso", "")
        time_str = iso[11:16] if len(iso) >= 16 else "?"
        platform = event.get("platform", "web")
        count = event.get("count", 0)

        self._append(f"[{time_str}] ", "time")
        self._append(f"{platform.upper()}", "platform")
        self._append(" • ", "activity")
        self._append(f"{count} unread", "unread")
        self._append("\n", "activity")

    def _render_activity(self, event: dict) -> None:
        """Render browsing activity event."""
        iso = event.get("iso", "")
        time_str = iso[11:16] if len(iso) >= 16 else "?"
        title = event.get("title", "").strip()[:60]
        url = event.get("url", "").strip()[:80]

        self._append(f"[{time_str}] ", "time")
        if title:
            self._append(f"{title}\n", "preview")
        if url:
            self._append(f"    {url}\n", "activity")

    def _on_clear(self) -> None:
        """Clear the activity display."""
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self.status_label.configure(text="Cleared")

    def _on_refresh(self) -> None:
        """Refresh activity from storage."""
        self._on_clear()
        self._load_activity()

    def _poll_activity(self) -> None:
        """Poll for new activity every 10 seconds."""
        if not self.winfo_exists():
            return
        # Could refresh automatically here, but user can click REFRESH
        self.after(10000, self._poll_activity)

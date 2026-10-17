"""Settings window (G4/G17): edit the validated settings from inside the GUI.

Scope (``notes/03-TASKS.md`` → G4):

* per-tool enable/disable toggles;
* a read-only view of the apps Xairex has learned (discovery adds entries
  automatically — there is no allowlist any more, G19);
* audio input/output device pickers (PortAudio enumeration only — no streams);
* speech-to-text model picker (sibling directories under ``models/whisper``)
  plus the ``stt.hotwords`` bias field;
* brain model picker fed by the local Ollama (loopback only, ``list()``);
* voice speed/volume;
* private-debug-log toggle.

Every edit is funnelled through the validated :class:`~xairex.config.Settings`
model and written back to ``config/settings.json`` atomically (see
:func:`xairex.config.save_settings`). The running engine keeps the settings it
booted with, so the window says *restart to apply* instead of pretending to
hot-reload.

Layout (G17): the whole form lives in a scrollable canvas (wheel + thin canvas
scrollbar) between the header and a fixed footer, so no section can ever be
clipped off-screen; the window sizes itself to the available screen height.

For tests (and day-to-day robustness) the device/model enumerators are
injectable providers; the real ones never leave the machine.
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox
from typing import Any

from pydantic import ValidationError

from xairex.config import Settings, save_settings
from xairex.gui import theme

#: Menu entry that maps to ``"device": null`` (PortAudio selects the default).
DEVICE_DEFAULT_LABEL = "System default"


# --------------------------------------------------------------- pure helpers


def device_label(index: int | None, name: str = "") -> str:
    """Menu label for an audio device (``None`` → the system default)."""
    if index is None:
        return DEVICE_DEFAULT_LABEL
    return f"{index}: {name}" if name else str(index)


def parse_device_label(label: str) -> int | None:
    """Inverse of :func:`device_label`; unparsable text falls back to the default."""
    text = str(label).strip()
    if not text or text == DEVICE_DEFAULT_LABEL:
        return None
    try:
        return int(text.split(":", 1)[0].strip())
    except ValueError:
        return None


def merged_settings(base: Settings, changes: dict[str, Any]) -> Settings:
    """Validated copy of *base* with dotted ``section.field`` *changes* applied.

    Widget values are untrusted input: everything is re-validated through the
    :class:`Settings` model, so out-of-range sliders, empty model names or a
    non-loopback brain URL raise ``pydantic.ValidationError`` and nothing is
    written. The loaded ``config_path`` is preserved so a later
    :func:`~xairex.config.save_settings` writes back to the same file.
    """
    data = base.model_dump(mode="json")
    for dotted, value in changes.items():
        section, _, field = str(dotted).partition(".")
        if not section or not field or not isinstance(data.get(section), dict):
            raise ValueError(f"change key must be 'section.field' with a known section; got {dotted!r}")
        data[section][field] = value
    merged = Settings.model_validate(data)
    merged.config_path = base.config_path
    return merged


def default_tool_names(settings: Settings) -> list[str]:
    """Names of the built-in tools (throwaway registry; nothing is executed)."""
    from xairex.tools import register_default_tools
    from xairex.tools.registry import ToolRegistry

    registry = register_default_tools(ToolRegistry(), settings)
    return registry.names()


def whisper_model_choices(model_dir: str, resolve: Callable[[str], Path]) -> list[str]:
    """Sibling STT model directories of *model_dir* (``models/whisper/*``).

    *resolve* turns the configured (portable, relative) path into an absolute
    one — normally :meth:`xairex.config.Settings.resolve_path`. The configured
    value is always included, even when the directory is missing right now.
    """
    current = Path(model_dir)
    try:
        names = sorted(p.name for p in resolve(model_dir).parent.iterdir() if p.is_dir())
    except OSError:
        names = []
    choices = [f"{current.parent.as_posix()}/{name}" for name in names]
    if model_dir not in choices:
        choices.insert(0, model_dir)
    return choices


# --------------------------------------------------------------------- window


class SettingsWindow(tk.Toplevel):
    """Settings editor for ``config/settings.json`` (one per app window)."""

    #: Accent colour per section card (cycles if a section is added).
    _ACCENTS = (theme.CYAN, theme.GREEN, theme.YELLOW, theme.MAGENTA)

    def __init__(
        self,
        master: tk.Misc,
        settings: Settings,
        on_saved: Callable[[Settings], None] | None = None,
        *,
        model_provider: Callable[[], list[str]] | None = None,
        input_provider: Callable[[], list[str]] | None = None,
        output_provider: Callable[[], list[str]] | None = None,
    ) -> None:
        super().__init__(master)
        self._base = settings
        self._on_saved = on_saved
        self.title("Xairex settings")
        self.configure(bg=theme.BG)
        width, height = 780, max(520, min(820, self.winfo_screenheight() - 140))
        self.geometry(f"{width}x{height}")
        self.minsize(700, 460)
        self._center_on(master, width, height)

        # Enumeration failures only shorten a menu; the configured value always
        # stays selectable. Tests inject deterministic providers.
        model_choices = self._probe(model_provider or self._probe_models, [settings.brain.model])
        input_choices = self._probe(input_provider or self._probe_inputs, [])
        output_choices = self._probe(output_provider or self._probe_outputs, [])

        self._build_header()
        self._build_footer()

        # Scrollable form: canvas + inner frame + thin canvas scrollbar. The
        # footer above stays pinned, so SAVE/CLOSE are always reachable.
        area = tk.Frame(self, bg=theme.BG)
        area.pack(fill="both", expand=True, padx=(18, 8), pady=(6, 0))
        self._content_canvas = tk.Canvas(area, bg=theme.BG, highlightthickness=0, bd=0)
        self._content_canvas.pack(side="left", fill="both", expand=True)
        self._content = tk.Frame(self._content_canvas, bg=theme.BG)
        self._content_id = self._content_canvas.create_window((0, 0), window=self._content, anchor="nw")
        self._sbar = theme.FluidScrollbar(area, target=self._content_canvas)
        self._sbar.pack(side="right", fill="y", padx=(6, 0))
        self._content.bind("<Configure>", self._on_content_configure)
        self._content_canvas.bind("<Configure>", self._on_canvas_configure)

        self._build_tools(settings)
        self._build_apps(settings)
        self._build_audio(settings, input_choices, output_choices)
        self._build_voice(settings)
        self._build_brain(settings, model_choices)
        self._build_stt(settings)
        self._build_privacy(settings)
        self._build_bridge(settings)
        tk.Frame(self._content, bg=theme.BG, height=6).pack(fill="x")

        self._bind_wheel_recursive(self._content_canvas)
        self._apps.bind("<MouseWheel>", self._apps_wheel)  # the list scrolls itself

        self.bind("<Escape>", lambda _event: self.destroy())

    # ------------------------------------------------------------- scroll glue

    def _center_on(self, master: tk.Misc, width: int, height: int) -> None:
        try:
            x = master.winfo_rootx() + max((master.winfo_width() - width) // 2, 30)
            y = master.winfo_rooty() + max((master.winfo_height() - height) // 2, 30)
            self.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass

    def _on_content_configure(self, _event: tk.Event | None = None) -> None:
        self._content_canvas.configure(scrollregion=self._content_canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self._content_canvas.itemconfigure(self._content_id, width=event.width)
        self._on_content_configure()

    def _on_wheel(self, event: tk.Event) -> None:
        delta = getattr(event, "delta", 0)
        if not delta:
            return
        self._content_canvas.yview_scroll(-int(delta / 120) or (-1 if delta > 0 else 1), "units")

    def _apps_wheel(self, event: tk.Event) -> str:
        delta = getattr(event, "delta", 0)
        if delta:
            self._apps.yview_scroll(-int(delta / 120) or (-1 if delta > 0 else 1), "units")
        return "break"

    def _bind_wheel_recursive(self, widget: tk.Misc) -> None:
        widget.bind("<MouseWheel>", self._on_wheel)
        for child in widget.winfo_children():
            self._bind_wheel_recursive(child)

    # ------------------------------------------------------------- enumerators

    @staticmethod
    def _probe(provider: Callable[[], list[str]], fallback: list[str]) -> list[str]:
        try:
            values = [str(value) for value in provider()]
        except Exception:  # noqa: BLE001 - enumeration must never crash the window
            return list(fallback)
        return values or list(fallback)

    def _probe_models(self) -> list[str]:
        from xairex.brain.ollama_client import list_local_models

        return list_local_models(self._base.brain.base_url, timeout_seconds=3.0)

    def _probe_inputs(self) -> list[str]:
        from xairex.audio.microphone import list_input_devices

        return [device_label(device.index, device.name) for device in list_input_devices()]

    def _probe_outputs(self) -> list[str]:
        from xairex.speech.playback import list_output_devices

        return [device_label(device.index, device.name) for device in list_output_devices()]

    # --------------------------------------------------------------- chrome

    def _build_header(self) -> None:
        head = tk.Frame(self, bg=theme.BG)
        head.pack(fill="x", padx=18, pady=(14, 0))
        tk.Label(head, text="SETTINGS", bg=theme.BG, fg=theme.CYAN, font=("Consolas", 16, "bold")).pack(side="left")
        tk.Label(
            head,
            text="xairex · config/settings.json · restart to apply",
            bg=theme.BG,
            fg=theme.DIM,
            font=theme.MONO_TINY,
        ).pack(side="right", pady=(8, 0))
        self._scan = theme.ScanBar(self, height=3)
        self._scan.pack(fill="x", padx=18, pady=(8, 0))
        self._scan.start()

    def _build_footer(self) -> None:
        footer = tk.Frame(self, bg=theme.BG)
        footer.pack(side="bottom", fill="x", padx=18, pady=(10, 14))
        self._status = tk.Label(
            footer,
            text="Nothing saved yet.",
            bg=theme.BG,
            fg=theme.DIM,
            font=theme.MONO_SMALL,
            anchor="w",
            justify="left",
            wraplength=470,
        )
        self._status.pack(side="left", fill="x", expand=True)
        theme.HoverButton(footer, "SAVE", self._on_save, fg=theme.CYAN, width=104, height=32).pack(
            side="left", padx=(10, 0)
        )
        theme.HoverButton(footer, "CLOSE", self.destroy, fg=theme.GRAY, width=104, height=32).pack(
            side="left", padx=(10, 0)
        )

    # --------------------------------------------------------------- buildings

    def _section(self, number: int, title: str, hint: str = "") -> tk.Frame:
        """Card with a numbered header and a pulsing accent strip."""
        card = tk.Frame(self._content, bg=theme.BG)
        card.pack(fill="x", pady=(14, 0))
        head = tk.Frame(card, bg=theme.BG)
        head.pack(fill="x")
        accent = self._ACCENTS[(number - 1) % len(self._ACCENTS)]
        self._accent = accent
        tk.Label(head, text=f"{number:02d}", bg=theme.BG, fg=accent, font=theme.MONO_BOLD).pack(side="left")
        tk.Label(head, text=title, bg=theme.BG, fg=theme.TEXT, font=theme.MONO_BOLD).pack(side="left", padx=(10, 0))
        if hint:
            tk.Label(head, text=hint, bg=theme.BG, fg=theme.DIM, font=theme.MONO_TINY).pack(side="right", pady=(3, 0))
        body = tk.Frame(card, bg=theme.PANEL, highlightthickness=1, highlightbackground=theme.EDGE)
        body.pack(fill="x", pady=(5, 0))
        theme.GlowStrip(body, color=accent).pack(side="left", fill="y")
        inner = tk.Frame(body, bg=theme.PANEL)
        inner.pack(side="left", fill="x", expand=True, padx=12, pady=10)
        return inner

    def _choice_row(self, parent: tk.Frame, label: str, var: tk.StringVar, options: list[str]) -> None:
        row = tk.Frame(parent, bg=theme.PANEL)
        row.pack(fill="x", pady=4)
        tk.Label(row, text=label, width=18, anchor="w", bg=theme.PANEL, fg=theme.TEXT, font=theme.MONO).pack(
            side="left"
        )
        menu = tk.OptionMenu(row, var, *options)
        menu.configure(
            bg=theme.EDGE,
            fg=theme.TEXT,
            activebackground=theme.EDGE_HI,
            activeforeground=theme.CYAN,
            relief="flat",
            highlightthickness=1,
            highlightbackground=theme.EDGE,
            font=theme.MONO_SMALL,
            anchor="w",
            padx=8,
            cursor="hand2",
        )
        menu["menu"].configure(
            bg=theme.PANEL,
            fg=theme.TEXT,
            activebackground=theme.EDGE,
            activeforeground=theme.CYAN,
            font=theme.MONO_SMALL,
        )
        theme.GlowBorder(menu, color=getattr(self, "_accent", theme.CYAN))
        menu.pack(side="left", fill="x", expand=True)

    def _scale_row(self, parent: tk.Frame, label: str, var: tk.DoubleVar, low: float, high: float) -> None:
        row = tk.Frame(parent, bg=theme.PANEL)
        row.pack(fill="x", pady=6)
        tk.Label(row, text=label, width=18, anchor="w", bg=theme.PANEL, fg=theme.TEXT, font=theme.MONO).pack(
            side="left"
        )
        scale = tk.Scale(
            row,
            variable=var,
            from_=low,
            to=high,
            resolution=0.05,
            orient="horizontal",
            bg=theme.PANEL,
            fg=theme.CYAN,
            troughcolor=theme.BG_DEEP,
            activebackground=theme.EDGE,
            highlightthickness=1,
            highlightbackground=theme.EDGE,
            relief="flat",
            bd=0,
            sliderrelief="flat",
            sliderlength=26,
            width=10,
            font=theme.MONO_SMALL,
        )
        theme.GlowBorder(scale, color=getattr(self, "_accent", theme.CYAN))
        scale.pack(side="left", fill="x", expand=True)

    def _label_row(self, parent: tk.Frame, label: str) -> tk.Frame:
        row = tk.Frame(parent, bg=theme.PANEL)
        row.pack(fill="x", pady=4)
        tk.Label(row, text=label, width=18, anchor="w", bg=theme.PANEL, fg=theme.TEXT, font=theme.MONO).pack(
            side="left"
        )
        return row

    def _build_tools(self, settings: Settings) -> None:
        box = self._section(1, "TOOLS", "off = Xairex refuses those commands")
        self._tool_vars: dict[str, tk.BooleanVar] = {}
        disabled = set(settings.tools.disabled)
        grid = tk.Frame(box, bg=theme.PANEL)
        grid.pack(fill="x")
        for position, name in enumerate(default_tool_names(settings)):
            cell = tk.Frame(grid, bg=theme.PANEL)
            cell.grid(row=position // 2, column=position % 2, sticky="w", padx=(2, 44), pady=3)
            var = tk.BooleanVar(self, value=name not in disabled)
            self._tool_vars[name] = var
            theme.Toggle(cell, var, on=theme.GREEN).pack(side="left")
            tk.Label(cell, text=name, bg=theme.PANEL, fg=theme.TEXT, font=theme.MONO_SMALL).pack(
                side="left", padx=(10, 0)
            )

    def _build_apps(self, settings: Settings) -> None:
        box = self._section(2, "LEARNED APPS", "grows automatically — ask her to open anything")
        self._apps = tk.Listbox(
            box,
            height=5,
            bg=theme.BG_DEEP,
            fg=theme.TEXT,
            font=theme.MONO_SMALL,
            selectbackground=theme.EDGE_HI,
            selectforeground=theme.TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=theme.EDGE,
            activestyle="none",
            exportselection=False,
        )
        learned = sorted(settings.tools.apps.items())
        if learned:
            for name, target in learned:
                self._apps.insert("end", f"{name}  →  {target}")
        else:
            self._apps.insert("end", "(nothing learned yet — just ask her to open any app)")
        self._apps.pack(fill="x")
        theme.GlowBorder(self._apps, color=getattr(self, "_accent", theme.CYAN))

    def _build_audio(self, settings: Settings, input_choices: list[str], output_choices: list[str]) -> None:
        box = self._section(3, "AUDIO DEVICES", "applied on the next start")
        input_options = self._unique([DEVICE_DEFAULT_LABEL, *input_choices])
        output_options = self._unique([DEVICE_DEFAULT_LABEL, *output_choices])
        self._input_var = self._device_var(settings.audio.input_device, input_options)
        self._output_var = self._device_var(settings.audio.output_device, output_options)
        self._choice_row(box, "microphone (input)", self._input_var, input_options)
        self._choice_row(box, "speaker (output)", self._output_var, output_options)

    def _build_voice(self, settings: Settings) -> None:
        box = self._section(4, "VOICE", "speech speed and volume")
        self._speed_var = tk.DoubleVar(self, value=settings.tts.speed)
        self._scale_row(box, "speed ×", self._speed_var, 0.5, 2.0)
        self._volume_var = tk.DoubleVar(self, value=settings.tts.volume)
        self._scale_row(box, "volume", self._volume_var, 0.05, 1.0)

    def _build_brain(self, settings: Settings, model_choices: list[str]) -> None:
        box = self._section(5, "BRAIN", "local Ollama — loopback only")
        options = self._unique(sorted([*model_choices, settings.brain.model]))
        self._brain_var = tk.StringVar(self, value=settings.brain.model)
        self._choice_row(box, "model", self._brain_var, options)

    def _build_stt(self, settings: Settings) -> None:
        box = self._section(6, "SPEECH-TO-TEXT", "local Whisper model on disk")
        stt_options = whisper_model_choices(settings.stt.model_dir, settings.resolve_path)
        self._stt_var = tk.StringVar(self, value=settings.stt.model_dir)
        self._choice_row(box, "model directory", self._stt_var, stt_options)

        row = self._label_row(box, "hotwords")
        self._hotwords_var = tk.StringVar(self, value=settings.stt.hotwords)
        entry = tk.Entry(
            row,
            textvariable=self._hotwords_var,
            bg=theme.BG_DEEP,
            fg=theme.TEXT,
            insertbackground=theme.CYAN,
            font=theme.MONO_SMALL,
            relief="flat",
            highlightthickness=1,
            highlightbackground=theme.EDGE,
            highlightcolor=theme.CYAN,
        )
        entry.pack(side="left", fill="x", expand=True, ipady=4)
        theme.GlowBorder(entry, color=getattr(self, "_accent", theme.CYAN))

    def _build_privacy(self, settings: Settings) -> None:
        box = self._section(7, "PRIVACY")
        self._debug_var = tk.BooleanVar(self, value=settings.logging.debug_log_private)
        row = tk.Frame(box, bg=theme.PANEL)
        row.pack(fill="x")
        theme.Toggle(row, self._debug_var, on=theme.CYAN).pack(side="left")
        tk.Label(
            row,
            text="write transcripts and answers to the log file (troubleshooting only)",
            bg=theme.PANEL,
            fg=theme.TEXT,
            font=theme.MONO_SMALL,
        ).pack(side="left", padx=(10, 0))

    def _build_bridge(self, settings: Settings) -> None:
        box = self._section(8, "BROWSER BRIDGE", "loopback only — the Xairex extension connects here")

        self._bridge_enabled_var = tk.BooleanVar(self, value=settings.bridge.enabled)
        row = tk.Frame(box, bg=theme.PANEL)
        row.pack(fill="x")
        theme.Toggle(row, self._bridge_enabled_var, on=theme.GREEN).pack(side="left")
        tk.Label(
            row,
            text="enabled — Chrome/Edge extension can connect while Xairex runs",
            bg=theme.PANEL,
            fg=theme.TEXT,
            font=theme.MONO_SMALL,
        ).pack(side="left", padx=(10, 0))

        port_row = self._label_row(box, "port")
        self._bridge_port_var = tk.StringVar(self, value=str(settings.bridge.port))
        entry = tk.Entry(
            port_row,
            textvariable=self._bridge_port_var,
            width=10,
            bg=theme.BG_DEEP,
            fg=theme.TEXT,
            insertbackground=theme.CYAN,
            font=theme.MONO_SMALL,
            relief="flat",
            highlightthickness=1,
            highlightbackground=theme.EDGE,
            highlightcolor=theme.CYAN,
        )
        entry.pack(side="left", ipady=4)
        theme.GlowBorder(entry, color=getattr(self, "_accent", theme.CYAN))
        tk.Label(
            port_row,
            text="  1024–65535; the extension options must use the same port",
            bg=theme.PANEL,
            fg=theme.DIM,
            font=theme.MONO_TINY,
        ).pack(side="left")

        self._retention_var = tk.DoubleVar(self, value=settings.bridge.retention_hours)
        self._scale_row(box, "log retention (h)", self._retention_var, 1, 24)

        self._bridge_announce_var = tk.BooleanVar(self, value=settings.bridge.announce_messages)
        row2 = tk.Frame(box, bg=theme.PANEL)
        row2.pack(fill="x", pady=(4, 0))
        theme.Toggle(row2, self._bridge_announce_var, on=theme.CYAN).pack(side="left")
        tk.Label(
            row2,
            text="speak short notes when a new message arrives (rate-limited)",
            bg=theme.PANEL,
            fg=theme.TEXT,
            font=theme.MONO_SMALL,
        ).pack(side="left", padx=(10, 0))

    # ------------------------------------------------------------- small utils

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))

    @staticmethod
    def _device_var(index: int | None, options: list[str]) -> tk.StringVar:
        if index is None:
            label = DEVICE_DEFAULT_LABEL
        else:
            label = next((option for option in options if parse_device_label(option) == index), None) or device_label(
                index
            )
            if label not in options:  # device not present right now — keep it selectable
                options.append(label)
        return tk.StringVar(value=label)

    # ------------------------------------------------------------- save/cancel

    def _collect_changes(self) -> dict[str, Any]:
        return {
            "tools.disabled": [name for name, var in self._tool_vars.items() if not var.get()],
            "audio.input_device": parse_device_label(self._input_var.get()),
            "audio.output_device": parse_device_label(self._output_var.get()),
            "tts.speed": round(float(self._speed_var.get()), 2),
            "tts.volume": round(float(self._volume_var.get()), 2),
            "brain.model": self._brain_var.get().strip(),
            "stt.model_dir": self._stt_var.get(),
            "stt.hotwords": self._hotwords_var.get().strip(),
            "logging.debug_log_private": bool(self._debug_var.get()),
            "bridge.enabled": bool(self._bridge_enabled_var.get()),
            "bridge.port": int(str(self._bridge_port_var.get()).strip()),
            "bridge.retention_hours": round(float(self._retention_var.get()), 1),
            "bridge.announce_messages": bool(self._bridge_announce_var.get()),
        }

    def _on_save(self) -> None:
        try:
            updated = merged_settings(self._base, self._collect_changes())
        except (ValidationError, ValueError) as exc:
            messagebox.showerror(
                "Xairex settings",
                f"Not saved — a value is invalid for its setting.\n\n{exc}",
                parent=self,
            )
            return
        try:
            path = save_settings(updated)
        except OSError as exc:
            messagebox.showerror("Xairex settings", f"Could not write settings.json:\n{exc}", parent=self)
            return
        self._base = updated
        if self._on_saved is not None:
            self._on_saved(updated)
        self._status.configure(text=f"Saved to {path.name} — restart Xairex to apply.", fg=theme.GREEN)

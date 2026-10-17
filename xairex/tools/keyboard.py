"""Keyboard control: type text and press key combos (G20/G22, D39/D41).

Windows ``SendInput`` via ctypes — the same path a physical keyboard takes.
The owner asked for hands-free typing ("type this into notepad", "type the
song name in the YouTube search box") and later for typing inside Turbo C++
(G22), which runs under DOSBox.

Two injection modes:

* ``unicode`` — ``KEYEVENTF_UNICODE`` characters: right for modern Windows
  apps (Notepad, browsers, our own GUI);
* ``vk`` — real virtual-key presses carrying the hardware scan code: right for
  DOS/DOSBox environments (Turbo C++), which translate scancodes and ignore
  Unicode injection. ``auto`` (the default) picks ``vk`` when the foreground
  process is DOSBox.

Keystrokes go to whatever window has focus; this module never runs shell
commands and accepts no free-form key names (fixed allowlist of keys and
modifiers only). Tests monkeypatch :func:`_send_inputs`, so no real
keystrokes are ever sent by the test suite.
"""

from __future__ import annotations

import logging
import re
import sys
import time

from xairex.tools.registry import ToolResult, ToolSpec

logger = logging.getLogger("xairex.tools.keyboard")

_MAX_TEXT = 4000

#: Keystroke pacing. WinUI editors (Windows 11 Notepad) mangle fast synthetic
#: bursts — live probe 2026-10-16: 0/2 ms per char produced dropped and
#: duplicated characters ("hello 333333333"), 5–10 ms was mostly clean but
#: hiccuped once, 12 ms passed every case (plain text, newlines, punctuation)
#: while a classic Win32 edit (Run dialog) took a full-speed batch fine.
#: 12 ms ≈ 80 chars/s — imperceptible for short text, ~48 s for the 4 000
#: character cap (tool timeout 90 s).
_KEY_INTERVAL = 0.012
#: Small pause before the first keystroke so a just-activated window has
#: finished taking keyboard focus (probe: the very first char was eaten when
#: typing immediately after the window came to front).
_SETTLE = 0.15

_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004
_INPUT_KEYBOARD = 1

_MODIFIERS: dict[str, int] = {
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "win": 0x5B,
    "windows": 0x5B,
}

_NAMED_KEYS: dict[str, int] = {
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "backspace": 0x08,
    "bksp": 0x08,
    "delete": 0x2E,
    "del": 0x2E,
    "insert": 0x2D,
    "ins": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pgup": 0x21,
    "pagedown": 0x22,
    "pgdn": 0x22,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
}

#: single characters that are valid as the main key of a combo
_CHAR_KEYS: dict[str, int] = {}
for _letter in "abcdefghijklmnopqrstuvwxyz":
    _CHAR_KEYS[_letter] = 0x41 + (ord(_letter) - ord("a"))
for _digit in "0123456789":
    _CHAR_KEYS[_digit] = 0x30 + int(_digit)
_CHAR_KEYS["`"] = 0xC0  # VK_OEM_3 — VS Code's "new terminal" combo (ctrl+shift+`)

_COMBO_SPLIT = re.compile(r"\s*(?:,|;|\bthen\b)\s*")


def _utf16_units(text: str) -> list[int]:
    """UTF-16 code units for *text* (surrogate pairs included)."""
    raw = text.encode("utf-16-le")
    return [raw[index] | (raw[index + 1] << 8) for index in range(0, len(raw), 2)]


#: SendInput's ctypes scaffolding, built once on first use (per-call structure
#: construction dominated the cost profile — probe 2026-10-16).
_INPUT_CORE: dict | None = None
#: Foreground-window inspection handles, built once on first use.
_FG_CORE: tuple | None = None


def _ensure_input_core() -> dict:
    global _INPUT_CORE
    if _INPUT_CORE is None:  # pragma: no cover - Windows-only by design
        import ctypes
        from ctypes import wintypes

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

        class INPUT(ctypes.Structure):
            class _UNION(ctypes.Union):
                _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

            _anonymous_ = ("u",)
            _fields_ = [("type", wintypes.DWORD), ("u", _UNION)]

        _INPUT_CORE = {
            "INPUT": INPUT,
            "KEYBDINPUT": KEYBDINPUT,
            "size": ctypes.sizeof(INPUT),
            "send": ctypes.windll.user32.SendInput,
            "scan": ctypes.windll.user32.MapVirtualKeyW,
        }
    return _INPUT_CORE


def _send_inputs(events: list[tuple[str, int, bool]]) -> int:
    """SendInput wrapper. ``events`` are ``("vk"|"unicode", code, key_up)``.

    VK events carry the real hardware scan code (``MapVirtualKeyW``), which
    DOSBox/SDL translate into DOS keys — Unicode-only injection is ignored
    there (probe 2026-10-16). Kept as the single monkeypatch point for tests.
    """
    if sys.platform != "win32":  # pragma: no cover - Windows-only by design
        raise OSError("keyboard control needs Windows")
    core = _ensure_input_core()
    input_type = core["INPUT"]
    array = (input_type * len(events))()
    for index, (kind, code, key_up) in enumerate(events):
        flags = _KEYEVENTF_KEYUP if key_up else 0
        if kind == "unicode":
            flags |= _KEYEVENTF_UNICODE
            w_vk, w_scan = 0, code
        else:
            w_vk, w_scan = code, int(core["scan"](code, 0)) & 0xFF
        array[index].type = _INPUT_KEYBOARD
        array[index].ki = core["KEYBDINPUT"](wVk=w_vk, wScan=w_scan, dwFlags=flags, time=0, dwExtraInfo=None)
    sent = core["send"](len(events), array, core["size"])
    if sent != len(events):
        raise OSError("SendInput was blocked by the system")
    return sent


_VKSCAN = None


def _vk_for_char(char: str) -> tuple[int, bool]:
    """``(virtual key, needs_shift)`` for *char* on the active keyboard layout.

    Raises ``ValueError`` when the character has no plain key (e.g. ctrl/alt
    chord or accent not on this layout) — honest failure beats typing garbage.
    """
    global _VKSCAN
    if sys.platform != "win32":  # pragma: no cover - Windows-only by design
        raise OSError("keyboard control needs Windows")
    if _VKSCAN is None:  # pragma: no cover - Windows-only by design
        import ctypes

        _VKSCAN = ctypes.windll.user32.VkKeyScanW
    code = int(_VKSCAN(ord(char[0])))
    if code == -1:
        raise ValueError(f"I don't have a key for {char!r} on this keyboard layout")
    state = (code >> 8) & 0xFF
    if state & 0x06:
        raise ValueError(f"{char!r} needs ctrl/alt on this layout; I only type plain characters")
    return code & 0xFF, bool(state & 0x01)


def _foreground_process_name() -> str:
    """Image path of the process owning the foreground window ("" if unknown)."""
    global _FG_CORE
    if sys.platform != "win32":
        return ""
    try:
        if _FG_CORE is None:  # pragma: no cover - Windows-only by design
            import ctypes

            _FG_CORE = (ctypes, ctypes.windll.user32, ctypes.windll.kernel32)
        ctypes, user32, kernel32 = _FG_CORE
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(0x1000, False, pid.value)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return ""
        try:
            size = ctypes.c_ulong(260)
            buffer = ctypes.create_unicode_buffer(260)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return buffer.value
            return ""
        finally:
            kernel32.CloseHandle(handle)
    except Exception:  # noqa: BLE001 - defensive; headless sessions
        return ""


def _vk_char_events(char: str) -> list[tuple[str, int, bool]]:
    """Down/up events (with shift when needed) for one character, VK mode."""
    vk, shift = _vk_for_char(char)
    events: list[tuple[str, int, bool]] = []
    if shift:
        events.append(("vk", 0x10, False))  # VK_SHIFT
    events.append(("vk", vk, False))
    events.append(("vk", vk, True))
    if shift:
        events.append(("vk", 0x10, True))
    return events


def type_text(
    text: str,
    *,
    interval: float = _KEY_INTERVAL,
    settle: float = _SETTLE,
    mode: str = "auto",
) -> None:
    """Type *text* as keystrokes (newlines become real Enter presses).

    ``mode="unicode"`` injects characters (modern Windows apps);
    ``mode="vk"`` presses real keys with scan codes (DOS/DOSBox — Turbo C++ —
    which ignores Unicode injection); ``mode="auto"`` (default) picks ``vk``
    when the foreground process is DOSBox, else ``unicode``. ``\\n`` is always
    a VK_RETURN press — multiline controls (Notepad, the Turbo C++ editor)
    handle it far more reliably than raw CR/LF characters (probe 2026-10-16).
    Paced at ``interval`` seconds per keystroke: fast synthetic bursts are
    mangled by WinUI editors (see :data:`_KEY_INTERVAL`). Pass ``interval=0``
    and ``settle=0`` to send flat out (tests, classic Win32 targets).
    """
    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    mode = str(mode).lower()
    if mode == "auto":
        mode = "vk" if "dosbox" in _foreground_process_name().lower() else "unicode"
    if mode not in ("unicode", "vk"):
        raise ValueError(f"unknown typing mode {mode!r}")
    pairs: list[list[tuple[str, int, bool]]] = []
    for char in normalized:
        if char == "\n":
            pairs.append([("vk", 0x0D, False), ("vk", 0x0D, True)])
            continue
        if mode == "vk":
            pairs.append(_vk_char_events(char))
            continue
        for unit in _utf16_units(char):
            pairs.append([("unicode", unit, False), ("unicode", unit, True)])
    if not pairs:
        return
    if settle:
        time.sleep(settle)
    for index, events in enumerate(pairs):
        _send_inputs(events)
        if interval and index + 1 < len(pairs):
            time.sleep(interval)


def press_combo(combo: str) -> None:
    """Press one combo like ``enter``, ``ctrl+s`` or ``alt+f4``."""
    parts = [part.strip().lower() for part in str(combo).split("+") if part.strip()]
    if not parts:
        raise ValueError("empty key combo")
    *modifiers, main = parts
    for modifier in modifiers:
        if modifier not in _MODIFIERS:
            raise ValueError(f"unknown modifier {modifier!r}")
    if main in _MODIFIERS:
        raise ValueError(f"{main!r} needs a main key, e.g. '{main}+c'")
    if main not in _NAMED_KEYS and main not in _CHAR_KEYS:
        raise ValueError(f"unknown key {main!r}")
    code = _NAMED_KEYS.get(main, _CHAR_KEYS.get(main, 0))

    events: list[tuple[str, int, bool]] = []
    for modifier in modifiers:
        events.append(("vk", _MODIFIERS[modifier], False))
    events.append(("vk", code, False))
    events.append(("vk", code, True))
    for modifier in reversed(modifiers):
        events.append(("vk", _MODIFIERS[modifier], True))
    _send_inputs(events)


def _combos(raw: str) -> list[str]:
    return [part for part in _COMBO_SPLIT.split(str(raw).strip()) if part]


def type_text_tool() -> ToolSpec:
    def handler(args: dict) -> ToolResult:
        text = str(args.get("text", ""))
        if not text:
            return ToolResult(False, "Tell me what to type.")
        if len(text) > _MAX_TEXT:
            return ToolResult(False, f"That text is too long to type in one go (max {_MAX_TEXT} characters).")
        try:
            type_text(text)
            if bool(args.get("enter", False)):
                time.sleep(0.05)
                press_combo("enter")
        except (OSError, ValueError) as exc:
            return ToolResult(False, f"I couldn't type that: {exc}")
        suffix = " and pressed Enter" if bool(args.get("enter", False)) else ""
        return ToolResult(
            True, f"Typed {len(text)} characters into the focused window{suffix}.", data={"characters": len(text)}
        )

    return ToolSpec(
        name="type_text",
        description=(
            "Type text as keyboard input into whatever window currently has focus (e.g. Notepad, "
            "a browser search box). Set enter=true to press Enter right after."
        ),
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The exact text to type."},
                "enter": {"type": "boolean", "description": "Press Enter after typing."},
            },
            "required": ["text"],
        },
        handler=handler,
        timeout_seconds=90.0,  # 4000 chars are paced at ~8 ms each on purpose
    )


def press_keys_tool() -> ToolSpec:
    def handler(args: dict) -> ToolResult:
        raw = str(args.get("keys", "")).strip()
        combos = _combos(raw)
        if not combos:
            return ToolResult(False, "Tell me which keys to press, like 'enter' or 'ctrl+s'.")
        try:
            for index, combo in enumerate(combos):
                if index:
                    time.sleep(0.05)
                press_combo(combo)
        except (OSError, ValueError) as exc:
            return ToolResult(False, f"I couldn't press those keys: {exc}")
        return ToolResult(True, f"Pressed {raw}.", data={"keys": combos})

    return ToolSpec(
        name="press_keys",
        description=(
            "Press a key or combo in the focused window: 'enter', 'tab', 'esc', 'ctrl+s', 'ctrl+a', "
            "'alt+f4', 'alt+tab', 'win', 'f5', arrows, function keys. Chain with commas: 'ctrl+s, enter'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "keys": {"type": "string", "description": "One combo or a comma-separated chain, e.g. 'ctrl+s, enter'."}
            },
            "required": ["keys"],
        },
        handler=handler,
        timeout_seconds=30.0,
    )

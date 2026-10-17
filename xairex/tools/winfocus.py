"""Win32 window plumbing shared by the UI-driving tools (G22 Turbo, G24 VS Code).

Extracted verbatim-in-behaviour from ``xairex/tools/turbo_cpp.py`` (G22, D41)
where it was verified live: the foreground lock refuses a plain
``SetForegroundWindow`` while another app holds focus, so the working recipe is
a lone Alt tap + ``AttachThreadInput`` dance + verification, with a guarded
centre click as the last resort (never click blind — the window must really be
on top at that point).
"""

from __future__ import annotations

import ctypes
import subprocess
import time
from ctypes import wintypes

#: Settle between focus attempts (seconds); module-level so tests can zero it.
FOCUS_ATTEMPT_SLEEP = 0.35


def pids(image: str) -> set[int]:
    """Process ids whose image name matches *image* (via tasklist)."""
    out = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    found: set[int] = set()
    for line in out.splitlines():
        parts = [part.strip().strip('"') for part in line.split(",")]
        if len(parts) >= 2 and parts[0].lower() == image.lower():
            try:
                found.add(int(parts[1]))
            except ValueError:
                continue
    return found


def windows_of(pid_value: int, visible_only: bool = True) -> list[tuple[int, str, str]]:
    """Visible top-level windows of a process: ``(hwnd, title, class)`` in z-order."""
    user32 = ctypes.windll.user32
    found: list[tuple[int, str, str]] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def callback(hwnd, _lparam):
        owner = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value != pid_value:
            return True
        if visible_only and not user32.IsWindowVisible(hwnd):
            return True
        title = ctypes.create_unicode_buffer(160)
        cls = ctypes.create_unicode_buffer(160)
        user32.GetWindowTextW(hwnd, title, 160)
        user32.GetClassNameW(hwnd, cls, 160)
        found.append((int(hwnd), title.value, cls.value))
        return True

    user32.EnumWindows(callback, None)
    return found


def alt_tap() -> None:
    user32 = ctypes.windll.user32
    user32.keybd_event(0x12, 0, 0, 0)  # VK_MENU down
    user32.keybd_event(0x12, 0, 2, 0)  # VK_MENU up


def attach_bypass(hwnd: int) -> None:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    foreground = user32.GetForegroundWindow()
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)
    ours = kernel32.GetCurrentThreadId()
    others = {thread for thread in (user32.GetWindowThreadProcessId(foreground, None), ours) if thread}
    for thread in others:
        user32.AttachThreadInput(thread, target_thread, True)
    try:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        for thread in others:
            user32.AttachThreadInput(thread, target_thread, False)


def click_center(hwnd: int) -> None:
    user32 = ctypes.windll.user32
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    x = (rect.left + rect.right) // 2
    y = (rect.top + rect.bottom) // 2
    if user32.WindowFromPoint(wintypes.POINT(x, y)) != hwnd:
        return  # another window is really on top there — never click blind
    user32.SetCursorPos(x, y)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP


def focus(hwnd: int, attempts: int = 12) -> bool:
    """Best-effort foreground steal with verification. True once the window has it."""
    user32 = ctypes.windll.user32
    for _ in range(attempts):
        if user32.GetForegroundWindow() == hwnd:
            return True
        alt_tap()
        attach_bypass(hwnd)
        if user32.GetForegroundWindow() != hwnd:
            click_center(hwnd)
        time.sleep(FOCUS_ATTEMPT_SLEEP)
    return user32.GetForegroundWindow() == hwnd

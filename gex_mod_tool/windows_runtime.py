"""Resolve the Windows SDK ICU used by this Qt build before importing Qt."""

from __future__ import annotations

import ctypes
import sys


_system_icu = None


def prepare() -> None:
    global _system_icu
    if sys.platform == "win32" and _system_icu is None:
        # Qt 6.10's Windows wheel links the OS ICU C API. An unrelated ICU
        # with the same filename can have version-suffixed exports instead.
        # Keep the intended OS library loaded before any Qt module import.
        _system_icu = ctypes.WinDLL("icuuc.dll", winmode=0x00000800)

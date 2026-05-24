"""Shared utilities for frozen (PyInstaller) and unfrozen (pip install) modes.

When packaged as a single exe with PyInstaller, ``sys.frozen`` is True
and ``sys.executable`` points to the exe itself.  All subprocess spawns
must use the exe path + subcommands instead of ``pythonw.exe`` + script
paths.

This module is the single source of truth for spawn arguments and
resource paths so that every other module stays identical across modes.
"""

import subprocess
import sys
from pathlib import Path
from typing import NoReturn


def is_frozen() -> bool:
    """``True`` when running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def _exe_path() -> str:
    """Path to the current executable (exe itself when frozen, pythonw/python otherwise)."""
    if is_frozen():
        return sys.executable
    if sys.platform == "win32":
        pw = Path(sys.executable).parent / "pythonw.exe"
        return str(pw) if pw.exists() else sys.executable
    return sys.executable


# ── Spawn argument builders ──────────────────────────────────────────


def notify_args(event_key: str, show_ui: bool = False) -> list[str]:
    """Command-line args to launch a notification popup for *event_key*."""
    if is_frozen():
        args = [sys.executable, "notify", event_key]
    else:
        script = str(Path(__file__).resolve().parent / "notify_popup.py")
        args = [_exe_path(), script, event_key]
    if show_ui:
        args.append("--show-ui")
    return args


def config_gui_args() -> list[str]:
    """Command-line args to launch the GUI configuration window."""
    if is_frozen():
        return [sys.executable, "config-gui"]
    script = str(Path(__file__).resolve().parent / "configure_gui.py")
    return [_exe_path(), script]


def tray_args() -> list[str]:
    """Command-line args to launch the system-tray daemon."""
    if is_frozen():
        return [sys.executable, "tray"]
    script = str(Path(__file__).resolve().parent / "tray.py")
    return [_exe_path(), script]


# ── Spawn helper ─────────────────────────────────────────────────────


def popen_spawn(args: list[str], env: dict | None = None) -> None:
    """Fire-and-forget subprocess spawn — never blocks, no console flash."""
    kwargs: dict = {
        "args": args,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if env is not None:
        kwargs["env"] = env
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(**kwargs)


# ── Console attachment (Windows frozen CLI) ──────────────────────────


def attach_parent_console() -> None:
    """Attach to the parent process's console so ``print()`` is visible.

    When the exe is built with ``console=False`` (GUI subsystem), the
    process starts without a console.  Calling this before any CLI output
    reconnects to the parent terminal so ``cn status`` and friends work.
    """
    if not is_frozen() or sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.kernel32.AttachConsole(-1)
    except Exception:
        pass


# ── Resource paths ───────────────────────────────────────────────────


def get_sounds_dir() -> Path:
    """Return the directory containing built-in ``.wav`` sound files.

    When frozen, sound files are extracted to ``sys._MEIPASS`` by
    PyInstaller.  Otherwise they live next to this module.
    """
    if is_frozen():
        return Path(sys._MEIPASS) / "claude_notifier" / "sounds"
    return Path(__file__).resolve().parent / "sounds"

"""Cross-platform sound playback with zero non-stdlib dependencies.

- Windows   → ``winsound`` (built-in)
- macOS     → ``afplay``  (built-in)
- Linux     → ``paplay`` / ``aplay`` (PulseAudio / ALSA)

Sound files are bundled as package data and resolved relative to the
module so that both editable and regular installs work.
"""

import subprocess
import sys
from pathlib import Path

from claude_notifier import config
from claude_notifier.frozen import get_sounds_dir

_SOUNDS_DIR = get_sounds_dir()

CATEGORY_FILE: dict[str, str] = {
    "success": "complete.wav",
    "warning": "alert.wav",
    "info":    "submit.wav",
}

_FALLBACK_ORDER: dict[str, list[str]] = {
    "success": ["complete.wav", "submit.wav"],
    "warning": ["alert.wav", "submit.wav"],
    "info":    ["submit.wav", "complete.wav"],
}


def _builtin_path(category: str) -> Path | None:
    filename = CATEGORY_FILE.get(category)
    if filename is None:
        return None
    path = _SOUNDS_DIR / filename
    return path if path.exists() else None


def play(category: str) -> None:
    """Play a notification sound for *category*.

    *category* is one of ``"success"``, ``"warning"``, or ``"info"``.
    Uses the user's custom sound if configured, otherwise the matching
    built-in ``.wav`` file.
    """
    cfg = config.load()
    if not cfg.get("sound_enabled", True):
        return

    custom = cfg.get("sound_custom_path")
    path: str | None = None

    if custom and Path(custom).exists():
        path = custom
    else:
        builtin = _builtin_path(category)
        if builtin:
            path = str(builtin)
        else:
            for fallback_cat in _FALLBACK_ORDER.get(category, []):
                fb = _builtin_path(fallback_cat)
                if fb:
                    path = str(fb)
                    break

    if path is None:
        return

    _play_file(path)


def _play_file(path: str) -> None:
    """Platform-dispatch sound playback.  Never raises."""
    try:
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(
                path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        elif sys.platform == "darwin":
            subprocess.run(
                ["afplay", path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            for cmd in (["paplay", path], ["aplay", path]):
                try:
                    subprocess.run(
                        cmd, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, timeout=2)
                    break
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
    except Exception:
        pass  # sound is best-effort

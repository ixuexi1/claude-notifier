"""User-level configuration for claude-notifier.

Stored in ``~/.claude-notifier/config.json``, completely separate from
Claude Code's own ``settings.json`` (which only holds hooks).
"""

import json
import time
from pathlib import Path

from claude_notifier.hooks import ConfigError

CONFIG_DIR = Path.home() / ".claude-notifier"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_CONFIG: dict = {
    "sound_enabled": True,
    "sound_custom_path": None,
    "popup_duration_ms": 5000,
    "events_enabled": [
        "stop",
        "permission",
    ],
}

_CACHE_TTL = 1.0  # seconds — short enough to pick up external changes
_cache: dict | None = None
_cache_time: float = 0.0


def load() -> dict:
    """Read config from disk, filling missing keys with defaults.

    Results are cached for ``_CACHE_TTL`` seconds to avoid repeated
    disk I/O from frequent callers (tray polling, notification popups,
    sound playback).
    """
    global _cache, _cache_time
    now = time.monotonic()
    if _cache is not None and (now - _cache_time) < _CACHE_TTL:
        return dict(_cache)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        _cache = dict(DEFAULT_CONFIG)
        _cache_time = now
        return dict(DEFAULT_CONFIG)
    except json.JSONDecodeError:
        # Back up the damaged file so it isn't silently overwritten
        bad = CONFIG_PATH.with_suffix(CONFIG_PATH.suffix + ".bad")
        try:
            bad.write_bytes(CONFIG_PATH.read_bytes())
        except OSError:
            pass
        raise ConfigError(
            CONFIG_PATH,
            "JSON is corrupted — the file has been backed up to "
            f"{bad.name}.  Please fix or remove it.",
        ) from None
    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    _cache = merged
    _cache_time = now
    return dict(merged)


def save(config: dict) -> None:
    """Write config to disk and update the in-memory cache."""
    global _cache, _cache_time
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    _cache = dict(config)
    _cache_time = time.monotonic()


def get(key: str):
    """Return a single config value (with default)."""
    return load().get(key, DEFAULT_CONFIG.get(key))


def set_(key: str, value) -> None:
    """Set a single config key and persist."""
    cfg = load()
    cfg[key] = value
    save(cfg)

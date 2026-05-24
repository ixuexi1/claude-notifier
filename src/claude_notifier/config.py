"""User-level configuration for claude-notifier.

Stored in ``~/.claude-notifier/config.json``, completely separate from
Claude Code's own ``settings.json`` (which only holds hooks).
"""

import json
from pathlib import Path

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


def load() -> dict:
    """Read config from disk, filling missing keys with defaults."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG)

    merged = dict(DEFAULT_CONFIG)
    merged.update(data)
    return merged


def save(config: dict) -> None:
    """Write config to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get(key: str):
    """Return a single config value (with default)."""
    return load().get(key, DEFAULT_CONFIG.get(key))


def set_(key: str, value) -> None:
    """Set a single config key and persist."""
    cfg = load()
    cfg[key] = value
    save(cfg)

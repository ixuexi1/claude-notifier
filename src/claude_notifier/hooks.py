"""Claude Code settings.json hook management.

Reads / writes / merges hook entries so that ``cn on`` / ``cn off``
do the right thing without touching non-hook settings keys.
"""

import json
import os
import sys
from pathlib import Path

from claude_notifier.events import EVENTS
from claude_notifier.frozen import is_frozen, _exe_path

SETTINGS_PATHS = [
    Path(os.environ.get("APPDATA", "")) / "Claude" / "settings.json",
    Path.home() / ".claude" / "settings.json",
    Path(".claude") / "settings.json",
]


# ── settings.json helpers ──────────────────────────────────────────


def find_settings_path() -> Path | None:
    """Return the first existing Claude Code settings path, or ``None``."""
    for p in SETTINGS_PATHS:
        if p.exists():
            return p
    return None


def read_settings(path: Path) -> dict:
    """Read Claude Code settings JSON.  Returns ``{}`` on any failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def write_settings(path: Path, data: dict) -> None:
    """Atomically write *data* to *path*, creating parent dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Hook entries ───────────────────────────────────────────────────


def build_hook_entry(event_key: str) -> dict:
    """Build a single hook entry for *event_key* (e.g. ``"stop"``).

    When packaged as a frozen exe, the hook command runs the exe directly
    with ``notify <key>`` subcommand.  Otherwise it uses ``pythonw -m
    claude_notifier.notify_popup <key>``.
    """
    event = _resolve_event(event_key)
    if is_frozen():
        hook: dict = {
            "type": "command",
            "command": sys.executable,
            "args": ["notify", event_key],
        }
    else:
        hook = {
            "type": "command",
            "command": _exe_path(),
            "args": ["-m", "claude_notifier.notify_popup", event_key],
        }
    entry: dict = {"hooks": [hook]}
    if event.matcher is not None:
        entry["matcher"] = event.matcher
    return entry


def _resolve_event(event_key: str):
    """Look up an EventConfig by key.  Raises ``KeyError`` on unknown keys."""
    for e in EVENTS:
        if e.key == event_key:
            return e
    raise KeyError(f"Unknown event key: {event_key!r}")


# ── Public API ─────────────────────────────────────────────────────


def install_hooks(
    event_keys: list[str] | None = None,
    settings_path: Path | None = None,
) -> Path:
    """Ensure *only* the hook types in *event_keys* are installed.

    Hooks that were previously installed but are no longer in
    *event_keys* are **removed**.  This is the single source of truth
    for hook installation — both the CLI and the GUI call it.
    """
    if event_keys is None:
        event_keys = [e.key for e in EVENTS if e.hook_name]

    if settings_path is None:
        settings_path = find_settings_path()
    if settings_path is None:
        settings_path = Path.home() / ".claude" / "settings.json"

    settings = read_settings(settings_path)
    hooks = settings.setdefault("hooks", {})

    # Build a clean set of hook names managed by this tool
    all_managed = {e.hook_name for e in EVENTS if e.hook_name}
    wanted = {_resolve_event(k).hook_name for k in event_keys}
    wanted.discard("")                          # pseudo-events like "test"

    # Remove hooks the user no longer wants
    for name in list(hooks):
        if name in all_managed and name not in wanted:
            del hooks[name]

    # Add / refresh wanted hooks
    for key in event_keys:
        event = _resolve_event(key)
        if not event.hook_name:
            continue
        hooks[event.hook_name] = [build_hook_entry(key)]

    if not hooks:
        settings.pop("hooks", None)
    else:
        settings["hooks"] = hooks

    write_settings(settings_path, settings)
    return settings_path


def remove_hooks(settings_path: Path | None = None) -> Path | None:
    """Remove **all** claude-notifier hooks from Claude Code settings."""
    if settings_path is None:
        settings_path = find_settings_path()
    if settings_path is None:
        return None

    settings = read_settings(settings_path)
    managed = {e.hook_name for e in EVENTS if e.hook_name}

    hooks = settings.get("hooks", {})
    for name in list(hooks):
        if name in managed:
            del hooks[name]

    if not hooks:
        settings.pop("hooks", None)
    else:
        settings["hooks"] = hooks

    write_settings(settings_path, settings)
    return settings_path


def hooks_status(settings_path: Path | None = None) -> dict[str, bool]:
    """Return ``{event_key: is_installed}`` for every known event."""
    if settings_path is None:
        settings_path = find_settings_path()
    if settings_path is None:
        return {e.key: False for e in EVENTS}

    settings = read_settings(settings_path)
    hooks = settings.get("hooks", {})
    return {e.key: e.hook_name in hooks for e in EVENTS}

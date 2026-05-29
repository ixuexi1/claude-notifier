"""Claude Code settings.json hook management.

Reads / writes / merges hook entries so that ``cn on`` / ``cn off``
do the right thing without touching non-hook settings keys or
user-defined entries under the same hook names.
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

# Reverse mapping: hook_name → event_key
_HOOK_NAME_TO_KEY = {e.hook_name: e.key for e in EVENTS if e.hook_name}
_KNOWN_EVENT_KEYS = {e.key for e in EVENTS}


class ConfigError(Exception):
    """Raised when a settings file is corrupted and cannot safely be modified."""

    def __init__(self, path: Path, detail: str) -> None:
        self.path = path
        self.detail = detail
        super().__init__(f"{path}: {detail}")


# ── settings.json helpers ──────────────────────────────────────────


def find_settings_path() -> Path | None:
    """Return the first existing Claude Code settings path, or ``None``."""
    for p in SETTINGS_PATHS:
        if p.exists():
            return p
    return None


def read_settings(path: Path) -> dict:
    """Read Claude Code settings JSON.  Aborts on corruption — never
    returns a partial / empty dict that would overwrite user config."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        raise ConfigError(
            path,
            f"JSON is corrupted: {e}\n"
            f"Please fix or remove the file before using claude-notifier.",
        ) from e


def write_settings(path: Path, data: dict) -> None:
    """Atomically write *data* to *path*, creating parent dirs if needed.

    A backup of the previous settings is saved to ``<path>.bak`` before
    the write.  The write itself uses a temp-file + ``os.replace`` so
    the target file is never in a half-written state.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Backup existing settings
    if path.exists():
        bak = path.with_suffix(path.suffix + ".bak")
        try:
            bak.write_bytes(path.read_bytes())
        except OSError:
            pass  # best-effort backup

    # Atomic write via temp file
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        # Clean up temp file on failure
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


# ── Hook entry helpers ─────────────────────────────────────────────


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


def _is_our_entry(entry) -> bool:
    """Return ``True`` if *entry* was created by this tool.

    Identifies entries by precise matching of command-line args against
    known event keys.  Gracefully returns ``False`` for malformed or
    unexpected entry structures.
    """
    if not isinstance(entry, dict):
        return False
    hooks = entry.get("hooks")
    if not isinstance(hooks, list) or not hooks:
        return False
    hook = hooks[0]
    if not isinstance(hook, dict):
        return False
    if hook.get("type") != "command":
        return False
    args = hook.get("args")
    if not isinstance(args, list):
        return False
    command = hook.get("command")
    command_name = Path(command).name.lower() if isinstance(command, str) else ""
    # Frozen: ["notify", "<event_key>"]
    if (
        len(args) == 2
        and args[0] == "notify"
        and args[1] in _KNOWN_EVENT_KEYS
        and command_name in {"claude-notifier.exe", "claude-notifier"}
    ):
        return True
    # Unfrozen: ["-m", "claude_notifier.notify_popup", "<event_key>"]
    if (
        len(args) == 3
        and args[0] == "-m"
        and args[1] == "claude_notifier.notify_popup"
        and args[2] in _KNOWN_EVENT_KEYS
    ):
        return True
    return False


def _resolve_event(event_key: str):
    """Look up an EventConfig by key.  Raises ``KeyError`` on unknown keys."""
    for e in EVENTS:
        if e.key == event_key:
            return e
    raise KeyError(f"Unknown event key: {event_key!r}")


def _get_hooks_dict(settings: dict, path: Path) -> dict:
    """Return the ``hooks`` dict from *settings*, validating its type."""
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        raise ConfigError(
            path,
            "'hooks' key is not a dict — the settings file may be malformed.",
        )
    return hooks


def _get_hook_entries(hooks: dict, name: str, path: Path) -> list:
    """Return the hook entry list for *name*, validating its type."""
    entries = hooks.get(name, [])
    if not isinstance(entries, list):
        raise ConfigError(
            path,
            f"hooks['{name}'] is not a list — the settings file may be malformed.",
        )
    return entries


# ── Public API ─────────────────────────────────────────────────────


def install_hooks(
    event_keys: list[str] | None = None,
    settings_path: Path | None = None,
) -> Path:
    """Ensure *only* the hook types in *event_keys* are installed.

    Only removes entries that were created by this tool — user-defined
    entries under the same hook names are preserved.
    """
    if event_keys is None:
        event_keys = [e.key for e in EVENTS if e.hook_name]

    if settings_path is None:
        settings_path = find_settings_path()
    if settings_path is None:
        settings_path = Path.home() / ".claude" / "settings.json"

    settings = read_settings(settings_path)
    hooks = _get_hooks_dict(settings, settings_path)

    all_managed = {e.hook_name for e in EVENTS if e.hook_name}
    wanted_hook_names = {_resolve_event(k).hook_name for k in event_keys}
    wanted_hook_names.discard("")

    # For each managed hook name: remove our old entries, keep user's
    for name in all_managed:
        if name not in hooks:
            continue
        existing = _get_hook_entries(hooks, name, settings_path)
        user_entries = [e for e in existing if not _is_our_entry(e)]
        if name in wanted_hook_names:
            key = _HOOK_NAME_TO_KEY[name]
            hooks[name] = user_entries + [build_hook_entry(key)]
        elif user_entries:
            hooks[name] = user_entries
        else:
            del hooks[name]

    # Add wanted hooks that don't exist at all yet
    for key in event_keys:
        event = _resolve_event(key)
        if not event.hook_name:
            continue
        if event.hook_name not in hooks:
            hooks[event.hook_name] = [build_hook_entry(key)]

    if not hooks:
        settings.pop("hooks", None)
    else:
        settings["hooks"] = hooks

    write_settings(settings_path, settings)
    return settings_path


def remove_hooks(settings_path: Path | None = None) -> Path | None:
    """Remove **only claude-notifier entries** from Claude Code settings.

    User-defined entries under the same hook names are left untouched.
    """
    if settings_path is None:
        settings_path = find_settings_path()
    if settings_path is None:
        return None

    settings = read_settings(settings_path)
    managed = {e.hook_name for e in EVENTS if e.hook_name}

    hooks = _get_hooks_dict(settings, settings_path)
    for name in list(hooks):
        if name in managed:
            existing = _get_hook_entries(hooks, name, settings_path)
            kept = [e for e in existing if not _is_our_entry(e)]
            if kept:
                hooks[name] = kept
            else:
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
    hooks = _get_hooks_dict(settings, settings_path)
    return {
        e.key: any(
            _is_our_entry(entry)
            for entry in _get_hook_entries(hooks, e.hook_name, settings_path)
            if e.hook_name in hooks
        )
        for e in EVENTS
    }

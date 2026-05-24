"""CLI entry point — ``cn`` command with all subcommands."""

import argparse
import subprocess
import sys
from pathlib import Path

from claude_notifier import __version__
from claude_notifier.frozen import notify_args, config_gui_args, tray_args, popen_spawn


# ── Subcommand handlers ──────────────────────────────────────────

def cmd_on(args):
    """``cn on`` — install hooks listed in user config into settings.json."""
    from claude_notifier import hooks, config
    cfg = config.load()
    enabled = cfg.get("events_enabled", [])
    path = hooks.install_hooks(event_keys=enabled)
    print(f"✓ Hooks installed → {path}")
    if args.daemon:
        popen_spawn(tray_args())


def cmd_off(args):
    """``cn off`` — remove all claude-notifier hooks from settings.json."""
    from claude_notifier import hooks
    path = hooks.remove_hooks()
    if path:
        print(f"✓ Hooks removed from {path}")
    else:
        print("✗ No settings file found — nothing to remove")


def cmd_test(args):
    """``cn test`` — show a test notification with the current config."""
    popen_spawn(notify_args("test", show_ui=True))
    print("✓ Test notification sent")


def cmd_status(args):
    """``cn status`` — display hook installation state and config summary."""
    from claude_notifier import hooks, config

    cfg = config.load()
    status = hooks.hooks_status()

    print(f"Claude Notifier v{__version__}")
    print(f"Config: {config.CONFIG_PATH}")
    print()
    print("Hooks:")
    for key, installed in status.items():
        mark = "✓" if installed else "✗"
        print(f"  {mark} {key}")

    print()
    print("Sound:  ", "ON" if cfg.get("sound_enabled") else "OFF")
    custom = cfg.get("sound_custom_path")
    if custom:
        print(f"Sound file: {custom}")


def cmd_sound(args):
    """``cn sound on|off|path`` — toggle sound alerts or set a custom .wav file."""
    from claude_notifier import config

    if args.action == "on":
        config.set_("sound_enabled", True)
        print("✓ Sound notifications enabled")
    elif args.action == "off":
        config.set_("sound_enabled", False)
        print("✓ Sound notifications disabled")
    elif args.action == "path":
        if not args.path:
            print("✗ Provide a path: cn sound path --path /my/sound.wav")
            return
        p = Path(args.path)
        if not p.exists():
            print(f"✗ File not found: {p}")
            return
        config.set_("sound_custom_path", str(p.resolve()))
        print(f"✓ Custom sound set to: {p.resolve()}")


def cmd_configure(args):
    """``cn configure`` — open the PySide6 GUI configurator window."""
    popen_spawn(config_gui_args())
    print("✓ GUI configurator launched")


# ═══════════════════════════════
# Parser & main
# ═══════════════════════════════

def main():
    # Ensure Unicode output on Windows terminals
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(prog="cn", description="Claude Code desktop notifier")
    parser.add_argument("--version", action="version", version=f"claude-notifier v{__version__}")

    sub = parser.add_subparsers(dest="command")

    p_on = sub.add_parser("on", help="Install notification hooks")
    p_on.add_argument("--daemon", action="store_true", help="Also start system tray icon")

    sub.add_parser("off", help="Remove notification hooks")
    sub.add_parser("test", help="Show a test notification")
    sub.add_parser("status", help="Show hook and config status")

    p_sound = sub.add_parser("sound", help="Configure sound notifications")
    p_sound.add_argument("action", choices=["on", "off", "path"], nargs="?", default="on",
                         help="on | off | path (set custom file)")
    p_sound.add_argument("--path", dest="path", help="Path to custom .wav file (for 'sound path')")

    sub.add_parser("configure", help="Open the GUI configurator")

    args = parser.parse_args()

    handlers = {
        "on":        cmd_on,
        "off":       cmd_off,
        "test":      cmd_test,
        "status":    cmd_status,
        "sound":     cmd_sound,
        "configure": cmd_configure,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return

    handler(args)


if __name__ == "__main__":
    main()

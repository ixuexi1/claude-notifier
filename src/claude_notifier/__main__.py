"""Allow ``python -m claude_notifier`` and serve as PyInstaller entry point.

When running as a frozen exe (``sys.frozen`` is True), the first
positional argument is treated as a subcommand:

    claude-notifier.exe notify <key>       → notification popup
    claude-notifier.exe notify <key> --show-ui  → UI process (re-spawn)
    claude-notifier.exe tray               → system tray daemon
    claude-notifier.exe config-gui         → GUI configurator
    claude-notifier.exe [anything else]    → CLI (cn on/off/test/...)

When unfrozen (pip install), delegates straight to the CLI entry point.
"""

import sys

from claude_notifier.frozen import is_frozen, attach_parent_console


def main() -> None:
    if is_frozen():
        if len(sys.argv) > 1:
            sub = sys.argv[1]

            if sub == "notify":
                sys.argv = [sys.argv[0]] + sys.argv[2:]
                from claude_notifier.notify_popup import main as notify_main
                notify_main()
                return
            if sub == "tray":
                sys.argv = [sys.argv[0]] + sys.argv[2:]
                from claude_notifier.tray import main as tray_main
                tray_main()
                return
            if sub == "config-gui":
                sys.argv = [sys.argv[0]] + sys.argv[2:]
                from claude_notifier.configure_gui import main as config_main
                config_main()
                return
            # CLI subcommands ("status", "on", etc.) — pass through

        else:
            # Double-click — default to system tray
            from claude_notifier.tray import main as tray_main
            tray_main()
            return

    attach_parent_console()
    from claude_notifier.cli import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()

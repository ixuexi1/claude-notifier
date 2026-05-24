# Claude Notifier

**Beautiful frosted-glass desktop notifications for Claude Code.**

When Claude finishes responding or needs your permission, a stunning
acrylic-blur popup appears — DWM frosted glass, gradient glow borders,
smooth fade animations.  A distinctive visual style no other notifier offers.

![platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

## Features

- **Frosted-glass popup** — Windows acrylic blur (DWM), gradient glow
  borders, fade-in/out animations, centred card design
- **6 event types** — `Stop`, `PermissionRequest`, `Notification`,
  `SubagentStop`, `PreToolUse`, `PostToolUse`
- **Sound notifications** — built-in chimes per event category, custom
  `.wav` support, zero extra dependencies
- **Cross-platform** — full glass popup on Windows; system-native
  notifications on macOS / Linux when PySide6 is absent
- **System tray** — right-click to configure, test, or toggle sound
- **GUI configurator** — matching glassmorphism panel with per-event
  toggle switches
- **CLI-first** — `cn on`, `cn off`, `cn test`, `cn status`, `cn sound`,
  `cn configure`
- **Standalone exe** — PyInstaller single-file build, no Python required

## Installation

### pip

```bash
pip install claude-notifier
cn on
```

### From source

```bash
git clone https://github.com/ixuexi1/claude-notifier.git
cd claude-notifier
pip install -e .
cn on
```

### Standalone exe (Windows)

Download `claude-notifier.exe` from
[Releases](https://github.com/ixuexi1/claude-notifier/releases).
Double-click to start the system tray, or run from terminal:

```powershell
claude-notifier.exe on      # install hooks
claude-notifier.exe status  # check status
```

## Quick start

```bash
cn on           # install hooks (default: Stop + PermissionRequest)
cn test         # show a test notification
cn status       # see what's active
cn configure    # open the GUI to pick which events to enable
```

## Commands

| Command | Description |
|---|---|
| `cn on` | Install notification hooks |
| `cn on --daemon` | Install hooks + start system tray |
| `cn off` | Remove all hooks |
| `cn test` | Send a test notification popup |
| `cn status` | Show hook & config status |
| `cn sound on/off` | Toggle sound |
| `cn sound path --path <file>` | Use a custom `.wav` file |
| `cn configure` | Open the GUI configurator |

## Configuration

User preferences live in `~/.claude-notifier/config.json` (separate
from Claude Code's own `settings.json`):

```json
{
  "sound_enabled": true,
  "popup_duration_ms": 5000,
  "sound_custom_path": null,
  "events_enabled": ["stop", "permission"]
}
```

Hooks are written to Claude Code's `settings.json` by `cn on` / `cn off`.

### Changing which events notify

1. **GUI:** `cn configure` → toggle switches → Apply.
2. **CLI:** edit `~/.claude-notifier/config.json` → change
   `events_enabled` → `cn on`.

> Only `stop` (response complete) and `permission` (needs your approval)
> are enabled by default because other events fire very frequently.

## Requirements

- **Python** 3.9+
- **Windows** — PySide6 is auto-installed
- **macOS / Linux** — zero dependencies (system-native notifications)

## How it works

`cn on` writes [Claude Code hooks](https://docs.anthropic.com/en/docs/claude-code/settings#hooks)
into `~/.claude/settings.json`.  Each hook runs the notification popup
with the matching event key.  The hook process reads stdin (JSON context),
spawns the actual popup in a detached subprocess, and returns
immediately so Claude Code isn't blocked.

```
Claude Code  ──hook──>  claude-notifier.exe notify stop
                           │
                           ├─ read JSON from stdin
                           ├─ spawn detached UI process
                           └─ exit immediately
                                │
                                └─ PySide6 frosted-glass popup
                                   + sound
```

## License

MIT — see [LICENSE](LICENSE).

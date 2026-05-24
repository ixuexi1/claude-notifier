# Claude Notifier

Desktop notifications for Claude Code, with frosted-glass popups on Windows.

A small utility that shows a visual popup and plays a sound when Claude Code
fires a hook (e.g. response complete, permission request). Windows gets an
acrylic-blur popup via DWM; other platforms fall back to system-native
notifications.

![platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

## What it does

- **Popup notification** — acrylic blur (DWM) on Windows, native notifications elsewhere
- **6 hook events** — Stop, PermissionRequest, Notification, SubagentStop, PreToolUse, PostToolUse
- **Sound alerts** — built-in chimes per event category, custom .wav support
- **System tray** — right-click menu for quick configure / test / sound toggle
- **GUI configurator** — toggle switches per event type
- **CLI** — `cn on`, `cn off`, `cn test`, `cn status`, `cn sound`, `cn configure`

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

## Usage

```bash
cn on           # install hooks (default: Stop + PermissionRequest)
cn test         # show a test notification
cn status       # see what's active
cn configure    # open GUI to pick which events fire
```

| Command | Description |
|---|---|
| `cn on` | Install notification hooks |
| `cn on --daemon` | Install hooks + start system tray |
| `cn off` | Remove all hooks |
| `cn test` | Send a test notification |
| `cn status` | Show hook & config status |
| `cn sound on/off` | Toggle sound |
| `cn sound path --path <file>` | Use a custom .wav file |
| `cn configure` | Open the GUI configurator |

## Configuration

Preferences are stored in `~/.claude-notifier/config.json`:

```json
{
  "sound_enabled": true,
  "popup_duration_ms": 5000,
  "sound_custom_path": null,
  "events_enabled": ["stop", "permission"]
}
```

Hooks are written to Claude Code's `settings.json` by `cn on` / `cn off`.

> Only `stop` and `permission` are enabled by default — other events fire
> frequently and may be distracting.

## Requirements

- Python 3.9+
- Windows: PySide6 (auto-installed)
- macOS / Linux: no extra dependencies

## How it works

`cn on` writes [Claude Code hooks](https://docs.anthropic.com/en/docs/claude-code/settings#hooks)
into `~/.claude/settings.json`. When a hook fires:

```
Claude Code  ──hook──>  notifier receives JSON on stdin
                           │
                           ├─ spawns detached UI process
                           └─ exits immediately (doesn't block Claude)
                                │
                                └─ popup window + sound
```

## License

MIT — see [LICENSE](LICENSE).

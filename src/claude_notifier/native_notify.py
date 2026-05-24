"""Cross-platform system-native notification fallback.

Used when PySide6 is not available (macOS / Linux, or headless).
"""

import subprocess
import sys


def show_native(title: str, message: str) -> bool:
    """Show a system-native notification.  Returns ``True`` on success."""
    try:
        if sys.platform == "win32":
            return _windows_toast(title, message)
        elif sys.platform == "darwin":
            return _macos_notify(title, message)
        else:
            return _linux_notify(title, message)
    except Exception:
        return False


def _escape_ps(s: str) -> str:
    """Escape a string for safe use inside a PowerShell double-quoted string."""
    return (
        s.replace("`", "``")
         .replace('"', '`"')
         .replace("$", "`$")
         .replace("\x00", "")
    )


def _windows_toast(title: str, message: str) -> bool:
    """Show a Windows toast notification via PowerShell.

    Falls back to a plain ``MessageBox`` if the toast API is unavailable
    (e.g. older Windows versions or headless sessions).
    """
    title_safe = _escape_ps(title)
    msg_safe = _escape_ps(message)

    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager,"
        " Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
        "$tpl = [Windows.UI.Notifications.ToastNotificationManager]"
        "::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
        f'$tpl.GetElementsByTagName("text").Item(0)'
        f'.AppendChild($tpl.CreateTextNode("{title_safe}")) > $null;'
        f'$tpl.GetElementsByTagName("text").Item(1)'
        f'.AppendChild($tpl.CreateTextNode("{msg_safe}")) > $null;'
        "$toast = New-Object Windows.UI.Notifications.ToastNotification($tpl);"
        '[Windows.UI.Notifications.ToastNotificationManager]'
        '::CreateToastNotifier("Claude Notifier").Show($toast);'
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=10,
        )
        return True
    except Exception:
        pass

    # Fallback — plain MessageBox
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)
        return True
    except Exception:
        return False


def _macos_notify(title: str, message: str) -> bool:
    script = (
        f'display notification "{message}" with title "{title}"'
    )
    subprocess.run(
        ["osascript", "-e", script],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=5,
    )
    return True


def _linux_notify(title: str, message: str) -> bool:
    subprocess.run(
        ["notify-send", title, message],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=5,
    )
    return True


def can_show_glass() -> bool:
    """Check whether the full PySide6 glassmorphism popup can be used."""
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
        return True
    except ImportError:
        return False

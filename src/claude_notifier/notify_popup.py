import ctypes
import json
import os
import sys
from ctypes import wintypes

from claude_notifier.events import BY_KEY
from claude_notifier.frozen import notify_args, popen_spawn
from claude_notifier.glass import apply_glass, paint_glass_background
from claude_notifier.native_notify import can_show_glass, show_native

# ── Named mutex for single-popup enforcement (Windows) ─────────────
# A named mutex is atomic, auto-released on process exit, and immune
# to PID reuse — strictly safer than a PID file.
# Local\\ prefix keeps it session-scoped (no admin privilege needed).

_MUTEX_NAME = "Local\\ClaudeNotifierUIPopup"
_ui_mutex_handle: int = 0


def _acquire_ui_mutex() -> bool:
    """Try to acquire the single-popup mutex.  Returns ``True`` if this
    process should show UI; ``False`` if another popup is already running."""
    global _ui_mutex_handle
    if sys.platform != "win32":
        return True
    handle = ctypes.windll.kernel32.CreateMutexW(None, True, _MUTEX_NAME)
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
        return False
    _ui_mutex_handle = handle or 0
    return handle != 0

# Sound is best-effort — the popup must never crash
try:
    from claude_notifier import sound
except ImportError:
    sound = None

# ══════════════════════════════════════════
# PySide6 imports (guarded)
# ══════════════════════════════════════════

if can_show_glass():
    from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Property
    from PySide6.QtGui import QPainter, QColor
    from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
else:
    # Stub — prevents NameError at import time when PySide6 is missing.
    # _run_ui() guards all glass-path code with a runtime can_show_glass()
    # check, so these stubs are never actually called.
    QWidget = object  # type: ignore
    QApplication = None  # type: ignore
    QTimer = None  # type: ignore
    Qt = None  # type: ignore
    QPropertyAnimation = None  # type: ignore
    QEasingCurve = None  # type: ignore
    QPainter = None  # type: ignore
    QColor = None  # type: ignore
    QVBoxLayout = None  # type: ignore
    QLabel = None  # type: ignore

    def Property(_type, fget=None, fset=None):  # type: ignore
        return property(fget, fset)

# ══════════════════════════════════════════
# Low-level keyboard hook (WH_KEYBOARD_LL)
# Captures keystrokes globally without stealing focus.
# Windows-only — on other platforms the popup uses native notifications.
# ══════════════════════════════════════════

if sys.platform == "win32":
    WH_KEYBOARD_LL = 13
    WM_KEYDOWN = 0x0100
    VK_RETURN = 0x0D
    VK_ESCAPE = 0x1B

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
        ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM,
    )

    # Module-level globals because WH_KEYBOARD_LL callback receives raw
    # C function pointers — it cannot capture closures or `self`.
    # _hook_proc must be kept alive for the lifetime of the hook; if it
    # is garbage-collected the callback becomes a dangling pointer.
    _hook_popup: object | None = None
    _hook_proc: object | None = None
    _hook_handle: object | None = None

    def _keyboard_hook(nCode, wParam, lParam):
        if nCode >= 0 and wParam == WM_KEYDOWN:
            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            if kb.vkCode in (VK_RETURN, VK_ESCAPE):
                popup = _hook_popup
                if popup is not None:
                    popup._start_fade_out()
                    # Return 0 so the key still reaches the active
                    # application — the popup dismisses without
                    # stealing the keystroke.
                    return 0
        return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

    _hook_proc = LowLevelKeyboardProc(_keyboard_hook)

    def _install_hook(popup):
        global _hook_popup, _hook_handle
        _hook_popup = popup
        _hook_handle = ctypes.windll.user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, _hook_proc, None, 0,
        )

    def _remove_hook():
        global _hook_popup, _hook_handle
        if _hook_handle:
            ctypes.windll.user32.UnhookWindowsHookEx(_hook_handle)
            _hook_handle = None
        _hook_popup = None

else:
    def _install_hook(popup): pass
    def _remove_hook(): pass


# ══════════════════════════════════════════
# Notification popup — a single centred card window with DWM acrylic blur.
# The card IS the window.  No fullscreen overlay — the desktop shows through.
# ══════════════════════════════════════════

CARD_W, CARD_H = 460, 145


class NotificationPopup(QWidget):
    """A single centred acrylic-blur card that acts as a desktop notification.

    The widget *is* the card — there is no fullscreen overlay.  DWM
    acrylic blur is applied to the window so the desktop content behind
    the card appears softened.

    Dismissed by click, any keypress (via low-level keyboard hook), or
    automatically after the configured duration.
    """

    def __init__(self, icon: str, title: str, message: str):
        super().__init__()
        self.setWindowTitle("Claude Notification")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setFixedSize(CARD_W, CARD_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Centre on the primary screen
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.move((geo.width() - CARD_W) // 2, (geo.height() - CARD_H) // 2)

        font_family = "Microsoft YaHei UI"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 18)
        layout.setSpacing(5)

        self.label_title = QLabel(f"{icon}  {title}")
        self.label_title.setStyleSheet(
            "color: #E4EEF6; font-size: 15px; font-weight: 600;"
            f" font-family: '{font_family}'; background: transparent;"
        )
        layout.addWidget(self.label_title)

        self.label_body = QLabel(message)
        self.label_body.setWordWrap(True)
        self.label_body.setStyleSheet(
            "color: rgba(185, 205, 225, 0.82); font-size: 12px;"
            f" font-family: '{font_family}'; background: transparent;"
        )
        layout.addWidget(self.label_body)

        self.label_hint = QLabel("click  ·  any key  ·  auto-dismiss")
        self.label_hint.setStyleSheet(
            "color: rgba(255, 255, 255, 0.20); font-size: 8px;"
            f" font-family: '{font_family}'; background: transparent;"
        )
        self.label_hint.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.label_hint)

        self._opacity = 0.0

    # ── Qt property for fade animation ──

    def get_opacity(self) -> float:
        return self._opacity

    def set_opacity(self, val: float) -> None:
        self._opacity = val
        self.update()

    opacity = Property(float, get_opacity, set_opacity)

    # ── Painting ──

    def paintEvent(self, event):
        """Draw the acrylic-blur card: tinted translucent background,
        specular highlight across the top, and a gradient glow border."""
        w, h = float(self.width()), float(self.height())
        if w < 8 or h < 8:
            return
        with QPainter(self) as p:
            p.setOpacity(self._opacity)
            paint_glass_background(
                p, w, h, 22.0,
                bg_start=QColor(16, 18, 28, 80),
                bg_end=QColor(6, 8, 18, 105),
                border_start=QColor(120, 165, 210, 50),
                border_mid=QColor(145, 130, 200, 40),
                border_end=QColor(105, 175, 215, 50),
                spec_start=QColor(255, 255, 255, 65),
                spec_end=QColor(255, 255, 255, 0),
                glow_color_start=QColor(110, 160, 210, 10),
                glow_color_mid=QColor(140, 120, 190, 7),
                glow_color_end=QColor(110, 160, 210, 10),
            )

    # ── Interaction ──

    def mousePressEvent(self, event):
        """Any click on the card starts the fade-out sequence."""
        self._start_fade_out()

    def _start_fade_out(self):
        """Begin fade-out animation and unregister the keyboard hook."""
        if hasattr(self, "_fading") and self._fading:
            return
        self._fading = True
        _remove_hook()
        self._anim = QPropertyAnimation(self, b"opacity")
        self._anim.setDuration(160)
        self._anim.setStartValue(self._opacity)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim.finished.connect(self.close)
        self._anim.start()

    def showEvent(self, event):
        """On first paint: install the global keyboard hook, apply DWM
        acrylic blur, start the fade-in animation, and schedule auto-dismiss."""
        super().showEvent(event)
        self._fading = False
        _install_hook(self)
        apply_glass(self)

        # DWM acrylic sometimes needs a second application after the
        # window is fully realised on screen.  Without this the window
        # may show as opaque on first paint.
        QTimer.singleShot(80, lambda: apply_glass(self))

        self._anim = QPropertyAnimation(self, b"opacity")
        self._anim.setDuration(280)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

        try:
            from claude_notifier.config import get
            duration = get("popup_duration_ms") or 5000
        except Exception:
            duration = 5000
        QTimer.singleShot(duration, self._start_fade_out)


# ══════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════

_UI_FLAG = "--show-ui"
# Only the tool_name is passed via env var (not the full hook context)
# to keep the environment block small and avoid leaking hook internals.
_TOOL_ENV = "CLAUDE_NOTIFIER_TOOL"


def _read_hook_stdin() -> dict | None:
    """If stdin carries JSON hook context from Claude Code, parse it."""
    if sys.stdin.isatty():
        return None
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return None


def _read_tool_name() -> str | None:
    """Read the tool name passed from the hook process via env var."""
    raw = os.environ.get(_TOOL_ENV)
    return raw.strip() if raw else None


def _tool_name_from_ctx(ctx: dict | None) -> str | None:
    if not ctx:
        return None
    return ctx.get("tool_name") or ctx.get("tool", {}).get("name")


def _spawn_ui_process(event_key: str, ctx: dict | None) -> None:
    """Start the popup in a detached process so the hook can exit immediately.

    Claude Code hooks block until the hook process exits.  We therefore
    do the minimum work here (parse stdin) and hand off the actual UI
    to a child process that outlives us.  Only the tool_name is passed
    to the child — the full hook context stays in this process.
    """
    env = os.environ.copy()
    tool_name = _tool_name_from_ctx(ctx)
    if tool_name:
        env[_TOOL_ENV] = tool_name
    else:
        env.pop(_TOOL_ENV, None)

    popen_spawn(notify_args(event_key, show_ui=True), env=env)


def _run_ui(event_key: str, tool_name: str | None = None) -> None:
    event = BY_KEY.get(event_key, BY_KEY["stop"])

    icon = event.icon
    title = event.title
    message = event.message
    if tool_name:
        message = f"{message}: {tool_name}"

    if can_show_glass():
        # If another popup is already showing, skip this one.
        # The existing popup will auto-dismiss shortly and the next
        # hook will be picked up.
        if not _acquire_ui_mutex():
            return

        app = QApplication.instance() or QApplication(sys.argv)
        try:
            app.setStyle("Fusion")
        except Exception:
            pass
        popup = NotificationPopup(icon, title, message)
        popup.show()
        try:
            if sound:
                sound.play(event.category)
        except Exception:
            pass

        # Force-deadline: app.exec() should return after the popup
        # dismisses, but a safety timer guarantees the process exits
        # even if the Qt event loop gets stuck (e.g. DWM interaction
        # with frameless translucent windows on some Windows builds).
        try:
            from claude_notifier.config import get  # noqa: E402
            deadline = (get("popup_duration_ms") or 5000) + 15000
        except Exception:
            deadline = 20000  # safe default
        QTimer.singleShot(deadline, app.quit)

        app.exec()
    else:
        show_native(title, message)


def main():
    show_ui = _UI_FLAG in sys.argv
    argv = [a for a in sys.argv if a != _UI_FLAG]
    event_key = argv[1] if len(argv) > 1 else "stop"

    if show_ui:
        _run_ui(event_key, _read_tool_name())
        return

    # Claude Code hooks pipe JSON on stdin and wait for this process to exit.
    # Never block here — spawn UI and return immediately.
    if not sys.stdin.isatty():
        ctx = _read_hook_stdin()
        _spawn_ui_process(event_key, ctx)
        return

    # Manual run / ``cn test`` (inherits a TTY stdin).
    _run_ui(event_key)


if __name__ == "__main__":
    main()

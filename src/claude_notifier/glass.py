"""Shared Windows DWM glass effects and gradient painting utilities.

PySide6 imports are guarded — this module imports cleanly on all
platforms.  Glass effects only activate on Windows; on other
platforms the painting functions are no-ops.
"""

import ctypes
import sys

# ── PySide6 — guarded so the package is importable everywhere ──
_GLASS_AVAILABLE = False
try:
    from PySide6.QtCore import Qt, QRectF                     # noqa: F401
    from PySide6.QtGui import (                               # noqa: F401
        QPainter, QPainterPath, QColor, QPen, QBrush, QLinearGradient,
    )
    from PySide6.QtWidgets import QWidget                     # noqa: F401
    _GLASS_AVAILABLE = True
except ImportError:
    pass

# ══════════════════════════════════════════
# DWM structs & constants (Windows only)
# ══════════════════════════════════════════


class _ACCENTPOLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_uint),
        ("AccentFlags", ctypes.c_uint),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_uint),
    ]


class _WINCOMPATTRDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("pData", ctypes.c_void_p),
        ("dataSize", ctypes.c_ulong),
    ]


_WCA_ACCENT_POLICY = 19
_ACCENT_ENABLE_BLURBEHIND = 3
_ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWCP_ROUND = 2


def _apply_acrylic(hwnd: int) -> bool:
    """Try acrylic blur first; fall back to plain blurbehind on older Windows.

    Acrylic (ACCENT_ENABLE_ACRYLICBLURBEHIND) is available from Win10 1803.
    On earlier builds or if DWM composition is disabled, we fall back to
    the simpler blurbehind effect instead of failing silently.
    """
    user32 = ctypes.windll.user32
    for state in (_ACCENT_ENABLE_ACRYLICBLURBEHIND, _ACCENT_ENABLE_BLURBEHIND):
        try:
            accent = _ACCENTPOLICY()
            accent.AccentState = state
            accent.AccentFlags = 0
            accent.GradientColor = 0x14_00_00_00
            accent.AnimationId = 0
            data = _WINCOMPATTRDATA()
            data.Attribute = _WCA_ACCENT_POLICY
            data.pData = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
            data.dataSize = ctypes.sizeof(accent)
            if user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data)):
                return True
        except Exception:
            continue
    return False


def _apply_round(hwnd: int) -> None:
    try:
        dwmapi = ctypes.windll.dwmapi
        corner = ctypes.c_int(_DWMWCP_ROUND)
        dwmapi.DwmSetWindowAttribute(
            hwnd, _DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(corner), ctypes.sizeof(corner),
        )
    except Exception:
        pass


def apply_glass(widget: "QWidget") -> None:
    """Apply Windows DWM acrylic blur and rounded corners to a widget.

    No-op on non-Windows platforms.
    """
    if not _GLASS_AVAILABLE or sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())
    except Exception:
        return
    if hwnd:
        _apply_acrylic(hwnd)
        _apply_round(hwnd)


# ══════════════════════════════════════════
# Shared gradient painting
# ══════════════════════════════════════════


def paint_glass_background(
    painter: "QPainter",
    w: float,
    h: float,
    r: float,
    bg_start: "QColor",
    bg_end: "QColor",
    border_start: "QColor",
    border_mid: "QColor",
    border_end: "QColor",
    spec_start: "QColor | None" = None,
    spec_end: "QColor | None" = None,
    glow_color_start: "QColor | None" = None,
    glow_color_mid: "QColor | None" = None,
    glow_color_end: "QColor | None" = None,
) -> None:
    """Paint a rounded-rect glass panel with gradient background, specular
    highlight, glow border, and outer glow.

    Shared by the notification popup card and the configuration window.
    Callers customise colour stops only — the structure is shared.

    No-op when PySide6 is unavailable (non-Windows / headless).
    """
    if not _GLASS_AVAILABLE:
        return

    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    path = QPainterPath()
    path.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), r, r)

    bg = QLinearGradient(0.0, 0.0, w, h)
    bg.setColorAt(0.0, bg_start)
    bg.setColorAt(1.0, bg_end)
    painter.fillPath(path, bg)

    if spec_start is not None and spec_end is not None:
        spec = QLinearGradient(0.0, 0.0, 0.0, h * 0.5)
        spec.setColorAt(0.0, spec_start)
        spec.setColorAt(1.0, spec_end)
        painter.fillPath(path, spec)

    border = QLinearGradient(0.0, 0.0, w, h)
    border.setColorAt(0.0, border_start)
    border.setColorAt(0.5, border_mid)
    border.setColorAt(1.0, border_end)
    painter.setPen(QPen(QBrush(border), 1.2))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)

    if glow_color_start and glow_color_mid and glow_color_end:
        glow_path = QPainterPath()
        glow_path.addRoundedRect(QRectF(-2, -2, w + 4, h + 4), r + 2, r + 2)
        glow = QLinearGradient(0.0, 0.0, w, h)
        glow.setColorAt(0.0, glow_color_start)
        glow.setColorAt(0.5, glow_color_mid)
        glow.setColorAt(1.0, glow_color_end)
        painter.setPen(QPen(QBrush(glow), 4.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(glow_path)

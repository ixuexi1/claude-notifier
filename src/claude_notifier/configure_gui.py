"""Claude notification configurator — frosted-glass settings panel.

A PySide6 window with toggle switches for every Claude Code hook event,
sound preferences, and popup duration.  All glass effects are provided
by the shared ``glass`` module.
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QRectF
from PySide6.QtGui import (
    QPainter, QPainterPath, QColor, QPen, QBrush,
    QLinearGradient, QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QScrollArea, QSpinBox,
    QMessageBox,
)

from claude_notifier import config
from claude_notifier.events import EVENTS
from claude_notifier.frozen import notify_args, popen_spawn
from claude_notifier.glass import apply_glass
from claude_notifier.hooks import (
    ConfigError,
    find_settings_path,
    read_settings,
    install_hooks,
    remove_hooks,
    hooks_status,
)


# ══════════════════════════════════════════
# Custom Toggle Switch
# ══════════════════════════════════════════

class ToggleSwitch(QPushButton):
    """Checkable toggle painted as a glowing slider."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(48, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText("")

    def paintEvent(self, event):
        w, h = float(self.width()), float(self.height())
        r = h / 2
        checked = self.isChecked()
        hover = self.underMouse()

        with QPainter(self) as p:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            # Track: rounded pill that the thumb slides along
            track_rect = QRectF(0, 0, w, h)
            if checked:
                track_color = QColor(0, 200, 255, 50)
                track_border = QColor(0, 200, 255, 110)
            elif hover:
                track_color = QColor(120, 140, 170, 80)
                track_border = QColor(120, 140, 170, 120)
            else:
                track_color = QColor(100, 120, 150, 55)
                track_border = QColor(120, 140, 170, 65)

            p.setPen(QPen(track_border, 1.0))
            p.setBrush(track_color)
            p.drawRoundedRect(track_rect, r, r)

            # Thumb: slides left→right on toggle
            thumb_r = r - 3
            thumb_x = w - r - 3 if checked else r + 1
            thumb_rect = QRectF(thumb_x - thumb_r, h / 2 - thumb_r,
                                thumb_r * 2, thumb_r * 2)

            if checked:
                thumb_color = QColor(0, 220, 255)
                # Radial glow behind the thumb when active
                glow = QRadialGradient(thumb_rect.center(), thumb_r * 2.5)
                glow.setColorAt(0.0, QColor(0, 220, 255, 60))
                glow.setColorAt(1.0, QColor(0, 220, 255, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(glow)
                p.drawEllipse(thumb_rect.center(), thumb_r * 2.5, thumb_r * 2.5)
            else:
                thumb_color = QColor(180, 195, 215)

            # Subtle shadow under the thumb for depth
            p.setPen(QPen(QColor(0, 0, 0, 30), 1.0))
            p.setBrush(thumb_color)
            p.drawEllipse(thumb_rect)


# ══════════════════════════════════════════
# Main config window
# ══════════════════════════════════════════

class ConfigWindow(QWidget):
    """Frameless glassmorphism window with scrollable toggle list."""

    def __init__(self):
        super().__init__()
        self._settings_path: Path | None = None
        self._event_toggles: dict[str, ToggleSwitch] = {}

        self.setWindowTitle("Claude Notifier Config")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self.setFixedSize(420, 700)

        self._build_ui()
        self._apply_styles()
        QTimer.singleShot(0, self._scan)

    # ── Glass background ──

    def paintEvent(self, event):
        w, h = float(self.width()), float(self.height())
        if w < 8 or h < 8:
            return
        r = 16.0
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), r, r)
        with QPainter(self) as p:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            g = QLinearGradient(0.0, 0.0, w, h)
            g.setColorAt(0.0, QColor(14, 16, 30, 178))
            g.setColorAt(0.35, QColor(20, 22, 40, 170))
            g.setColorAt(0.65, QColor(12, 15, 34, 175))
            g.setColorAt(1.0, QColor(8, 10, 26, 182))
            p.fillPath(path, g)
            spec = QLinearGradient(0.0, 0.0, 0.0, h * 0.45)
            spec.setColorAt(0.0, QColor(255, 255, 255, 26))
            spec.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.fillPath(path, spec)
            border = QLinearGradient(0.0, 0.0, w, h)
            border.setColorAt(0.0, QColor(0, 180, 240, 65))
            border.setColorAt(0.5, QColor(120, 80, 220, 50))
            border.setColorAt(1.0, QColor(0, 200, 255, 75))
            p.setPen(QPen(QBrush(border), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

    # ── UI construction ──

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 10, 24, 18)
        layout.setSpacing(0)

        # Close button
        close_row = QHBoxLayout()
        close_row.setContentsMargins(0, 0, 0, 0)
        close_row.addStretch(1)
        self.btn_close = QPushButton("×")        # ×
        self.btn_close.setObjectName("closeButton")
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.close)
        close_row.addWidget(self.btn_close)
        layout.addLayout(close_row, 0)

        # Title
        title = QLabel("✦  CLAUDE  NOTIFIER  ✦")   # ✦
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title, 0)
        layout.addSpacing(4)

        subtitle = QLabel("HOOKS   CONFIGURATION   PANEL")
        subtitle.setObjectName("subtitleLabel")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle, 0)
        layout.addSpacing(10)

        # Separator
        sep = QFrame()
        sep.setObjectName("sepLine")
        sep.setFixedHeight(1)
        sep.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(sep, 0)
        layout.addSpacing(8)

        # File path row
        path_row = QHBoxLayout()
        path_row.setContentsMargins(4, 0, 4, 0)
        path_row.setSpacing(10)

        self.path_icon = QLabel("\U0001F4C4")
        self.path_icon.setObjectName("pathIcon")
        self.path_icon.setFixedWidth(20)
        path_row.addWidget(self.path_icon, 0)

        path_text_col = QVBoxLayout()
        path_text_col.setSpacing(1)
        path_label = QLabel("配置文件")     # 配置文件
        path_label.setObjectName("pathLabel")
        path_text_col.addWidget(path_label, 0)
        self.path_value = QLabel("扫描中...")    # 扫描中...
        self.path_value.setObjectName("pathValue")
        self.path_value.setWordWrap(True)
        path_text_col.addWidget(self.path_value, 0)
        path_row.addLayout(path_text_col, 1)

        self.status_dot = QLabel()
        self.status_dot.setObjectName("statusDot")
        self.status_dot.setFixedSize(10, 10)
        path_row.addWidget(self.status_dot, 0)

        layout.addLayout(path_row, 0)
        layout.addSpacing(10)

        # Scrollable toggle area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("scrollArea")
        scroll.setStyleSheet(
            "QScrollArea#scrollArea { background: transparent; border: none; }"
            "QScrollArea#scrollArea QWidget { background: transparent; }"
            "QScrollBar:vertical { background: rgba(255,255,255,0.03);"
            "  width: 6px; border-radius: 3px; }"
            "QScrollBar::handle:vertical { background: rgba(255,255,255,0.12);"
            "  border-radius: 3px; min-height: 20px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical"
            "  { height: 0; }"
        )

        scroll_content = QWidget()
        scroll_content.setObjectName("scrollContent")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(6)

        # Event toggles — every hook-mapped event gets a row
        sec_label = QLabel("通知事件")      # 通知事件
        sec_label.setObjectName("sectionLabel")
        sec_label.setStyleSheet(
            "color: rgba(150, 190, 220, 0.5); font-size: 10px;"
            " letter-spacing: 2px; background: transparent; padding-left: 4px;"
        )
        scroll_layout.addWidget(sec_label)

        for event in EVENTS:
            if not event.hook_name:
                continue
            row, btn = self._make_toggle(event.title, event.message)
            self._event_toggles[event.key] = btn
            scroll_layout.addWidget(row)

        scroll_layout.addSpacing(6)

        # Sound section
        sv_label = QLabel("音效")  # 音效
        sv_label.setStyleSheet(
            "color: rgba(150, 190, 220, 0.5); font-size: 10px;"
            " letter-spacing: 2px; background: transparent; padding-left: 4px;"
        )
        scroll_layout.addWidget(sv_label)

        self.toggle_sound, self.toggle_sound_btn = self._make_toggle(
            "音效提醒",                       # 音效提醒
            "任务完成时播放提示音")  # 任务完成时播放提示音
        scroll_layout.addWidget(self.toggle_sound)

        scroll_layout.addSpacing(6)

        # Duration setting
        dur_label = QLabel("显示设置")
        dur_label.setStyleSheet(
            "color: rgba(150, 190, 220, 0.5); font-size: 10px;"
            " letter-spacing: 2px; background: transparent; padding-left: 4px;"
        )
        scroll_layout.addWidget(dur_label)

        dur_row = QFrame()
        dur_row.setObjectName("toggleRow")
        dur_row.setFixedHeight(56)
        dur_row_layout = QHBoxLayout(dur_row)
        dur_row_layout.setContentsMargins(14, 8, 10, 8)
        dur_row_layout.setSpacing(12)

        dur_text_col = QVBoxLayout()
        dur_text_col.setSpacing(2)
        dur_tl = QLabel("弹窗持续时间")
        dur_tl.setObjectName("toggleTitle")
        dur_text_col.addWidget(dur_tl, 0)
        dur_dl = QLabel("通知弹窗自动消失的时间")
        dur_dl.setObjectName("toggleDesc")
        dur_text_col.addWidget(dur_dl, 0)
        dur_row_layout.addLayout(dur_text_col, 1)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 60)
        self.duration_spin.setValue(5)
        self.duration_spin.setSuffix(" 秒")
        self.duration_spin.setFixedWidth(80)
        self.duration_spin.setCursor(Qt.CursorShape.PointingHandCursor)
        self.duration_spin.setStyleSheet("""
            QSpinBox {
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 6px;
                color: #C8E0F0; font-size: 12px;
                padding: 4px 8px;
            }
            QSpinBox:hover {
                border: 1px solid rgba(0,200,255,0.35);
            }
            QSpinBox:focus {
                border: 1px solid rgba(0,200,255,0.6);
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 16px;
                border: none;
                background: rgba(255,255,255,0.04);
                border-radius: 3px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: rgba(0,200,255,0.15);
            }
            QSpinBox::up-arrow {
                width: 8px; height: 8px;
            }
            QSpinBox::down-arrow {
                width: 8px; height: 8px;
            }
        """)
        dur_row_layout.addWidget(self.duration_spin, 0, Qt.AlignmentFlag.AlignVCenter)
        scroll_layout.addWidget(dur_row)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)
        layout.addSpacing(10)

        # Buttons
        self.btn_apply = QPushButton("应  用  配  置")  # 应  用  配  置
        self.btn_apply.setObjectName("applyButton")
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.clicked.connect(self._apply)
        layout.addWidget(self.btn_apply, 0)
        layout.addSpacing(8)

        aux_row = QHBoxLayout()
        aux_row.setContentsMargins(0, 0, 0, 0)
        aux_row.setSpacing(10)

        self.btn_test = QPushButton("测试通知")  # 测试通知
        self.btn_test.setObjectName("auxButton")
        self.btn_test.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_test.clicked.connect(self._test)
        aux_row.addWidget(self.btn_test, 1)

        self.btn_uninstall = QPushButton("卸载通知")  # 卸载通知
        self.btn_uninstall.setObjectName("dangerButton")
        self.btn_uninstall.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_uninstall.clicked.connect(self._uninstall)
        aux_row.addWidget(self.btn_uninstall, 1)

        layout.addLayout(aux_row, 0)

    def _make_toggle(self, title: str, desc: str) -> tuple[QFrame, ToggleSwitch]:
        row = QFrame()
        row.setObjectName("toggleRow")
        row.setFixedHeight(56)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(14, 8, 10, 8)
        row_layout.setSpacing(12)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        tl = QLabel(title)
        tl.setObjectName("toggleTitle")
        text_col.addWidget(tl, 0)
        dl = QLabel(desc)
        dl.setObjectName("toggleDesc")
        text_col.addWidget(dl, 0)
        row_layout.addLayout(text_col, 1)

        btn = ToggleSwitch()
        row_layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)

        return row, btn

    # ── Stylesheet ──

    def _apply_styles(self):
        self.setStyleSheet("""
            QWidget { font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif; }

            QLabel#titleLabel {
                color: rgba(0, 210, 255, 0.55);
                font-size: 13px; font-weight: 600;
                letter-spacing: 4px; background: transparent;
            }

            QLabel#subtitleLabel {
                color: rgba(0, 200, 255, 0.25);
                font-size: 9px; letter-spacing: 2px; background: transparent;
            }

            QFrame#sepLine {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(0,200,255,0),   stop:0.4 rgba(0,200,255,40),
                    stop:0.5 rgba(100,180,255,60), stop:0.6 rgba(0,200,255,40),
                    stop:1 rgba(0,200,255,0)
                );
                border: none;
            }

            QLabel#pathIcon   { font-size: 16px; background: transparent; }
            QLabel#pathLabel  {
                color: rgba(150,190,220,0.5); font-size: 10px;
                letter-spacing: 2px; text-transform: uppercase;
                background: transparent;
            }
            QLabel#pathValue  {
                color: rgba(180,210,240,0.7); font-size: 11px;
                background: transparent;
            }
            QLabel#statusDot  {
                background: #22C55E; border-radius: 5px;
                min-width: 10px; max-width: 10px;
                min-height: 10px; max-height: 10px;
            }

            QFrame#toggleRow {
                background: rgba(255,255,255,0.025);
                border: 1px solid rgba(255,255,255,0.05);
                border-radius: 10px;
            }

            QLabel#toggleTitle {
                color: #C8E0F0; font-size: 12px; font-weight: 500;
                background: transparent;
            }
            QLabel#toggleDesc {
                color: rgba(160,200,230,0.45); font-size: 9px;
                background: transparent;
            }

            QPushButton#closeButton {
                color: rgba(180,200,230,0.7);
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 14px; font-size: 16px; font-weight: 600;
            }
            QPushButton#closeButton:hover {
                color: #FF6070;
                background: rgba(255,80,100,0.15);
                border: 1px solid rgba(255,100,120,0.35);
            }

            QPushButton#applyButton {
                color: #C8E8FF; background: transparent;
                border: 1.5px solid rgba(0,200,255,0.40);
                border-radius: 10px; padding: 13px 24px;
                font-size: 14px; font-weight: 600;
                letter-spacing: 4px; min-height: 46px;
            }
            QPushButton#applyButton:hover {
                background: rgba(0,200,255,0.08);
                border: 1.5px solid rgba(0,220,255,0.65); color: #FFF;
            }
            QPushButton#applyButton:pressed {
                background: rgba(0,200,255,0.15);
            }
            QPushButton#applyButton[applied="true"] {
                color: #22C55E;
                border: 1.5px solid rgba(34, 197, 94, 0.5);
                background: rgba(34, 197, 94, 0.08);
            }
            QPushButton#applyButton[applied="true"]:hover {
                background: rgba(34, 197, 94, 0.15);
                border: 1.5px solid rgba(34, 197, 94, 0.7); color: #FFF;
            }

            QPushButton#auxButton {
                color: rgba(180,210,240,0.6);
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 8px; padding: 9px 16px;
                font-size: 12px; font-weight: 500;
            }
            QPushButton#auxButton:hover {
                color: #C8E8FF;
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.15);
            }

            QPushButton#dangerButton {
                color: rgba(255,130,130,0.5);
                background: rgba(255,80,80,0.04);
                border: 1px solid rgba(255,80,80,0.12);
                border-radius: 8px; padding: 9px 16px;
                font-size: 12px; font-weight: 500;
            }
            QPushButton#dangerButton:hover {
                color: #FF7080;
                background: rgba(255,80,80,0.1);
                border: 1px solid rgba(255,80,80,0.3);
            }
        """)

    # ── Logic ──

    def _scan(self):
        try:
            self._do_scan()
        except ConfigError as e:
            QMessageBox.critical(
                self, "Settings Error",
                f"Cannot read settings:\n\n{e.detail}\n\n"
                f"File: {e.path}")

    def _do_scan(self):
        p = find_settings_path()
        if p is None:
            p = Path.home() / ".claude" / "settings.json"
            self.path_value.setText(str(p))
            self.status_dot.setStyleSheet(
                "background: #F59E0B; border-radius: 5px;"
                " min-width: 10px; max-width: 10px;"
                " min-height: 10px; max-height: 10px;")
        else:
            self._settings_path = p
            status = hooks_status(p)
            for event in EVENTS:
                if not event.hook_name:
                    continue
                self._event_toggles[event.key].setChecked(
                    status.get(event.key, False))
            self.path_value.setText(str(p))
            self.status_dot.setStyleSheet(
                "background: #22C55E; border-radius: 5px;"
                " min-width: 10px; max-width: 10px;"
                " min-height: 10px; max-height: 10px;")

        self._settings_path = p

        cfg = config.load()
        self.toggle_sound_btn.setChecked(cfg.get("sound_enabled", True))
        duration_ms = cfg.get("popup_duration_ms", 5000)
        self.duration_spin.setValue(max(1, duration_ms // 1000))

    def _apply(self):
        try:
            self._do_apply()
        except ConfigError as e:
            QMessageBox.critical(
                self, "Settings Error",
                f"Cannot apply settings:\n\n{e.detail}\n\n"
                f"File: {e.path}")

    def _do_apply(self):
        # Collect which events the user wants enabled
        wanted = sorted(
            key for key, btn in self._event_toggles.items()
            if btn.isChecked()
        )
        install_hooks(event_keys=wanted, settings_path=self._settings_path)

        # Persist sound / duration preferences
        cfg = config.load()
        cfg["sound_enabled"] = self.toggle_sound_btn.isChecked()
        cfg["popup_duration_ms"] = self.duration_spin.value() * 1000
        config.save(cfg)

        self._flash_button()

    def _flash_button(self):
        self.btn_apply.setText("√  已应用")    # √  已应用
        self.btn_apply.setProperty("applied", True)
        self.btn_apply.style().unpolish(self.btn_apply)
        self.btn_apply.style().polish(self.btn_apply)
        QTimer.singleShot(2000, self._reset_button)

    def _reset_button(self):
        self.btn_apply.setText("应  用  配  置")  # 应  用  配  置
        self.btn_apply.setProperty("applied", False)
        self.btn_apply.style().unpolish(self.btn_apply)
        self.btn_apply.style().polish(self.btn_apply)

    def _test(self):
        popen_spawn(notify_args("test", show_ui=True))

    def _uninstall(self):
        remove_hooks(self._settings_path)
        for btn in self._event_toggles.values():
            btn.setChecked(False)

    # ── Window drag (Windows native) ──

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.position().toPoint())
            if child is None or child is self:
                try:
                    import ctypes
                    hwnd = int(self.winId())
                    ctypes.windll.user32.ReleaseCapture()
                    ctypes.windll.user32.SendMessageW(hwnd, 0xA1, 2, 0)
                except Exception:
                    pass
        return super().mousePressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, lambda: apply_glass(self))
        QTimer.singleShot(80, lambda: apply_glass(self))


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationDisplayName("Claude Notifier Config")
    try:
        app.setStyle("Fusion")
    except Exception:
        pass

    w = ConfigWindow()
    screen = app.primaryScreen()
    if screen:
        geo = screen.geometry()
        w.move(
            (geo.width() - w.width()) // 2,
            int(geo.height() * 0.08),
        )

    w.show()
    # Safety timeout: if the Qt event loop gets stuck (rare DWM
    # interaction issue with frameless acrylic windows), force exit
    # so the process doesn't become a zombie.
    QTimer.singleShot(1_800_000, app.quit)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

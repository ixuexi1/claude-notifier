"""System tray icon for persistent notification management.

Right-click menu: configure, test, toggle sound, quit.
Windows-only (requires PySide6).
"""

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QAction
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from claude_notifier import __version__, config
from claude_notifier.frozen import notify_args, config_gui_args, popen_spawn
from claude_notifier.hooks import hooks_status, find_settings_path, remove_hooks


def _make_icon(colour: QColor) -> QIcon:
    """Generate a simple coloured-circle tray icon."""
    pix = QPixmap(32, 32)
    pix.fill(Qt.GlobalColor.transparent)
    with QPainter(pix) as p:
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(colour))
        p.setPen(QPen(QColor(255, 255, 255, 40), 1.5))
        p.drawEllipse(4, 4, 24, 24)
    return QIcon(pix)


class NotifierTray:
    """System tray icon that reflects hook status in real time."""

    def __init__(self):
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self._icon_active = _make_icon(QColor(0, 200, 255))
        self._icon_inactive = _make_icon(QColor(100, 100, 100))

        self.tray = QSystemTrayIcon()
        self.tray.setToolTip(f"Claude Notifier v{__version__}")

        self._build_menu()
        self._update_icon()
        self.tray.show()

        self._timer = QTimer()
        self._timer.timeout.connect(self._update_icon)
        self._timer.start(30_000)           # refresh every 30 s

    # ── menu ──

    def _build_menu(self) -> None:
        menu = QMenu()

        a_config = QAction("配置面板", menu)       # 配置面板
        a_config.triggered.connect(self._open_config)
        menu.addAction(a_config)
        menu.addSeparator()

        a_test = QAction("测试通知", menu)         # 测试通知
        a_test.triggered.connect(lambda: popen_spawn(notify_args("test", show_ui=True)))
        menu.addAction(a_test)
        menu.addSeparator()

        self.a_sound = QAction("音效提醒", menu)   # 音效提醒
        self.a_sound.setCheckable(True)
        self.a_sound.triggered.connect(self._toggle_sound)
        menu.addAction(self.a_sound)
        menu.addSeparator()

        a_quit = QAction("退出", menu)             # 退出
        a_quit.triggered.connect(self._quit)
        menu.addAction(a_quit)

        self.tray.setContextMenu(menu)

    # ── actions ──

    def _update_icon(self) -> None:
        status = hooks_status(find_settings_path())
        active = any(status.values())
        self.tray.setIcon(self._icon_active if active else self._icon_inactive)

        cfg = config.load()
        self.a_sound.setChecked(cfg.get("sound_enabled", True))

    def _open_config(self) -> None:
        """Launch the GUI configurator in a detached process."""
        popen_spawn(config_gui_args())

    def _toggle_sound(self) -> None:
        config.set_("sound_enabled", self.a_sound.isChecked())

    def _quit(self) -> None:
        remove_hooks()
        self.tray.hide()
        self.app.quit()


def main() -> None:
    _ = NotifierTray()
    sys.exit(QApplication.instance().exec())


if __name__ == "__main__":
    main()

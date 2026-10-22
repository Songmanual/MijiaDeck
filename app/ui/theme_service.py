# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""主题编排：设置解析（跟随系统/浅色/深色）、siui 色组与全局 QSS 刷新。

切换采用「重建式刷新」：全局 QSS 整块替换 + siui 全局色组切换 +
回调各界面重建（卡片网格/托盘行/工作台都是可重建结构）；即用即建
的对话框与 Toast 重开自然获得新主题。
"""

import logging

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QMenu, QWidget

from app.ui import si_theme

logger = logging.getLogger(__name__)

# 设置里的可选值
MODE_SYSTEM = "system"
MODE_LIGHT = "light"
MODE_DARK = "dark"


class _TooltipStyleFilter(QObject):
    """统一禁用菜单、下拉列表和悬停提示的原生硬阴影。"""

    def eventFilter(self, obj, event):
        is_tooltip = obj.metaObject().className() == "QTipLabel"
        is_popup = (isinstance(obj, QWidget) and
                    (isinstance(obj, QMenu) or obj.windowType() == Qt.Popup))
        if is_tooltip or is_popup:
            if event.type() == QEvent.Type.Polish:
                obj.setWindowFlags(obj.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
                if is_tooltip:
                    obj.setAttribute(Qt.WA_TranslucentBackground, True)
                    self._style_tooltip(obj)
            elif event.type() == QEvent.Type.Show:
                if is_tooltip:
                    self._style_tooltip(obj)
                if QGuiApplication.platformName() == "windows":
                    self._remove_windows_shadow(obj)
        return super().eventFilter(obj, event)

    @staticmethod
    def _style_tooltip(tooltip):
        # A tooltip can inherit transparent QLabel rules from its trigger.
        # Give its own window an explicit opaque fill, leaving only the rounded
        # corners transparent instead of exposing the desktop through the body.
        tooltip.setObjectName('appToolTip')
        tooltip.setAttribute(Qt.WA_StyledBackground, True)
        colors = si_theme.SiColors
        style = (f'QLabel#appToolTip {{ background-color: {colors.CARD};'
                 f' color: {colors.TEXT_PRIMARY}; border: 1px solid {colors.LINE};'
                 ' border-radius: 4px; padding: 4px 7px;'
                 ' font-family: "Microsoft YaHei UI", "Segoe UI";'
                 ' font-size: 8pt; font-weight: 400; }')
        if tooltip.styleSheet() != style:
            tooltip.setStyleSheet(style)

    @staticmethod
    def _remove_windows_shadow(popup):
        # 只去掉窗口类的阴影，不禁用 DWM 渲染（会导致圆角提示黑底）。
        import ctypes
        from ctypes import wintypes
        hwnd = wintypes.HWND(int(popup.winId()))
        user32 = ctypes.WinDLL("user32")
        user32.GetClassLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetClassLongW.restype = wintypes.DWORD
        user32.SetClassLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
        user32.SetClassLongW.restype = wintypes.DWORD
        style = user32.GetClassLongW(hwnd, -26)  # GCL_STYLE
        if style & 0x20000:  # CS_DROPSHADOW
            user32.SetClassLongW(hwnd, -26, style & ~0x20000)


def effective_theme(mode: str) -> str:
    """把设置值解析为实际主题；跟随系统时读 Qt 色彩方案，未知回退深色。"""
    if mode in si_theme.PALETTES:
        return mode
    try:
        scheme = QGuiApplication.styleHints().colorScheme()
        from PySide6.QtCore import Qt
        if scheme == Qt.ColorScheme.Light:
            return "light"
    except Exception:
        pass
    return "dark"


def apply_theme(mode: str, accent: str | None = None) -> str:
    """应用主题设置并刷新全局样式，返回实际生效的主题名。"""
    theme = effective_theme(mode)
    if accent is not None:
        si_theme.set_accent(accent)
    si_theme.set_theme(theme)
    si_theme.sync_siui_colors()
    try:
        app = QGuiApplication.instance()
        if app is not None:
            if not hasattr(app, "_mihome_tooltip_filter"):
                app._mihome_tooltip_filter = _TooltipStyleFilter(app)
                app.installEventFilter(app._mihome_tooltip_filter)
            from PySide6.QtGui import QFont
            from PySide6.QtWidgets import QToolTip
            QToolTip.setFont(QFont("Microsoft YaHei UI", 8))
            app.setStyleSheet(si_theme.build_qss())
            for window in app.topLevelWidgets():
                if window.metaObject().className() == 'QTipLabel':
                    _TooltipStyleFilter._style_tooltip(window)
    except Exception:
        logger.exception("应用全局 QSS 失败")
    return theme


class ThemeController(QObject):
    """持有当前设置模式；跟随系统时监听系统配色变化并广播切换。

    系统配色变化与应用主题是两件事：即使设置为固定深/浅色，
    托盘图标仍需跟随系统配色（任务栏底色由系统决定）。
    """

    theme_changed = Signal(str)  # 实际生效的主题名
    system_scheme_changed = Signal(str)  # 系统配色："dark" / "light"

    def __init__(self):
        super().__init__()
        from app.core.settings_store import get_theme_mode
        self._mode = get_theme_mode()
        self._hints = QGuiApplication.styleHints()
        self._hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> str:
        """切换设置模式并立即应用；返回实际生效主题。"""
        self._mode = mode
        theme = apply_theme(mode)
        self.theme_changed.emit(theme)
        return theme

    def _on_system_scheme_changed(self, scheme) -> None:
        from PySide6.QtCore import Qt

        name = "light" if scheme == Qt.ColorScheme.Light else "dark"
        self.system_scheme_changed.emit(name)
        if self._mode != MODE_SYSTEM:
            return
        theme = apply_theme(MODE_SYSTEM)
        self.theme_changed.emit(theme)
        logger.info("系统配色变化，跟随切换为 %s", theme)

    def set_accent(self, accent: str) -> None:
        theme = apply_theme(self._mode, accent)
        self.theme_changed.emit(theme)

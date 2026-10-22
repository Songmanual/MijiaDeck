# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""系统托盘控制器：常驻图标 + 菜单 + 快捷窗口编排。"""

from PySide6.QtCore import QElapsedTimer, QSize, QTimer
from PySide6.QtGui import QAction, QCursor, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from app.core.jobs import JobExecutor
from app.core.models import DeviceInfo
from app.core.service import MijiaService
from app.ui.tray.quick_window import TrayQuickWindow
from app.ui.popup_menu import style_popup_menu


class TrayController:
    """托盘图标控制器：常驻图标 + 快捷窗口 + 右键菜单。"""

    def __init__(self, service: MijiaService, jobs: JobExecutor, main_window):
        self._service = service
        self._jobs = jobs
        self._main = main_window
        self._pending_show = False
        self._last_tray_click = QElapsedTimer()
        # 快捷窗口设为独立顶层窗口，不随主窗口模态对话框被阻塞
        self._create_quick_window()

        # 使用自定义 tray_icon.png 作为托盘图标，提供多尺寸确保清晰
        from app import resource_path
        _icon_path = str(resource_path("app/ui/tray_icon.png"))
        _tray_icon = QIcon(_icon_path)
        _tray_icon.addFile(_icon_path, QSize(16, 16))
        _tray_icon.addFile(_icon_path, QSize(32, 32))
        _tray_icon.addFile(_icon_path, QSize(48, 48))
        self._tray = QSystemTrayIcon(_tray_icon, main_window)
        self._tray.setToolTip("")
        self._tray.activated.connect(self._on_activated)

        menu = QMenu()
        menu.setObjectName("appMenu")
        act_show = QAction("显示主窗口", menu)
        act_show.triggered.connect(self._show_main)
        menu.addAction(act_show)
        act_manage = QAction("编辑卡片", menu)
        act_manage.triggered.connect(self._emit_manage)
        menu.addAction(act_manage)
        act_settings = QAction("设置", menu)
        act_settings.triggered.connect(self._on_settings)
        menu.addAction(act_settings)
        act_reset_position = QAction("托盘悬浮窗位置还原", menu)
        act_reset_position.triggered.connect(self._reset_quick_position)
        menu.addAction(act_reset_position)
        menu.addSeparator()
        act_quit = QAction("退出", menu)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)
        style_popup_menu(menu)
        menu.aboutToShow.connect(lambda: style_popup_menu(menu))
        self._tray.setContextMenu(menu)
        self._hover_elapsed = QElapsedTimer()
        self._hover_fired = False
        self._hover_opened = False
        self._hover_timer = QTimer(main_window)
        self._hover_timer.setInterval(50)
        self._hover_timer.timeout.connect(self._check_tray_hover)
        self._hover_timer.start()

        # 快捷窗口的信号接线统一在 _create_quick_window 内做一次，
        # 此处重复连接曾导致每次触发弹两次对话框

        # 托盘图标常驻，无需可用性检查也尝试显示
        self._tray.show()
        # 两种系统配色都使用灰黑底、白色标志的统一品牌图标。
        from PySide6.QtGui import QGuiApplication
        self.apply_system_icon_theme(
            QGuiApplication.styleHints().colorScheme())

    def apply_system_icon_theme(self, scheme) -> None:
        """刷新系统托盘图标；两种配色使用同一品牌设计。

        scheme 接受 Qt.ColorScheme 或 \"dark\"/\"light\" 字符串。
        """
        from PySide6.QtCore import Qt

        if isinstance(scheme, str):
            is_light = scheme == "light"
        else:
            is_light = scheme == Qt.ColorScheme.Light
        if is_light:
            icon_file = "app/ui/tray_icon_light.png"
        else:
            icon_file = "app/ui/tray_icon.png"
        from app import resource_path
        path = str(resource_path(icon_file))
        icon = QIcon(path)
        icon.addFile(path, QSize(16, 16))
        icon.addFile(path, QSize(32, 32))
        icon.addFile(path, QSize(48, 48))
        self._tray.setIcon(icon)

    def _create_quick_window(self) -> None:
        """创建快捷窗口并接线；主题切换时整窗重建复用。"""
        self._quick = TrayQuickWindow(self._service, self._jobs, None)
        self._quick.manage_requested.connect(self._on_manage)
        self._quick.open_device_requested.connect(self._on_open_device)
        self._quick.speaker_changed.connect(self._main._update_voice_fab)

    def refresh_speaker(self) -> None:
        self._quick._update_audio_bar()

    def refresh_audio_after_command(self, did: str) -> None:
        self._quick._audio_bar.refresh_after_command(did)

    def _emit_manage(self) -> None:
        # 经方法转发而非构造期绑定信号：retheme 重建窗口后菜单仍指向新窗口
        self._quick.manage_requested.emit()

    def _check_tray_hover(self) -> None:
        cursor = QCursor.pos()
        icon_rect = self._tray.geometry()
        over_icon = (self._tray.isVisible() and not icon_rect.isEmpty()
                     and icon_rect.contains(cursor))
        quick = self._quick
        if over_icon:
            quick._leave_timer.stop()
            if not self._hover_elapsed.isValid():
                self._hover_elapsed.start()
            menu = self._tray.contextMenu()
            if (not self._hover_fired and self._hover_elapsed.elapsed() >= 400
                    and not (menu and menu.isVisible())
                    and not QApplication.activeModalWidget()):
                self._hover_fired = True
                if not quick.isVisible() and not quick.is_explicitly_visible():
                    quick.show_near_tray()
                    self._hover_opened = True
        else:
            self._hover_elapsed.invalidate()
            self._hover_fired = False
            if self._hover_opened:
                if not quick.isVisible():
                    self._hover_opened = False
                elif quick.frameGeometry().contains(cursor):
                    quick._leave_timer.stop()
                elif not quick._leave_timer.isActive() and not quick.is_animating():
                    quick._leave_timer.start()

    def _on_activated(self, reason) -> None:
        if reason not in (QSystemTrayIcon.ActivationReason.Trigger,
                          QSystemTrayIcon.ActivationReason.DoubleClick):
            return
        # 第一下立即响应，双击和它随后的松开通知不再切换第二次。
        if (self._last_tray_click.isValid()
                and self._last_tray_click.elapsed() < QApplication.doubleClickInterval()):
            if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
                self._last_tray_click.start()
            return
        self._last_tray_click.start()
        self._hover_fired = True
        self._hover_opened = False
        quick = self._quick
        visible = quick.isVisible() or quick.is_explicitly_visible()
        if quick.is_animating():
            quick.abort_toggle_animation()
        if visible:
            quick.hide_animated()
        else:
            quick.show_near_tray()

    def _show_main(self) -> None:
        self._quick.hide_animated()
        self._main.show()
        self._main.raise_()
        self._main.activateWindow()
        if self._main.isMinimized():
            self._main.showNormal()

    def _quit(self) -> None:
        self._hover_timer.stop()
        self._tray.hide()
        # 标记为强制退出，避免 closeEvent 拦截为隐藏到托盘
        self._main.request_force_quit()
        self._main.close()
        # quitOnLastWindowClosed 为 False 时需显式退出事件循环
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _on_manage(self) -> None:
        self._main.show_tray_manager()

    def _on_settings(self) -> None:
        # Settings belongs to the main window, not the auto-hiding quick popup.
        self._quick.abort_toggle_animation()
        self._quick.hide()
        if self._main.isMinimized():
            self._main.showNormal()
        else:
            self._main.show()
        self._main.raise_()
        self._main.activateWindow()
        # Finish dismissing the tray context menu before entering the modal layer.
        QTimer.singleShot(0, self._main, self._main.show_settings)

    def _reset_quick_position(self) -> None:
        self._quick.reset_position()

    def _on_open_device(self, did: str) -> None:
        # 仅打开设备详情，不呼出主窗口，避免主窗口隐藏时卡死
        self._quick.hide()
        # 直接创建详情对话框，parent 设为 None 使其独立于主窗口显隐
        dev = next((d for d in self._main.devices() if d.did == did), None)
        if dev is None:
            return
        if '.camera.' in dev.model:
            self._main._open_camera_window(dev)
            return
        from app.ui.device_dialog import DeviceDetailDialog
        dlg = DeviceDetailDialog(self._service, self._jobs, dev, None)
        dlg.load()
        dlg.exec()
        dlg.deleteLater()

    def set_devices(self, devices: list[DeviceInfo], known_power: dict[str, bool | None]) -> None:
        self._quick.set_devices(devices, known_power)

    def set_metrics(self, metrics: dict[str, str | None]) -> None:
        self._quick.set_metrics(metrics)
        if self._pending_show:
            # 重建前窗口正显示着：设备填充完毕后再呼出，避免空窗口闪现
            self._pending_show = False
            self._quick.show_near_tray()

    def retheme(self) -> None:
        """主题切换：整个快捷窗口重建。

        快捷窗口的内联样式散布在窗框/音频栏/语音条/设备行/工具条
        多处，逐控件补样式总有遗漏（曾反复出现新旧色混杂残留）；
        整窗重建让全部样式天然取新调色板。设备与开关状态由主窗口
        在本调用之后立刻 set_devices 推送，显示状态在此登记。
        """
        was_visible = self._quick.isVisible() or self._quick.is_explicitly_visible()
        self._quick.abort_toggle_animation()
        self._quick.hide()
        self._quick.deleteLater()
        self._create_quick_window()
        self._pending_show = was_visible

    def hide_quick(self) -> None:
        self._quick.hide()

    def set_tray_visible(self, visible: bool) -> None:
        """按设置开关托盘图标显隐：开启时常驻图标可见，关闭时隐藏。"""
        try:
            self._tray.setVisible(visible)
        except Exception:
            pass

    def is_available(self) -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()


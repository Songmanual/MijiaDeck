# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""Persistent, resizable camera preview windows; no generic device editor."""

import ctypes
import ctypes.wintypes as wintypes
import sys
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QAbstractButton, QVBoxLayout, QWidget
from app import resource_path

from app.core.jobs import JobExecutor
from app.core.models import DeviceInfo
from app.core.service import MijiaService
from app.ui.overlay_dialog import OverlayDialog
from app.ui.window_caption import WindowCaption, RESIZE_MARGIN
from app.ui.si_theme import SiColors


class DeviceDetailDialog(OverlayDialog):
    def __init__(self, service: MijiaService, jobs: JobExecutor,
                 device: DeviceInfo, parent=None):
        from app.core.device_controls import is_camera
        if not is_camera(device):
            raise ValueError('Only cameras use this preview window')
        camera_window = True
        super().__init__(None if camera_window else parent, overlay=not camera_window,
                         modal=Qt.NonModal if camera_window else Qt.WindowModal)
        self.device = device
        self._camera_positioned = False
        self._camera_restore_geometry = None
        if camera_window:
            self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint |
                                Qt.WindowSystemMenuHint | Qt.WindowMinMaxButtonsHint |
                                Qt.WindowCloseButtonHint)
            self.setAttribute(Qt.WA_TranslucentBackground, False)
            self.setMinimumSize(480, 360)
            self.setWindowTitle(f'{device.name} - {device.room_name}' if device.room_name else device.name)
            self.setWindowIcon(QIcon(str(resource_path('app/ui/icon.png'))))

        outer = QVBoxLayout(self._panel)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        self._camera = None
        if camera_window:
            from app.ui.camera_preview import CameraPreviewPanel
            outer.setContentsMargins(1, 1, 1, 1)
            outer.setSpacing(0)
            self._title_bar = WindowCaption(self)
            outer.addWidget(self._title_bar)
            body = QWidget(self._panel)
            body_layout = QVBoxLayout(body)
            body_layout.setContentsMargins(20, 8, 20, 16)
            self._camera = CameraPreviewPanel(service, jobs, device, body)
            body_layout.addWidget(self._camera)
            outer.addWidget(body, stretch=1)
            self._workbench = self._camera
            self._style_camera_frame()

    @property
    def panel(self):
        return self._workbench

    def load(self) -> None:
        if self._camera is not None:
            self._camera.load()

    def done(self, result) -> None:
        if self._camera is not None:
            # Closing an already minimized window may produce no child hide
            # event, so release the session explicitly before the close fade.
            self._camera._poll.stop()
            self._camera.stop()
        super().done(result)

    def retheme(self) -> None:
        """主题切换：面板底色 + 工作台头部按钮与功能区块重建。"""
        super().retheme()
        self._workbench.retheme()
        if self._camera is not None:
            self._style_camera_frame()
            self._title_bar.retheme()

    def _style_camera_frame(self):
        self._panel.setStyleSheet(f'QFrame#overlayPanel {{ background: {SiColors.WINDOW_BG}; border: 1px solid {SiColors.LINE}; border-radius: 0; }}')

    def _enable_camera_shadow(self):
        """Let DWM draw the external shadow without blurring decoded video."""
        if QGuiApplication.platformName() != 'windows':
            return False
        class Margins(ctypes.Structure):
            _fields_ = [(name, ctypes.c_int) for name in ('left', 'right', 'top', 'bottom')]
        try:
            dwm = ctypes.WinDLL('dwmapi')
            dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
            dwm.DwmSetWindowAttribute.restype = ctypes.c_long
            dwm.DwmExtendFrameIntoClientArea.argtypes = [wintypes.HWND, ctypes.POINTER(Margins)]
            dwm.DwmExtendFrameIntoClientArea.restype = ctypes.c_long
            hwnd = wintypes.HWND(int(self.winId()))
            policy = ctypes.c_int(2)  # DWMNCRP_ENABLED, independent of frameless style.
            dwm.DwmSetWindowAttribute(hwnd, 2, ctypes.byref(policy), ctypes.sizeof(policy))
            margins = Margins(1, 1, 1, 1)
            return dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins)) >= 0
        except (OSError, AttributeError):
            return False

    def showMaximized(self):  # noqa: N802
        if getattr(self, '_camera', None) is not None and not self.isMaximized():
            # Windows can change a frameless QDialog's state without enlarging
            # its client area. Set the target bounds before changing state;
            # setting geometry afterwards would clear WindowMaximized again.
            self._camera_restore_geometry = self.normalGeometry() if self.isMinimized() else self.geometry()
            screen = self.screen()
            if screen is not None:
                self.setGeometry(screen.availableGeometry())
        super().showMaximized()

    def showNormal(self):  # noqa: N802
        restore = (getattr(self, '_camera_restore_geometry', None)
                   if self.isMaximized() else None)
        super().showNormal()
        if restore is not None:
            self.setGeometry(restore)
            self._camera_restore_geometry = None

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_overlay()
        if self._camera is not None:
            self._panel.setGeometry(self.rect())
            return
        pw = min(900, max(320, self.width() - 40))
        ph = min(640, self.height() - 40)
        x = (self.width() - pw) // 2
        y = (self.height() - ph) // 2
        self._panel.setGeometry(x, y, pw, ph)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._camera is not None:
            if not self._camera_positioned:
                self._camera_positioned = True
                self._center_on_screen(900, 600, margin=24)
            self._panel.setGeometry(self.rect())
            self._enable_camera_shadow()
            self.raise_()
            return
        if self._fill_parent_window():
            self.raise_()
            self._fade_in()
            return
        # 托盘独立弹出：铺满可用屏幕（遮罩盖住全屏，避免只罩一小块、
        # 周围露出桌面壁纸的突兀观感），面板由 resizeEvent 居中放置
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.availableGeometry())
        self.raise_()
        self._fade_in()

    def _camera_hit_test(self, x, y):
        """Logical coordinates; native window movement/resizing is owned by Windows."""
        if not self.isMaximized():
            left, right = x <= RESIZE_MARGIN, x >= self.width() - RESIZE_MARGIN
            top, bottom = y <= RESIZE_MARGIN, y >= self.height() - RESIZE_MARGIN
            if top and left:
                return 13
            if top and right:
                return 14
            if bottom and left:
                return 16
            if bottom and right:
                return 17
            if left:
                return 10
            if right:
                return 11
            if top:
                return 12
            if bottom:
                return 15
        header_bottom = self._camera._canvas.mapTo(self, QPoint(0, 0)).y()
        if y < header_bottom and not isinstance(self.childAt(int(x), int(y)), QAbstractButton):
            return 2  # HTCAPTION: drag title / double-click maximize.
        return 1

    def nativeEvent(self, eventType, message):  # noqa: N802
        if sys.platform == 'win32' and getattr(self, '_camera', None) is not None and eventType == 'windows_generic_MSG':
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x031e:  # WM_DWMCOMPOSITIONCHANGED
                self._enable_camera_shadow()
            if msg.message == 0x0084:  # WM_NCHITTEST
                point = wintypes.POINT(ctypes.c_short(msg.lParam & 0xffff).value,
                                       ctypes.c_short((msg.lParam >> 16) & 0xffff).value)
                ctypes.windll.user32.ScreenToClient(int(self.winId()), ctypes.byref(point))
                dpr = self.devicePixelRatioF() or 1
                return True, self._camera_hit_test(point.x / dpr, point.y / dpr)
            if msg.message == 0x00a3 and msg.wParam == 2:
                self.showNormal() if self.isMaximized() else self.showMaximized()
                return True, 0
        return False, 0



# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""扫码登录对话框。

上游的登录二维码只往终端打印 ASCII 字符，图形界面无法直接复用，
因此这里用适配层拆出的两步流程：先取 loginUrl 渲染成图片展示，
再在后台长轮询等待扫码结果。
"""

import io

import qrcode
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.ui.si_theme import SiColors


class LoginDialog(QDialog):
    """模态登录窗：三态切换 获取中 -> 待扫码 -> 失败可重试。

    凭据仍有效时上游直接返回免登录结论，本窗口立即关闭。
    """

    def __init__(self, service, jobs, parent=None):
        super().__init__(parent)
        self._service = service
        self._jobs = jobs
        # 登录数据要在 begin 与 wait 两次调用间传递
        self._login_data = None
        # 登录轮次：串行队列无法取消任务，「重新获取」后旧长轮询
        # （最长阻塞两分钟）完成时必须被丢弃，否则会用过期凭据误关窗口
        self._generation = 0

        self.setWindowTitle("登录米家账号")
        # Ask Qt to register its icon-free native window class. Merely clearing
        # WM_SETICON leaves Windows falling back to the class's default icon.
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint |
                            Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setModal(True)
        self.setMinimumSize(320, 380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 30, 24, 24)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        self._qr_label = QLabel(alignment=Qt.AlignCenter)
        self._qr_label.setMinimumSize(260, 260)
        layout.addWidget(self._qr_label)

        self._status_label = QLabel(alignment=Qt.AlignCenter)
        layout.addWidget(self._status_label)

        self._retry_btn = QPushButton("重新获取二维码")
        self._retry_btn.clicked.connect(self._begin_login)
        self._retry_btn.hide()
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self._retry_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

    def showEvent(self, event):
        super().showEvent(event)
        if QGuiApplication.platformName() == 'windows':
            self._clear_inherited_icon()

    def _clear_inherited_icon(self):
        # The native class is icon-free; clear the parent icon Qt still assigns
        # to owned dialogs. The title, border and close button remain native.
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL('user32')
        hwnd = wintypes.HWND(int(self.winId()))
        user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.SendMessageW.restype = ctypes.c_ssize_t
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.SendMessageW(hwnd, 0x0080, 0, 0)
        user32.SendMessageW(hwnd, 0x0080, 1, 0)
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0037)

    def exec_and_wait(self) -> int:
        """启动登录流程并阻塞至完成或用户关闭窗口。"""
        self._begin_login()
        return self.exec()

    # ---------- 流程编排 ----------

    def _begin_login(self) -> None:
        self._generation += 1
        generation = self._generation
        self._retry_btn.hide()
        self._set_status("正在获取登录二维码…", error=False)
        self._qr_label.clear()
        self._jobs.submit(
            self._service.qr_login_begin,
            on_success=lambda data: self._on_qr_data(data, generation),
            on_error=lambda e: self._on_failed(e, generation),
        )

    def _on_qr_data(self, data: dict | None, generation: int) -> None:
        if generation != self._generation or not self.isVisible():
            return
        if data is None:
            # 本地凭据自动刷新成功，无需扫码
            self.accept()
            return
        self._login_data = data
        self._show_qr_image(data["loginUrl"])
        self._set_status("请使用米家 APP 扫描二维码", error=False)
        self._jobs.submit(
            lambda: self._service.qr_login_wait(self._login_data),
            on_success=lambda _: self._on_login_success(generation),
            on_error=lambda e: self._on_failed(e, generation),
        )

    def _on_login_success(self, generation: int) -> None:
        if generation != self._generation or not self.isVisible():
            return
        self.accept()

    def _on_failed(self, error: Exception, generation: int) -> None:
        if generation != self._generation or not self.isVisible():
            return
        self._set_status(str(error), error=True)
        self._retry_btn.show()

    # ---------- 绘制 ----------

    def _show_qr_image(self, login_url: str) -> None:
        qr = qrcode.QRCode(border=2, box_size=6)
        qr.add_data(login_url)
        image = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue())
        self._qr_label.setPixmap(
            pixmap.scaled(self._qr_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def _set_status(self, text: str, error: bool) -> None:
        self._status_label.setText(text)
        color = "#c0392b" if error else f"{SiColors.TEXT_SECONDARY}"
        self._status_label.setStyleSheet(f"color: {color};")



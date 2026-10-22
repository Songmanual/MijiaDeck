# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""版本检查的界面流程：发起检查 → 有新版本弹对话框，否则按场景反馈。

自动（启动时）与手动（关于页/设置入口）共用这一条链路，仅反馈策略
不同：自动检查在「无新版本」与「网络失败」时完全静默，不打扰
用户；手动检查两种情况都要给出明确回显，否则用户无法区分
「没新版」与「断网了」。
"""

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from app.core.update_checker import UpdateChecker, is_newer
from app.ui.toast import Toast


def check_update(parent, manual: bool) -> None:
    """发起一次检查；parent 用于挂 checker 与弹对话框。"""
    checker = UpdateChecker(parent)

    def _finish(info, error) -> None:
        checker.deleteLater()
        if error is not None:
            if manual:
                Toast.info(parent, f"检查更新失败：{error}", 4000)
            return
        from app import __version__
        if info is None or not is_newer(info.tag, __version__):
            if hasattr(parent, '_on_update_available'):
                parent._on_update_available(None)
            if manual:
                Toast.info(parent, "当前已是最新版本", 2500)
            return
        if hasattr(parent, '_on_update_available'):
            parent._on_update_available(info)
            if not manual:
                return
        prompt_new_version(parent, info)

    checker.check_finished.connect(_finish)
    checker.check()


def prompt_new_version(parent, info) -> None:
    """弹「发现新版本」对话框：前往下载 / 暂不更新。"""
    from app import __version__

    # 主窗体可能已隐藏到托盘（启动静默场景），给隐藏父级弹
    # 模态框位置会落在不可见区域，此时改挂屏幕中央
    host = None if (parent is not None and parent.isHidden()) else parent
    box = QMessageBox(host)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle("发现新版本")
    box.setText(f"发现新版本 {info.tag}（当前 v{__version__}）")
    if info.name and info.name != info.tag:
        box.setInformativeText(info.name)
    download = box.addButton("前往下载", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("暂不更新", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(download)
    box.exec()
    if box.clickedButton() is download:
        QDesktopServices.openUrl(QUrl(info.url))

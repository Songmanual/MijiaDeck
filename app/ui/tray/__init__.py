# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""系统托盘子系统：控制器、快捷窗口、音频栏与管理对话框。"""

from app.ui.tray.controller import TrayController
from app.ui.tray.manager_dialog import TrayManagerDialog

__all__ = ["TrayController", "TrayManagerDialog"]

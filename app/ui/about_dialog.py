# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""关于对话框：项目信息、功能简介与上游依赖致谢。"""

from PySide6.QtCore import QSize, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import QLabel, QPushButton, QSizePolicy, QVBoxLayout

import qtawesome as qta

from app import APP_NAME, UPDATE_REPOSITORY, __version__
from app.ui.overlay_dialog import OverlayDialog
from app.ui.si_theme import SiColors
from app.ui.toast import Toast

GITHUB_URL = f"https://github.com/{UPDATE_REPOSITORY}" if UPDATE_REPOSITORY else ""
UPSTREAM_URL = "https://github.com/huanyuejue/MiHome-Windows"
MIJIA_API_URL = "https://github.com/Do1e/mijia-api"


class AboutDialog(OverlayDialog):
    """关于：遮罩 + 居中面板，与设置页同款观感。

    api_version 是上游 mijiaAPI 的实际安装版本（由适配层实时提供，
    见 MijiaService.api_version），与本地版本号同行展示便于排查兼容性。
    """

    def __init__(self, parent=None, api_version: str = ""):
        super().__init__(parent)
        self.setWindowTitle("关于")

        panel = self._panel
        panel.setFixedSize(440, 410)

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(14)

        # ---- 标题 + 版本 ----
        self._title_label = QLabel(APP_NAME)
        self._title_label.setFont(QFont("Microsoft YaHei UI", 14, QFont.Weight.DemiBold))
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._title_label)

        version_text = f"版本 v{__version__}"
        if api_version:
            version_text += f" | mijiaAPI {api_version}"
        self._version_label = QLabel(version_text)
        self._version_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._version_label)

        # ---- 功能简介 ----
        self._intro_label = QLabel(
            "米家设备的 Windows 桌面控制端：扫码登录米家账号后，"
            "在本地窗口中查看与控制家里全部米家设备——设备卡片快速开关、"
            "详情工作台、系统托盘快捷控制、小爱语音指令与深浅色主题。")
        self._intro_label.setWordWrap(True)
        lay.addWidget(self._intro_label)
        lay.addSpacing(16)

        # ---- 上游依赖：mijiaAPI ----
        self._dep_title_label = QLabel("开源致谢")
        dep_title_font = QFont("Microsoft YaHei UI", 10, QFont.Weight.DemiBold)
        self._dep_title_label.setFont(dep_title_font)
        self._dep_title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._dep_title_label)

        self._dep_label = QLabel(
            f'本项目基于 <a href="{UPSTREAM_URL}">MiHome-Windows</a> 改进，'
            f'通过 <a href="{MIJIA_API_URL}">mijiaAPI</a> 连接米家设备。'
            "米家 API 的 Python 封装。扫码登录、设备列表、属性读写与动作执行"
            "均由 mijiaAPI 完成，本项目仅负责界面与交互。")
        self._dep_label.setWordWrap(True)
        self._dep_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._dep_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction)
        self._dep_label.setOpenExternalLinks(True)
        lay.addWidget(self._dep_label)

        lay.addStretch(1)

        # ---- 底部：检测更新 + GitHub 入口（上下堆叠）----
        btn_col = QVBoxLayout()
        btn_col.setSpacing(10)
        self._update_btn = QPushButton(" 检测更新")
        self._update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_btn.setIcon(qta.icon("mdi.update", color=SiColors.TEXT_PRIMARY))
        self._update_btn.setIconSize(QSize(20, 20))
        self._update_btn.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self._update_btn.clicked.connect(self._check_update)
        self._checking = False
        btn_col.addWidget(self._update_btn, alignment=Qt.AlignHCenter)

        self._github_btn = QPushButton(" GitHub 仓库")
        self._github_btn.setEnabled(bool(GITHUB_URL))
        if not GITHUB_URL:
            self._github_btn.setText(" GitHub 仓库（待发布）")
        self._github_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._github_btn.setIcon(qta.icon("mdi.github", color=SiColors.TEXT_PRIMARY))
        self._github_btn.setIconSize(QSize(20, 20))
        self._github_btn.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self._github_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(GITHUB_URL)))
        btn_col.addWidget(self._github_btn, alignment=Qt.AlignHCenter)
        lay.addLayout(btn_col)

        self._apply_styles()

    def _check_update(self) -> None:
        # 请求在途时忽略重复点击，避免叠发多个网络请求
        if self._checking:
            return
        self._checking = True
        self._update_btn.setEnabled(False)
        self._update_btn.setText(" 检查中…")
        icon_color = SiColors.TEXT_SECONDARY

        def _restore() -> None:
            self._checking = False
            if self._update_btn is not None:
                self._update_btn.setEnabled(True)
                self._update_btn.setText(" 检测更新")
                self._update_btn.setIcon(
                    qta.icon("mdi.update", color=SiColors.TEXT_PRIMARY))

        def _finish(info, error) -> None:
            checker.deleteLater()
            _restore()
            if error is not None:
                Toast.info(self, f"检查更新失败：{error}", 4000)
                return
            from app import __version__
            from app.core.update_checker import is_newer
            if info is None or not is_newer(info.tag, __version__):
                Toast.info(self, "当前已是最新版本", 2500)
                return
            from app.ui.update_flow import prompt_new_version
            prompt_new_version(self, info)

        from app.core.update_checker import UpdateChecker
        checker = UpdateChecker(self)
        checker.check_finished.connect(_finish)
        # 检查中文案用次要色弱化，配合禁用态传达「进行中」
        self._update_btn.setIcon(qta.icon("mdi.update", color=icon_color))
        checker.check()

    def _apply_styles(self) -> None:
        """主题相关内联样式：构造与 retheme 共用。"""
        self._title_label.setStyleSheet(
            f"color: {SiColors.TEXT_PRIMARY}; background: transparent;")
        self._version_label.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 9pt;")
        self._intro_label.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 10pt;")
        self._dep_title_label.setStyleSheet(
            f"color: {SiColors.TEXT_PRIMARY}; background: transparent;")
        self._dep_label.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 10pt;"
            f" a {{ color: {SiColors.THEME}; }}")
        btn_style = (
            f"QPushButton {{ background: {SiColors.SURFACE}; border: none;"
            f" border-radius: 8px; padding: 8px 18px; color: {SiColors.TEXT_PRIMARY}; }}"
            f"QPushButton:hover {{ background: {SiColors.BTN_HOVER}; }}"
            f"QPushButton:disabled {{ color: {SiColors.TEXT_FAINT}; }}")
        self._update_btn.setStyleSheet(btn_style)
        self._update_btn.setIcon(
            qta.icon("mdi.update", color=SiColors.TEXT_PRIMARY))
        self._github_btn.setStyleSheet(btn_style)
        self._github_btn.setIcon(qta.icon("mdi.github", color=SiColors.TEXT_PRIMARY))

    def retheme(self) -> None:
        """主题切换：重设面板底色与全部内联样式。"""
        super().retheme()
        self._apply_styles()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_overlay()
        # 面板居中放置
        x = (self.width() - self._panel.width()) // 2
        y = (self.height() - self._panel.height()) // 2
        self._panel.move(x, y)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._fill_parent_window():
            self.raise_()
            self._fade_in()
            return
        # 无可见父窗口（托盘路径）：铺满可用屏幕
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.availableGeometry())
        self.raise_()
        self._fade_in()

# SPDX-License-Identifier: GPL-3.0-or-later
"""Version, transient loading status and account actions in one fixed footer."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QProgressBar
from app import __version__
from app.ui.si_theme import SiColors


class FooterBar(QFrame):
    check_requested = Signal()
    update_requested = Signal()
    account_requested = Signal()

    def __init__(self, height, parent=None):
        super().__init__(parent)
        self.setObjectName('reservedFooter')
        self.setFixedHeight(height)
        self._release = None
        self._status_text = ''
        self._progress_value = None
        self._progress_text = ''
        layout = QHBoxLayout(self)
        # Compensate the font's lower ink centre while keeping the controls
        # vertically centred (about 2 physical pixels at 200% scaling).
        layout.setContentsMargins(18, 0, 18, 2)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignVCenter)
        self.version = QPushButton(f'当前版本号:v{__version__}')
        self.version.setAccessibleName('检查新版本')
        self.version.clicked.connect(self.check_requested)
        layout.addWidget(self.version)
        self.update_button = QPushButton()
        self.update_button.clicked.connect(self.update_requested)
        layout.addWidget(self.update_button)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedSize(112, 4)
        self.progress.setAccessibleName('设备加载进度')
        layout.addWidget(self.progress)
        self.status = QLabel()
        layout.addWidget(self.status)
        layout.addStretch(1)
        self.account = QPushButton('退出登录')
        self.account.clicked.connect(self.account_requested)
        layout.addWidget(self.account)
        for button in (self.version, self.update_button, self.account):
            button.setCursor(Qt.PointingHandCursor)
        self.set_status('')
        self.retheme()

    def set_status(self, text):
        self._status_text = text
        self._sync_status()

    def set_progress(self, value, text=''):
        self._progress_value = value
        self._progress_text = text
        if value is not None:
            self.progress.setValue(value)
            self.progress.setAccessibleDescription(text)
        self._sync_status()

    def _sync_status(self):
        loading = self._progress_value is not None
        text = self._progress_text if loading else self._status_text
        self.status.setText(text)
        self.status.setVisible(bool(text))
        self.progress.setVisible(loading)
        self.version.setVisible(not text and not loading)
        self.update_button.setVisible(not text and not loading and self._release is not None)

    def set_release(self, info):
        self._release = info
        self.update_button.setText(f'发现新版 {info.tag}' if info else '')
        self.set_status(self._status_text)

    def set_logged_in(self, logged_in):
        self.account.setText('退出登录' if logged_in else '登录账号')

    def retheme(self):
        base = QColor(SiColors.WINDOW_BG)
        background = '#f0f2f5' if base.lightness() >= 128 else base.darker(115).name()
        self.setStyleSheet(
            f'QFrame#reservedFooter {{ background: {background}; border: none;'
            f' border-top: 1px solid {SiColors.LINE}; border-radius: 0; }}'
            f'QPushButton {{ color: {SiColors.TEXT_SECONDARY}; background: transparent;'
            f' border: none; padding: 2px 0; font-size: 8pt; }}'
            f'QPushButton:hover {{ color: {SiColors.THEME}; }}'
            f'QLabel {{ color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 8pt; }}'
            f'QProgressBar {{ background: {SiColors.LINE}; border: none; border-radius: 2px; }}'
            f'QProgressBar::chunk {{ background: {SiColors.THEME}; border-radius: 2px; }}')
        self.update_button.setStyleSheet(f'color: {SiColors.THEME}; font-size: 8pt;')

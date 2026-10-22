# SPDX-License-Identifier: GPL-3.0-or-later
"""Version, transient loading status and account actions in one fixed footer."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
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
        layout = QHBoxLayout(self)
        # Compensate the font's lower ink centre while keeping the controls
        # vertically centred (about 2 physical pixels at 200% scaling).
        layout.setContentsMargins(18, 0, 18, 2)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignVCenter)
        self.version = QPushButton(f'当前版本号:v{__version__}')
        self.version.setToolTip('检查新版本')
        self.version.clicked.connect(self.check_requested)
        layout.addWidget(self.version)
        self.update_button = QPushButton()
        self.update_button.clicked.connect(self.update_requested)
        layout.addWidget(self.update_button)
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
        self.status.setText(text)
        self.status.setVisible(bool(text))
        self.version.setVisible(not text)
        self.update_button.setVisible(not text and self._release is not None)

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
            f'QLabel {{ color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 8pt; }}')
        self.update_button.setStyleSheet(f'color: {SiColors.THEME}; font-size: 8pt;')

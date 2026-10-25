# SPDX-License-Identifier: GPL-3.0-or-later
"""Branded loading view, driven by actual device-loading stages."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget
from app import APP_NAME, resource_path
from app.ui.si_theme import SiColors


class LoadingPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('loadingPage')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(0)
        layout.addStretch(1)
        logo = QLabel()
        logo.setPixmap(QIcon(str(resource_path('app/ui/icon.png'))).pixmap(60, 60))
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)
        layout.addSpacing(20)
        title = QLabel(APP_NAME)
        title.setObjectName('loadingTitle')
        title.setFont(QFont('Microsoft YaHei UI', 24, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(8)
        subtitle = QLabel('米家设备桌面控制')
        subtitle.setObjectName('loadingSubtitle')
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setFont(QFont('Microsoft YaHei UI', 10))
        layout.addWidget(subtitle)
        layout.addSpacing(30)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedSize(280, 5)
        self.progress.setAccessibleName('设备加载进度')
        layout.addWidget(self.progress, alignment=Qt.AlignHCenter)
        layout.addSpacing(15)
        self.status = QLabel('正在准备设备…')
        self.status.setObjectName('loadingStatus')
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setFont(QFont('Microsoft YaHei UI', 9))
        layout.addWidget(self.status)
        layout.addStretch(1)
        self.retheme()

    def set_progress(self, value, text):
        self.progress.setValue(value)
        self.status.setText(text)
        self.progress.setAccessibleDescription(text)

    def retheme(self):
        self.setStyleSheet(
            f'QWidget#loadingPage {{ background: {SiColors.WINDOW_BG}; }}'
            f'QLabel {{ color: {SiColors.TEXT_SECONDARY}; background: transparent; }}'
            f'QLabel#loadingTitle {{ color: {SiColors.TEXT_PRIMARY}; font-size: 24pt; font-weight: 700; }}'
            'QLabel#loadingSubtitle { font-size: 10pt; }'
            'QLabel#loadingStatus { font-size: 9pt; }'
            f'QProgressBar {{ background: {SiColors.LINE}; border: none; border-radius: 2px; }}'
            f'QProgressBar::chunk {{ background: {SiColors.THEME}; border-radius: 2px; }}')

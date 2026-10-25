# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared square caption controls; visual parameters reference GearPower ui.xaml.

https://github.com/XAVIER0229/GearPower/blob/main/ui.xaml
"""
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QIcon, QFont
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QLabel
from app.ui.si_theme import SiColors, is_dark

CAPTION_HEIGHT = 34
BRAND_CAPTION_HEIGHT = 48
CAPTION_BUTTON_WIDTH = 46
RESIZE_MARGIN = 6


class CaptionButton(QPushButton):
    """Draw the three simple caption marks without private-use font glyphs."""
    def __init__(self, glyph, parent, window, close=False):
        super().__init__(glyph, parent)
        self._window = window
        self._close = close
        self._colors = ('#53657A', '#E9EFF6', '#DDE7F2', '#17202B')

    def paintEvent(self, event):
        ink, hover, pressed, active = self._colors
        painter = QPainter(self)
        if self.isDown() or self.underMouse():
            background = ('#F1707A' if self.isDown() else '#E81123') if self._close else (pressed if self.isDown() else hover)
            painter.fillRect(self.rect(), QColor(background))
            ink = '#FFFFFF' if self._close else active
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(ink), 1))
        x, y = self.width() / 2, self.height() / 2
        from PySide6.QtCore import QLineF, QRectF
        if self._close:
            painter.drawLine(QLineF(x-5, y-5, x+5, y+5))
            painter.drawLine(QLineF(x+5, y-5, x-5, y+5))
        elif self.text() == '\ue921':
            painter.drawLine(QLineF(x-5, y, x+5, y))
        elif self._window.isMaximized():
            painter.drawLine(QLineF(x-2, y-5, x+5, y-5))
            painter.drawLine(QLineF(x+5, y-5, x+5, y+2))
            painter.drawRect(QRectF(x-5, y-2, 7, 7))
        else:
            painter.drawRect(QRectF(x-4.5, y-4.5, 9, 9))
        painter.end()


class WindowCaption(QFrame):
    def __init__(self, window, show_tooltips=True, brand=False):
        super().__init__(window)
        self._window = window
        self._show_tooltips = show_tooltips
        self.setObjectName('titleBar')
        self.setFixedHeight(BRAND_CAPTION_HEIGHT if brand else CAPTION_HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._brand_name = None
        if brand:
            from app import APP_NAME, resource_path
            layout.addSpacing(22)
            logo = QLabel()
            logo.setStyleSheet('background: transparent;')
            logo.setPixmap(QIcon(str(resource_path('app/ui/icon.png'))).pixmap(20, 20))
            logo.setAttribute(Qt.WA_TransparentForMouseEvents)
            layout.addWidget(logo)
            layout.addSpacing(10)
            self._brand_name = QLabel(APP_NAME)
            self._brand_name.setFont(QFont('Microsoft YaHei UI', 10, QFont.DemiBold))
            self._brand_name.setAttribute(Qt.WA_TransparentForMouseEvents)
            layout.addWidget(self._brand_name)
        layout.addStretch(1)
        self.minimize_button = self._button('\ue921', '最小化', window.showMinimized)
        self.maximize_button = self._button('\ue922', '最大化', self.toggle_maximized)
        self.close_button = self._button('\ue8bb', '关闭', window.close, close=True)
        for button in (self.minimize_button, self.maximize_button, self.close_button):
            layout.addWidget(button)
        window.installEventFilter(self)
        self.retheme()
        self._sync_maximized()

    def _button(self, glyph, tooltip, action, close=False):
        button = CaptionButton(glyph, self, self._window, close)
        button.setObjectName('captionClose' if close else 'captionButton')
        button.setFixedSize(CAPTION_BUTTON_WIDTH, self.height())
        button.setAutoDefault(False)
        button.setCursor(Qt.ArrowCursor)
        if self._show_tooltips:
            button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.clicked.connect(action)
        return button

    def retheme(self):
        if is_dark():
            ink, hover, pressed, active = '#A9B8CC', '#16202C', '#1B2837', '#E9F0F8'
        else:
            ink, hover, pressed, active = '#53657A', '#E9EFF6', '#DDE7F2', '#17202B'
        self.setStyleSheet(f'QFrame#titleBar {{ background: {SiColors.WINDOW_BG}; border: none; border-radius: 0; }}')
        if self._brand_name is not None:
            self._brand_name.setStyleSheet(f'color: {SiColors.TEXT_PRIMARY}; background: transparent; font-size: 10pt; font-weight: 600;')
        for button in (self.minimize_button, self.maximize_button, self.close_button):
            button._colors = (ink, hover, pressed, active)
            button.update()

    def toggle_maximized(self):
        self._window.showNormal() if self._window.isMaximized() else self._window.showMaximized()
        self._sync_maximized()

    def _sync_maximized(self):
        maximized = self._window.isMaximized()
        self.maximize_button.setText('\ue923' if maximized else '\ue922')
        label = '还原' if maximized else '最大化'
        self.maximize_button.setAccessibleName(label)
        if self._show_tooltips:
            self.maximize_button.setToolTip(label)

    def eventFilter(self, obj, event):
        if obj is self._window and event.type() == QEvent.WindowStateChange:
            self._sync_maximized()
        return super().eventFilter(obj, event)

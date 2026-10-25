# SPDX-License-Identifier: GPL-3.0-or-later
"""Outline preview action using the same palette as appliance power."""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QPushButton
import qtawesome as qta
from app.ui.si_theme import SiColors


class CameraPlayButton(QPushButton):
    def __init__(self, size=36, icon_size=26, *, online=True, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._icon_size = icon_size
        self._glyph_key = None
        self.setEnabled(online)
        self.setCursor(Qt.PointingHandCursor if online else Qt.ArrowCursor)
        self.setAccessibleName('查看摄像头画面' if online else '摄像头离线')
        self.setStyleSheet('background: transparent; border: none; padding: 0;')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self.isEnabled():
            background = SiColors.THEME_PRESSED if self.isDown() else SiColors.THEME_HOVER if self.underMouse() else SiColors.THEME
            ink = SiColors.ON_THEME_TEXT
        else:
            background, ink = SiColors.SURFACE, SiColors.ICON_DIM
        color = QColor(background)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QRectF(self.rect()))
        key = (ink, self._icon_size, self.devicePixelRatioF())
        if key != self._glyph_key:
            ratio = self.devicePixelRatioF()
            self._glyph = qta.icon('mdi.play-outline', color=ink).pixmap(
                QSize(self._icon_size, self._icon_size), ratio)
            ratio = self._glyph.devicePixelRatioF()
            image = self._glyph.toImage()
            total = sx = sy = 0
            for y in range(image.height()):
                for x in range(image.width()):
                    alpha = image.pixelColor(x, y).alpha()
                    total += alpha
                    sx += (x + .5) * alpha
                    sy += (y + .5) * alpha
            self._glyph_center = QPointF(sx / total / ratio, sy / total / ratio)
            self._glyph_key = key
        # Align visible ink, including its uneven font bearings, to the circle.
        origin = QPointF(self.width()/2, self.height()/2) - self._glyph_center
        painter.drawPixmap(origin, self._glyph)
        painter.end()

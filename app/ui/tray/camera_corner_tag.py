# SPDX-License-Identifier: GPL-3.0-or-later
"""Flat horizontal corner label identifying camera cards."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget
from app.ui.si_theme import SiColors


class CameraCornerTag(QWidget):
    def __init__(self, parent, *, corner_radius=9, width=38, height=12, font_size=5.5):
        super().__init__(parent)
        self._corner_radius = corner_radius
        self._font_size = font_size
        self.setObjectName('cameraCornerTag')
        self.setFixedSize(width, height)
        self.move(0, 0)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAccessibleName('摄像头 CAMERA')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.parentWidget().rect()), self._corner_radius, self._corner_radius)
        painter.setClipPath(clip)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(SiColors.CAMERA_TAG_BG))
        tag = QPainterPath()
        tag.moveTo(0, 0)
        width, height = self.width(), self.height()
        tag.lineTo(width, 0)
        tag.quadTo(width, height, width - height, height)
        tag.lineTo(0, height)
        tag.closeSubpath()
        painter.drawPath(tag)
        painter.setClipPath(tag, Qt.IntersectClip)
        painter.translate(width / 2 - 1, height / 2)
        text = QPainterPath()
        font = QFont('Segoe UI')
        font.setPointSizeF(self._font_size)
        font.setWeight(QFont.Weight.Bold)
        text.addText(QPointF(0, 0), font, 'CAMERA')
        # Center visible glyphs instead of the font's ascent/descent line box.
        painter.translate(-text.boundingRect().center())
        painter.fillPath(text, QColor('#ffffff'))
        painter.end()

# SPDX-License-Identifier: GPL-3.0-or-later
"""Flat horizontal corner label identifying camera cards."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget
from app.ui.si_theme import SiColors


class CameraCornerTag(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName('cameraCornerTag')
        self.setFixedSize(38, 12)
        self.move(0, 0)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAccessibleName('摄像头 CAMERA')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.parentWidget().rect()), 9, 9)
        painter.setClipPath(clip)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(SiColors.CAMERA_TAG_BG))
        tag = QPainterPath()
        tag.moveTo(0, 0)
        tag.lineTo(38, 0)
        tag.quadTo(38, 12, 26, 12)
        tag.lineTo(0, 12)
        tag.closeSubpath()
        painter.drawPath(tag)
        painter.setClipPath(tag, Qt.IntersectClip)
        painter.translate(18, 6)
        text = QPainterPath()
        text.addText(QPointF(0, 0), QFont('Segoe UI', 5.5, QFont.Weight.Bold), 'CAMERA')
        # Center visible glyphs instead of the font's ascent/descent line box.
        painter.translate(-text.boundingRect().center())
        painter.fillPath(text, QColor('#ffffff'))
        painter.end()

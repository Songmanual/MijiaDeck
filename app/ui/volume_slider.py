# SPDX-License-Identifier: GPL-3.0-or-later
"""Volume slider with an inline number and a soft accent halo."""
from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QRadialGradient
from PySide6.QtWidgets import QLabel, QSlider, QStyle, QStyleOptionSlider

from app.ui.si_theme import SiColors


class VolumeSlider(QSlider):
    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.setFixedHeight(42)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName("音箱音量")
        self.setStyleSheet(
            "QSlider { padding: 0 9px; }"
            f"QSlider::groove:horizontal {{ height: 4px; background: {SiColors.SURFACE}; border-radius: 2px; }}"
            f"QSlider::sub-page:horizontal {{ background: {SiColors.ACCENT_BORDER}; border-radius: 2px; }}"
            f"QSlider::add-page:horizontal {{ background: {SiColors.SURFACE}; border-radius: 2px; }}"
            "QSlider::handle:horizontal { width: 24px; height: 24px; background: transparent;"
            " border: none; margin: -10px 0; }")
        self.value_label = QLabel("—", self)
        self.value_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet(
            f"color: {SiColors.ON_THEME_TEXT}; background: transparent; border: none;"
            " font-size: 8pt; font-weight: 600;")
        self.sliderPressed.connect(self.update)
        self.sliderReleased.connect(self.update)

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        handle = self.style().subControlRect(
            QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self)
        center = handle.center()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        glow = QColor(SiColors.THEME)
        glow.setAlpha(145 if self.isSliderDown() else 120 if self.underMouse() else 90)
        gradient = QRadialGradient(center, 20)
        gradient.setColorAt(0, glow)
        gradient.setColorAt(.55, glow)
        middle = QColor(glow)
        middle.setAlpha(glow.alpha() // 2)
        gradient.setColorAt(.78, middle)
        clear = QColor(glow)
        clear.setAlpha(0)
        gradient.setColorAt(1, clear)
        painter.setBrush(gradient)
        painter.drawEllipse(center, 20, 20)
        # 半透明主题色与轻微高光，模拟磨砂玻璃的柔和层次。
        body = QLinearGradient(QPointF(center.x(), center.y() - 12),
                               QPointF(center.x(), center.y() + 12))
        top = QColor(SiColors.THEME).lighter(115)
        top.setAlpha(215)
        bottom = QColor(SiColors.THEME)
        bottom.setAlpha(240)
        body.setColorAt(0, top)
        body.setColorAt(1, bottom)
        painter.setBrush(body)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, 12, 12)
        painter.end()
        self.value_label.setGeometry(QRect(center.x() - 12, center.y() - 12, 24, 24))

    def enterEvent(self, event):  # noqa: N802
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):  # noqa: N802
        super().leaveEvent(event)
        self.update()

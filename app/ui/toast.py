# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""轻量通知浮层：右下角滑现、停留后淡出。

用于"刷新完成，新增 X 台"这类无需用户确认的结果反馈，不打断
当前操作；同一时刻只保留最新一条，新消息直接替换旧消息。
"""

import shiboken6
from PySide6.QtCore import QEvent, QPoint, QPropertyAnimation, QTimer
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QWidget

from app.ui.si_theme import SiColors


class Toast(QFrame):
    _current: "Toast | None" = None

    @classmethod
    def info(cls, parent: QWidget, text: str, duration_ms: int = 4000) -> None:
        if cls._current is not None and shiboken6.isValid(cls._current):
            cls._current.deleteLater()
        toast = cls(parent, text)
        cls._current = toast
        toast._popup(duration_ms)

    def __init__(self, parent: QWidget, text: str):
        super().__init__(parent)
        self.setObjectName("toastCard")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 12, 18, 12)
        label = QLabel(text)
        self._label = label
        label.setWordWrap(True)
        label.setFont(QFont("Microsoft YaHei UI", 10))
        label.setStyleSheet(
            f"color: {SiColors.TEXT_PRIMARY}; background: transparent;")
        lay.addWidget(label)
        parent.installEventFilter(self)

    def _popup(self, duration_ms: int) -> None:
        self._position()
        self.show()
        self.raise_()
        QTimer.singleShot(duration_ms, self._fade_out)

    def _position(self):
        host = self.parentWidget()
        fab = getattr(host, "_voice_fab", None)
        beside_fab = fab is not None and shiboken6.isValid(fab) and fab.isVisible()
        if beside_fab:
            button = fab._ball
            point = button.mapTo(host, QPoint(0, 0))
            maximum = max(80, min(420, point.x() - 14 - 20))
        else:
            maximum = max(80, min(420, host.width() - 40))
        natural = QFontMetrics(self._label.font()).horizontalAdvance(self._label.text()) + 38
        width = min(maximum, max(80, natural))
        self.setFixedWidth(width)
        self._label.setMaximumWidth(width - 38)
        self.adjustSize()
        x = max(16, host.width() - self.width() - 20)
        from app.ui.voice_fab import BOTTOM_RESERVED_HEIGHT
        bottom = BOTTOM_RESERVED_HEIGHT if hasattr(host, '_voice_fab') else 0
        y = max(16, host.height() - bottom - self.height() - 16)
        if beside_fab:
            x = max(16, point.x() - 14 - self.width())
            y = max(16, point.y() + (button.height() - self.height()) // 2)
        self.move(x, y)

    def eventFilter(self, obj, event):
        if obj is self.parentWidget() and event.type() == QEvent.Resize:
            QTimer.singleShot(0, self, self._position)
        return super().eventFilter(obj, event)

    def _fade_out(self) -> None:
        if not shiboken6.isValid(self):
            return
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(400)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.finished.connect(self.deleteLater)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""QLineEdit 占位提示的打字机动画。

主窗口语音悬浮球与托盘语音条共用：逐字显示，整句停留后循环重播，
重播前检查输入框仍可见（宿主面板收起/窗口隐藏则不再继续）。
"""

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QLineEdit

_TYPE_INTERVAL_MS = 80
_HOLD_BEFORE_REPLAY_MS = 1800


class TypewriterPlaceholder(QObject):
    """逐字写入 QLineEdit 的 placeholder，完整停留后循环。"""

    def __init__(self, edit: QLineEdit, text: str):
        super().__init__(edit)
        self._edit = edit
        self._text = text
        self._pos = 0
        self._timer = QTimer(self)
        self._timer.setInterval(_TYPE_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        """从头播放；用户输入时 placeholder 自动隐去不受影响。"""
        self._timer.stop()
        self._pos = 0
        self._edit.setPlaceholderText("")
        self._timer.start()

    def stop(self, clear: bool = False) -> None:
        self._timer.stop()
        if clear:
            self._edit.setPlaceholderText("")

    def is_active(self) -> bool:
        return self._timer.isActive()

    def _tick(self) -> None:
        self._pos += 1
        if self._pos >= len(self._text):
            # 整句显示完停留片刻再重播，避免无限快速循环
            self._edit.setPlaceholderText(self._text)
            self._pos = 0
            self._timer.stop()
            QTimer.singleShot(_HOLD_BEFORE_REPLAY_MS, self._replay)
            return
        self._edit.setPlaceholderText(self._text[:self._pos])

    def _replay(self) -> None:
        # 停留期间面板/窗口可能已隐藏，重播前确认仍可见
        if self._edit.isVisible():
            self.start()


# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""托盘管理对话框用的拖拽排序行。"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame


class _DraggableRow(QFrame):
    """支持拖拽排序的行。"""

    dragStarted = Signal(str)  # noqa: N815
    dragFinished = Signal()  # noqa: N815

    def __init__(self, did: str, parent=None):
        super().__init__(parent)
        self._did = did
        self._dragging = False
        self._drag_start = None

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if e.button() == Qt.LeftButton:
            self._drag_start = e.pos()
            self._dragging = False
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        if self._drag_start is None:
            return
        if not self._dragging:
            dist = (e.pos() - self._drag_start).manhattanLength()
            if dist >= 10:
                self._dragging = True
                self.dragStarted.emit(self._did)
                # 先抓图再隐藏：用透明度保持占位，避免布局收缩
                pixmap = self.grab()
                from PySide6.QtWidgets import QGraphicsOpacityEffect
                eff = QGraphicsOpacityEffect(self)
                eff.setOpacity(0.0)
                self.setGraphicsEffect(eff)
                from PySide6.QtGui import QDrag
                drag = QDrag(self)
                from PySide6.QtCore import QMimeData
                mime = QMimeData()
                mime.setText(self._did)
                drag.setMimeData(mime)
                drag.setPixmap(pixmap.scaledToWidth(min(pixmap.width(), 280), Qt.SmoothTransformation))
                drag.setHotSpot(e.pos())
                drag.exec(Qt.MoveAction)
                self.setGraphicsEffect(None)
                self._dragging = False
                self._drag_start = None
                self.dragFinished.emit()
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        self._dragging = False
        self._drag_start = None
        super().mouseReleaseEvent(e)



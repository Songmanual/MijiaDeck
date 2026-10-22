# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""工作台卡片包装器：承载删除×与拖拽手柄。

内部装 prop_widgets 的原生卡片，对外仍暴露 prop 供刷新链路复用。
"""

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QApplication, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from app.ui.si_theme import SiColors


class WorkbenchItemWrapper(QFrame):
    request_delete = Signal(str)  # key
    request_move = Signal(str, int)  # key, direction (+1/-1)

    def __init__(self, key: str, inner: QWidget, parent=None):
        super().__init__(parent)
        self.key = key
        self.inner = inner
        # 卡片尺寸对齐添加抽屉的 ModuleCard，保持网格统一样式；88 高度避免文字底被裁切
        self._base_height = 88
        self.setFixedHeight(self._base_height)
        from PySide6.QtWidgets import QSizePolicy as _SP
        self.setSizePolicy(_SP.Expanding, _SP.Fixed)
        inner.setSizePolicy(_SP.Expanding, _SP.Fixed)
        self.setObjectName("workbenchItem")
        self.setStyleSheet(
            "QFrame#workbenchItem { border: 1px solid transparent; border-radius: 14px; }"
            "QFrame#workbenchItem[edit=\"true\"] { border: 1px solid rgba(61,187,164,0.35); background: rgba(61,187,164,0.04); }"
            "QFrame#workbenchItem[offline=\"true\"] { border: 1px solid transparent; background: transparent; }"
        )
        # 枚举卡片改为流式自适应，不设置固定高度以免截断多行按钮
        self._is_enum = hasattr(inner, "_buttons")
        # 组合卡片包含多个子控件，需要自适应高度
        self._is_group = hasattr(inner, "_children")
        if self._is_enum or self._is_group:
            self.setSizePolicy(_SP.Expanding, _SP.Preferred)
            inner.setSizePolicy(_SP.Expanding, _SP.Preferred)
            self.setMinimumHeight(88)
            inner.setMinimumHeight(86)
            self.setMaximumHeight(16777215)
            inner.setMaximumHeight(16777215)
        else:
            # 非枚举保持固定 88
            inner.setFixedHeight(self._base_height - 2)
        # widget 级样式表优先级最高，完整卡片观感在此兜底，
        # 避免祖先链样式被中途覆盖后卡片退化为透明底；
        # 底色与主页设备卡片保持一致（#2a2c32 / #333540）
        inner.setStyleSheet(inner.styleSheet() + (
            f"QFrame#propCard {{ background: {SiColors.CARD}; border: 1px solid {SiColors.LINE}; border-radius: 14px; }}"
            f"QFrame#propCard:hover {{ background: {SiColors.CARD_HOVER}; border-color: {SiColors.CARD_BORDER_HOVER}; }}"
        ))
        # 滑块卡片原高度 104，统一为 76，需收紧内边距并刷新圆形拇指
        if hasattr(inner, "_slider"):
            try:
                lay_inner = inner.layout()
                if lay_inner is not None:
                    lay_inner.setContentsMargins(14, 8, 14, 10)
                    lay_inner.setSpacing(6)
                inner._slider.style_data.thumb_width = 18
                inner._slider.style_data.thumb_height = 18
                inner._slider.update()
            except Exception:
                pass
        # 分组卡片内部包含多行，收紧间距以塞进统一样式
        if hasattr(inner, "_children"):
            try:
                lay_inner = inner.layout()
                if lay_inner is not None:
                    lay_inner.setContentsMargins(14, 10, 14, 10)
                    lay_inner.setSpacing(6)
                for child in getattr(inner, "_children", []):
                    # 子控件不限制高度，由内容撑开
                    child.setMinimumHeight(0)
                    child.setMaximumHeight(16777215)
                    cl = child.layout()
                    if cl is not None:
                        cl.setContentsMargins(12, 6, 12, 6)
                        cl.setSpacing(4)
                    if hasattr(child, "_slider"):
                        child._slider.setFixedHeight(28)
                        child._slider.style_data.thumb_width = 18
                        child._slider.style_data.thumb_height = 18
                        child._slider.update()
                    # 输入框子控件（TextRowSection）特殊处理
                    if hasattr(child, "_editor"):
                        child.setMinimumHeight(60)
                        child.setMaximumHeight(72)
                        editor = child._editor
                        editor.setFixedHeight(28)
            except Exception:
                pass

        lay = QVBoxLayout(self)
        lay.setContentsMargins(1, 1, 1, 1)
        lay.setSpacing(0)

        # 顶部工具条：仅管理模式显示，极简风格
        self._bar = QFrame()
        self._bar.setStyleSheet("QFrame { background: transparent; border: none; }")
        self._bar.setFixedHeight(28)
        self._bar.hide()
        bar_lay = QHBoxLayout(self._bar)
        bar_lay.setContentsMargins(6, 0, 6, 0)
        bar_lay.setSpacing(6)
        self._handle = QLabel("⠿")
        self._handle.setStyleSheet(f"color: {SiColors.ICON_DIM}; font-size: 11pt; background: transparent;")
        self._handle.setToolTip("拖动排序")
        self._handle.setCursor(Qt.OpenHandCursor)
        self._handle.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        bar_lay.addWidget(self._handle)
        bar_lay.addStretch(1)
        self._up_btn = QPushButton("↑")
        self._up_btn.setFixedSize(22, 22)
        self._up_btn.setCursor(Qt.ArrowCursor)
        self._up_btn.setToolTip("上移")
        self._up_btn.clicked.connect(lambda: self.request_move.emit(self.key, -1))
        self._down_btn = QPushButton("↓")
        self._down_btn.setFixedSize(22, 22)
        self._down_btn.setCursor(Qt.ArrowCursor)
        self._down_btn.setToolTip("下移")
        self._down_btn.clicked.connect(lambda: self.request_move.emit(self.key, 1))
        for btn in (self._up_btn, self._down_btn):
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: 1px solid {SiColors.SURFACE}; border-radius: 6px; color: {SiColors.TEXT_SECONDARY}; font-size: 9pt; }}"
                f"QPushButton:hover {{ background: {SiColors.CARD}; border-color: {SiColors.BTN_HOVER}; color: {SiColors.TEXT_PRIMARY}; }}"
            )
        bar_lay.addWidget(self._up_btn)
        bar_lay.addWidget(self._down_btn)
        self._del_btn = QPushButton("✕")
        self._del_btn.setFixedSize(22, 22)
        self._del_btn.setCursor(Qt.PointingHandCursor)
        self._del_btn.setToolTip("移除")
        self._del_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {SiColors.DEL_BORDER}; border-radius: 6px; color: {SiColors.DEL_TEXT}; font-size: 9pt; }}"
            f"QPushButton:hover {{ background: rgba(192,57,43,0.15); border-color: {SiColors.DEL_BORDER_HOVER}; color: #e57373; }}"
        )
        self._del_btn.clicked.connect(lambda: self.request_delete.emit(self.key))
        bar_lay.addWidget(self._del_btn)
        lay.addWidget(self._bar)
        lay.addWidget(inner)

        self._mode = "normal"
        self._drag_start = None

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._mode == "manage" and event.button() == Qt.LeftButton:
            # 仅按住手柄区域才启动拖拽，避免与滑块冲突
            if self._bar.geometry().contains(event.pos()) and self._handle.geometry().contains(
                self._bar.mapFromParent(event.pos())
            ):
                self._drag_start = event.pos()
                self._handle.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._mode == "manage" and self._drag_start is not None and event.buttons() & Qt.LeftButton:
            if (event.pos() - self._drag_start).manhattanLength() > QApplication.startDragDistance():
                # 隐藏原位置，仅显示拖拽图标
                pix = self.grab()
                eff = QGraphicsOpacityEffect(self)
                eff.setOpacity(0.0)
                self.setGraphicsEffect(eff)
                drag = QDrag(self)
                mime = QMimeData()
                mime.setText(self.key)
                drag.setMimeData(mime)
                drag.setPixmap(pix)
                drag.setHotSpot(event.pos())
                drag.exec(Qt.MoveAction)
                self.setGraphicsEffect(None)
                self._drag_start = None
                self._handle.setCursor(Qt.OpenHandCursor)
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_start = None
        if hasattr(self, "_handle"):
            self._handle.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def set_mode(self, mode: str) -> None:
        """normal / manage（同时显示移动与删除）"""
        self._mode = mode
        if self._is_enum or self._is_group:
            # 枚举/组合卡片高度自适应，不固定
            if mode == "normal":
                self._bar.hide()
                self.setProperty("edit", False)
            else:
                self._bar.show()
                self._up_btn.show()
                self._down_btn.show()
                self._del_btn.show()
                self.setProperty("edit", True)
        else:
            if mode == "normal":
                self._bar.hide()
                self.setFixedHeight(self._base_height)
                self.inner.setFixedHeight(self._base_height - 2)
                self.setProperty("edit", False)
            else:  # manage
                self._bar.show()
                self._up_btn.show()
                self._down_btn.show()
                self._del_btn.show()
                self.setFixedHeight(self._base_height + 28)
                self.inner.setFixedHeight(self._base_height - 2)
                self.setProperty("edit", True)
        self.style().unpolish(self)
        self.style().polish(self)

    def estimated_height(self) -> int:
        """瀑布流分栏用的高度估算：渲染与重排动画共用同一公式。

        两处各写一份曾导致重排后卡片跨列分布与初始渲染不一致。
        """
        if self._is_enum:
            cnt = len(getattr(self.inner, "_buttons", []))
            rows = (cnt + 5) // 6
            return 88 + max(0, rows - 1) * 48
        if self._is_group:
            return 88 + len(getattr(self.inner, "_children", [])) * 52
        return self._base_height + (28 if self._mode == "manage" else 0)

    def set_offline(self, offline: bool) -> None:
        self.setEnabled(not offline)
        # 离线态走属性选择器，整块替换样式表会把 [edit="true"] 的
        # 管理模式规则抹掉且无法恢复
        self.setProperty("offline", offline)
        self.style().unpolish(self)
        self.style().polish(self)



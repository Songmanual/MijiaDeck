# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""侧滑抽屉：展示设备全部可用功能，支持逐项添加。

已添加的功能置灰禁用，避免重复。
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.overlay_dialog import OverlayDialog
from app.ui.si_theme import SiColors


class ModuleCard(QFrame):
    add_requested = Signal(str)

    def __init__(self, key: str, title: str, desc: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.setObjectName("propCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(12)
        self._title = QLabel(title)
        self._title.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.DemiBold))
        self._title.setStyleSheet(f"color: {SiColors.TEXT_PRIMARY}; background: transparent;")
        self._title.setWordWrap(True)
        # wordWrap 的 QLabel 压缩下限是"最长单词"宽度：长英文功能名会把
        # 右侧按钮挤出抽屉（QScrollArea 下列表容器被最小宽度撑宽）。
        # setMinimumWidth(0) 是空操作（默认最小尺寸已是 0），必须用
        # Ignored 水平策略让布局完全忽略尺寸提示、按分配宽度强制换行
        self._title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._desc = QLabel(desc)
        self._desc.setStyleSheet(f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 8pt;")
        self._desc.setWordWrap(True)
        self._desc.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(4)
        text_col.addWidget(self._title)
        text_col.addWidget(self._desc)
        lay.addLayout(text_col, stretch=1)
        self._btn = QPushButton("+")
        self._btn.setFixedSize(28, 28)
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.setStyleSheet(
            f"QPushButton {{ background: {SiColors.SURFACE}; border: none; border-radius: 14px; color: {SiColors.TEXT_PRIMARY}; font-size: 14pt; }}"
            f"QPushButton:hover {{ background: {SiColors.THEME}; }}"
        )
        self._btn.clicked.connect(self._on_btn_clicked)
        lay.addWidget(self._btn, alignment=Qt.AlignVCenter)
        self._added = False

    def _on_btn_clicked(self) -> None:
        # 已添加的点击即视为移除请求，仍通过同一信号由外层切换
        self.add_requested.emit(self.key)

    def set_added(self, added: bool) -> None:
        self._added = added
        # 已添加的也可点击移除，保持可点击
        self._btn.setEnabled(True)
        self._btn.setText("✓" if added else "+")
        if added:
            self._btn.setStyleSheet(
                "QPushButton { background: rgba(255,255,255,0.18); border: none; border-radius: 14px; color: #ffffff; font-size: 12pt; }"
                "QPushButton:hover { background: rgba(255,255,255,0.28); }"
            )
            self.setStyleSheet(
                f"QFrame#propCard {{ background: {SiColors.THEME}; border: 1px solid {SiColors.THEME}; border-radius: 14px; }}")
            self._title.setStyleSheet(f"color: {SiColors.ON_THEME_TEXT}; background: transparent;")
            self._desc.setStyleSheet(f"color: {SiColors.ON_THEME_TEXT}; background: transparent; font-size: 8pt;")
        else:
            # 不可读项即使未添加也不高亮，避免误导为空卡
            if "不可读" in self._desc.text():
                self._btn.setStyleSheet(
                    f"QPushButton {{ background: {SiColors.WINDOW_BG}; border: 1px solid {SiColors.SURFACE}; border-radius: 14px; color: {SiColors.OFFLINE_SUB}; font-size: 11pt; }}"
                    f"QPushButton:hover {{ background: {SiColors.CARD}; }}"
                )
                self.setStyleSheet(f"QFrame#propCard {{ background: {SiColors.WINDOW_BG}; border: 1px dashed {SiColors.SURFACE}; border-radius: 14px; }}")
            else:
                self._btn.setStyleSheet(
                    f"QPushButton {{ background: {SiColors.SURFACE}; border: none; border-radius: 14px; color: {SiColors.TEXT_PRIMARY}; font-size: 14pt; }}"
                    f"QPushButton:hover {{ background: {SiColors.THEME}; color: #fff; }}"
                )
                self.setStyleSheet("")
            self._title.setStyleSheet(f"color: {SiColors.TEXT_PRIMARY}; background: transparent;")
            self._desc.setStyleSheet(f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 8pt;")
            # 不可读项额外提示
            if "不可读" in self._desc.text():
                self.setToolTip("该功能固件未开放读取/写入，加入后仅显示占位，无法操作")
                self._title.setStyleSheet(f"color: {SiColors.OFFLINE_TEXT}; background: transparent;")
            else:
                self.setToolTip("")


class AddDrawer(OverlayDialog):
    add_module = Signal(str)

    def __init__(self, parent=None):
        # 侧滑抽屉不播放淡入（showEvent 只贴几何），保留即点即出的手感
        super().__init__(parent)

        # 右侧面板
        self._panel.setFixedWidth(380)

        lay = QVBoxLayout(self._panel)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        header = QHBoxLayout()
        title = QLabel("添加功能")
        title.setFont(QFont("Microsoft YaHei UI", 12, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {SiColors.TEXT_PRIMARY}; background: transparent;")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self._make_close_button())
        lay.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QWidget { background: transparent; }")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list_host = QWidget()
        self._list_host.setStyleSheet("background: transparent;")
        self._list_lay = QVBoxLayout(self._list_host)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(10)
        self._scroll.setWidget(self._list_host)
        lay.addWidget(self._scroll)

        self._cards: dict[str, ModuleCard] = {}

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_overlay()
        self._panel.setGeometry(self.width() - 400, 20, 380, self.height() - 40)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # 贴合窗口尺寸，实现右侧侧滑而非居中弹出
        self._fill_parent_window()
        self.raise_()

    def set_modules(self, modules: list[tuple[str, str, str]], added_keys: set[str]) -> None:
        while self._list_lay.count():
            item = self._list_lay.takeAt(0)
            if w := item.widget():
                w.deleteLater()
        self._cards.clear()
        # 已添加置顶，工作中可用（可读/可写）在前，不可读沉底
        def _rank(m):
            key, _, desc = m
            added = 0 if key in added_keys else 1
            unreadable = 1 if "不可读" in desc else 0
            return (added, unreadable)
        sorted_modules = sorted(modules, key=_rank)
        for key, title, desc in sorted_modules:
            card = ModuleCard(key, title, desc)
            card.add_requested.connect(self.add_module.emit)
            card.set_added(key in added_keys)
            self._list_lay.addWidget(card)
            self._cards[key] = card
        self._list_lay.addStretch(1)

    def mark_added(self, key: str) -> None:
        if card := self._cards.get(key):
            card.set_added(True)



# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""属性元数据到详情区块的自动映射与分组。

按属性类型生成功能卡片，并按名称前缀做关联聚类：
- 同前缀的属性归入同一功能组（如 mode-one-bright / mode-one-ct）
- 组内存在 bool 开关时形成父子关系：主开关关闭时其余参数灰显禁用
- 单属性按类型独立成卡：bool 电源行 / 数值滑块 / 枚举网格 / 输入行 / 只读行

控件来自 si_theme 工厂（SiliconUI 控件）；滑块禁用滚轮调节，避免
在详情页滚动浏览时误改数值。写入时机：拖动只预览，松手才下发。
"""

from typing import Any, Callable

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from app.siui.components.slider_ import SiSlider

from app.core.models import PropInfo
from app.ui.power_button import PowerButton
from app.ui.si_theme import SiColors, themed_label, themed_switch


# 常见传感器/统计属性的展示单位，命中则给只读值加上单位后缀
_PROP_UNITS: dict[str, str] = {
    "temperature": "°C",
    "relative-humidity": "%",
    "humidity": "%",
    "battery-level": "%",
    "power-consumption": "W",
    "electric-power": "W",
    "download-speed": "MB/s",
    "upload-speed": "MB/s",
    "rssi": "dBm",
    "online-time": "min",
    "work-countdown-sec": "s",
    "break-countdown-sec": "s",
    "delay-off-countdown": "s",
    "delay-time": "s",
    "work-minutes": "min",
    "break-minutes": "min",
}


class FlowLayout(QLayout):
    """流式布局：按钮按内容宽度自适应，自动换行，避免固定 6 列截断。"""

    def __init__(self, parent=None, margin: int = 0, spacing: int = 8):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items: list = []

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self.doLayout(QRect(0, 0, width, 0), True).height()

    def setGeometry(self, rect) -> None:
        super().setGeometry(rect)
        self.doLayout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = self.doLayout(QRect(0, 0, 0, 0), True)
        # 加上边距
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def doLayout(self, rect: QRect, testOnly: bool) -> QSize:
        x = rect.x()
        y = rect.y()
        lineHeight = 0
        spacing = self.spacing()
        for item in self._items:

            spaceX = spacing
            spaceY = spacing
            nextX = x + item.sizeHint().width() + spaceX
            if nextX - spaceX > rect.right() and lineHeight > 0:
                x = rect.x()
                y = y + lineHeight + spaceY
                nextX = x + item.sizeHint().width() + spaceX
                lineHeight = 0
            if not testOnly:
                item.setGeometry(QRect(x, y, item.sizeHint().width(), item.sizeHint().height()))
            x = nextX
            lineHeight = max(lineHeight, item.sizeHint().height())
        return QSize(rect.width(), y + lineHeight - rect.y())


def _card_frame() -> QFrame:
    frame = QFrame()
    frame.setObjectName("propCard")
    # QFrame 子类默认不按样式表绘制背景，必须显式启用 styled background
    frame.setAttribute(Qt.WA_StyledBackground, True)
    return frame


def _section_title(text: str) -> QLabel:
    label = themed_label(text, SiColors.TEXT_PRIMARY)
    label.setFont(QFont("Microsoft YaHei UI", 11, QFont.Weight.DemiBold))
    return label


def _value_label() -> QLabel:
    label = themed_label("", SiColors.TEXT_SECONDARY)
    label.setFont(QFont("Microsoft YaHei UI", 10))
    return label


class _NoWheelSlider(SiSlider):
    """禁用滚轮调节的滑块：滚轮事件穿透给页面滚动；拇指用 THUMB 调色板色。"""

    def wheelEvent(self, event) -> None:  # noqa: N802 (Qt 命名约定)
        event.ignore()


def _make_slider() -> _NoWheelSlider:
    slider = _NoWheelSlider()
    slider.setOrientation(Qt.Horizontal)
    slider.setRange(0, 100)
    slider.style_data.track_color = QColor(SiColors.THEME)
    # 拇指用主文字色：深色模式近白、浅色模式近黑，两种卡片上都可见
    # 拇指恒色：悬停不变色，详情页与工作台共用同一套观感
    slider.style_data.thumb_idle_color = QColor(SiColors.THUMB)
    slider.style_data.thumb_hover_color = QColor(SiColors.THUMB)
    slider.style_data.background_color = QColor(SiColors.SURFACE)
    # 圆形拇指：宽高相等 + 圆角由组件内部按半宽绘制
    slider.style_data.thumb_width = 18
    slider.style_data.thumb_height = 18
    # siui 在构造时把绘制用的 _thumb_color 从 style_data 快照，
    # 构造后改 style_data 不会回写，需手动设一次初始拇指色
    slider.thumbColor = QColor(SiColors.THUMB)
    slider.update()
    return slider


# ---------- 关联分组 ----------

def group_key(name: str) -> str:
    """功能组 key：取名称前两段（mode-one-bright -> mode-one）。"""
    parts = name.split("-")
    return "-".join(parts[:2]) if len(parts) >= 3 else name


def group_props(props: list[PropInfo]) -> list[tuple[str, list[PropInfo], PropInfo | None]]:
    """按名称前缀聚类属性。

    返回 (组 key, 成员列表, 主开关) 序列；组内存在 bool 可写开关时
    它作为主开关（父子联动的父节点），单属性组主开关为 None。
    """
    groups: dict[str, list[PropInfo]] = {}
    order: list[str] = []
    for prop in props:
        key = group_key(prop.name)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(prop)

    result = []
    for key in order:
        members = groups[key]
        master: PropInfo | None = None
        if len(members) >= 2:
            for member in members:
                if member.type == "bool" and member.writable:
                    if master is None or len(member.name) < len(master.name):
                        master = member
        result.append((key, members, master))
    return result


def is_primary_slider(prop: PropInfo) -> bool:
    """亮度/色温这类高频调节滑块，布局时排在最前。"""
    name = prop.name.lower()
    return (
        prop.writable and bool(prop.range)
        and prop.type in ("int", "uint", "float")
        and ("bright" in name or "color" in name
             or name.endswith("-ct") or name == "ct"
             or "temperature" in name)
    )


# ---------- 功能区块 ----------

class PowerRowSection(QFrame):
    """电源行卡片：属性名 + 状态文字 + 圆形电源钮，整行点击切换。"""

    def __init__(self, prop: PropInfo, write: Callable[[bool], None]):
        super().__init__()
        self.prop = prop
        self._write = write
        self._current = False
        self.setObjectName("propCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)

        self._circle = PowerButton(40, icon_size=32)
        self._circle.clicked.connect(self._toggle)

        self._title = themed_label(prop.desc, SiColors.TEXT_PRIMARY)
        self._title.setFont(QFont("Microsoft YaHei UI", 12, QFont.Weight.DemiBold))
        self._state = themed_label("已关闭", SiColors.TEXT_SECONDARY)
        self._state.setFont(QFont("Microsoft YaHei UI", 9))

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        text_col.addWidget(self._title)
        text_col.addWidget(self._state)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.setSpacing(18)
        lay.addWidget(self._circle)
        lay.addLayout(text_col)
        lay.addStretch(1)
        self.setFixedHeight(76)
        self.setMinimumHeight(76)
        self._apply(False)

    def _toggle(self) -> None:
        new_state = not bool(self._current)
        self._apply(new_state)
        self._write(new_state)

    def _apply(self, state: bool) -> None:
        self._current = state
        self._circle.set_state(state)
        self._state.setText("已开启" if state else "已关闭")

    def refresh_value(self, value: Any) -> None:
        self._apply(bool(value))

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt 命名约定)
        if event.button() == Qt.LeftButton:
            self._toggle()
        super().mouseReleaseEvent(event)


class SliderSection(QFrame):
    """滑块卡片：标题 + 实时值 + siui 滑块。"""

    def __init__(self, prop: PropInfo, write: Callable[[Any], None]):
        super().__init__()
        self.prop = prop
        self._write = write
        self.setObjectName("propCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        low, high, step = prop.range
        self._decimals = 0 if prop.type != "float" else _decimals_of(step)

        title_row = QHBoxLayout()
        title_row.addWidget(_section_title(prop.desc))
        title_row.addSpacing(8)
        self._value_label = _value_label()
        title_row.addWidget(self._value_label)
        title_row.addStretch(1)
        title_host = QWidget()
        title_host.setStyleSheet("background: transparent;")
        title_host.setLayout(title_row)

        self._slider = _make_slider()
        self._slider.setRange(int(low), int(high))
        # 拖动过程只预览，松手才下发，避免一次拖动连发几十条指令
        self._slider.valueChanged.connect(self._on_preview)
        self._slider.sliderReleased.connect(self._commit)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 22)
        lay.setSpacing(14)
        lay.addWidget(title_host)
        lay.addWidget(self._slider)
        self.setMinimumHeight(104)
        self._update_value_text(low)

    def _on_preview(self, value: int) -> None:
        self._update_value_text(value)

    def _commit(self) -> None:
        self._write(self._slider.value())

    def _update_value_text(self, value: Any) -> None:
        if self._decimals:
            self._value_label.setText(f"{float(value):.{self._decimals}f}")
        else:
            self._value_label.setText(str(value))

    def refresh_value(self, value: Any) -> None:
        # blockSignals 会同时挡掉 siui 内部的进度动画同步，
        # 因此设值后手动调用其内部回调让轨道视觉跟随真实值
        self._slider.blockSignals(True)
        try:
            self._slider.setValue(int(value))
            self._slider._onValueChanged(int(value))
        finally:
            self._slider.blockSignals(False)
        self._update_value_text(value)


class EnumGridSection(QFrame):
    """模式卡片：标题 + 圆形按钮网格，点击即写入对应枚举值。"""

    def __init__(self, prop: PropInfo, write: Callable[[Any], None]):
        super().__init__()
        self.prop = prop
        self._write = write
        self.setObjectName("propCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._buttons: list[QPushButton] = []
        self._values: list[Any] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 22)
        lay.setSpacing(12)
        lay.addWidget(_section_title(prop.desc))

        grid_host = QWidget()
        grid_host.setStyleSheet("background: transparent;")
        grid = FlowLayout(grid_host, margin=0, spacing=8)
        grid.setContentsMargins(0, 6, 0, 0)
        group = QButtonGroup(grid_host)
        group.setExclusive(False)
        for index, item in enumerate(prop.value_list):
            text = item.get("desc_zh_cn") or item.get("description") or str(item["value"])
            button = QPushButton()
            button.setCursor(Qt.PointingHandCursor)
            button.setText(str(text))
            button.setToolTip(text)
            button.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.Medium))
            button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            button.setMinimumHeight(30)
            # 自适应宽度：按文字计算，减小左右内边距以容纳更多列
            button.setStyleSheet("QPushButton { padding: 5px 8px; }")
            button.clicked.connect(lambda _, v=item["value"]: self._pick(v))
            group.addButton(button)
            grid.addWidget(button)
            self._buttons.append(button)
            self._values.append(item["value"])
        lay.addWidget(grid_host)
        self._highlight(None)

    def _pick(self, value: Any) -> None:
        self._highlight(value)
        self._write(value)

    def _highlight(self, value: Any) -> None:
        for button, item_value in zip(self._buttons, self._values):
            active = item_value == value
            button.setStyleSheet(
                f"QPushButton {{ background: {SiColors.THEME if active else f'{SiColors.SURFACE}'};"
                f" color: {'{SiColors.ON_THEME_TEXT}' if active else SiColors.TEXT_PRIMARY};"
                f" border: 1px solid {SiColors.THEME if active else f'{SiColors.SURFACE}'}; border-radius: 8px; padding: 6px 12px; }}"
            )

    def refresh_value(self, value: Any) -> None:
        self._highlight(value)


class ReadOnlySection(QFrame):
    """只读行卡片：属性名在左，当前值在右。

    覆盖三类只读形态：
    - 枚举：按 value_list 翻译为中文胶囊感文字
    - 字符串/数值：多行可选中，空值占位
    - 不可读(rw="")：占位提示，不显示 None
    """

    def __init__(self, prop: PropInfo):
        super().__init__()
        self.prop = prop
        self.setObjectName("propCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._is_string = prop.type == "string"
        self._has_enum = bool(prop.value_list)
        self._is_unreadable = not prop.readable
        self._value = _value_label()
        self._value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        if self._is_string:
            self._value.setWordWrap(True)
            self._value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        else:
            self._value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        # 不可读或初始未刷新时给占位，避免空卡
        placeholder = "不支持读取" if self._is_unreadable else "—"
        self._value.setText(placeholder)
        if self._is_unreadable:
            self._value.setStyleSheet(f"color: {SiColors.OFFLINE_SUB}; background: transparent; font-size: 9pt;")
            self.setToolTip("该属性固件未开放读取（spec rw=\"\"），仅作占位展示")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(12)
        title = _section_title(prop.desc)
        # 不可读标题置灰，区分“只读可看”与“不可读”
        if self._is_unreadable:
            title.setStyleSheet(f"color: {SiColors.OFFLINE_TEXT}; background: transparent;")
        lay.addWidget(title)
        lay.addStretch(1)
        lay.addWidget(self._value)
        if self._is_string:
            self.setMinimumHeight(64)
            self.setMaximumHeight(96)
        else:
            self.setFixedHeight(64)

    def refresh_value(self, value: Any) -> None:
        # 不可读属性不应被轮询到，若误刷新到 None/"" 仍保持占位
        if self._is_unreadable and (value is None or value == ""):
            self._value.setText("不支持读取")
            return
        self._value.setText(_format_display(value, self.prop))


class StatusPillSection(QFrame):
    """状态胶囊卡：不可写、无 value_list 的裸数值/字符串，仅作当前值展示。

    针对 mode/fault/status/flow 这类固件未给枚举选项、直接读写数字也无
    意义属性，展示为右侧胶囊型状态文字而非可误改的数字输入框。
    """

    def __init__(self, prop: PropInfo):
        super().__init__()
        self.prop = prop
        self.setObjectName("propCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._value = _value_label()
        self._value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        if prop.type == "string":
            self._value.setWordWrap(True)
        # 可写裸数值不可回读（readable=False）时轮询不会刷新，
        # 初始给占位而非空白；仅写不读的属性（如 toggle/change-value）同理
        if not prop.readable:
            self._value.setText("—")
            self.setToolTip("该属性固件未开放读取，仅作状态占位")

        pill = QFrame()
        pill.setObjectName("statusPill")
        pill.setAttribute(Qt.WA_StyledBackground, True)
        pill.setStyleSheet(
            f"QFrame#statusPill {{ background: {SiColors.SURFACE}; border: 1px solid {SiColors.LINE}; border-radius: 9px; padding: 2px 10px; }}")
        pl = QHBoxLayout(pill)
        pl.setContentsMargins(8, 2, 8, 2)
        pl.addWidget(self._value)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 14, 20, 14)
        lay.setSpacing(12)
        lay.addWidget(_section_title(prop.desc))
        lay.addStretch(1)
        lay.addWidget(pill)
        self.setFixedHeight(64)

    def refresh_value(self, value: Any) -> None:
        self._value.setText(_format_display(value, self.prop))


class TextRowSection(QFrame):
    """输入行卡片：顶部标题 + 下方输入控件。

    字符串属性带"设置"按钮对齐小爱文本指令卡；数字属性用自提交的
    数字框。布局从"标题+控件同行"改为"标题在上、控件在下"，长文本
    不被标题挤压，也符合表单输入直觉。
    """

    def __init__(self, prop: PropInfo, write: Callable[[Any], None]):
        super().__init__()
        self.prop = prop
        self.setObjectName("propCard")
        self.setAttribute(Qt.WA_StyledBackground, True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 12, 20, 14)
        lay.setSpacing(8)
        lay.addWidget(_section_title(prop.desc))

        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        if prop.type in ("int", "uint"):
            editor = QSpinBox()
            if prop.range:
                editor.setRange(int(prop.range[0]), int(prop.range[1]))
            elif prop.type == "uint":
                editor.setRange(0, 2147483647)
            else:
                editor.setRange(-2147483648, 2147483647)
            editor.setFixedHeight(32)
            editor.editingFinished.connect(lambda: write(editor.value()))
            # 批量回读里读不到的属性为 None，直接跳过避免 int(None) 抛异常
            display = lambda v: v is not None and editor.setValue(int(v))  # noqa: E731
            input_row.addWidget(editor, 1)
        elif prop.type == "float":
            editor = QDoubleSpinBox()
            editor.setDecimals(2)
            editor.setRange(-1e9, 1e9)
            editor.setFixedHeight(32)
            editor.editingFinished.connect(lambda: write(editor.value()))
            display = lambda v: v is not None and editor.setValue(float(v))  # noqa: E731
            input_row.addWidget(editor, 1)
        else:
            # 与 workbench_panel 文本指令卡同一套内联 QLineEdit 样式，
            # 避免 siui 胶囊输入框造成两处字符串输入视觉不一致
            from PySide6.QtWidgets import QLineEdit
            editor = QLineEdit()
            editor.setFixedHeight(32)
            editor.setMinimumWidth(0)
            editor.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            editor.setStyleSheet(
                f"QLineEdit {{ background: {SiColors.WINDOW_BG}; border: 1px solid {SiColors.LINE}; border-radius: 8px; "
                f"padding: 6px 10px; color: {SiColors.TEXT_PRIMARY}; selection-background-color: {SiColors.THEME}; font-size: 10pt; }}"
                f"QLineEdit:focus {{ border-color: {SiColors.THEME}; }}"
            )
            # 提交仅由"设置"按钮与回车触发；editingFinished 会在失焦时
            # 触发，删除内容后点卡片外部也会误提交，故弃用
            btn = QPushButton("设置")
            btn.setFixedSize(56, 32)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background: {SiColors.THEME}; color: {SiColors.ON_THEME_TEXT}; border: none; border-radius: 8px; font-size: 9pt; font-weight: 600; }}"
                f"QPushButton:hover {{ background: {SiColors.THEME_HOVER}; }}")
            def _commit_text(e=editor):
                write(e.text())
            btn.clicked.connect(lambda: _commit_text())
            editor.returnPressed.connect(lambda: _commit_text())
            input_row.addWidget(editor, 1)
            input_row.addWidget(btn)
            # 空值/None 只清空不回写 "None"，避免路由等读不到值的可读
            # string 属性默认显示 "None"
            display = lambda v: editor.setText("" if v is None or v == "" else str(v))  # noqa: E731

        self._editor = editor
        self._display_fn = display
        lay.addLayout(input_row)
        # 使用最小高度而非固定高度，避免在组合卡片中被裁切
        self.setMinimumHeight(64)

    def refresh_value(self, value: Any) -> None:
        self._editor.blockSignals(True)
        try:
            self._display_fn(value)
        finally:
            self._editor.blockSignals(False)


class GroupSection(QFrame):
    """关联功能组卡片：主开关控制组内其余参数的可用性。

    主开关关闭时子参数区块整体禁用（灰显且不可交互），开启后恢复，
    呈现"开启功能后才需要调整参数"的父子级关系。
    """

    def __init__(self, key: str, members: list[PropInfo], master: PropInfo,
                 write: Callable[[PropInfo, Any], None]):
        super().__init__()
        self.prop = master
        self.setObjectName("propCard")
        self.setAttribute(Qt.WA_StyledBackground, True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 20)
        lay.setSpacing(8)

        head = QHBoxLayout()
        title = master.desc or key
        self._title = _section_title(title)
        head.addWidget(self._title)
        head.addStretch(1)
        self._switch = themed_switch()
        self._switch.toggled.connect(self._on_master_changed)
        head.addWidget(self._switch)
        lay.addLayout(head)

        self._children: list[QWidget] = []
        for member in members:
            if member is master:
                continue
            child = build_prop_section(
                member, lambda value, m=member: write(m, value)
            )
            self._children.append(child)
            lay.addWidget(child)
        # 初始化时不禁用子控件，等待 refresh_value 同步真实状态

    def _on_master_changed(self, state: bool) -> None:
        self._set_children_enabled(state)
        self._write_master(state)

    def _write_master(self, state: bool) -> None:
        # 由 workbench_panel 构造分组卡片后注入
        if self._master_write is not None:
            self._master_write(state)

    _master_write: Callable[[bool], None] | None = None

    def set_master_write(self, write: Callable[[bool], None]) -> None:
        self._master_write = write

    def _set_children_enabled(self, state: bool) -> None:
        for child in self._children:
            child.setEnabled(state)

    def refresh_value(self, value: Any) -> None:
        state = bool(value)
        self._switch.blockSignals(True)
        try:
            self._switch.setChecked(state)
            # SiSwitchRefactor 动画同步：setChecked 不更新 _progress
            self._switch.progress = 1.0 if state else 0.0
            try:
                self._switch.progress_ani.setCurrentValue(1.0 if state else 0.0)
            except Exception:
                pass
        finally:
            self._switch.blockSignals(False)
        self._set_children_enabled(state)


def build_prop_section(prop: PropInfo, write: Callable[[Any], None]) -> QWidget:
    """按元数据生成功能区块；write 在用户确认修改时收到新值。

    可写分支按可用操作形态分流：bool→电源行、枚举→网格、
    带 range→滑块、纯数字/字符串无附加语义→可写输入行。
    不可写分支再分可读展示 / 无枚举的裸状态胶囊 / 不可读占位。
    """
    if prop.type == "bool" and prop.writable:
        return PowerRowSection(prop, write)
    if prop.writable and prop.value_list:
        return EnumGridSection(prop, write)
    if prop.writable and prop.range and prop.type in ("int", "uint", "float"):
        return SliderSection(prop, write)
    if prop.writable:
        # 可写字符串：输入框可编辑；可写裸数值（无 range/无枚举）展示为
        # 状态胶囊，避免暴露无意义的数字输入框让用户误改（如 mode/flow）
        if prop.type == "string":
            return TextRowSection(prop, write)
        return StatusPillSection(prop)
    if not prop.readable:
        # rw=""：不可读也不可写，占位提示
        return ReadOnlySection(prop)
    if prop.value_list:
        # 只读且固件给了枚举选项：翻译成状态展示
        return ReadOnlySection(prop)
    # 只读裸数值/字符串（mode/fault/status/flow 等）：胶囊状态展示而非空卡
    return StatusPillSection(prop)


def _decimals_of(step: float) -> int:
    text = f"{step:g}"
    return len(text.split(".")[1]) if "." in text else 0


def _format_display(value: Any, prop: PropInfo | None = None) -> str:
    if value is None or value == "":
        return "—"
    if value is True:
        return "开启"
    if value is False:
        return "关闭"
    # 只读枚举按 value_list 翻译为中文，避免显示 0/1/2
    if prop is not None and prop.value_list:
        for item in prop.value_list:
            if item.get("value") == value:
                text = item.get("desc_zh_cn") or item.get("description") or str(value)
                return str(text)
    # 常见传感器/统计属性补单位，让裸数值可读
    if prop is not None and prop.type in ("int", "uint", "float"):
        unit = _PROP_UNITS.get(prop.name)
        if unit is not None:
            return f"{value}{unit}"
    return str(value)



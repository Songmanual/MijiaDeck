# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""米家风格的设备卡片。

卡片按设备角色提供常用操作：圆形电源钮直接开关，面板本体只展示；
调光调色灯点击打开小控制窗，其他设备使用各自的详情路径。

设备是否支持开关在列表接口里拿不到：电源钮初始隐藏，后台批量探测
确认有可写开关属性后才显示并回填真实状态。
"""

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from app.siui.components.container import SiRowCard

from app.core.models import DeviceInfo
from app.core.device_controls import device_title, device_subtitle, has_device_details, supports_card_power, is_camera
from app.ui.camera_play_button import CameraPlayButton
from app.ui.power_button import PowerButton
from app.ui.si_theme import SiColors
import qtawesome as qta

_POWER_BTN_SIZE = 36
_ICON_SIZE = 34
# 主页内容使用更舒展的尺寸，不影响全局 DPI 或托盘卡片。
# 网格以此最小宽度计算列数，再均分可用宽度，避免右侧留下整块空白。
_CARD_FIXED_WIDTH = 212
_CARD_FIXED_HEIGHT = 92

# 离线卡片的灰置配色：背景更暗、文字更灰，hover 不提亮


class DeviceCard(SiRowCard):
    power_clicked = Signal(str)  # did
    open_requested = Signal(str)  # did

    def __init__(self, device: DeviceInfo, parent=None):
        super().__init__(parent, self.LeftToRight)
        self.device = device
        self._busy = False
        self._hovered = False
        self._online = device.online
        self._metrics_text = None
        self._panel_states = {}

        self.style_data.background_color = QColor(
            SiColors.OFFLINE_CARD if not self._online else SiColors.CARD)
        self.style_data.border_radius = 14.0
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        # 初始基准尺寸；主窗口按实际网格宽度分配最终列宽。
        self.setFixedSize(_CARD_FIXED_WIDTH, _CARD_FIXED_HEIGHT)
        self.setCursor(Qt.PointingHandCursor if has_device_details(device) else Qt.ArrowCursor)
        self.muteStretchWidget()

        self._power_btn = PowerButton(_POWER_BTN_SIZE, icon_size=22)
        self._power_btn.clicked.connect(lambda: self.power_clicked.emit(device.did))
        # 列表接口不带开关信息，先隐藏电源钮；后台探测确认设备
        # 有可写开关属性后再显示并回填真实状态
        self._power_btn.hide()
        self._power_btn.set_online(self._online)

        name_color = SiColors.INFO_TEXT if self._online else SiColors.OFFLINE_TEXT
        self._name_label = QLabel(device_title(device))
        self._name_label.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.Medium))
        self._name_label.setAccessibleName(device.name)
        self._name_label.setMinimumWidth(0)
        self._name_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        # 允许换行：长名称不再把所在列撑宽，卡片宽度保持整齐
        self._name_label.setWordWrap(True)
        self._name_label.setStyleSheet(
            f"color: {name_color}; background: transparent; font-size: 10.2pt; font-weight: 500;")

        self._sub_label = QLabel(self._sub_text())
        self._sub_label.setFont(QFont("Microsoft YaHei UI", 8))
        self._sub_label.setWordWrap(True)
        self._sub_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        sub_color = SiColors.TEXT_SECONDARY if self._online else SiColors.OFFLINE_SUB
        self._sub_label.setStyleSheet(
            f"color: {sub_color}; background: transparent; font-size: 9pt;")
        # 离线卡片电源钮不可操作
        if not self._online:
            self._power_btn.setEnabled(False)

        # 设备图标：后台拉取就绪后由 set_icon 填入，未就绪前保持隐藏
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(_ICON_SIZE, _ICON_SIZE)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        model_icons = {
            "wifispeaker": "mdi.speaker",
            "light": "mdi.lightbulb-outline",
            "plug": "mdi.power-socket-eu",
            "sensor": "mdi.thermometer",
            "humidifier": "mdi.water-outline",
            "airpurifier": "mdi.air-filter",
            "curtain": "mdi.blinds",
            "camera": "mdi.cctv",
        }
        icon = next((value for key, value in model_icons.items() if key in device.model),
                    "mdi.devices")
        self._icon_label.setPixmap(qta.icon(icon, color=SiColors.THEME_DIM).pixmap(24, 24))
        self._icon_label.setStyleSheet("background: transparent; border: none;")

        # 左侧文字列整体垂直居中，与右侧电源钮同一水平轴
        text_col = QWidget()
        text_col.setAttribute(Qt.WA_TranslucentBackground)
        text_lay = QVBoxLayout(text_col)
        text_lay.setContentsMargins(0, 0, 0, 0)
        text_lay.setSpacing(5)
        text_lay.addStretch(1)
        text_lay.addWidget(self._name_label)
        text_lay.addWidget(self._sub_label)
        text_lay.addStretch(1)

        lay = self.layout()
        lay.setContentsMargins(12, 10, 12, 10)
        lay.addWidget(self._icon_label, alignment=Qt.AlignVCenter)
        lay.addSpacing(7)
        lay.addWidget(text_col, stretch=1)
        lay.addWidget(self._power_btn, alignment=Qt.AlignVCenter)
        self._play_btn = None
        if is_camera(device):
            self._play_btn = CameraPlayButton(_POWER_BTN_SIZE, online=self._online)
            self._play_btn.clicked.connect(lambda: self.open_requested.emit(device.did))
            lay.addWidget(self._play_btn, alignment=Qt.AlignVCenter)
            from app.ui.tray.camera_corner_tag import CameraCornerTag
            self._camera_tag = CameraCornerTag(self, corner_radius=14, width=46, height=14, font_size=6)
            self._camera_tag.raise_()

    def paintEvent(self, event) -> None:  # noqa: N802
        """A fine outline keeps the cards legible on the quiet page background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(self.style_data.background_color)
        border = SiColors.CARD_BORDER_HOVER if self._hovered and self._online and has_device_details(self.device) else SiColors.LINE
        painter.setPen(QPen(QColor(border), 1))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 14, 14)
        painter.end()

    # ---------- 状态渲染 ----------

    def set_icon(self, path: Path | None) -> None:
        """填入设备图标；路径无效或图片损坏时保持隐藏不打断布局。"""
        if path is None or not path.is_file():
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return
        self._icon_label.setPixmap(pixmap.scaled(
            _ICON_SIZE, _ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        self._icon_label.show()

    def set_power_state(self, state: bool) -> None:
        if not supports_card_power(self.device):
            self._power_btn.hide()
            return
        # 能设置状态即证明设备具备开关能力，电源钮随之可见
        self._power_btn.set_state(state)
        self._power_btn.show()

    def _sub_text(self, metrics: str | None = None) -> str:
        """副标题文案：离线优先显示离线标记，有读数时附带。"""
        return device_subtitle(self.device, metrics, self._panel_states)

    def set_metrics(self, text: str | None) -> None:
        """副标题附带实时读数（温湿度等），离线卡片不叠加读数。"""
        # 离线设备不展示温湿度，读数可能是旧缓存
        if not self._online:
            return
        self._metrics_text = text
        self._sub_label.setText(self._sub_text(text))

    def set_panel_states(self, states):
        if self.device.switch_channels:
            self._panel_states = dict(states)
            self._sub_label.setText(self._sub_text(self._metrics_text))

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._power_btn.set_busy(busy)

    # ---------- hover 观感 ----------

    def enterEvent(self, event) -> None:  # noqa: N802 (Qt 命名约定)
        self._hovered = True
        self._apply_card_color()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 (Qt 命名约定)
        self._hovered = False
        self._apply_card_color()
        super().leaveEvent(event)

    def _apply_card_color(self) -> None:
        if not self._online:
            # 离线卡片整体灰置，hover 不提亮（无交互暗示）
            self.style_data.background_color = QColor(SiColors.OFFLINE_CARD)
        else:
            self.style_data.background_color = QColor(
                SiColors.CARD_HOVER if self._hovered and has_device_details(self.device) else SiColors.CARD
            )
        self.update()

    # ---------- 交互 ----------

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 (Qt 命名约定)
        # 电源钮自己消费点击事件，能走到这里的都是卡片空白区
        if event.button() == Qt.LeftButton and has_device_details(self.device) and self._online:
            self.open_requested.emit(self.device.did)
        super().mouseReleaseEvent(event)



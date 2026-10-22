# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""托盘左键快捷窗口：设备/场景行、音频栏、小爱语音条与呼出动画。"""

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPoint,
    QRectF,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import qtawesome as qta

from app.core import settings_store, tray_store
from app.core.jobs import JobExecutor
from app.core.models import DeviceInfo, SceneInfo, is_speaker
from app.core.service import MijiaService
from app.ui.power_button import PowerButton
from app.ui.si_theme import SiColors
from app.ui.toast import Toast
from app.ui.tray.audio_bar import _TrayAudioBar
from app.ui.typewriter import TypewriterPlaceholder

_SHADOW_PAD = 6
_PANEL_WIDTH = 400
_CARD_HEIGHT = 58
_LIST_HEIGHT = 310  # Keep the viewport size independent of individual card heights.


def _svg_icon(filename: str, original_color: str) -> QIcon:
    from app import resource_path
    svg = resource_path(f"app/ui/icons/{filename}").read_bytes()
    svg = svg.replace(original_color.encode("ascii"), SiColors.TEXT_SECONDARY.encode("ascii"))
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(svg).render(painter, QRectF(0, 0, 64, 64))
    painter.end()
    faded = QPixmap(pixmap.size())
    faded.fill(Qt.transparent)
    painter = QPainter(faded)
    painter.setOpacity(.65)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return QIcon(faded)


class TrayQuickWindow(QDialog):
    """托盘左键弹出的快捷操作面板。"""

    manage_requested = Signal()
    speaker_changed = Signal()
    open_device_requested = Signal(str)  # did

    def __init__(self, service: MijiaService, jobs: JobExecutor, parent=None):
        super().__init__(parent)
        self._service = service
        self._jobs = jobs
        self._devices: list[DeviceInfo] = []
        self._known_power: dict[str, bool | None] = {}
        self._metrics: dict[str, str | None] = {}
        self._sub_labels: dict[str, QLabel] = {}
        self._sub_widths: dict[str, int] = {}
        self._columns: int = settings_store.get_tray_columns()

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(False)
        self.hide()

        # 保存引用：retheme 必须对控件自身重设样式——子控件自身样式表
        # 优先于窗口级样式表，只设窗口级会被构造时的旧样式盖住
        self._root = QFrame(self)
        self._root.setObjectName("trayQuickPanel")
        self._root.setStyleSheet(
            "QFrame#trayQuickPanel { background: transparent; border: none; }")
        lay = QVBoxLayout(self._root)
        lay.setContentsMargins(12, 8, 12, 10)
        lay.setSpacing(8)

        # 标题栏：单双列切换 + 编辑卡片
        self._drag_header = QWidget()
        self._drag_header.setStyleSheet('background: transparent;')
        self._drag_header.setCursor(Qt.ArrowCursor)
        self._drag_header.installEventFilter(self)
        header = QHBoxLayout(self._drag_header)
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        title = QLabel("快捷控制")
        title.setFont(QFont("Microsoft YaHei UI", 10, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {SiColors.TEXT_PRIMARY}; background: transparent;")
        title.setCursor(Qt.ArrowCursor)
        title.installEventFilter(self)
        self._drag_title = title
        header.addWidget(title)
        header.addStretch(1)
        # 单双列切换：图标表示当前列数，点击切换
        self._cols_btn = QPushButton()
        self._cols_btn.setFixedSize(22, 22)
        self._cols_btn.setCursor(Qt.PointingHandCursor)
        self._cols_btn.setIconSize(QSize(14, 14))
        self._cols_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 6px; }"
            f"QPushButton:hover {{ background: {SiColors.BTN_HOVER}; }}")
        self._cols_btn.setAutoDefault(False)
        self._cols_btn.setDefault(False)
        self._cols_btn.clicked.connect(self._toggle_columns)
        self._refresh_cols_btn()
        header.addWidget(self._cols_btn)
        self._edit_btn = QPushButton()
        self._edit_btn.setFixedSize(22, 22)
        self._edit_btn.setCursor(Qt.PointingHandCursor)
        self._edit_btn.setAccessibleName("编辑卡片")
        self._edit_btn.setIcon(_svg_icon("tray-edit.svg", "#222429"))
        self._edit_btn.setIconSize(QSize(16, 16))
        self._edit_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 6px; }"
            f"QPushButton:hover {{ background: {SiColors.BTN_HOVER}; }}")
        self._edit_btn.setAutoDefault(False)
        self._edit_btn.setDefault(False)
        self._edit_btn.clicked.connect(self.manage_requested.emit)
        header.addWidget(self._edit_btn)
        lay.addWidget(self._drag_header)

        # 滚动列表：列数可切换（1/2），可见行数固定 4 行
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        # Keep card/icon proportions while giving the expanded panel more room.
        self._scroll.setFixedHeight(_LIST_HEIGHT)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: transparent; width: 6px; margin: 0 2px 0 0; }"
            f"QScrollBar::handle:vertical {{ background: {SiColors.SCROLLBAR}; border-radius: 3px; min-height: 30px; }}"
            f"QScrollBar::handle:vertical:hover {{ background: {SiColors.SCROLLBAR_HOVER}; }}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._host = QWidget()
        self._host.setStyleSheet("background: transparent;")
        self._list_lay = QVBoxLayout(self._host)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(6)
        self._scroll.setWidget(self._host)
        lay.addWidget(self._scroll, stretch=1)

        self._empty = QLabel("暂无卡片\n点击右上角编辑图标添加")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setStyleSheet(f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 9pt;")
        self._empty.hide()
        lay.addWidget(self._empty)

        # 底部小爱输入条：有小爱音箱才显示，复用主页悬浮球同款交互
        self._voice_frame = QFrame()
        self._voice_frame.setObjectName("voiceInputBar")
        self._voice_frame.setFixedHeight(36)
        self._voice_frame.setStyleSheet(
            f"QFrame#voiceInputBar {{ background: {SiColors.FLOAT_SURFACE}; border: 1px solid {SiColors.FLOAT_BORDER}; border-radius: 18px; }}")
        voice_lay = QHBoxLayout(self._voice_frame)
        voice_lay.setContentsMargins(10, 4, 10, 4)
        self._voice_edit = QLineEdit()
        self._voice_edit.setFont(QFont("Microsoft YaHei UI", 9))
        self._voice_edit.setStyleSheet(f"QLineEdit {{ background: transparent; border: none; color: {SiColors.TEXT_PRIMARY}; }}")
        self._voice_edit.installEventFilter(self)
        self._voice_edit.returnPressed.connect(self._emit_voice)
        voice_lay.addWidget(self._voice_edit)
        send_btn = QPushButton()
        send_btn.setFixedSize(28, 28)
        send_btn.setIcon(qta.icon('mdi.keyboard-outline', color=SiColors.ON_THEME_TEXT))
        send_btn.setIconSize(QSize(24, 24))
        send_btn.setAccessibleName("发送小爱指令")
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.setAutoDefault(False)
        send_btn.setStyleSheet(
            f"QPushButton {{ background: {SiColors.THEME}; border: none; border-radius: 7px; }}"
            f"QPushButton:hover {{ background: {SiColors.THEME_HOVER}; }}"
            f"QPushButton:pressed {{ background: {SiColors.THEME_PRESSED}; }}")
        send_btn.clicked.connect(self._emit_voice)
        voice_lay.addWidget(send_btn)
        self._voice_frame.hide()
        # 占位打字机与主页悬浮球共用同一实现：常量、节奏、停留
        self._hint_full = "对小爱输入“打开卧室灯”，回车执行"
        self._typewriter = TypewriterPlaceholder(self._voice_edit, self._hint_full)

        # 底部输入框：占满宽度
        lay.addWidget(self._voice_frame)

        # 音箱音频控制栏：不放在设备卡片内，顶部单独界面
        self._audio_bar = _TrayAudioBar(service, jobs, self)
        self._audio_bar.speaker_requested.connect(self._show_speaker_menu)

        self._panel = QFrame(self)
        self._panel.setObjectName("trayUnifiedPanel")
        self._panel.setStyleSheet(
            f"QFrame#trayUnifiedPanel {{ background: {SiColors.CARD}; border: 1px solid {SiColors.LINE}; border-radius: 6px; }}")
        self._panel_shadow = QGraphicsDropShadowEffect(self._panel)
        self._panel_shadow.setBlurRadius(10)
        self._panel_shadow.setOffset(0, 0)
        self._panel_shadow.setColor(QColor(0, 0, 0, 45))
        self._panel.setGraphicsEffect(self._panel_shadow)
        self._separator = QFrame()
        self._separator.setFixedHeight(1)
        self._separator.setStyleSheet("background: transparent; border: none;")
        self._separator.hide()
        divider_row = QHBoxLayout()
        divider_row.setContentsMargins(14, 0, 14, 0)
        divider_row.addStretch(3)
        divider_row.addWidget(self._separator, 14)
        divider_row.addStretch(3)
        self._outer_lay = QVBoxLayout(self._panel)
        self._outer_lay.setContentsMargins(0, 0, 0, 0)
        self._outer_lay.setSpacing(0)
        self._outer_lay.addWidget(self._audio_bar)
        self._outer_lay.addLayout(divider_row)
        self._outer_lay.addWidget(self._root)
        window_lay = QVBoxLayout(self)
        window_lay.setContentsMargins(_SHADOW_PAD, _SHADOW_PAD, _SHADOW_PAD, _SHADOW_PAD)
        window_lay.addWidget(self._panel)
        self.resize(_PANEL_WIDTH + 2 * _SHADOW_PAD, 480 + 2 * _SHADOW_PAD)
        self.setMinimumSize(280 + 2 * _SHADOW_PAD, 280 + 2 * _SHADOW_PAD)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._tray_dids: list[str] = tray_store.load()
        # 场景与统一顺序缓存：呼出时从 tray_store 刷新（见 _rebuild / show_near_tray）
        self._tray_scenes: list[dict] | None = None
        self._tray_order: list[dict] | None = None
        # 呼出/隐藏动画与点击外部隐藏
        self._target_pos: QPoint | None = None
        self._show_anim: QParallelAnimationGroup | None = None
        self._hide_anim: QParallelAnimationGroup | None = None
        self._pointer_has_entered = False
        self._leave_timer = QTimer(self)
        self._leave_timer.setSingleShot(True)
        self._leave_timer.setInterval(300)
        self._leave_timer.timeout.connect(self._hide_after_pointer_leave)
        self._outside_filter_installed = False
        self._tray_visible: bool = False  # 显式呼出状态（Tool 窗口失焦时 isVisible 会误报 False）
        self._drag_start_global = None
        self._drag_start_pos = None
        self._dragging = False
        self._audio_drag_handle = self._make_drag_handle(self._audio_bar)
        self._audio_bar._drag_header.layout().addSpacing(16)
        self._quick_drag_handle = self._make_drag_handle(self._drag_header)
        header.insertWidget(2, self._quick_drag_handle)
        self._drag_surfaces = (self._drag_header, self._drag_title,
                               self._audio_bar._drag_header,
                               self._audio_drag_handle, self._quick_drag_handle)
        for surface in self._drag_surfaces:
            surface.setCursor(Qt.ArrowCursor)
            surface.installEventFilter(self)
        # Include the padding above the audio header: it is the visual top bar.
        for surface in (self, self._panel, self._audio_bar):
            surface.installEventFilter(self)

    def _make_drag_handle(self, parent):
        handle = QLabel(parent)
        handle.setFixedSize(16, 16)
        handle.setPixmap(_svg_icon('tray-move.svg', '#666666').pixmap(16, 16))
        handle.setStyleSheet('background: transparent; border: none;')
        handle.setAccessibleName('拖动调整浮窗位置')
        return handle

    def is_animating(self) -> bool:
        """呼出/隐藏动画是否正在进行。"""
        return self._show_anim is not None or self._hide_anim is not None

    def abort_toggle_animation(self) -> None:
        """终止进行中的呼出/隐藏动画并复位透明度（托盘图标切换显隐用）。"""
        for anim in (self._show_anim, self._hide_anim):
            if anim is not None:
                try:
                    anim.stop()  # 中途停止不发 finished，须手动清理
                except Exception:
                    pass
                anim.deleteLater()
        self._show_anim = None
        self._hide_anim = None
        self.setWindowOpacity(1.0)

    def is_explicitly_visible(self) -> bool:
        """显式呼出状态（Tool 窗口失焦时 isVisible 会误报 False）。"""
        return self._tray_visible

    def _refresh_cols_btn(self) -> None:
        """图标与提示跟随当前列数：横向条目为单列，并排条目为双列。"""
        if self._columns == 1:
            tip = "单列显示，点击切换双列"
        else:
            tip = "双列显示，点击切换单列"
        self._cols_btn.setIcon(_svg_icon("tray-layout.svg", "#484848"))
        self._cols_btn.setAccessibleName(tip)

    def _toggle_columns(self) -> None:
        self._columns = 1 if self._columns == 2 else 2
        settings_store.set_tray_columns(self._columns)
        self._refresh_cols_btn()
        self._rebuild()

    def set_devices(self, devices: list[DeviceInfo], known_power: dict[str, bool | None]) -> None:
        """由主窗口在设备列表刷新后调用，传入全量设备与开关记忆。"""
        self._devices = list(devices)
        self._known_power = dict(known_power)
        self._tray_dids = tray_store.load()
        self._tray_scenes = tray_store.load_scenes()
        self._tray_order = tray_store.load_order()
        self._update_audio_bar()
        self._update_voice_bar()
        if self.isVisible():
            self._rebuild()
            # 不再 adjustSize——它会按 sizeHint 漏算语音条/音频栏，导致窗口逐次缩短

    def set_metrics(self, metrics: dict[str, str | None]) -> None:
        """主窗口温湿度读数同步：更新内存并就地刷新可见行副标题。"""
        import shiboken6

        if not shiboken6.isValid(self):
            return
        self._metrics = dict(metrics)
        if not self.isVisible():
            return
        for did, text in metrics.items():
            sub = self._sub_labels.get(did)
            if sub is None or not shiboken6.isValid(sub):
                continue
            dev = next((d for d in self._devices if d.did == did), None)
            if dev is None:
                continue
            if dev.online:
                sub_text = f"{dev.room_name} | {text}" if text else dev.room_name
            else:
                sub_text = f"{dev.room_name} · 离线"
            self._set_elided(sub, sub_text, self._sub_widths.get(did))

    def _update_voice_bar(self) -> None:
        has_speaker = any(is_speaker(d) and d.online for d in self._devices)
        was_visible = self._voice_frame.isVisible()
        self._voice_frame.setVisible(has_speaker)
        if has_speaker and self.isVisible():
            # 仅在由隐藏变显示或尚未启动时才开跑，避免轮询 set_devices 每 5s 重置打字
            if not was_visible or not self._typewriter.is_active():
                # 若正处于 1.8s 停留期（timer 已停但占位为全句），不打断
                if self._voice_edit.placeholderText() != self._hint_full:
                    self._typewriter.start()
        else:
            self._typewriter.stop(clear=True)
        self._sync_tray_height()

    def _pick_speaker(self) -> DeviceInfo | None:
        """输出音箱：设置的默认音箱（在线时）优先，否则第一个在线音箱。"""
        pref = settings_store.get_default_speaker_did()
        if pref:
            for d in self._devices:
                if d.did == pref and is_speaker(d) and d.online:
                    return d
        return next((d for d in self._devices if is_speaker(d) and d.online), None)

    def _update_audio_bar(self) -> None:
        # 有在线小爱音箱时显示音频控制栏；无则隐藏
        speaker = self._pick_speaker()
        if speaker is not None:
            self._audio_bar.set_speaker(speaker.did, speaker.name)
        else:
            self._audio_bar.set_speaker(None)
        self._quick_drag_handle.setVisible(speaker is None)
        self._sync_tray_height()

    def _show_speaker_menu(self) -> None:
        menu = QMenu(self)
        menu.setWindowFlag(Qt.FramelessWindowHint, True)
        menu.setWindowFlag(Qt.NoDropShadowWindowHint, True)
        menu.setAttribute(Qt.WA_TranslucentBackground, True)
        menu.setFont(QFont("Microsoft YaHei UI", 10))
        menu.setMinimumWidth(180)
        menu.setStyleSheet(
            f"QMenu {{ background: {SiColors.CARD}; border: 1px solid {SiColors.LINE};"
            " border-radius: 10px; padding: 6px; font-size: 10pt; }"
            f"QMenu::item {{ color: {SiColors.TEXT_PRIMARY}; padding: 8px 16px 8px 10px; border-radius: 6px; }}"
            f"QMenu::item:selected {{ background: {SiColors.BTN_HOVER}; }}"
            f"QMenu::item:disabled {{ color: {SiColors.TEXT_DISABLED}; }}")
        pref = settings_store.get_default_speaker_did()
        options = [("", "自动（第一个在线音箱）", True)]
        speakers = sorted((d for d in self._devices if is_speaker(d)),
                          key=lambda d: (not d.online, d.name, d.did))
        options.extend((d.did, f"{d.name}（{d.room_name}）" + (" · 离线" if not d.online else ""),
                        d.online) for d in speakers)
        for did, label, online in options:
            action = menu.addAction(label)
            action.setFont(menu.font())
            action.setEnabled(online)
            if did == pref:
                action.setIcon(qta.icon('mdi.check', color=SiColors.THEME_DIM))
            action.triggered.connect(lambda _, value=did: self._select_speaker(value))
        button = self._audio_bar._speaker_btn
        self._leave_timer.stop()
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()) + QPoint(0, 6))
        menu.deleteLater()
        if not self.underMouse():
            self._leave_timer.start()

    def _select_speaker(self, did: str) -> None:
        if did and not any(d.did == did and is_speaker(d) and d.online for d in self._devices):
            return
        settings_store.set_default_speaker_did(did)
        self._update_audio_bar()
        self.speaker_changed.emit()

    def _sync_tray_height(self) -> None:
        # 确定性计算窗口高度，不依赖 adjustSize（隐藏态会漏算语音条/音频栏）：
        # 由各固定子控件高度累加，显隐结果一致，呼出前即可得到正确尺寸避免闪烁；
        # 已显示时外扩并保持底部贴边，避免语音/音频栏显隐挤压卡片
        self._separator.setVisible(not self._audio_bar.isHidden())
        self._root.layout().setContentsMargins(12, 4 if not self._audio_bar.isHidden() else 8, 12, 10)
        audio_h = 0
        if not self._audio_bar.isHidden():
            ah = self._audio_bar.sizeHint().height()
            audio_h = (ah if ah > 0 else 96) + 1  # 外层 spacing
        voice_h = 36 + 8 if not self._voice_frame.isHidden() else 0  # 36 + 间距10
        # 根面板：标题 + 固定列表区域 + 内容边距和间距
        root_margins = self._root.layout().contentsMargins()
        root_h = 26 + _LIST_HEIGHT + root_margins.top() + root_margins.bottom() + 16
        h = audio_h + root_h + voice_h + 2 * _SHADOW_PAD
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            max_h = screen.availableGeometry().height() - 20
            h = min(h, max_h)
        h = max(h, self.minimumHeight())
        if abs(h - self.height()) < 2:
            return
        if self._tray_visible:
            old_h = self.height()
            self.resize(self.width(), h)
            delta = h - old_h
            geo = self.geometry()
            self.move(geo.x(), geo.y() - delta)
        else:
            self.resize(self.width(), h)

    def _emit_voice(self) -> None:
        text = self._voice_edit.text().strip()
        if not text:
            return
        speaker = self._pick_speaker()
        if speaker is None:
            return
        # 设置的默认音箱不在线/不在列表 → 已回退：提示里说明，并把
        # 设置回退为「自动」（否则偏好一直指向离线设备，每次都要回退）
        pref = settings_store.get_default_speaker_did()
        fallback_note = ""
        if pref and pref != speaker.did:
            fallback_note = f"（首选音箱离线，已由「{speaker.name}」代答）"
            settings_store.set_default_speaker_did("")
        self._voice_edit.clear()
        self._jobs.submit(
            lambda: self._service.run_action(speaker.did, "execute-text-directive", [text]),
            on_success=lambda _, note=fallback_note, did=speaker.did: self._on_voice_success(text, note, did),
            on_error=lambda e: self._on_voice_error(e),
        )

    def _on_voice_success(self, text: str, fallback_note: str = "", did: str = "") -> None:
        self._audio_bar.refresh_after_command(did)
        from app.ui.toast import Toast
        Toast.info(self, f"已告诉小爱同学：{text}{fallback_note}", 3000)

    def _on_voice_error(self, err: Exception) -> None:
        from app.ui.toast import Toast
        Toast.info(self, f"执行失败：{err}", 4000)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is getattr(self, '_audio_bar', None) and event.type() == QEvent.Resize:
            # Include the panel's 1px inset: visible top/right gaps are both 12px.
            self._audio_drag_handle.move(self._audio_bar.width() - 27, 11)
        drag_surface = obj in getattr(self, '_drag_surfaces', (
            getattr(self, '_drag_header', None), getattr(self, '_drag_title', None)))
        if obj in (self, getattr(self, '_panel', None), getattr(self, '_audio_bar', None)) and event.type() in (
                QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.MouseButtonRelease):
            header = (self._audio_bar._drag_header if not self._audio_bar.isHidden() else self._drag_header)
            bottom = header.mapTo(self, QPoint(0, header.height())).y()
            y = self.mapFromGlobal(event.globalPosition().toPoint()).y()
            drag_surface = self._drag_start_global is not None or _SHADOW_PAD <= y <= bottom
        if drag_surface:
            kind = event.type()
            if kind == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._drag_start_global = event.globalPosition().toPoint()
                self._drag_start_pos = self.pos()
                self._leave_timer.stop()
                event.accept()
                return True
            if kind == QEvent.MouseMove and self._drag_start_global is not None and event.buttons() & Qt.LeftButton:
                from PySide6.QtWidgets import QApplication
                from PySide6.QtGui import QGuiApplication
                delta = event.globalPosition().toPoint() - self._drag_start_global
                if self._dragging or delta.manhattanLength() >= QApplication.startDragDistance():
                    if not self._dragging:
                        self.abort_toggle_animation()
                    self._dragging = True
                    screen = QGuiApplication.screenAt(event.globalPosition().toPoint()) or self.screen()
                    self.move(self._clamp_position(self._drag_start_pos + delta, screen))
                event.accept()
                return True
            if kind == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton and self._drag_start_global is not None:
                if self._dragging:
                    self._save_position()
                self._drag_start_global = self._drag_start_pos = None
                self._dragging = False
                event.accept()
                return True
        if obj is getattr(self, "_voice_edit", None) and event.type() == event.Type.KeyPress and event.key() == Qt.Key_Escape:
            self._voice_edit.clear()
            return True
        if not self.isVisible():
            return super().eventFilter(obj, event)
        # 只监听失活事件（点击托盘图标、切到其他应用/桌面），不监听全局
        # MouseButtonPress——点击托盘图标本身就是窗口外点击，若用 MouseButtonPress
        # 判断窗口外会与呼出竞态，造成"开了又关/闪烁"
        et = event.type()
        if et in (QEvent.WindowDeactivate, QEvent.ApplicationDeactivate):
            # 呼出动画期间不隐藏，等动画完成再评估
            if self._show_anim is not None:
                return super().eventFilter(obj, event)
            if not self.underMouse():
                QTimer.singleShot(20, self._maybe_hide_on_deactivate)
            return super().eventFilter(obj, event)
        return super().eventFilter(obj, event)

    def _maybe_hide_on_deactivate(self) -> None:
        import shiboken6

        if not shiboken6.isValid(self) or not self.isVisible() or self._show_anim is not None or self._dragging:
            return
        # 只有真正失活且鼠标不在托盘窗口内才隐藏
        if self.isActiveWindow() or self.underMouse():
            return
        # 若当前激活窗口是本应用的其他窗口（主窗口/管理对话框/设备详情），
        # 则不应隐藏托盘——用户只是切到了我方另一个窗口
        from PySide6.QtWidgets import QApplication
        active = QApplication.activeWindow()
        if active is not None and active is not self:
            # 管理对话框/详情是顶层窗口，主窗口也可能是，需判断是否同属本应用
            top = active.window()
            if top is not None and top is not self:
                return
        if not self._pointer_has_entered:
            if not self._leave_timer.isActive():
                self._leave_timer.start()
            return
        self.hide_animated()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._pointer_has_entered = True
        self._leave_timer.stop()
        self._leave_timer.setInterval(300)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._pointer_has_entered and not self._dragging:
            self._leave_timer.start()
        super().leaveEvent(event)

    def _hide_after_pointer_leave(self) -> None:
        from PySide6.QtGui import QCursor
        from PySide6.QtWidgets import QApplication
        if not self.isVisible() or self._dragging or self.frameGeometry().contains(QCursor.pos()):
            return
        if QApplication.activePopupWidget() is not None:
            self._leave_timer.start()
            return
        if QApplication.mouseButtons() != Qt.NoButton:
            self._leave_timer.start()
            return
        self.hide_animated()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # 延迟安装，避免托盘那一下 MouseButtonPress 立刻又触发隐藏
        QTimer.singleShot(120, self._install_outside_filter)

    def hideEvent(self, event) -> None:  # noqa: N802
        self._tray_visible = False
        self._drag_start_global = self._drag_start_pos = None
        self._dragging = False
        self._pointer_has_entered = False
        self._leave_timer.stop()
        self._typewriter.stop()
        self._remove_outside_filter()
        super().hideEvent(event)

    def _install_outside_filter(self) -> None:
        import shiboken6

        if not shiboken6.isValid(self) or self._outside_filter_installed:
            return
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
            self._outside_filter_installed = True

    def _remove_outside_filter(self) -> None:
        if not self._outside_filter_installed:
            return
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            try:
                app.removeEventFilter(self)
            except Exception:
                pass
        self._outside_filter_installed = False

    def refresh_power(self, dids: list[str]) -> None:
        if not dids:
            return
        self._jobs.submit(
            lambda: self._service.power_states(dids),
            on_success=self._apply_power,
            on_error=lambda _: None,
        )

    def _apply_power(self, states: dict[str, bool | None]) -> None:
        import shiboken6

        if not shiboken6.isValid(self):
            return
        for did, st in states.items():
            self._known_power[did] = st
        # 遍历 QGridLayout 直接子项
        grid = getattr(self, "_grid", None)
        if grid is None:
            return
        for did, st in states.items():
            for i in range(grid.count()):
                w = grid.itemAt(i).widget()
                if w is not None and getattr(w, "_did", None) == did:
                    btn = getattr(w, "_power_btn", None)
                    if btn is not None:
                        btn.set_state(st)
                    break

    def _rebuild(self) -> None:
        self._destroy_grid()
        dids = getattr(self, "_tray_dids", None)
        if dids is None:
            dids = self._tray_dids = tray_store.load()
        scene_data = getattr(self, "_tray_scenes", None)
        if scene_data is None:
            scene_data = self._tray_scenes = tray_store.load_scenes()
        order = getattr(self, "_tray_order", None)
        if order is None:
            order = self._tray_order = tray_store.load_order()
        lookup = {d.did: d for d in self._devices}
        did_set = set(dids)
        scene_map = {s["scene_id"]: SceneInfo(**s) for s in scene_data}
        # 设备与场景按统一排序混排；不在 order 里的（异常文件兜底）追加末尾
        rows: list[QFrame] = []
        seen: set[tuple[str, str]] = set()
        for item in order:
            t, i = item["type"], item["id"]
            if t == "device" and i in did_set and lookup.get(i) is not None:
                rows.append(self._make_row(lookup[i]))
            elif t == "scene" and i in scene_map:
                rows.append(self._make_scene_row(scene_map[i]))
            else:
                continue
            seen.add((t, i))
        for d in dids:
            if ("device", d) not in seen and lookup.get(d) is not None:
                rows.append(self._make_row(lookup[d]))
                seen.add(("device", d))
        for s in scene_data:
            sid = s["scene_id"]
            if ("scene", sid) not in seen:
                rows.append(self._make_scene_row(scene_map[sid]))
                seen.add(("scene", sid))
        if not rows:
            self._empty.show()
            self._scroll.hide()
            return
        self._empty.hide()
        self._scroll.show()
        # 使用 QGridLayout + setColumnStretch 强制各列等宽，单卡也能保持列宽
        cols = self._columns
        self._grid = QGridLayout()
        self._grid.setContentsMargins(0, 0, 0, 0)
        for c in range(cols):
            self._grid.setColumnStretch(c, 1)
        self._grid.setHorizontalSpacing(6)
        self._grid.setVerticalSpacing(6)
        for idx, row in enumerate(rows):
            self._grid.addWidget(row, idx // cols, idx % cols)
        self._list_lay.addLayout(self._grid)
        self._list_lay.addStretch(1)
        online_dids = [d for d in dids if lookup.get(d) and lookup[d].online and self._known_power.get(d) is None]
        if online_dids:
            self.refresh_power(online_dids)

    def _destroy_grid(self) -> None:
        grid = getattr(self, "_grid", None)
        if grid is None:
            return
        # 移除 _list_lay 中的 grid 布局项
        for i in range(self._list_lay.count()):
            item = self._list_lay.itemAt(i)
            if item and item.layout() is grid:
                self._list_lay.takeAt(i)
                break
        # 清理 grid 中的 widget
        while grid.count():
            it = grid.takeAt(0)
            if w := it.widget():
                w.deleteLater()
        grid.deleteLater()
        self._grid = None
        self._sub_labels.clear()
        self._sub_widths.clear()
        # 移除多余的 stretch
        for i in range(self._list_lay.count() - 1, -1, -1):
            item = self._list_lay.itemAt(i)
            if item and item.spacerItem():
                self._list_lay.takeAt(i)
                break

    def _card_text_width(self, has_power: bool) -> int:
        """卡片文本列的可用宽度（窗口宽固定，各边距确定，可直接算出）。

        卡片内文本不省略时 QLabel 最小宽取整段文本，温湿度+开关会把
        列宽撑爆、整个网格溢出面板；所有文本都按此宽度省略兜底。
        """
        # 根面板左右边距 24 + 列间距 6×(cols-1)，滚动条不占宽度
        inner = self.width() - 2 * _SHADOW_PAD - 24 - 6 * (self._columns - 1)
        col = inner / self._columns
        # 卡片左右边距 20 + 状态点 6 + 间距 10；有开关时再留 28+10
        return max(36, round(col - 20 - 6 - 10 - (38 if has_power else 0)))

    @staticmethod
    def _set_elided(label: QLabel, text: str, width: int | None) -> None:
        """按可用宽度省略显示文本，不显示悬停文字。"""
        if width is None:
            label.setText(text)
        else:
            label.setText(label.fontMetrics().elidedText(
                text, Qt.ElideRight, width))
        label.setToolTip("")

    def _make_row(self, dev: DeviceInfo) -> QFrame:
        row = QFrame()
        row.setObjectName("trayRow")
        row.setAttribute(Qt.WA_StyledBackground, True)
        row.setFixedHeight(_CARD_HEIGHT)
        from PySide6.QtWidgets import QSizePolicy
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row.setStyleSheet(
            f"QFrame#trayRow {{ background: {SiColors.TRAY_CARD}; border: none; border-radius: 9px; }}"
            f"QFrame#trayRow:hover {{ background: {SiColors.TRAY_CARD_HOVER}; }}")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 5, 10, 5)
        lay.setSpacing(10)

        status = QLabel()
        status.setFixedSize(6, 6)
        status.setStyleSheet(
            f"background: {SiColors.ONLINE if dev.online else SiColors.OFFLINE_SUB}; border-radius: 3px;")
        lay.addWidget(status)

        known = self._known_power.get(dev.did)
        avail = self._card_text_width(known is not None)
        is_camera = '.camera.' in dev.model

        text_col = QVBoxLayout()
        if is_camera:
            text_col.setContentsMargins(0, 8, 0, 0)
        text_col.setSpacing(2)
        name = QLabel()
        name.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.Medium))
        name.setStyleSheet(f"color: {SiColors.TEXT_PRIMARY if dev.online else SiColors.OFFLINE_TEXT}; background: transparent; font-size: 9pt; font-weight: 500;")
        # 水平 Ignored：布局可无限压缩标签，文本绝不可能把列撑宽
        # （setMinimumWidth(0) 无效——qSmartMinSize 只认 >0 的显式最小宽）
        name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._set_elided(name, dev.name, avail)
        # 副标题：在线仅显示房间（+温湿度），离线才追加“· 离线”
        metrics = self._metrics.get(dev.did)
        if dev.online:
            sub_text = f"{dev.room_name} | {metrics}" if metrics else dev.room_name
        else:
            sub_text = f"{dev.room_name} · 离线"
        sub = QLabel()
        # setFont 提供与渲染一致的 fontMetrics；但应用级 QSS `*{font-size:10pt}`
        # 会盖掉 setFont，故样式表里也要写 8pt，两者缺一度量与渲染就不一致
        sub.setFont(QFont("Microsoft YaHei UI", 8))
        sub.setStyleSheet(f"color: {SiColors.TEXT_SECONDARY if dev.online else f'{SiColors.OFFLINE_SUB}'}; background: transparent; font-size: 8pt;")
        sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._set_elided(sub, sub_text, avail)
        self._sub_labels[dev.did] = sub
        self._sub_widths[dev.did] = avail
        text_col.addWidget(name)
        text_col.addWidget(sub)
        lay.addLayout(text_col, stretch=1)

        btn = None
        if known is not None:
            btn = PowerButton(28, icon_size=22)
            btn.set_state(known)
            def _on_toggle(checked=False, d=dev.did, b=btn):
                b.set_busy(True)
                self._jobs.submit(
                    lambda: self._service.toggle_power(d),
                    on_success=lambda ns, dd=d, bb=b: self._on_toggle_done(dd, ns, bb),
                    on_error=lambda e, bb=b: bb.set_busy(False),
                )
            btn.clicked.connect(_on_toggle)
            lay.addWidget(btn)
        row._did = dev.did  # type: ignore[attr-defined]
        row._power_btn = btn  # type: ignore[attr-defined]
        if is_camera:
            from app.ui.tray.camera_corner_tag import CameraCornerTag
            tag = CameraCornerTag(row)
            tag.raise_()

        row.mousePressEvent = lambda e, d=dev.did: self.open_device_requested.emit(d) if e.button() == Qt.LeftButton else None
        row.setCursor(Qt.PointingHandCursor)
        return row

    def _on_toggle_done(self, did: str, ns: bool, btn) -> None:
        self._known_power[did] = ns
        btn.set_state(ns)
        btn.set_busy(False)

    # ---------- 场景行 ----------

    def _make_scene_row(self, scene: SceneInfo) -> QFrame:
        row = QFrame()
        row.setObjectName("trayRow")
        row.setAttribute(Qt.WA_StyledBackground, True)
        row.setFixedHeight(_CARD_HEIGHT)
        from PySide6.QtWidgets import QSizePolicy
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        row.setStyleSheet(
            f"QFrame#trayRow {{ background: {SiColors.TRAY_CARD}; border: none; border-radius: 9px; }}"
            f"QFrame#trayRow:hover {{ background: {SiColors.TRAY_CARD_HOVER}; }}")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(10, 5, 10, 5)
        lay.setSpacing(10)

        avail = self._card_text_width(True)
        scene_icon = QLabel()
        scene_icon.setFixedSize(6, 6)
        scene_icon.setStyleSheet(f"background: {SiColors.THEME}; border-radius: 3px;")
        lay.addWidget(scene_icon)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        name = QLabel()
        name.setFont(QFont("Microsoft YaHei UI", 9, QFont.Weight.Medium))
        name.setStyleSheet(f"color: {SiColors.TEXT_PRIMARY}; background: transparent; font-size: 9pt; font-weight: 500;")
        name.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._set_elided(name, scene.name, avail)
        sub = QLabel()
        sub.setFont(QFont("Microsoft YaHei UI", 8))
        sub.setStyleSheet(f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 8pt;")
        sub.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._set_elided(sub, scene.home_name or "手动场景", avail)
        text_col.addWidget(name)
        text_col.addWidget(sub)
        lay.addLayout(text_col, stretch=1)

        btn = QPushButton()
        btn.setObjectName("sceneRunBtn")
        btn.setFixedSize(28, 28)
        btn.setIconSize(QSize(18, 18))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setAccessibleName("执行场景")
        self._apply_scene_btn(btn, busy=False)
        btn.clicked.connect(lambda _, s=scene, b=btn: self._run_scene(s, b))
        lay.addWidget(btn)
        row._scene_id = scene.scene_id  # type: ignore[attr-defined]
        return row

    def _apply_scene_btn(self, btn: QPushButton, busy: bool) -> None:
        btn.setEnabled(not busy)
        if busy:
            btn.setIcon(qta.icon('mdi.play', color=SiColors.ICON_DIM))
            btn.setStyleSheet(
                f"QPushButton#sceneRunBtn {{ background: {SiColors.SURFACE_PRESSED};"
                f" border: none; border-radius: 14px; }}")
            return
        btn.setIcon(qta.icon('mdi.play', color=SiColors.ON_THEME_TEXT))
        btn.setStyleSheet(
            f"QPushButton#sceneRunBtn {{ background: {SiColors.THEME}; border: none;"
            f" border-radius: 14px; }}"
            f"QPushButton#sceneRunBtn:hover {{ background: {SiColors.THEME_HOVER}; }}"
            f"QPushButton#sceneRunBtn:pressed {{ background: {SiColors.THEME_DIM}; }}")

    def _run_scene(self, scene: SceneInfo, btn: QPushButton) -> None:
        # 与主界面场景卡一致：点击即执行（无二次确认），执行中置忙碌态
        self._apply_scene_btn(btn, busy=True)
        self._jobs.submit(
            lambda: self._service.run_scene(scene),
            on_success=lambda _, s=scene, b=btn: self._on_scene_done(s, b),
            on_error=lambda e, s=scene, b=btn: self._on_scene_failed(s, b, e),
        )

    def _on_scene_done(self, scene: SceneInfo, btn: QPushButton) -> None:
        import shiboken6

        if not shiboken6.isValid(self) or not shiboken6.isValid(btn):
            return
        self._apply_scene_btn(btn, busy=False)
        Toast.info(self, f"已执行场景「{scene.name}」", 2200)

    def _on_scene_failed(self, scene: SceneInfo, btn: QPushButton, error: Exception) -> None:
        import shiboken6

        if not shiboken6.isValid(self) or not shiboken6.isValid(btn):
            return
        self._apply_scene_btn(btn, busy=False)
        Toast.info(self, f"执行场景「{scene.name}」失败：{error}", 4000)

    def show_near_tray(self) -> None:
        """在托盘附近或屏幕右下角显示，显示前重建以保证与托盘存储一致。"""
        self._tray_dids = tray_store.load()
        self._tray_scenes = tray_store.load_scenes()
        self._tray_order = tray_store.load_order()
        self._rebuild()
        # 顶部音频栏与语音输入条显隐需在计算弹出位置前确定，以便窗口高度正确
        self._update_audio_bar()
        self._update_voice_bar()
        # 托盘内的温湿度设备在显示时补拉一次读数，确保副标题及时带上温湿度
        try:
            dids = [d for d in self._tray_dids if self._metrics.get(d) is None]
            if dids:
                self._jobs.submit(
                    lambda: self._service.read_metrics(dids),
                    on_success=lambda m: self.set_metrics({**self._metrics, **{k: v for k, v in m.items() if v}}),  # noqa: E501
                    on_error=lambda _: None,
                )
        except Exception:
            pass
        # 先显示并同步高度，再计算弹出位置，避免首帧用未校正高度导致压住任务栏
        self._play_show_animation()

    def _play_show_animation(self) -> None:
        # 若正在隐藏，先停掉
        if self._hide_anim is not None:
            try:
                self._hide_anim.stop()  # 中途停止不发 finished，须手动清理
            except Exception:
                pass
            self._hide_anim.deleteLater()
            self._hide_anim = None
        if self._show_anim is not None:
            try:
                self._show_anim.stop()
            except Exception:
                pass
            self._show_anim.deleteLater()
            self._show_anim = None
        # 呼出前先同步高度（隐藏态确定性计算），保证窗口尺寸在显示前即正确，
        # 避免显示后再 resize 造成闪烁
        self._sync_tray_height()
        target = self._popup_position()
        self._target_pos = target
        self._pointer_has_entered = False
        self._leave_timer.stop()
        self._leave_timer.setInterval(3000)
        # 动画起点：目标下方 4px + 透明 0，全部在隐藏态摆好，只 show 一次
        start = QPoint(target.x(), target.y() + 4)
        self.move(start)
        self.setWindowOpacity(0.0)
        self._tray_visible = True
        self.show()
        self.raise_()
        self.activateWindow()
        group = QParallelAnimationGroup(self)
        pos_anim = QPropertyAnimation(self, b"pos", group)
        pos_anim.setStartValue(start)
        pos_anim.setEndValue(target)
        pos_anim.setDuration(180)
        pos_anim.setEasingCurve(QEasingCurve.OutCubic)
        op_anim = QPropertyAnimation(self, b"windowOpacity", group)
        op_anim.setStartValue(0.0)
        op_anim.setEndValue(1.0)
        op_anim.setDuration(180)
        op_anim.setEasingCurve(QEasingCurve.InOutQuad)
        group.addAnimation(pos_anim)
        group.addAnimation(op_anim)
        self._show_anim = group
        # 自然结束时清理；被打断的组在各 stop 处手动 deleteLater，
        # 否则旧组随每次显隐在窗口下不断堆积
        group.finished.connect(lambda: (
            setattr(self, "_show_anim", None),
            group.deleteLater(),
        ))
        group.start()

    def _clamp_position(self, point, screen):
        if screen is None:
            return point
        geo = screen.availableGeometry()
        return QPoint(max(geo.left(), min(point.x(), geo.right() + 1 - self.width())),
                      max(geo.top(), min(point.y(), geo.bottom() + 1 - self.height())))

    def _popup_position(self):
        from PySide6.QtGui import QGuiApplication, QCursor
        saved = settings_store.get_tray_position()
        screen = next((s for s in QGuiApplication.screens()
                       if saved and s.name() == saved['screen']), None)
        screen = screen or QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return self.pos()
        geo = screen.availableGeometry()
        point = (geo.topLeft() + QPoint(saved['x'], saved['y']) if saved else
                 QPoint(geo.right() + 1 - self.width(), geo.bottom() + 1 - self.height()))
        return self._clamp_position(point, screen)

    def _save_position(self):
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.screenAt(self.frameGeometry().center()) or self.screen()
        if screen is None:
            return
        point = self._clamp_position(self.pos(), screen)
        self.move(point)
        self._target_pos = point
        offset = point - screen.availableGeometry().topLeft()
        settings_store.set_tray_position(dict(screen=screen.name(), x=offset.x(), y=offset.y()))

    def reset_position(self):
        settings_store.set_tray_position(None)
        if self.isVisible():
            self.abort_toggle_animation()
            self._target_pos = self._popup_position()
            self.move(self._target_pos)

    def hide_animated(self) -> None:
        """带动画隐藏；已隐藏或正隐藏则直接返回。"""
        if not self.isVisible():
            return
        if self._hide_anim is not None:
            return
        if self._show_anim is not None:
            try:
                self._show_anim.stop()  # 中途停止不发 finished，须手动清理
            except Exception:
                pass
            self._show_anim.deleteLater()
            self._show_anim = None
        start = self.pos()
        end = QPoint(start.x(), start.y() + 4)
        group = QParallelAnimationGroup(self)
        pos_anim = QPropertyAnimation(self, b"pos", group)
        pos_anim.setStartValue(start)
        pos_anim.setEndValue(end)
        pos_anim.setDuration(160)
        pos_anim.setEasingCurve(QEasingCurve.InCubic)
        op_anim = QPropertyAnimation(self, b"windowOpacity", group)
        op_anim.setStartValue(self.windowOpacity() if self.windowOpacity() > 0 else 1.0)
        op_anim.setEndValue(0.0)
        op_anim.setDuration(160)
        op_anim.setEasingCurve(QEasingCurve.InOutQuad)
        group.addAnimation(pos_anim)
        group.addAnimation(op_anim)

        def _on_finished():
            self._hide_anim = None
            group.deleteLater()
            self.setWindowOpacity(1.0)
            # 避免递归触发 hideEvent 中的动画
            self.hide()

        group.finished.connect(_on_finished)
        self._hide_anim = group
        group.start()

    def focusOutEvent(self, event) -> None:  # noqa: N802
        super().focusOutEvent(event)
        QTimer.singleShot(20, self._maybe_hide)

    def _maybe_hide(self) -> None:
        import shiboken6

        if not shiboken6.isValid(self):
            return
        # 失焦触发：与 deactivate 同一套排除逻辑，避免管理对话框/详情
        # 等本应用窗口打开时误隐藏托盘
        if self._show_anim is not None or self._dragging or self.isActiveWindow() or self.underMouse():
            return
        from PySide6.QtWidgets import QApplication
        active = QApplication.activeWindow()
        if active is not None and active is not self:
            top = active.window()
            if top is not None and top is not self:
                return
        if not self._pointer_has_entered:
            if not self._leave_timer.isActive():
                self._leave_timer.start()
            return
        self.hide_animated()





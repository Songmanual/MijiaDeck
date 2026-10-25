# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""主窗口：米家 APP 风格的深色卡片视图。

顶部为家庭名与房间筛选 tab，中部是设备卡片网格（列数随窗口宽度
自适应）。卡片电源钮提供快速开关：设备列表接口不含开关状态，
首次点击先经详情接口确认能力，再读取当前值取反写入，成功后
把真实状态回填到卡片；点击卡片本体打开详情对话框。
"""

import ctypes
import ctypes.wintypes as wintypes
import logging
import sys
from pathlib import Path

import shiboken6
from PySide6.QtCore import QEvent, QPropertyAnimation, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import QGraphicsOpacityEffect, QGraphicsDropShadowEffect
from PySide6.QtGui import QAction, QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import qtawesome as qta

from app.core import cache as device_cache
from app.core import icon_store
from app.core.jobs import JobExecutor
from app.core.models import DeviceInfo, SceneInfo, is_speaker
from app.core.device_controls import prepare_device_cards, has_device_details, is_light
from app.core.service import MijiaService
from app.ui.device_card import DeviceCard
from app.ui.device_dialog import DeviceDetailDialog
from app.ui.window_caption import WindowCaption, BRAND_CAPTION_HEIGHT, RESIZE_MARGIN
from app.ui.scene_card import SceneCard
from app.ui.si_theme import SiColors
from app.ui.room_tabs import RoomTabStrip, RoomTab, build_room_menu
from app.ui.toast import Toast
from app.ui.tray import TrayController, TrayManagerDialog
from app.ui.voice_fab import VoiceFab, BOTTOM_RESERVED_HEIGHT
from app.ui.footer_bar import FooterBar
from app.ui.settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)

_ALL_ROOMS = "全屋"
_ALL_HOMES = "全部"
# 场景选项卡：位于「全屋」左侧的特殊房间值，选中后网格切换为场景视图
_SCENE_TAB = "场景"

# 外部（APP/语音）改状态后卡片靠轮询跟随；批量读一次请求
_POLL_INTERVAL_MS = 5_000
_METRICS_INTERVAL_MS = 5 * 60 * 1000


def _refresh_summary(total: int, added: int, removed: int) -> str:
    """刷新结果通知文案：有增减报增减，无变化明确告知。"""
    if not added and not removed:
        return f"设备列表无变化（共 {total} 台）"
    if added and removed:
        return f"本次刷新：新增 {added} 台，移除 {removed} 台"
    if added:
        return f"本次刷新：新增 {added} 台设备"
    return f"本次刷新：移除 {removed} 台设备"

# 无边框窗口的边缘拖拽热区宽度（像素）
_RESIZE_MARGIN = RESIZE_MARGIN
_TITLE_BAR_HEIGHT = BRAND_CAPTION_HEIGHT
_GRID_SPACING = 8

# Windows 原生窗口消息与命中测试代码
_WM_NCHITTEST = 0x0084
_WM_NCLBUTTONDBLCLK = 0x00A3
_HTCLIENT = 1
_HTCAPTION = 2
_HTLEFT = 10
_HTRIGHT = 11
_HTTOP = 12
_HTTOPLEFT = 13
_HTTOPRIGHT = 14
_HTBOTTOM = 15
_HTBOTTOMLEFT = 16
_HTBOTTOMRIGHT = 17


class MainWindow(QMainWindow):
    _loading_progress = Signal(int, int, str)
    def __init__(self):
        super().__init__()
        self._service = MijiaService()
        self._jobs = JobExecutor(self)

        from app import APP_NAME, resource_path
        self.setWindowIcon(QIcon(str(resource_path("app/ui/icon.png"))))
        self.setWindowTitle(APP_NAME)
        # 由 Qt 显式移除系统标题栏，避免 nativeEvent 时序变化时同时出现
        # 系统标题栏和自绘按钮。拖动/边缘命中仍通过 WM_NCHITTEST 交给系统。
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        # 默认窗口尺寸在首次显示时按真实 DPR 应用（见 showEvent）：
        # 构造期窗口未创建，DPR 读数不可靠（曾导致默认尺寸放大一圈）
        self._default_size_applied = False
        self.setMinimumSize(760, 520)

        self._all_devices: list[DeviceInfo] = []
        self._cards: dict[str, DeviceCard] = {}
        self._homes: list[str] = []
        self._current_home: str = ""
        self._current_room = _ALL_ROOMS
        self._settings_dialog: SettingsDialog | None = None
        # did -> 开关状态记忆；None 表示确认无开关能力。
        # 探测结论是设备的固有属性，跨家庭/房间/刷新复用；
        # 串行队列 FIFO 保证探测与开关写入的回调顺序不会互相覆盖
        self._known_power: dict[str, bool | None] = {}
        # did -> 环境读数文案（温湿度），随轮询更新、随网格重建回填
        self._metrics: dict[str, str | None] = {}
        # 刷新防重入：请求在途时忽略再次点击
        self._loading_devices = False
        self._load_generation = 0
        self._load_active = False
        self._load_full_page = False
        self._load_show_footer = False
        self._load_value = 0
        self._load_pending = set()
        self._load_had_failure = False
        self._account_transition = False
        self._logged_out = True
        self._login_dialog = None
        from app.core.availability import NetworkMonitor
        self._network_monitor = NetworkMonitor(self)
        self._network_online = self._network_monitor.online
        self._reconnecting = False
        self._connection_failed = False
        # 启动自动检查更新每次进程只做一次，避免 start 被重复触发
        self._update_check_done = False
        # 轮询防重入：上一轮批量读取未返回时跳过本轮定时触发
        self._poll_in_flight = False
        # 网格重排防抖：拖动窗口会触发密集 resizeEvent，全部重建
        # 卡片代价太高，等布局稳定且列数变化时才重建
        self._grid_columns = 0
        # 托盘常驻内存优化：窗口隐藏期间不构建卡片网格（数十个
        # 卡片控件 + 样式约占 20-30MB），标记脏位、首次显示时构建
        self._grid_dirty = False
        # 隐藏无可控制功能的设备（设置开关，默认关）
        from app.core.settings_store import get_hide_no_func_devices
        self._hide_no_func = get_hide_no_func_devices()
        # 场景选项卡（设置开关，默认开）与场景视图状态：
        # _scenes 为 None 表示尚未加载，空列表为「确认无场景」
        from app.core.settings_store import get_show_scene_tab
        self._show_scene_tab = get_show_scene_tab()
        self._scenes: list[SceneInfo] | None = None
        self._scene_cards: dict[str, SceneCard] = {}
        # 场景列表后台拉取防重入
        self._loading_scenes = False
        # 产品页名称回退的异步查询防重入
        self._localize_busy = False
        # DPI 变化时恢复期望逻辑尺寸：Qt 在缩放变化后保持物理尺寸
        # （逻辑尺寸被重算），窗口会显得偏大且底部留白；这里记住
        # 用户视角的逻辑尺寸，变化后恢复，让窗口跟随元素一起缩放
        self._expected_logical: tuple[int, int] | None = None
        self._last_dpr: float | None = None
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(60)
        self._resize_timer.timeout.connect(self._on_resize_settled)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(_POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._on_poll_tick)
        self._metrics_timer = QTimer(self)
        self._metrics_timer.setInterval(_METRICS_INTERVAL_MS)
        self._metrics_timer.timeout.connect(self._refresh_metrics)
        self._metrics_timer.timeout.connect(self._push_tray_metrics)

        # 右下角小爱语音悬浮球：设备列表里存在小爱音箱才显示
        self._voice_fab = VoiceFab(self)
        self._voice_fab.submitted.connect(self._on_voice_command)
        self._voice_did: str | None = None

        # 主题控制器：跟随系统模式下监听系统配色变化
        from app.ui import si_theme as _si_theme_mod
        from app.ui.theme_service import ThemeController
        self._theme_ctrl = ThemeController()
        self._si_theme_mod = _si_theme_mod
        self._theme_ctrl.theme_changed.connect(self._on_theme_changed)
        # 托盘图标跟系统配色（任务栏底色由系统决定），独立于应用主题
        self._theme_ctrl.system_scheme_changed.connect(self._on_system_scheme_changed)

        # 系统托盘：左键快捷窗口，默认空需用户自主添加
        self._force_quit = False
        try:
            self._tray = TrayController(self._service, self._jobs, self)
            from app.core.settings_store import get_minimize_to_tray
            self._tray.set_tray_visible(get_minimize_to_tray())
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[Tray] 创建失败: {e}")
            self._tray = None

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- 内嵌标题栏（无边框窗口的拖动/窗口控制区） ----
        root.addWidget(self._build_title_bar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        content = QVBoxLayout()
        content.setContentsMargins(29, 18, 29, 0)
        content.setSpacing(15)

        # ---- 顶栏：家庭切换器 + 刷新 ----
        top_bar = QHBoxLayout()
        # 家庭名是下拉切换器，多家庭账号按米家 APP 的方式隔离展示
        self._home_btn = QPushButton("我的家庭")
        self._home_btn.setObjectName("homeSwitcher")
        self._home_btn.setLayoutDirection(Qt.RightToLeft)
        self._home_btn.setIconSize(QSize(19, 19))
        self._home_btn.setAccessibleName("切换家庭")
        self._home_btn.setCursor(Qt.PointingHandCursor)
        self._home_btn.clicked.connect(self._show_home_menu)
        top_bar.addWidget(self._home_btn)
        self._device_summary = QFrame()
        self._device_summary.setObjectName("deviceSummary")
        self._device_summary.installEventFilter(self)
        summary_lay = QHBoxLayout(self._device_summary)
        summary_lay.setContentsMargins(17, 9, 17, 9)
        summary_lay.setSpacing(12)
        self._count_label = QLabel()
        self._count_label.setObjectName("deviceCountLabel")
        summary_lay.addWidget(self._count_label)
        self._summary_divider = QFrame()
        self._summary_divider.setFixedSize(1, 15)
        summary_lay.addWidget(self._summary_divider, alignment=Qt.AlignVCenter)
        self._online_dot = QLabel()
        self._online_dot.setFixedSize(6, 6)
        self._online_glow = QGraphicsDropShadowEffect(self._online_dot)
        self._online_glow.setBlurRadius(10)
        self._online_glow.setOffset(0, 0)
        self._online_dot.setGraphicsEffect(self._online_glow)
        summary_lay.addWidget(self._online_dot)
        self._online_label = QLabel()
        summary_lay.addWidget(self._online_label)
        top_bar.addWidget(self._device_summary)
        top_bar.addStretch(1)
        self._more_menu = QMenu(self)
        self._more_menu.addAction("编辑卡片").triggered.connect(self.show_tray_manager)
        self._more_menu.addAction("设置").triggered.connect(self.show_settings)
        self._more_menu.addSeparator()
        self._more_menu.addAction("关于").triggered.connect(self.show_about)
        self._refresh_btn = QPushButton()
        self._refresh_btn.setIconSize(QSize(24, 24))
        self._refresh_btn.setFixedSize(38, 38)
        self._refresh_btn.setCursor(Qt.PointingHandCursor)
        self._refresh_btn.setAccessibleName("刷新设备")
        self._refresh_btn.clicked.connect(lambda checked=False: self.load_devices(manual=True))
        self._refresh_spin = qta.Spin(self._refresh_btn, interval=16, step=6)
        self._more_btn = QPushButton()
        self._more_btn.setIconSize(QSize(24, 24))
        self._more_btn.setFixedSize(38, 38)
        self._more_btn.setAccessibleName("设置与管理")
        self._more_btn.setCursor(Qt.PointingHandCursor)
        self._more_btn.clicked.connect(self._show_more_menu)
        btn_wrapper = QWidget()
        btn_wrapper.setStyleSheet("background: transparent;")
        btn_layout = QHBoxLayout(btn_wrapper)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)
        btn_layout.addWidget(self._refresh_btn)
        btn_layout.addWidget(self._more_btn)
        top_bar.addWidget(btn_wrapper)
        content.addLayout(top_bar)

        # ---- 房间 tab 行 ----
        self._room_strip = RoomTabStrip()
        self._tab_row = self._room_strip.row
        self._tab_buttons: dict[str, RoomTab] = {}
        room_bar = QHBoxLayout()
        room_bar.setContentsMargins(0, 0, 0, 0)
        room_bar.setSpacing(12)
        room_bar.addWidget(self._room_strip, stretch=1)
        self._room_menu_btn = QPushButton()
        self._room_menu_btn.setFixedSize(40, 52)
        self._room_menu_btn.setIconSize(QSize(24, 24))
        self._room_menu_btn.setAccessibleName('房间列表与设备数量')
        self._room_menu_btn.setCursor(Qt.PointingHandCursor)
        self._room_menu_btn.clicked.connect(self._show_room_menu)
        room_bar.addWidget(self._room_menu_btn)
        room_content = QVBoxLayout()
        room_content.setContentsMargins(0, 0, 0, 0)
        room_content.setSpacing(5)  # Plus the grid's 5px top margin: 10px total.
        room_content.addLayout(room_bar)
        self._access_hint = QLabel()
        self._access_hint.setFont(QFont('Microsoft YaHei UI', 10))
        self._access_hint.setAlignment(Qt.AlignCenter)
        self._access_hint.setWordWrap(True)
        room_content.addWidget(self._access_hint)

        # ---- 卡片滚动区 ----
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._grid_host = QWidget()
        self._grid_host.setObjectName("gridHost")
        self._grid_host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # 布局只创建一次，重建网格时仅清空条目；反复替换布局会因
        # deleteLater 的延迟执行陷入死循环
        from PySide6.QtWidgets import QGridLayout
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 5, 0, 15)
        self._grid.setSpacing(_GRID_SPACING)
        self._scroll.setWidget(self._grid_host)
        # 垂直滚动条显隐会改变视口宽度但不触发窗口 resizeEvent，
        # 监听视口自身尺寸变化，否则列数校验漏掉这类宽度变化
        self._scroll.viewport().installEventFilter(self)
        room_content.addWidget(self._scroll, stretch=1)
        content.addLayout(room_content, stretch=1)

        content_host = QWidget()
        content_host.setObjectName("contentHost")
        content_host.setLayout(content)
        body.addWidget(content_host, stretch=1)
        normal_content = QWidget()
        normal_content.setLayout(body)
        self._content_stack = QStackedWidget()
        self._content_stack.addWidget(normal_content)
        from app.ui.loading_page import LoadingPage
        self._loading_page = LoadingPage()
        self._content_stack.addWidget(self._loading_page)
        root.addWidget(self._content_stack, stretch=1)
        self._footer = FooterBar(BOTTOM_RESERVED_HEIGHT)
        self._footer.check_requested.connect(self._check_footer_update)
        self._footer.update_requested.connect(self._open_footer_update)
        self._footer.account_requested.connect(self._change_account)
        root.addWidget(self._footer)

        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._clear_status_hint)

        # 底部黑色状态栏已移除，提示改为内容区内部 3 秒自动消失
        self.setStatusBar(None)

        # 顶栏/标题栏固定控件的内联样式集中在此设置，主题切换时重设
        self._reapply_chrome_styles()
        self._network_monitor.changed.connect(self._on_network_changed)
        self._loading_progress.connect(self._on_loading_progress)
        self._load_watchdog = QTimer(self)
        self._load_watchdog.setSingleShot(True)
        self._load_watchdog.setInterval(30000)
        self._load_watchdog.timeout.connect(self._on_loading_timeout)
        self._sync_access_ui()

    def _begin_loading(self, full_page=False, *, show_footer=False):
        self._load_generation += 1
        self._load_active = True
        self._load_full_page = full_page
        self._load_show_footer = show_footer and not full_page
        self._load_had_failure = False
        self._load_value = 0
        self._load_pending = {'list'}
        self._poll_timer.stop()
        self._metrics_timer.stop()
        self._footer.setVisible(not full_page)
        if full_page:
            self._voice_fab.collapse()
            self._voice_fab.hide()
            self._content_stack.setCurrentWidget(self._loading_page)
        self._on_loading_progress(self._load_generation, 3, '正在准备设备…')

    def _on_loading_progress(self, generation, value, text):
        if not self._load_active or generation != self._load_generation:
            return
        self._load_watchdog.start()
        self._load_value = max(self._load_value, min(100, value))
        self._loading_page.set_progress(self._load_value, text)
        if not self._load_show_footer:
            self._footer.set_progress(None)
            self._footer.set_status('')
        else:
            self._footer.set_progress(self._load_value, text)

    def _prepare_loading_states(self):
        if self._load_active:
            self._load_pending = {'power', 'metrics'}
            self._on_loading_progress(self._load_generation, 80, '正在读取设备状态…')

    def _load_task_done(self, task, *, generation=None, failed=False):
        if (not self._load_active or task not in self._load_pending
                or (generation is not None and generation != self._load_generation)):
            return
        self._load_pending.remove(task)
        self._load_had_failure |= failed
        if self._load_pending:
            self._on_loading_progress(self._load_generation, 90, '正在同步设备读数…')
        else:
            self._finish_loading()

    def _finish_loading(self, success=True):
        if not self._load_active:
            return
        if success:
            self._on_loading_progress(self._load_generation, 100, '设备已就绪')
        self._load_active = False
        self._load_watchdog.stop()
        self._set_refresh_busy(False)
        self._load_generation += 1
        self._load_pending.clear()
        self._content_stack.setCurrentIndex(0)
        self._footer.show()
        self._footer.set_progress(None)
        self._clear_status_hint()
        self._update_voice_fab()
        if success and self._access_state() == 'ready':
            self._poll_timer.start()
            self._metrics_timer.start()
        if success and self._load_had_failure:
            self._show_status('设备已载入，部分状态暂未读取', 5000)

    def _on_loading_timeout(self):
        self._finish_loading(success=False)
        if self._reconnecting:
            self._connection_failed = True
            self._sync_access_ui()
        self._show_status('刷新超时，请检查网络后重试。', 8000)

    def _accept_device_list(self, generation, result=None, error=None):
        if not self._load_active or generation != self._load_generation:
            return
        if error is not None:
            self._on_load_error(error)
        else:
            self._on_devices_loaded(result)

    def _access_state(self):
        if not self._network_online:
            return 'offline'
        if self._logged_out:
            return 'signed_out'
        if self._reconnecting:
            return 'unavailable' if self._connection_failed else 'loading'
        return 'ready'

    def _sync_access_ui(self):
        from app.core.availability import MESSAGES, speaker_hint
        state = self._access_state()
        ready = state == 'ready'
        hint = MESSAGES.get(state, '') or speaker_hint(self._all_devices)
        self._access_hint.setText(hint)
        self._access_hint.setVisible(bool(hint))
        self._access_hint.setStyleSheet(
            f'color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 10pt;')
        self._access_hint.setSizePolicy(QSizePolicy.Expanding,
            QSizePolicy.Preferred if ready else QSizePolicy.Expanding)
        self._scroll.setVisible(ready)
        self._home_btn.setVisible(ready)
        self._device_summary.setVisible(ready)
        self._room_strip.setVisible(ready)
        self._room_menu_btn.setVisible(ready)
        self._service.set_control_access(MESSAGES.get(state, ''))
        self._update_voice_fab()
        if self._tray is not None:
            self._tray._quick.set_access_state(state)
        if not ready:
            self._finish_loading(success=False)
            self._poll_timer.stop()
            self._metrics_timer.stop()
            for dialog in list(getattr(self, '_light_windows', {}).values()):
                if shiboken6.isValid(dialog):
                    dialog.reject()

    def _on_network_changed(self, online):
        self._network_online = online
        if online and not self._logged_out:
            self._reconnecting = True
            self._connection_failed = False
            self._known_power.clear()
            self._metrics.clear()
        self._sync_access_ui()
        if online:
            if self._logged_out:
                self.start()
            else:
                self.load_devices()

    # ---------- 主题 ----------

    def _reapply_chrome_styles(self) -> None:
        """主题相关的固定控件内联样式：主题切换时整体重设。

        卡片网格、托盘行、工作台等可重建结构由 _on_theme_changed
        走各自的重建入口；这里只管不重建的框架件。
        """
        self._title_bar.retheme()
        self._loading_page.retheme()
        self._footer.retheme()
        self._count_label.setStyleSheet(
            f"color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 10.2pt;")
        self._summary_divider.setStyleSheet(
            f"background: {SiColors.LINE}; border: none;")
        self._online_label.setStyleSheet(
            f"color: {SiColors.INFO_TEXT}; background: transparent; font-size: 10.2pt;")
        self._style_device_summary()
        self._online_dot.setStyleSheet(
            f"background: {SiColors.ONLINE}; border: none; border-radius: 3px;")
        glow_color = QColor(SiColors.ONLINE)
        glow_color.setAlpha(140)
        self._online_glow.setColor(glow_color)
        self._style_popup_menu(self._more_menu)
        self._more_btn.setIcon(qta.icon('ph.gear-light', color=SiColors.TEXT_SECONDARY))
        self._home_btn.setIcon(qta.icon('mdi.chevron-down', color=SiColors.TEXT_SECONDARY))
        self._room_menu_btn.setIcon(qta.icon('mdi.menu', color=SiColors.TEXT_SECONDARY))
        self._room_menu_btn.setStyleSheet('QPushButton { background: transparent; border: none; }')
        for button in (self._refresh_btn, self._more_btn):
            button.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; border-radius: 8px; }}"
                f"QPushButton:hover {{ background: {SiColors.BTN_HOVER}; }}")
        self._update_refresh_icon()

    def _style_device_summary(self) -> None:
        # Qt stylesheet radii require integer pixels; a half-pixel radius at
        # odd heights can leave this frame square after a font/layout change.
        radius = max(1, self._device_summary.height() // 2)
        self._device_summary.setStyleSheet(
            f"QFrame#deviceSummary {{ background: {SiColors.SURFACE};"
            f" border: 1px solid {SiColors.LINE}; border-radius: {radius}px; }}")

    def _update_refresh_icon(self) -> None:
        options = dict(color=SiColors.TEXT_SECONDARY, color_disabled=SiColors.TEXT_SECONDARY)
        if self._loading_devices:
            options["animation"] = self._refresh_spin
        self._refresh_btn.setIcon(qta.icon('ph.arrow-clockwise-light', **options))

    def _set_refresh_busy(self, busy: bool) -> None:
        self._loading_devices = busy
        self._refresh_btn.setEnabled(not busy)
        self._refresh_btn.setAccessibleName("正在刷新…" if busy else "刷新设备")
        if busy:
            self._refresh_spin.start()
        else:
            self._refresh_spin.stop()
        self._update_refresh_icon()

    def apply_theme_mode(self, mode: str) -> None:
        """设置页切换主题入口：应用后经 theme_changed 信号触发重建。"""
        self._theme_ctrl.set_mode(mode)

    def apply_theme_color(self, color: str) -> None:
        self._theme_ctrl.set_accent(color)

    def _on_system_scheme_changed(self, scheme: str) -> None:
        """系统深浅色变化：托盘图标跟随任务栏底色，与应用主题无关。"""
        if self._tray is not None:
            self._tray.apply_system_icon_theme(scheme)

    def _on_theme_changed(self, theme: str) -> None:
        """主题切换广播：重建可重建结构并刷新固定件。"""
        self._reapply_chrome_styles()
        self._rebuild_tabs()
        self._rebuild_grid()
        self._update_count_label()
        self._voice_fab.retheme()
        if self._tray is not None:
            # 托盘快捷窗口整窗重建后，立刻回填设备/开关/读数；
            # 若重建前窗口正显示，set_devices 会自动重新呼出
            self._tray.retheme()
            self._update_tray_devices()
            self._push_tray_metrics()
        # 打开中的设置页自身也刷新（其样式为构造时求值的内联样式）
        dlg = self._settings_dialog
        if dlg is not None and shiboken6.isValid(dlg) and dlg.isVisible():
            dlg.retheme()
        # 托盘独立打开的详情对话框（即用即建，但开着时切主题需重建）
        from PySide6.QtWidgets import QApplication
        from app.ui.device_dialog import DeviceDetailDialog
        from app.ui.light_controls import LightControlDialog
        for w in QApplication.topLevelWidgets():
            if isinstance(w, (DeviceDetailDialog, LightControlDialog)) and w.isVisible():
                w.retheme()
        if self._all_devices:
            self._refresh_power_states(force=False)
        self._sync_access_ui()

    # ---------- 内嵌标题栏与窗口操作 ----------

    def _build_title_bar(self) -> QWidget:
        bar = WindowCaption(self, show_tooltips=False, brand=True)
        self._title_bar = bar
        self._max_btn = bar.maximize_button
        bar.installEventFilter(self)
        return bar

    def _toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self._max_btn.setText("\uE923" if self.isMaximized() else "\uE922")

    # ---------- 原生窗口行为（Windows 消息拦截） ----------
    #
    # Qt 管理无边框客户区；WM_NCHITTEST 负责拖动与边缘缩放命中。

    def nativeEvent(self, eventType, message):  # noqa: N802 (Qt 命名约定)
        if sys.platform == "win32" and eventType == "windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            # FramelessWindowHint 的客户区与最大化边界交给 Qt 平台插件，
            # 不再叠加一套 WM_NCCALCSIZE 补偿，以免产生黑边或双标题栏。
            if msg.message == _WM_NCHITTEST:
                return True, self._hit_test(msg.lParam)
            if msg.message == _WM_NCLBUTTONDBLCLK and msg.wParam == _HTCAPTION:
                # 无边框窗口不依赖默认标题栏行为，显式切换 Qt 窗口状态。
                self._toggle_maximized()
                return True, 0
        return False, 0

    def _hit_test(self, lParam: int) -> int:
        """把鼠标位置翻译成系统命中代码：边缘缩放 / 标题栏拖动 / 客户区。"""
        # lParam 低/高 16 位分别是屏幕坐标 x/y（有符号，多显示器可为负）
        x = ctypes.c_short(lParam & 0xFFFF).value
        y = ctypes.c_short((lParam >> 16) & 0xFFFF).value
        pt = wintypes.POINT(x, y)
        hwnd = int(self.winId())
        ctypes.windll.user32.ScreenToClient(hwnd, ctypes.byref(pt))
        # ScreenToClient 返回物理像素，Qt 的尺寸是逻辑像素，需先统一
        dpr = self.devicePixelRatioF() or 1.0
        cx, cy = pt.x / dpr, pt.y / dpr

        if not self.isMaximized():
            m = _RESIZE_MARGIN
            on_left = cx <= m
            on_right = cx >= self.width() - m
            on_top = cy <= m
            on_bottom = cy >= self.height() - m
            if on_top and on_left:
                return _HTTOPLEFT
            if on_top and on_right:
                return _HTTOPRIGHT
            if on_bottom and on_left:
                return _HTBOTTOMLEFT
            if on_bottom and on_right:
                return _HTBOTTOMRIGHT
            if on_left:
                return _HTLEFT
            if on_right:
                return _HTRIGHT
            if on_top:
                return _HTTOP
            if on_bottom:
                return _HTBOTTOM

        # 标题栏区域交给系统（拖动/双击最大化）；窗口控制钮保持 HTCLIENT
        if cy <= _TITLE_BAR_HEIGHT:
            child = self.childAt(int(cx), int(cy))
            if not isinstance(child, QPushButton):
                return _HTCAPTION
        return _HTCLIENT

    # ---------- 启动与数据加载 ----------

    def _show_status(self, text: str, timeout_ms: int = 3000) -> None:
        self._footer.set_status('' if self._load_active and not self._load_show_footer else text)
        self._status_timer.stop()
        if timeout_ms > 0:
            self._status_timer.start(timeout_ms)

    def _clear_status_hint(self) -> None:
        self._footer.set_status('')

    def _check_footer_update(self):
        from app.ui.update_flow import check_update
        check_update(self, manual=True)

    def _on_update_available(self, info):
        self._footer.set_release(info)

    def _open_footer_update(self):
        info = self._footer._release
        if info is not None:
            from app.ui.update_flow import prompt_new_version
            prompt_new_version(self, info)

    def start(self) -> None:
        """应用入口第一步：校验登录态，决定拉列表还是弹扫码窗。"""
        if not self._network_online:
            self._sync_access_ui()
            return
        self._show_status("正在检查登录状态…")
        self._jobs.submit(
            self._service.login_status,
            on_success=self._after_login_check,
            # login_status 内部已兜底返回 False；这里只拦「根本没法问」的
            # 意外异常，同样按未登录处理，绝不让启动检查无声卡死
            on_error=lambda exc: (
                logger.warning("登录状态检查失败: %s", exc),
                self._after_login_check(False),
            ),
        )
        self._maybe_check_update()

    def _maybe_check_update(self) -> None:
        """按设置在启动时后台检查一次 GitHub 新版本。

        延迟数秒发起：错开设备列表加载与可能的扫码弹窗，避免多个
        对话框同时抢占；静默启动（托盘常驻）也要查，发现新版时
        对话框独立居中显示。
        """
        if self._update_check_done:
            return
        self._update_check_done = True
        from app.core.settings_store import get_check_update_enabled
        from app.core.update_checker import LATEST_API
        if not get_check_update_enabled() or not LATEST_API:
            return
        from PySide6.QtCore import QTimer

        def _run() -> None:
            from app.ui.update_flow import check_update
            check_update(self, manual=False)

        QTimer.singleShot(3000, self, _run)

    def _after_login_check(self, logged_in: bool) -> None:
        if logged_in:
            from app.core import account_store
            try:
                account_store.activate(self._service.account_id())
            except OSError as error:
                self._show_status(f'无法读取账号配置：{error}', 5000)
                return
            self._logged_out = False
            self._sync_access_ui()
            self._footer.set_logged_in(True)
            self._startup_load()
            return
        self._logged_out = True
        self._sync_access_ui()
        self._footer.set_logged_in(False)
        self._clear_status_hint()
        self._login_account()

    def _startup_load(self) -> None:
        """启动加载：缓存命中直接渲染，未命中走在线拉取。

        缓存里的开关记忆与温湿度读数一并恢复，启动瞬间即有完整
        可用的界面与上次读数，新值拿到后覆盖。
        """
        self._poll_timer.start()
        self._metrics_timer.start()
        cached = device_cache.load()
        if cached is None:
            self.load_devices(full_page=True)
            return
        self._begin_loading(full_page=True)
        devices, known_power, metrics = cached
        self._known_power.update(known_power)
        self._metrics.update(metrics)
        self._show_status("已从本地缓存加载，点击右上角刷新按钮可同步最新设备")
        self._prepare_loading_states()
        self._apply_devices(devices)

    def _login_account(self):
        from app.ui.login_dialog import LoginDialog
        if not self._network_online:
            self._sync_access_ui()
            return
        if self._login_dialog is not None:
            self._login_dialog.raise_()
            self._login_dialog.activateWindow()
            return
        dialog = self._login_dialog = LoginDialog(self._service, self._jobs, self)
        try:
            if dialog.exec_and_wait() == LoginDialog.Accepted:
                self._after_login_check(True)
        finally:
            self._login_dialog = None

    def _change_account(self):
        if self._account_transition:
            return
        if self._logged_out:
            self._login_account()
            return
        self._finish_loading(success=False)
        self._account_transition = True
        self._poll_timer.stop()
        self._metrics_timer.stop()
        self._resize_timer.stop()
        self._voice_fab.collapse()
        self._voice_fab.hide()
        for window in list(getattr(self, '_camera_windows', {}).values()):
            window.setWindowOpacity(0)
            window.close()
        if self._tray is not None:
            self._tray.hide_quick()
            self._tray.set_tray_visible(False)
        self.centralWidget().setEnabled(False)
        self._show_status('正在退出账号…', 0)
        self._jobs.cancel_pending()
        self._jobs.submit(self._service.logout,
            on_success=lambda _: self._account_signed_out(),
            on_error=self._account_change_failed)

    def _resume_account_ui(self):
        self._account_transition = False
        self.centralWidget().setEnabled(True)
        if self._tray is not None:
            from app.core.settings_store import get_minimize_to_tray
            self._tray.set_tray_visible(get_minimize_to_tray())

    def _account_change_failed(self, error):
        self._resume_account_ui()
        self._set_refresh_busy(False)
        self._poll_in_flight = False
        self._loading_scenes = False
        self._poll_timer.start()
        self._metrics_timer.start()
        self._update_voice_fab()
        self._show_status(f'退出账号失败：{error}', 5000)

    def _account_signed_out(self):
        self._logged_out = True
        self._all_devices = []
        self._known_power.clear()
        self._metrics.clear()
        self._scenes = []
        self._homes = [_ALL_HOMES]
        self._current_home = _ALL_HOMES
        self._current_room = _ALL_ROOMS
        self._home_btn.setText(_ALL_HOMES)
        self._poll_in_flight = False
        self._localize_busy = False
        self._loading_scenes = False
        self._voice_did = None
        self._set_refresh_busy(False)
        self._rebuild_tabs()
        self._rebuild_grid()
        self._update_count_label()
        if self._tray is not None:
            self._tray.retheme()
            self._tray.set_devices([], {})
        self._footer.set_logged_in(False)
        self._sync_access_ui()
        self._clear_status_hint()
        self._resume_account_ui()

    def load_devices(self, checked=False, *, full_page=False, manual=False) -> None:
        if not self._network_online:
            self._sync_access_ui()
            return
        if self._logged_out:
            self._login_account()
            return
        if self._loading_devices:
            return
        self._begin_loading(full_page=full_page, show_footer=manual)
        self._set_refresh_busy(True)
        self._show_status("正在获取设备列表…", 0)
        generation = self._load_generation
        progress = lambda value, text: self._loading_progress.emit(generation, value, text)
        self._jobs.submit(
            lambda: self._service.list_devices(progress=progress),
            on_success=lambda result: self._accept_device_list(generation, result=result),
            on_error=lambda error: self._accept_device_list(generation, error=error),
            priority=0,
        )

    def _on_devices_loaded(self, devices: list[DeviceInfo]) -> None:
        show_summary = not (self._load_active and self._load_full_page)
        self._reconnecting = False
        self._connection_failed = False
        if self._network_online and not self._logged_out:
            if not self._load_active:
                self._poll_timer.start()
                self._metrics_timer.start()
            self._service.set_control_access()
        # 对比要在替换前做：added/removed 以旧列表为基准
        added, removed = self._diff_devices(devices)
        self._prepare_loading_states()
        self._apply_devices(devices)
        device_cache.save(devices, self._known_power, self._metrics)
        self._set_refresh_busy(False)
        self._status_timer.stop()
        self._clear_status_hint()
        if show_summary and (self._all_devices or added or removed):
            Toast.info(self, _refresh_summary(len(devices), added, removed))

    def _diff_devices(self, devices: list[DeviceInfo]) -> tuple[int, int]:
        old = {d.did for d in self._all_devices}
        new = {d.did for d in devices}
        return len(new - old), len(old - new)

    def _apply_devices(self, devices: list[DeviceInfo]) -> None:
        prepare_device_cards(devices)
        from app.core.device_controls import prune_tray_selection, supports_card_power
        prune_tray_selection(devices)
        for device in devices:
            if not supports_card_power(device) or not device.online:
                self._known_power[device.did] = None
        self._all_devices = devices
        homes = sorted(
            {d.home_name for d in devices},
            key=lambda h: (h == "未知", h),
        )
        self._homes = [_ALL_HOMES] + homes
        if self._current_home not in self._homes:
            self._current_home = self._homes[0] if self._homes else _ALL_HOMES
        self._current_room = _ALL_ROOMS
        self._home_btn.setText(self._current_home)
        self._rebuild_tabs()
        self._rebuild_grid()
        self._update_count_label()
        self._refresh_power_states(force=False)
        # Classify live power capabilities first; then read sensor values only
        # for the remaining devices. Otherwise a cold refresh queries every
        # switch/split channel's incidental properties as well.
        if not (self._load_active and 'power' in self._load_pending):
            self._refresh_metrics()
        self._update_voice_fab()
        self._update_tray_devices()
        self._load_card_icons()
        self._sync_access_ui()
        # 场景入口开启时启动即预取场景列表，进场景页无需等待
        if self._show_scene_tab:
            self._load_scenes()

    # ---------- 设备图标 ----------

    def _load_card_icons(self) -> None:
        """增量拉取设备图标：只对缓存里没有的型号调接口。

        已下载图片的卡片回填由 _rebuild_grid 负责（建卡即查本地文件），
        本方法只处理缺失部分：拉 URL、缺图下发下载；图标 URL 与图片
        都落本地缓存（见 icon_store），设备列表不变时不会重复调接口。
        """
        if not self._network_online or self._logged_out:
            return
        models = sorted({d.model for d in self._all_devices if d.model})
        if not models:
            return
        # One model per task lets a manual refresh run between network lookups.
        for model in models:
            if icon_store.icon_path(model).is_file():
                continue
            self._jobs.submit(
                lambda m=model: self._service.icon_urls([m]),
                on_success=self._on_icons_ready,
                priority=20,
            )

    def _on_icons_ready(self, urls: dict[str, str | None]) -> None:
        """图标 URL 就绪：缺图的下发后台下载，下载完成回填当前可见卡片。"""
        for model, url in urls.items():
            if not url:
                continue
            if icon_store.icon_path(model).is_file():
                continue
            self._jobs.submit(
                lambda m=model, u=url: self._service.icon_file(m, u),
                on_success=lambda p, m=model: self._apply_card_icon(m, str(p))
                if p else None,
                priority=20,
            )

    def _apply_card_icon(self, model: str, path: str) -> None:
        """同一型号的所有卡片共用一份图标图片。"""
        if not path:
            return
        for card in self._cards.values():
            if card.device.model == model:
                card.set_icon(Path(path))

    def _maybe_localize_names(self) -> None:
        """未改名英文设备用中文名替换显示名（两个来源按序兜底）。

        ① spec 缓存里的产品名（多数设备有，零网络开销）；
        ② miot-spec 产品页（/p/<model>）的中文商品名——无公开 spec
          的设备（如仅蓝牙类）只有这里有，经后台线程抓取并缓存
          （含“确认无中文名”的结果，不重复查询）。
        改名设备与中文名设备不受影响；spec 产品名相同的设备
        （同型号多台）追加 did 尾号以区分。
        """
        if not self._all_devices:
            return
        try:
            names_now = {d.did: d.name for d in self._all_devices}
            replacements = self._service.localized_product_names(
                list(names_now), names_now)
            ascii_devices = [d for d in self._all_devices if d.name.isascii() and d.model]
            model_to_did = {d.model: d.did for d in ascii_devices}
            models = sorted(model_to_did)
            if models:
                # 产品页名称按型号缓存，需映射回 did 再并入替换表
                for model, product_name in self._service.cached_product_page_names(models).items():
                    replacements[model_to_did[model]] = product_name
        except Exception:
            logger.exception("本地化设备名失败")
            return
        if replacements:
            if self._apply_display_names(replacements):
                return  # 已重建并同步托盘
        # 仍有未解析的型号 → 提交一次后台查询（防重入）
        pending = sorted({d.model for d in ascii_devices
                          if not self._service.has_product_page_name(d.model)})
        if pending and not self._localize_busy:
            self._localize_busy = True
            remaining = set(pending)
            def completed(model, error=None):
                remaining.discard(model)
                if error is not None:
                    logger.warning('产品页名称查询失败: %s', error)
                if not remaining:
                    self._on_product_names_fetched()
            for model in pending:
                self._jobs.submit(
                    lambda m=model: self._service.product_page_name(m),
                    on_success=lambda _, m=model: completed(m),
                    on_error=lambda error, m=model: completed(m, error),
                    priority=20,
                )

    def _apply_display_names(self, replacements: dict[str, str]) -> bool:
        """把替换名写入设备对象并重建展示；返回是否有实际变化。"""
        changed = False
        for d in self._all_devices:
            new_name = replacements.get(d.did)
            if new_name and new_name != d.name:
                d.name = new_name
                changed = True
        if not changed:
            return False
        # 同型号多台替换后同名：追加 did 尾号区分（如 ·468）
        by_name: dict[str, int] = {}
        for d in self._all_devices:
            by_name[d.name] = by_name.get(d.name, 0) + 1
        for d in self._all_devices:
            if by_name.get(d.name, 0) > 1 and d.did in replacements:
                d.name = f"{d.name}·{d.did[-3:]}"
        self._rebuild_grid()
        self._update_count_label()
        self._update_tray_devices()
        return True

    def _on_product_names_fetched(self) -> None:
        self._localize_busy = False
        self._maybe_localize_names()

    def _on_product_names_failed(self, error: Exception) -> None:
        # service 层已把查询失败按「无中文名」缓存（避免反复重试堵队列），
        # 这里只会收到罕见意外；记录后等下次轮询再走完整流程
        self._localize_busy = False
        logger.warning("产品页名称查询失败: %s", error)

    def _update_tray_devices(self) -> None:
        if self._tray is not None:
            self._tray.set_devices(self._displayed_devices(), self._known_power)

    def _show_more_menu(self) -> None:
        """在更多按钮左下方弹出菜单，右边缘与按钮右边缘对齐。"""
        self._more_menu.adjustSize()
        pos = self._more_btn.mapToGlobal(self._more_btn.rect().bottomRight())
        menu_w = self._more_menu.sizeHint().width()
        self._more_menu.exec(QPoint(pos.x() - menu_w, pos.y() + 8))

    def request_force_quit(self) -> None:
        """托盘菜单「退出」调用：closeEvent 跳过隐藏到托盘，直接退出。"""
        self._force_quit = True

    def devices(self) -> list[DeviceInfo]:
        """当前全量设备列表（托盘快捷窗口打开详情用）。"""
        return self._all_devices

    def show_tray_manager(self) -> None:
        """打开托盘快捷项管理对话框（托盘菜单与主界面菜单共用入口）。"""
        if not self._all_devices:
            Toast.info(self, "请先刷新获取设备列表", 2500)
            return
        # 管理时收起快捷窗口避免与对话框重叠时显示旧状态
        if self._tray is not None:
            self._tray.hide_quick()
        # 主窗口可能已隐藏到托盘，管理对话框需独立显示
        parent = None if self.isHidden() else self
        # 场景数据始终按「全部家庭」口径：主界面缓存只在当前家庭为
        # 全部时才通用，否则交给对话框切页时自行拉取
        cached = self._scenes if self._current_home == _ALL_HOMES else None
        dlg = TrayManagerDialog(
            self._all_devices, parent,
            scenes=cached,
            scene_loader=(lambda: self._service.scene_list(None))
            if self._show_scene_tab else None,
            jobs=self._jobs,
        )
        result = dlg.exec()
        # 数据须在 deleteLater 前取出
        order = dlg.selected_order()
        scene_by_id = {s["scene_id"]: s for s in dlg.selected_scene_data()}
        dlg.deleteLater()
        if result == QDialog.Accepted:
            from app.core import tray_store as _ts
            # 三处写入保持同一展示顺序：order 为准，devices/scenes 按它
            # 排序落盘，order 缺失兜底合成时顺序才与旧显示一致
            dids = [it["id"] for it in order if it["type"] == "device"]
            scenes = [scene_by_id[it["id"]] for it in order
                      if it["type"] == "scene" and it["id"] in scene_by_id]
            _ts.save(dids)
            _ts.save_scenes(scenes)
            _ts.save_order(order)
            self._update_tray_devices()
            Toast.info(self, "托盘项目已更新", 2000)

    def show_about(self) -> None:
        """打开关于对话框（即用即建）。"""
        from app.ui.about_dialog import AboutDialog
        dlg = AboutDialog(self, api_version=self._service.api_version())
        dlg.exec()
        dlg.deleteLater()

    def show_settings(self) -> None:
        """打开设置对话框（托盘菜单与主界面菜单共用入口）。"""
        # 弹出期间置顶已有实例，避免托盘与主界面重复弹出
        dlg = self._settings_dialog
        if dlg is not None and dlg.isVisible():
            dlg.raise_()
            dlg.activateWindow()
            return
        dlg = SettingsDialog(self, devices=self._all_devices)
        self._settings_dialog = dlg
        dlg.exec()
        scale_changed = getattr(dlg, "_scale_changed", False)
        dlg.deleteLater()
        self._settings_dialog = None
        # 界面缩放改动需重启应用生效：提供一键重启（常驻托盘时关窗口
        # 只是隐藏到托盘、进程仍在，仅提示会让用户以为没生效）
        if scale_changed:
            from app.ui.restart import restart_app
            ret = QMessageBox.question(
                self, "界面缩放已保存",
                "界面缩放需重启应用后生效。\n是否立即重启？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes)
            if ret == QMessageBox.Yes:
                self._force_quit = True
                restart_app()
        # 设置可能变了，同步托盘图标显隐
        from app.core.settings_store import get_minimize_to_tray
        if self._tray is not None:
            self._tray.set_tray_visible(get_minimize_to_tray())
        # “隐藏无可控制功能的设备”开关可能变化：重载并刷新展示
        from app.core.settings_store import get_hide_no_func_devices
        new_hide = get_hide_no_func_devices()
        if new_hide != self._hide_no_func:
            self._hide_no_func = new_hide
            self._rebuild_tabs()
            self._rebuild_grid()
            self._update_count_label()
            self._update_tray_devices()
        # “显示场景选项卡”开关可能变化：重载选项卡并刷新网格；
        # 关闭时若正停留在场景视图，重置回全屋，避免入口消失后无法切回
        from app.core.settings_store import get_show_scene_tab
        new_show = get_show_scene_tab()
        if new_show != self._show_scene_tab:
            self._show_scene_tab = new_show
            if not new_show and self._current_room == _SCENE_TAB:
                self._current_room = _ALL_ROOMS
            self._rebuild_tabs()
            self._rebuild_grid()
            self._update_count_label()
        # 同步小爱悬浮按钮显隐
        self._update_voice_fab()
        if self._tray is not None:
            self._tray.refresh_speaker()

    def _update_voice_fab(self) -> None:
        """根据设置与设备列表决定小爱悬浮按钮显隐。

        输出音箱：设置的默认音箱（在线时）优先，否则回退第一个在线音箱。
        """
        from app.core.settings_store import get_default_speaker_did, get_voice_fab_enabled
        if (getattr(self, '_logged_out', False) or not getattr(self, '_network_online', True)
                or (getattr(self, '_load_active', False) and self._load_full_page)):
            self._voice_did = None
            self._voice_fab.collapse()
            self._voice_fab.hide()
            return
        pref = get_default_speaker_did()
        speaker = next(
            (d for d in self._all_devices
             if d.did == pref and is_speaker(d) and d.online),
            None,
        )
        if speaker is None:
            speaker = next(
                (d for d in self._all_devices if is_speaker(d) and d.online),
                None,
            )
        self._voice_did = speaker.did if speaker else None
        # 仅当设置开启且存在在线音箱时显示
        show = get_voice_fab_enabled() and speaker is not None
        self._voice_fab.setVisible(show)
        if not show:
            self._voice_fab.collapse()

    def _on_voice_command(self, text: str) -> None:
        did = self._voice_did
        if did is None:
            return
        # 设置的默认音箱离线/不在列表 → 已回退：提示里说明，并把
        # 设置回退为「自动」（否则偏好一直指向离线设备，每次都要回退）
        from app.core.settings_store import get_default_speaker_did, set_default_speaker_did
        pref = get_default_speaker_did()
        fallback_note = ""
        if pref and pref != did:
            fallback_note = "（首选音箱离线，已由当前在线音箱代答）"
            set_default_speaker_did("")
        self._jobs.submit(
            lambda: self._service.run_action(did, "execute-text-directive", [text]),
            on_success=lambda _, note=fallback_note: self._on_voice_command_success(text, note, did),
            on_error=lambda e: Toast.info(self, f"执行失败：{e}", 4000),
        )

    def _on_voice_command_success(self, text: str, note: str, did: str) -> None:
        if self._tray is not None:
            self._tray.refresh_audio_after_command(did)
        Toast.info(self, f"已告诉小爱同学：{text}{note}", 3000)

    def _update_count_label(self) -> None:
        if self._current_room == _SCENE_TAB:
            count = len(self._scenes or [])
            self._count_label.setText(f"共 {count} 个场景")
            self._summary_divider.hide()
            self._online_dot.hide()
            self._online_label.hide()
            return
        subset = self._visible_devices() if self._current_home == _ALL_HOMES else [
            d for d in self._visible_devices() if d.home_name == self._current_home
        ]
        total = len(subset)
        online = sum(1 for d in subset if d.online)
        self._count_label.setText(f"共 {total} 台设备")
        self._online_label.setText(f"<b>{online}</b> 台设备在线")
        self._summary_divider.show()
        self._online_dot.show()
        self._online_label.show()

    def _on_poll_tick(self) -> None:
        if self._poll_in_flight or not self._all_devices:
            return
        self._refresh_power_states(force=True)

    def _refresh_power_states(self, force: bool) -> None:
        """批量拉取当前可见设备的开关状态。

        force=False 探测还没有读到状态的设备（首次/新设备/上次失败）；
        force=True 忽略记忆全量重读（定时轮询）。
        离线设备的云端返回值是最后一次在线时的缓存，不可信，跳过。
        """
        if not getattr(self, '_network_online', True) or getattr(self, '_logged_out', False):
            return
        # 以 DeviceInfo.online 为准：离线设备的云端开关值不可信
        dids = [d.did for d in self._visible_devices() if d.online]
        online = {d.did for d in getattr(self, '_all_devices', self._visible_devices()) if d.online}
        dids += [child for d in self._visible_devices() if d.online
                 for child in getattr(d, 'switch_channels', ()) if child in online]
        dids = list(dict.fromkeys(dids))
        if not dids:
            if getattr(self, '_load_active', False):
                self._load_task_done('power')
            return
        if not force and not getattr(self, '_load_active', False):
            dids = [d for d in dids if self._known_power.get(d) is None]
            if not dids:
                return
        # None can mean a transient read failure, not just no capability.
        # The service uses cached specs to skip devices without a switch;
        # retry online devices so a missing button can recover automatically.
        self._poll_in_flight = True
        generation = getattr(self, '_load_generation', None)
        self._jobs.submit(
            lambda: self._service.power_states(dids),
            on_success=lambda states: self._apply_power_states(states, load_ticket=generation),
            on_error=lambda error: self._on_poll_error(error, load_ticket=generation),
            priority=1 if getattr(self, '_load_active', False) else 10,
        )

    def _on_poll_error(self, error: Exception, *, load_ticket=None) -> None:
        # 轮询失败不打断界面，但必须留痕：持续失败意味着网络/凭据异常
        self._poll_in_flight = False
        logger.warning("轮询设备开关状态失败: %s", error)
        self._load_task_done('power', generation=load_ticket, failed=True)
        if self._load_active and load_ticket == self._load_generation:
            self._refresh_metrics()

    def _apply_power_states(self, states: dict[str, bool | None], *, load_ticket=None) -> None:
        self._poll_in_flight = False
        for did, state in states.items():
            self._apply_power_state(did, state)
        self._maybe_localize_names()
        self._update_tray_devices()
        self._load_task_done('power', generation=load_ticket)
        if self._load_active and load_ticket == self._load_generation:
            self._refresh_metrics()

    def _apply_power_state(self, did: str, state: bool | None) -> None:
        # 离线设备的开关值不落记忆，避免云端缓存的旧值覆盖灰置状态
        dev = next((d for d in self._all_devices if d.did == did), None)
        if dev is not None and not dev.online:
            self._known_power[did] = None
            return
        self._known_power[did] = state
        card = self._cards.get(did)
        if card is not None and state is not None:
            card.set_power_state(state)
        self._update_panel_cards()

    def _update_panel_cards(self):
        for device in self._all_devices:
            card = self._cards.get(device.did)
            if device.switch_channels and card is not None:
                card.set_panel_states(self._known_power)

    def _refresh_metrics(self) -> None:
        """为无开关能力的可见设备批量拉温湿度读数（副标题展示）。

        有开关的设备副标题保持纯房间名；温湿度计这类设备读 SI 标准
        temperature/humidity 属性，读数失败静默跳过。
        """
        if not self._network_online or self._logged_out:
            return
        dids = [
            d.did for d in self._visible_devices()
            if d.online and self._known_power.get(d.did) is None
        ]
        if not dids:
            self._load_task_done('metrics')
            return
        generation = self._load_generation
        self._jobs.submit(
            lambda: self._service.read_metrics(dids),
            on_success=lambda metrics: self._apply_metrics(metrics, load_ticket=generation),
            on_error=lambda error: self._on_metrics_error(error, generation),
            priority=1 if self._load_active else 10,
        )

    def _apply_metrics(self, metrics: dict[str, str | None], *, load_ticket=None) -> None:
        dirty = False
        for did, text in metrics.items():
            if text:
                if self._metrics.get(did) != text:
                    dirty = True
                self._metrics[did] = text
            elif did in self._metrics:
                self._metrics.pop(did, None)
                dirty = True
            card = self._cards.get(did)
            if card is not None:
                card.set_metrics(text)
        if dirty and self._all_devices:
            device_cache.save(self._all_devices, self._known_power, self._metrics)
        self._maybe_localize_names()
        self._push_tray_metrics()
        self._load_task_done('metrics', generation=load_ticket)

    def _on_metrics_error(self, error, generation):
        logger.warning('拉取温湿度读数失败: %s', error)
        self._load_task_done('metrics', generation=generation, failed=True)

    def _push_tray_metrics(self) -> None:
        """把温湿度读数同步给托盘快捷窗口（副标题展示）。"""
        if self._tray is not None:
            try:
                self._tray.set_metrics(self._metrics)
            except Exception:
                # 托盘行可能在重建间隙销毁，同步失败可安全忽略
                pass

    def _visible_devices(self) -> list[DeviceInfo]:
        return [
            d for d in self._all_devices
            if (self._current_home == _ALL_HOMES or d.home_name == self._current_home)
            and (self._current_room == _ALL_ROOMS or d.room_name == self._current_room)
            and (not self._hide_no_func or self._device_has_functions(d))
        ]

    def _device_has_functions(self, device: DeviceInfo) -> bool:
        """None（spec 未拉取）视为有——等首轮轮询证实后再隐藏。"""
        state = self._service.spec_has_published_functions(device.spec_type)
        return state is not False

    def _displayed_devices(self) -> list[DeviceInfo]:
        """主页/托盘展示列表（含家庭/房间过滤与“隐藏无功能设备”）。"""
        if not self._hide_no_func:
            return self._all_devices
        return [d for d in self._all_devices if self._device_has_functions(d)]

    def _style_popup_menu(self, menu: QMenu) -> None:
        from app.ui.popup_menu import style_popup_menu
        style_popup_menu(menu)

    def _build_home_menu(self) -> QMenu:
        """紧凑的家庭菜单，字号独立于大标题，去掉原生方形投影。"""
        menu = QMenu(self)
        menu.setObjectName("homeMenu")
        self._style_popup_menu(menu)
        font = menu.font()
        for home in self._homes:
            action = menu.addAction(home)
            action.setFont(font)
            if home == self._current_home:
                action.setIcon(qta.icon('mdi.check', color=SiColors.THEME_DIM))
            action.triggered.connect(lambda _, h=home: self._select_home(h))
        return menu

    def _show_home_menu(self) -> None:
        if not self._homes:
            return
        menu = self._build_home_menu()
        menu.exec(self._home_btn.mapToGlobal(
            self._home_btn.rect().bottomLeft()) + QPoint(0, 6))
        menu.deleteLater()

    def _select_home(self, home: str) -> None:
        if home == self._current_home:
            return
        self._current_home = home
        self._current_room = _ALL_ROOMS
        # 场景列表随家庭范围过滤，切家庭后旧缓存失效
        self._scenes = None
        self._home_btn.setText(home)
        self._rebuild_tabs()
        self._rebuild_grid()
        self._animate_grid_in()
        self._update_count_label()
        self._refresh_power_states(force=False)
        self._refresh_metrics()

    def _animate_grid_in(self) -> None:
        """切换家庭/房间后卡片网格整体淡入（160ms），结束即移除效果。"""
        effect = QGraphicsOpacityEffect(self._grid_host)
        effect.setOpacity(0.0)
        self._grid_host.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(160)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        def _cleanup() -> None:
            # 快速连续切换时旧动画的 finished 会迟到，只清理仍属
            # 自己的效果，避免误删新一轮动画的透明度效果
            if self._grid_host.graphicsEffect() is effect:
                self._grid_host.setGraphicsEffect(None)

        anim.finished.connect(_cleanup)
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _on_load_error(self, error: Exception) -> None:
        self._finish_loading(success=False)
        self._set_refresh_busy(False)
        if not self._network_online or self._reconnecting:
            self._connection_failed = True
            self._sync_access_ui()
            return
        self._show_status("加载失败", 4000)
        QMessageBox.critical(self, "加载失败", str(error))

    # ---------- 房间 tab ----------

    def _rebuild_tabs(self) -> None:
        # 彻底清空布局条目（含 stretch）：只删按钮会残留 stretch 项，
        # 每次切换家庭都会把新按钮往右推一格
        while self._tab_row.count():
            item = self._tab_row.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()
        self._tab_buttons.clear()

        rooms = ([_SCENE_TAB] if self._show_scene_tab else []) + [_ALL_ROOMS] + sorted({
            d.room_name for d in self._all_devices
            if (self._current_home == _ALL_HOMES or d.home_name == self._current_home)
            and d.room_name and d.room_name != "未知"
        })
        for room in rooms:
            btn = RoomTab(room)
            btn.clicked.connect(lambda _, r=room: self._select_room(r))
            self._tab_row.addWidget(btn)
            btn.show()
            self._room_strip.watch_button(btn)
            self._tab_buttons[room] = btn
        self._tab_row.addStretch(1)
        self._room_strip.refresh()
        self._sync_tab_style()

    def _select_room(self, room: str) -> None:
        self._current_room = room
        self._sync_tab_style()
        self._rebuild_grid()
        self._animate_grid_in()
        if room == _SCENE_TAB:
            # 场景视图：有缓存先显示，后台刷新；无缓存时状态栏提示加载中
            if self._scenes is None:
                self._show_status("正在加载场景…")
            self._load_scenes()
            self._update_count_label()
            return
        self._refresh_power_states(force=False)
        # 切回设备视图刷新计数：场景模式的「共 N 个场景」必须换回设备计数
        self._update_count_label()

    def _sync_tab_style(self) -> None:
        for room, btn in self._tab_buttons.items():
            selected = room == self._current_room
            if btn.isChecked() != (room == self._current_room):
                btn.setChecked(room == self._current_room)
            if selected:
                self._room_strip.ensureWidgetVisible(btn, 16, 0)

    def _build_room_menu(self):
        devices = [d for d in self._displayed_devices()
                   if self._current_home == _ALL_HOMES or d.home_name == self._current_home]
        entries = []
        for room in self._tab_buttons:
            count = (None if room == _SCENE_TAB else len(devices) if room == _ALL_ROOMS
                     else sum(d.room_name == room for d in devices))
            entries.append((room, count))
        return build_room_menu(self, entries, self._current_room, self._select_room)

    def _show_room_menu(self):
        menu = self._build_room_menu()
        menu.ensurePolished()
        point = self._room_menu_btn.mapToGlobal(self._room_menu_btn.rect().bottomRight())
        point.setX(point.x() - menu.sizeHint().width() + 1)
        menu.exec(point + QPoint(0, 6))
        menu.deleteLater()

    # ---------- 卡片网格 ----------

    def _rebuild_grid(self) -> None:
        # 窗口不可见时跳过实际构建（尺寸也尚未确定），留待 showEvent
        if not self.isVisible():
            self._grid_dirty = True
            self._grid_columns = 0
            return
        self._grid_dirty = False
        # 设备与场景两个视图共用网格：切换视图时旧卡片已从布局移除并
        # 排队销毁，若不清引用，下次重建会对已销毁的 C++ 对象再次
        # deleteLater 抛 RuntimeError，界面卡在当前视图无法切换
        for card in self._cards.values():
            card.deleteLater()
        self._cards.clear()
        for card in self._scene_cards.values():
            card.deleteLater()
        self._scene_cards.clear()
        # takeAt 会移除条目，count 随之递减，循环必然终止
        while self._grid.count():
            if widget := self._grid.takeAt(0).widget():
                widget.deleteLater()

        if self._current_room == _SCENE_TAB:
            self._rebuild_scene_grid()
            return

        visible = sorted(
            self._visible_devices(),
            key=lambda d: (0 if d.online else 1, d.name),
        )
        cols = self._columns_for_width(self._scroll.viewport().width())
        self._grid_columns = cols
        rows = (len(visible) + cols - 1) // cols
        for index, device in enumerate(visible):
            card = DeviceCard(device)
            card.set_panel_states(self._known_power)
            card.setFixedWidth(self._grid_card_width(cols, index % cols))
            # 记忆里的开关状态与读数立即回显，重建卡片不丢状态
            known = self._known_power.get(device.did)
            if known is not None:
                card.set_power_state(known)
            if device.did in self._metrics:
                card.set_metrics(self._metrics.get(device.did))
            # 已下载的图标从本地文件回填：主题/tab 切换重建卡片后
            # 图标不消失；未下载的由 _load_card_icons 后台补齐
            path = icon_store.icon_path(device.model)
            if path.is_file():
                card.set_icon(path)
            card.power_clicked.connect(self._on_power_clicked)
            card.open_requested.connect(self._on_open_device)
            self._cards[device.did] = card
            self._grid.addWidget(card, index // cols, index % cols)
        self._finalize_grid(cols, rows)

    def _rebuild_scene_grid(self) -> None:
        """场景视图网格：卡片尺寸与设备卡一致，列数换算直接复用。"""
        scenes = sorted(self._scenes or [], key=lambda s: s.name)
        if not scenes:
            # 空状态：居中提示（含「确认无场景」与加载失败两种来源）
            hint = QLabel("暂无场景，可在米家 APP「智能」中添加")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setFont(QFont("Microsoft YaHei UI", 12))
            hint.setStyleSheet(
                f"color: {SiColors.TEXT_MUTED}; background: transparent;")
            self._grid.addWidget(hint, 0, 0)
            return

        cols = self._columns_for_width(self._scroll.viewport().width())
        self._grid_columns = cols
        rows = (len(scenes) + cols - 1) // cols
        for index, scene in enumerate(scenes):
            card = SceneCard(scene)
            card.setFixedWidth(self._grid_card_width(cols, index % cols))
            card.executed.connect(self._on_scene_executed)
            self._scene_cards[scene.scene_id] = card
            self._grid.addWidget(card, index // cols, index % cols)
        self._finalize_grid(cols, rows)

    def _finalize_grid(self, cols: int, rows: int) -> None:
        # 剩余空间分配给卡片本身，间距固定；清理历史 stretch，避免
        # 减少列数后旧列仍占用宽度。最后不足一排时保持左对齐。
        for col in range(max(cols, self._grid.columnCount())):
            self._grid.setColumnStretch(col, 0)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignLeft)
        # 多余垂直空间全部推到最后一行之后，避免行距被均分拉大
        for row in range(max(rows, self._grid.rowCount())):
            self._grid.setRowStretch(row, 0)
        self._grid.setRowStretch(rows, 1)

    def _columns_for_width(self, width: int) -> int:
        # 以最小卡片宽度计算列数，宽屏自动增加列数。
        from app.ui.device_card import _CARD_FIXED_WIDTH
        spacing = self._grid.spacing()
        eff = max(0, width)
        if eff <= 0:
            return 1
        cols = (eff + spacing) // (_CARD_FIXED_WIDTH + spacing)
        # 不设单排上限——宽屏下应自然补列而不是拉开卡片间距
        return max(1, cols)

    def _grid_card_width(self, cols: int, column: int = 0) -> int:
        """Distribute rounding pixels across columns so both outer margins match."""
        from app.ui.device_card import _CARD_FIXED_WIDTH
        available = self._scroll.viewport().width()
        width, remainder = divmod(available - (cols - 1) * self._grid.spacing(), cols)
        return max(_CARD_FIXED_WIDTH, width + (column < remainder))

    def showEvent(self, event) -> None:  # noqa: N802 (Qt 命名约定)
        super().showEvent(event)
        self._network_monitor.check_now()
        # 统一使用逻辑尺寸：200% 系统缩放时对应 2320×1480 物理像素。
        # 首次显示居中；后续托盘唤出保留用户调整的位置和大小。
        if not self._default_size_applied:
            self._default_size_applied = True
            self.resize(1160, 740)
            from PySide6.QtGui import QGuiApplication
            screen = self.screen() or QGuiApplication.primaryScreen()
            avail = screen.availableGeometry()
            self.move(avail.center().x() - self.width() // 2,
                      avail.center().y() - self.height() // 2)
        # 托盘常驻启动/唤出：隐藏期间积压的网格重建在此执行
        if self._grid_dirty:
            self._rebuild_grid()

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt 命名约定)
        super().resizeEvent(event)
        # 系统缩放切换时 Qt 对无边框窗口的尺寸重算可能失控（窗口被
        # 成倍放大超出屏幕），每次尺寸变化都钳制回所在屏幕的可用区域
        self._clamp_to_screen()
        # 缩放（DPR）变化：Qt 保持物理尺寸导致逻辑尺寸被重算——恢复
        # 变化前的逻辑尺寸，让窗口与界面元素同步缩放
        dpr = self.devicePixelRatioF() or 1.0
        if (self._last_dpr is not None and self._expected_logical is not None
                and abs(dpr - self._last_dpr) > 1e-9
                and not self.isMaximized() and not self.isMinimized()):
            w, h = self._expected_logical
            self._expected_logical = None
            QTimer.singleShot(0, lambda: (self.resize(w, h), self._clamp_to_screen()))
            self._last_dpr = dpr
        else:
            self._expected_logical = (self.width(), self.height())
            self._last_dpr = dpr
        # 拖动窗口时 resizeEvent 每秒触发几十次，全部重建卡片网格代价
        # 太高；防抖等布局稳定，列数真的变化时才重建
        self._resize_timer.start()
        self._voice_fab.reposition()

    def _clamp_to_screen(self) -> None:
        """把窗口尺寸/位置钳制回所在屏幕的可用工作区。

        覆盖两类异常：系统缩放切换后窗口异常放大；分辨率切换后窗口
        大半落在屏幕外。最大化/最小化状态不干预。
        """
        if self.isMaximized() or self.isMinimized():
            return
        screen = self.screen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        w, h = self.width(), self.height()
        if w > avail.width() or h > avail.height():
            self.resize(min(w, avail.width()), min(h, avail.height()))
        # 位置 sanity：窗口完全落在屏幕外时拉回可见区域
        g = self.geometry()
        if (g.right() < avail.left() or g.left() > avail.right()
                or g.bottom() < avail.top() or g.top() > avail.bottom()):
            self.move(avail.left() + 12, avail.top() + 12)

    def _on_resize_settled(self) -> None:
        # 按当前视图取卡片集合：空态（无卡片）无需重排
        cards = self._scene_cards if self._current_room == _SCENE_TAB else self._cards
        if not cards:
            return
        if self._columns_for_width(self._scroll.viewport().width()) != self._grid_columns:
            self._rebuild_grid()
        else:
            for index, card in enumerate(cards.values()):
                width = self._grid_card_width(self._grid_columns, index % self._grid_columns)
                if card.width() != width:
                    card.setFixedWidth(width)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt 命名约定)
        if (obj is getattr(self, "_device_summary", None)
                and event.type() == QEvent.Type.Resize):
            self._style_device_summary()
        if (obj is getattr(self, "_title_bar", None)
                and event.type() == QEvent.MouseButtonDblClick
                and event.button() == Qt.LeftButton):
            self._toggle_maximized()
            return True
        # 视口宽度变化的第二信号源（第一是窗口 resizeEvent）：滚动条
        # 显隐、布局瀑布等因素会让视口宽度晚于窗口稳定，此时复用同一
        # 防抖与列数校验，保证网格列数与最终视口宽度一致
        if (hasattr(self, "_scroll") and obj is self._scroll.viewport()
                and event.type() == QEvent.Type.Resize
                and self.isVisible()):
            self._resize_timer.start()
        return super().eventFilter(obj, event)

    # ---------- 快速开关 ----------

    def _on_power_clicked(self, did: str) -> None:
        card = self._cards.get(did)
        if card is None:
            return
        card.set_busy(True)
        self._jobs.submit(
            lambda: self._service.toggle_power(did),
            on_success=lambda new_state, c=card, d=did:
                self._on_power_done(c, d, new_state),
            on_error=lambda err, c=card: self._on_power_failed(c, err),
        )

    def _on_power_done(self, card: DeviceCard, did: str, new_state: bool) -> None:
        # 卡片可能在任务排队期间随网格重建被销毁，回调前先确认存活
        if not shiboken6.isValid(card):
            return
        card.set_busy(False)
        card.set_power_state(new_state)
        self._known_power[did] = new_state
        self._update_panel_cards()
        self._update_tray_devices()
        Toast.info(
            self, f"已{'打开' if new_state else '关闭'}「{card.device.name}」", 2500
        )

    def _on_power_failed(self, card: DeviceCard, error: Exception) -> None:
        if not shiboken6.isValid(card):
            return
        card.set_busy(False)
        QMessageBox.warning(self, "操作失败", str(error))

    # ---------- 场景（手动控制） ----------

    def _load_scenes(self) -> None:
        """拉取当前范围的场景列表；失败保留已有缓存。"""
        if not self._network_online or self._logged_out:
            return
        if self._loading_scenes:
            return
        self._loading_scenes = True
        self._jobs.submit(
            lambda: self._service.scene_list(
                None if self._current_home == _ALL_HOMES else self._current_home),
            on_success=self._on_scenes_loaded,
            on_error=self._on_scenes_failed,
        )

    def _on_scenes_loaded(self, scenes: list[SceneInfo]) -> None:
        self._loading_scenes = False
        self._scenes = scenes
        if self._current_room == _SCENE_TAB:
            self._rebuild_grid()
            self._update_count_label()

    def _on_scenes_failed(self, error: Exception) -> None:
        # 网络失败不打断界面：保留已有缓存，仅提示
        self._loading_scenes = False
        logger.warning("加载场景失败: %s", error)
        if self._current_room != _SCENE_TAB:
            # 预取失败且用户不在场景视图：静默；进场景页时会重新拉取
            return
        if self._scenes is None:
            self._show_status("场景加载失败", 4000)
        else:
            Toast.info(self, f"场景刷新失败：{error}", 4000)

    def _on_scene_executed(self, scene_id: str) -> None:
        scene = next((s for s in (self._scenes or []) if s.scene_id == scene_id), None)
        card = self._scene_cards.get(scene_id)
        if scene is None or card is None:
            return
        card.set_busy(True)
        self._jobs.submit(
            lambda s=scene: self._service.run_scene(s),
            on_success=lambda _, s=scene, c=card: self._on_scene_done(s, c),
            on_error=lambda e, s=scene, c=card: self._on_scene_failed(s, c, e),
        )

    def _on_scene_done(self, scene: SceneInfo, card: SceneCard) -> None:
        # 卡片可能在任务排队期间随网格重建被销毁，回调前先确认存活
        if not shiboken6.isValid(card):
            return
        card.set_busy(False)
        Toast.info(self, f"已执行场景「{scene.name}」", 2500)

    def _on_scene_failed(self, scene: SceneInfo, card: SceneCard, error: Exception) -> None:
        if not shiboken6.isValid(card):
            return
        card.set_busy(False)
        Toast.info(self, f"执行场景「{scene.name}」失败：{error}", 4000)

    # ---------- 详情 ----------

    def _on_open_device(self, did: str) -> None:
        device = next((d for d in self._all_devices if d.did == did), None)
        if device is None:
            return
        if not has_device_details(device) or not device.online:
            return
        if is_light(device):
            self._open_light_window(device)
            return
        if '.camera.' in device.model:
            self._open_camera_window(device)
            return

    def _open_light_window(self, device, *, from_tray=False):
        from app.ui.light_controls import LightControlDialog
        if not has_device_details(device) or self._access_state() != 'ready':
            return
        if not hasattr(self, '_light_windows'):
            self._light_windows = {}
        current = self._light_windows.get(device.did)
        if current is not None and shiboken6.isValid(current):
            current.show()
            current.raise_()
            current.activateWindow()
            return
        dialog = LightControlDialog(self._service, self._jobs, device,
                                    None if from_tray else self)
        self._light_windows[device.did] = dialog
        dialog.power_changed.connect(lambda state: (
            self._apply_power_state(device.did, state), self._update_tray_devices()))
        def closed(_):
            self._light_windows.pop(device.did, None)
            self._refresh_closed_detail(device.did)
            dialog.deleteLater()
        dialog.finished.connect(closed)
        card = self._cards.get(device.did)
        anchor = card.mapToGlobal(card.rect().bottomLeft()) if card is not None and self.isVisible() and not from_tray else None
        dialog.show_near(anchor)
        dialog.load()

    def _open_camera_window(self, device):
        if not hasattr(self, '_camera_windows'):
            self._camera_windows = {}
        current = self._camera_windows.get(device.did)
        if current is not None and shiboken6.isValid(current):
            if current.isMinimized():
                current.showNormal()
            current.show()
            current.raise_()
            current.activateWindow()
            return
        dialog = DeviceDetailDialog(self._service, self._jobs, device)
        self._camera_windows[device.did] = dialog
        def closed(_):
            self._camera_windows.pop(device.did, None)
            self._refresh_closed_detail(device.did)
            dialog.deleteLater()
        dialog.finished.connect(closed)
        dialog.load()
        dialog.show()
        dialog.activateWindow()

    def _refresh_closed_detail(self, did):
        if did in self._cards:
            self._jobs.submit(
                lambda: self._service.power_state(did),
                on_success=lambda state, d=did: self._apply_power_state(d, state),
                on_error=lambda exc: logger.warning("详情关闭后回读开关失败: %s", exc),
            )

    # ---------- 资源 ----------

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt 命名约定)
        # 托盘常驻时关闭窗口仅隐藏到托盘，不退出（除非走托盘"退出"）
        # 用户可在设置中关闭此行为，此时直接退出
        from app.core.settings_store import get_minimize_to_tray
        if get_minimize_to_tray() and not self._force_quit and self._tray is not None:
            # 隐藏窗口前确保托盘图标可见，常驻运行等待托盘重新呼出
            try:
                self._tray.set_tray_visible(True)
            except Exception:
                pass
            event.ignore()
            self.hide()
            # 常驻托盘态把物理页交还系统，任务管理器占用显著下降
            from app import trim_working_set
            trim_working_set()
            return
        # 真正退出
        if self._all_devices:
            device_cache.save(self._all_devices, self._known_power, self._metrics)
        if self._tray is not None:
            try:
                self._tray.hide_quick()
                self._tray._tray.hide()
            except Exception:
                pass
        self._jobs.shutdown()
        super().closeEvent(event)
        # quitOnLastWindowClosed 为 False（托盘常驻需要），关闭窗口不会自动
        # 退出事件循环；关闭托盘设置时需显式退出让进程真正结束
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.quit()


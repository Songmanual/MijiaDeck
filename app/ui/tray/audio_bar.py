# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""托盘快捷窗口顶部的简易音箱控制栏。"""

import shiboken6
import time

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import qtawesome as qta

from app.core.jobs import JobExecutor
from app.core.service import MijiaService
from app.ui.si_theme import SiColors
from app.ui.volume_slider import VolumeSlider


class _TrayAudioBar(QFrame):
    """托盘顶部的简易音箱控制栏：上一首 / 静音(播放暂停) / 下一首 + 音量条。"""

    speaker_requested = Signal()

    def __init__(self, service: MijiaService, jobs: JobExecutor, parent=None):
        super().__init__(parent)
        self._service = service
        self._jobs = jobs
        self._did: str | None = None
        self._speaker_revision = 0
        self._interaction_revision = 0
        self._read_in_flight = False
        self._mute_pending = False
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(2000)
        self._poll_timer.timeout.connect(self.refresh_state)
        self._command_refresh_timers = []
        for delay in (700, 2200):
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(delay)
            timer.timeout.connect(self.refresh_state)
            self._command_refresh_timers.append(timer)
        self._muted: bool | None = None
        self._mute_name: str = "mute-2"
        self._vol_name: str = "volume"
        self._vol_min = 0
        self._vol_max = 100
        self.setObjectName("audioBar")
        self.setStyleSheet(
            "QFrame#audioBar { background: transparent; border: none; }")
        self.hide()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 15, 10, 0)
        lay.setSpacing(0)

        # 标题：左上角加粗白字，与托盘设备一致
        self._drag_header = QWidget(self)
        self._drag_header.setStyleSheet('background: transparent;')
        tit = QHBoxLayout(self._drag_header)
        tit.setContentsMargins(0, 0, 0, 0)
        self._speaker_btn = QPushButton("小爱音箱")
        self._speaker_btn.setAutoDefault(False)
        self._speaker_btn.setCursor(Qt.PointingHandCursor)
        self._speaker_btn.setLayoutDirection(Qt.RightToLeft)
        self._speaker_btn.setIcon(qta.icon('mdi.chevron-down', color=SiColors.TEXT_SECONDARY))
        self._speaker_btn.setIconSize(QSize(14, 14))
        self._speaker_btn.setStyleSheet(
            f"QPushButton {{ color: {SiColors.TEXT_PRIMARY}; background: transparent; border: none;"
            " padding: 0; font-size: 12pt; font-weight: 600; }")
        self._speaker_btn.clicked.connect(self.speaker_requested.emit)
        tit.addWidget(self._speaker_btn)
        tit.addStretch(1)
        lay.addWidget(self._drag_header)
        lay.addSpacing(4)

        # 上排：⏮  ⏯(大)  ⏭  居中
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch(1)

        self._btn_prev = QPushButton()
        self._btn_prev.setIcon(qta.icon('mdi.skip-previous', color=SiColors.TEXT_PRIMARY))
        self._btn_prev.setIconSize(QSize(38, 38))
        self._btn_prev.setFixedSize(46, 46)
        self._btn_prev.setCursor(Qt.PointingHandCursor)
        self._btn_prev.setAccessibleName("上一首")
        self._btn_prev.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 8px; }"
            f"QPushButton:hover {{ background: {SiColors.SURFACE}; }}"
            f"QPushButton:pressed {{ background: {SiColors.BTN_PRESSED}; }}")
        self._btn_prev.clicked.connect(self._on_prev)
        btn_row.addWidget(self._btn_prev)

        self._btn_play = QPushButton()
        self._btn_play.setIcon(qta.icon('mdi.play', color=SiColors.TEXT_PRIMARY))
        self._btn_play.setIconSize(QSize(56, 56))
        self._btn_play.setFixedSize(64, 64)
        self._btn_play.setCursor(Qt.PointingHandCursor)
        self._btn_play.setAccessibleName("播放")
        self._btn_play.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 8px; }"
            f"QPushButton:hover {{ background: {SiColors.SURFACE}; }}"
            f"QPushButton:pressed {{ background: {SiColors.BTN_PRESSED}; }}")
        self._btn_play.clicked.connect(self._on_toggle_mute)
        btn_row.addWidget(self._btn_play)

        self._btn_next = QPushButton()
        self._btn_next.setIcon(qta.icon('mdi.skip-next', color=SiColors.TEXT_PRIMARY))
        self._btn_next.setIconSize(QSize(38, 38))
        self._btn_next.setFixedSize(46, 46)
        self._btn_next.setCursor(Qt.PointingHandCursor)
        self._btn_next.setAccessibleName("下一首")
        self._btn_next.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 8px; }"
            f"QPushButton:hover {{ background: {SiColors.SURFACE}; }}"
            f"QPushButton:pressed {{ background: {SiColors.BTN_PRESSED}; }}")
        self._btn_next.clicked.connect(self._on_next)
        btn_row.addWidget(self._btn_next)

        btn_row.addStretch(1)
        lay.addLayout(btn_row)

        # 下排：音量条
        vol_row = QHBoxLayout()
        vol_row.setSpacing(0)

        self._slider = VolumeSlider()
        self._slider.setRange(0, 100)
        self._slider.valueChanged.connect(self._on_slider_preview)
        self._slider.sliderPressed.connect(self._begin_interaction)
        self._slider.sliderReleased.connect(self._on_slider_commit)
        vol_row.addWidget(self._slider, stretch=1)

        self._vol_label = self._slider.value_label

        lay.addLayout(vol_row)

        self._volume: int | None = None
        self._pending_volume: int | None = None
        self._volume_confirmation: tuple[int, float] | None = None

    # ---------- 对外：托盘刷新时调用 ----------

    def set_speaker(self, did: str | None, name: str = "") -> None:
        self._speaker_btn.setText(self._speaker_btn.fontMetrics().elidedText(
            name or "小爱音箱", Qt.ElideRight, 200))
        self._speaker_btn.setToolTip("")
        if did == self._did and did is not None:
            # 同一设备，仅刷新可见性
            self.setVisible(True)
            return
        self._did = did
        self._speaker_revision += 1
        self._read_in_flight = False
        self._mute_pending = False
        for timer in self._command_refresh_timers:
            timer.stop()
        self._volume = None
        self._pending_volume = None
        self._volume_confirmation = None
        self._muted = None
        if not did:
            self.hide()
            return
        self.setVisible(True)
        self._set_enabled(False)
        self._vol_label.setText("…")
        self._slider.setEnabled(False)
        # 拉取音量范围与当前值
        self.refresh_state()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._poll_timer.start()
        if self._did:
            self.refresh_state()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._poll_timer.stop()
        for timer in self._command_refresh_timers:
            timer.stop()
        super().hideEvent(event)

    def _begin_interaction(self) -> None:
        self._interaction_revision += 1

    def refresh_after_command(self, did: str) -> None:
        if did != self._did or not self.isVisible():
            return
        self._begin_interaction()
        self._volume_confirmation = None
        for timer in self._command_refresh_timers:
            timer.start()

    def refresh_state(self) -> None:
        if (not self._did or self._read_in_flight or self._slider.isSliderDown()
                or self._pending_volume is not None or self._mute_pending):
            return
        self._read_in_flight = True
        revision = self._interaction_revision
        did = self._did

        def success(data):
            self._read_in_flight = False
            if (revision == self._interaction_revision and not self._slider.isSliderDown()
                    and self._pending_volume is None and not self._mute_pending):
                self._apply_state(data)

        def error(err):
            self._read_in_flight = False
            if revision == self._interaction_revision:
                self._on_fetch_error(err)

        self._submit_for_speaker(lambda: self._fetch_state(did), success, error)

    def _submit_for_speaker(self, function, on_success, on_error) -> None:
        revision = self._speaker_revision

        def deliver(callback, result):
            if shiboken6.isValid(self) and revision == self._speaker_revision:
                callback(result)

        self._jobs.submit(function,
                          on_success=lambda result: deliver(on_success, result),
                          on_error=lambda error: deliver(on_error, error))

    def _fetch_state(self, did=None):
        # 后台线程：先拿 spec 范围，再批量读值
        did = did or self._did
        if not did:
            return None
        # 取 volume/mute 的范围与可读性；device_detail 会走 spec 缓存
        try:
            detail = self._service.device_detail(did)
        except Exception:
            # 拿不到 detail 仍尝试直接读值
            detail = None

        vol_range = (0, 100, 1)
        mute_name = "mute-2"
        vol_name = "volume"
        if detail is not None:
            # 不能在命中 mute-2 时 break：若它在 spec 里排在 volume
            # 前面，音量范围将永远读不到
            mute_2_found = False
            for p in detail.props:
                if p.name == "volume" and p.range:
                    vol_range = p.range
                    vol_name = p.name
                if p.name == "mute-2":
                    mute_2_found = True
            # 未命中 mute-2，找首个非 mute-4 的 mute（排除麦克风）
            if not mute_2_found:
                for p in detail.props:
                    if p.name.startswith("mute") and p.writable and p.name != "mute-4":
                        mute_name = p.name
                        break

        # 批量读当前值
        try:
            vals = self._service.read_props(did, [vol_name, mute_name])
        except Exception:
            vals = {vol_name: None, mute_name: None}

        return {
            "vol_range": vol_range,
            "vol_name": vol_name,
            "mute_name": mute_name,
            "vals": vals,
        }

    def _apply_state(self, data) -> None:
        if not shiboken6.isValid(self) or data is None:
            return
        if self._did is None:
            return
        vol_range = data.get("vol_range", (0, 100, 1))
        self._vol_min, self._vol_max = int(vol_range[0]), int(vol_range[1])
        self._mute_name = data.get("mute_name", "mute-2")
        self._vol_name = data.get("vol_name", "volume")
        vals = data.get("vals", {})
        vol_name = self._vol_name
        mute_name = self._mute_name

        vol = vals.get(vol_name)
        mute = vals.get(mute_name)
        # 写入成功不代表云端读缓存立即更新。短暂保留刚设定的值，
        # 读到目标值即解除保护；超时后仍以设备实际读数为准。
        if self._volume_confirmation is not None and isinstance(vol, (int, float)):
            target, deadline = self._volume_confirmation
            if int(vol) == target or time.monotonic() >= deadline:
                self._volume_confirmation = None
            else:
                vol = None

        # 设滑块范围
        self._slider.blockSignals(True)
        try:
            self._slider.setRange(self._vol_min, self._vol_max)
            if isinstance(vol, (int, float)):
                self._slider.setValue(int(vol))
                self._vol_label.setText(str(int(vol)))
                self._volume = int(vol)
            elif self._volume is None:
                self._vol_label.setText("—")
        finally:
            self._slider.blockSignals(False)

        if isinstance(mute, bool):
            self._muted = mute
        elif isinstance(mute, int):
            self._muted = bool(mute)

        self._refresh_play_style()
        self._set_enabled(True)

    def _on_fetch_error(self, err: Exception) -> None:
        if not shiboken6.isValid(self):
            return
        if self._volume is None:
            self._vol_label.setText("—")
        self._set_enabled(self._did is not None)

    def _set_enabled(self, enabled: bool) -> None:
        self._btn_prev.setEnabled(enabled)
        self._btn_next.setEnabled(enabled)
        self._btn_play.setEnabled(enabled)
        self._slider.setEnabled(enabled)

    def _refresh_play_style(self) -> None:
        # 按钮点击切换静音：已静音显示「播放」（点击恢复），未静音
        # 图标和无障碍名称指向同一动作，不显示悬停文字。
        if self._muted:
            self._btn_play.setIcon(qta.icon('mdi.play', color=SiColors.TEXT_PRIMARY))
            self._btn_play.setAccessibleName("播放")
        else:
            self._btn_play.setIcon(qta.icon('mdi.pause', color=SiColors.TEXT_PRIMARY))
            self._btn_play.setAccessibleName("暂停")

    # ---------- 交互 ----------

    def _on_slider_preview(self, v: int) -> None:
        self._vol_label.setText(str(v))

    def _on_slider_commit(self) -> None:
        if not self._did:
            return
        v = int(self._slider.value())
        self._begin_interaction()
        # 松手才下发，避免拖动连击
        self._pending_volume = v
        self._volume_confirmation = None
        self._slider.setEnabled(False)
        did, vol_name = self._did, self._vol_name
        self._submit_for_speaker(
            lambda v=v, did=did, prop=vol_name: self._service.write_prop(did, prop, v),
            on_success=lambda _, v=v: self._on_volume_written(v),
            on_error=self._on_volume_error,
        )

    def _on_volume_written(self, v: int) -> None:
        if not shiboken6.isValid(self):
            return
        self._volume = v
        self._pending_volume = None
        self._slider.setEnabled(True)
        self.refresh_after_command(self._did)
        self._volume_confirmation = (v, time.monotonic() + 6)

    def _on_volume_error(self, err: Exception) -> None:
        if not shiboken6.isValid(self):
            return
        self._pending_volume = None
        self._volume_confirmation = None
        self._slider.setEnabled(True)
        # 回滚为旧值
        if self._volume is not None:
            self._slider.blockSignals(True)
            try:
                self._slider.setValue(int(self._volume))
                self._vol_label.setText(str(int(self._volume)))
            finally:
                self._slider.blockSignals(False)
        from app.ui.toast import Toast
        try:
            Toast.info(self, f"音量设置失败：{err}", 2500)
        except Exception:
            pass

    def _on_toggle_mute(self) -> None:
        if not self._did:
            return
        self._begin_interaction()
        self._mute_pending = True
        # 若尚未读到状态，按切换为静音处理
        cur = self._muted
        new_val = not cur if isinstance(cur, bool) else True
        self._btn_play.setEnabled(False)
        did = self._did
        mn = self._mute_name
        self._submit_for_speaker(
            lambda did=did, mn=mn, nv=new_val: self._service.write_prop(did, mn, nv),
            on_success=lambda _, nv=new_val: self._on_mute_written(nv),
            on_error=self._on_mute_error,
        )

    def _on_mute_written(self, new_val: bool) -> None:
        if not shiboken6.isValid(self):
            return
        self._muted = new_val
        self._mute_pending = False
        self._refresh_play_style()
        self._btn_play.setEnabled(True)
        self.refresh_after_command(self._did)

    def _on_mute_error(self, err: Exception) -> None:
        if not shiboken6.isValid(self):
            return
        self._mute_pending = False
        self._btn_play.setEnabled(True)
        from app.ui.toast import Toast
        try:
            Toast.info(self, f"静音切换失败：{err}", 2500)
        except Exception:
            pass

    def _on_prev(self) -> None:
        if not self._did:
            return
        self._btn_prev.setEnabled(False)
        did = self._did
        self._submit_for_speaker(
            lambda did=did: self._service.run_action(did, "previous"),
            on_success=lambda _, b=self._btn_prev: self._on_action_ok(b),
            on_error=lambda e, b=self._btn_prev: self._on_action_error(e, b),
        )

    def _on_next(self) -> None:
        if not self._did:
            return
        self._btn_next.setEnabled(False)
        did = self._did
        self._submit_for_speaker(
            lambda did=did: self._service.run_action(did, "next"),
            on_success=lambda _, b=self._btn_next: self._on_action_ok(b),
            on_error=lambda e, b=self._btn_next: self._on_action_error(e, b),
        )

    def _on_action_ok(self, btn: QPushButton) -> None:
        if not shiboken6.isValid(self):
            return
        btn.setEnabled(True)

    def _on_action_error(self, err: Exception, btn: QPushButton) -> None:
        if not shiboken6.isValid(btn):
            return
        btn.setEnabled(True)
        from app.ui.toast import Toast
        try:
            Toast.info(self, f"操作失败：{err}", 2500)
        except Exception:
            pass

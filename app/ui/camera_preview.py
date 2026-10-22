# SPDX-License-Identifier: GPL-3.0-or-later
"""Dedicated camera page: physical power, remote preview, audio and fullscreen."""
import threading
import time
import shiboken6
from PySide6.QtCore import QEvent, QPoint, QTimer, QUrl, Signal, Qt
from PySide6.QtGui import QColor
from PySide6.QtMultimedia import QMediaPlayer, QVideoSink, QAudioSink, QAudioFormat
from PySide6.QtWidgets import QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QMenu, QVBoxLayout, QWidget
from app.core.camera_preview import CameraPreviewError, CameraSession, ERRORS
from app.ui.camera_canvas import AspectVideoLayout, CameraCanvas
from app.ui.power_button import PowerButton
from app.ui.si_theme import SiColors
from app.ui.popup_menu import style_popup_menu
import qtawesome as qta


class CameraPreviewPanel(QFrame):
    _connected = Signal(int, str)
    _failed = Signal(int, object)
    _progress = Signal(int, str)
    _pcm = Signal(int, int, bytes)

    def __init__(self, service, jobs, device, parent=None):
        super().__init__(parent)
        self._service, self._jobs, self._device = service, jobs, device
        self._session = None
        self._generation = 0
        self._playing = False
        self._loaded = False
        self._read_pending = False
        self._power_busy = False
        self._power_state = None
        self._power_deadline = 0
        self._attempted = False
        self._quality = 1  # Fresh page always starts with the smooth stream; never persisted.
        self._muted = True
        self._audio_sink = None
        self._audio_io = None
        self._fullscreen = None
        self._drag_ready_at = 0
        self._url = ''
        self._switching_quality = False
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(16)
        self.header = QHBoxLayout()
        self.header.setSpacing(14)
        labels = QVBoxLayout()
        labels.setSpacing(4)
        self._title = QLabel(getattr(device, 'name', '摄像头'))
        self._title.setWordWrap(True)
        self._room = QLabel(getattr(device, 'room_name', ''))
        labels.addWidget(self._title)
        labels.addWidget(self._room)
        self.header.addLayout(labels, 1)
        self._power = PowerButton(44, 28, self)
        self._power.set_online(device.online)
        self._power.setToolTip('摄像头开关')
        self._power.clicked.connect(self._toggle_power)
        self.header.insertWidget(0, self._power, alignment=Qt.AlignVCenter)
        self._layout.addLayout(self.header)
        self._canvas = CameraCanvas(self)
        self._status = self._canvas._notice
        self._video_layout = AspectVideoLayout()
        self._video_layout.addWidget(self._canvas)
        self._layout.addLayout(self._video_layout, 1)
        self._drag_hint = QLabel('拖拽画面可调整摄像头角度', self)
        self._drag_hint.setAlignment(Qt.AlignCenter)
        self._drag_hint.setVisible(device.model == 'chuangmi.camera.029a02')
        self._hint_slot = QWidget(self)
        self._hint_slot.setVisible(device.model == 'chuangmi.camera.029a02')
        self._layout.addWidget(self._hint_slot)
        self._canvas.installEventFilter(self)
        self._canvas.retry.connect(self._retry)
        self._canvas.mute_clicked.connect(self._toggle_mute)
        self._canvas.quality_clicked.connect(self._show_quality)
        self._canvas.fullscreen_clicked.connect(self._toggle_fullscreen)
        self._canvas.dragged.connect(self._drag)
        self._sink = QVideoSink(self)
        self._player = QMediaPlayer(self)
        self._player.setVideoOutput(self._sink)
        self._player.errorOccurred.connect(self._on_player_error)
        self._sink.videoFrameChanged.connect(self._on_frame)
        self._connected.connect(self._on_connected)
        self._failed.connect(self._on_failed)
        self._progress.connect(self._on_progress)
        self._pcm.connect(self._on_pcm)
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(self._on_timeout)
        self._poll = QTimer(self)
        self._poll.setInterval(5000)
        self._poll.timeout.connect(self._refresh_power)
        QApplication.instance().aboutToQuit.connect(self.stop)
        self.retheme()

    def retheme(self):
        self.setStyleSheet('QFrame { background: transparent; border: none; }')
        self._title.setStyleSheet(f'color: {SiColors.TEXT_PRIMARY}; background: transparent; font-size: 15pt; font-weight: 600;')
        self._room.setStyleSheet(f'color: {SiColors.TEXT_SECONDARY}; background: transparent; font-size: 9pt;')
        hint_color = QColor(SiColors.TEXT_SECONDARY)
        hint_color.setAlphaF(.65)
        self._drag_hint.setStyleSheet(f'color: {hint_color.name(QColor.HexArgb)}; background: transparent; font-size: 8pt;')
        self._hint_slot.setFixedHeight(self._drag_hint.sizeHint().height())
        QTimer.singleShot(0, self, self._position_drag_hint)
        self._power._apply()

    def _position_drag_hint(self):
        if self._fullscreen is not None or not self._drag_hint.isVisible():
            return
        video_bottom = self._canvas.geometry().bottom() + 1
        window_bottom = self.mapFrom(self.window(), QPoint(0, self.window().height() - 1)).y()
        height = self._drag_hint.sizeHint().height()
        self._drag_hint.setGeometry(0, round((video_bottom + window_bottom - height) / 2),
                                    self.width(), height)
        self._drag_hint.raise_()

    def eventFilter(self, watched, event):
        if watched is self._canvas and event.type() in (QEvent.Resize, QEvent.Move):
            QTimer.singleShot(0, self, self._position_drag_hint)
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self, self._position_drag_hint)

    def load(self):
        self._loaded = True
        self._refresh_power()
        if self.isVisible():
            self._poll.start()

    def _refresh_power(self):
        if self._read_pending or self._power_busy or not self._device.online:
            if not self._device.online:
                self._canvas.message('摄像头已离线')
            return
        self._read_pending = True
        def success(state):
            if not shiboken6.isValid(self):
                return
            self._read_pending = False
            if self._power_busy or (time.monotonic() < self._power_deadline and state != self._power_state):
                return
            if state is None:
                if self._power_state is None:
                    self._canvas.message('暂时无法读取摄像头状态，点击画面重试')
                return
            self._apply_power(bool(state))
        def failure(_):
            if shiboken6.isValid(self):
                self._read_pending = False
                if self._power_state is None:
                    self._canvas.message('读取摄像头状态失败，点击画面重试')
        self._jobs.submit(lambda: self._service.power_state(self._device.did), on_success=success, on_error=failure)

    def _apply_power(self, state):
        previous = self._power_state
        self._power_state = state
        self._power.set_state(state)
        self._power.setToolTip('让摄像头休眠' if state else '唤醒摄像头')
        if not state:
            self.stop()
            self._attempted = False
            self._canvas.message('摄像机已休眠', sleeping=True)
        else:
            if previous is not True:
                self._attempted = False
            if self.isVisible() and not self._attempted and not self._session:
                self.start()

    def _toggle_power(self):
        if self._power_busy:
            return
        if self._power_state is None:
            self._refresh_power()
            return
        target = not self._power_state
        self._power_busy = True
        self._power.set_busy(True)
        def success(_):
            if not shiboken6.isValid(self):
                return
            self._power_busy = False
            self._power.set_busy(False)
            self._power_deadline = time.monotonic() + 5
            self._apply_power(target)
        def failure(_):
            if shiboken6.isValid(self):
                self._power_busy = False
                self._power.set_busy(False)
                self._canvas.message('摄像头开关操作失败，请重试', clear=False)
        self._jobs.submit(lambda: self._service.set_power_state(self._device.did, target), on_success=success, on_error=failure)

    def _retry(self):
        if self._power_state is None:
            self._refresh_power()
        elif self._power_state and not self._session:
            self.start()

    def start(self):
        if not self._device.online or self._power_state is False:
            self._canvas.message('摄像头已离线' if not self._device.online else '摄像机已休眠', sleeping=self._power_state is False)
            return
        self.stop()
        self._attempted = True
        session = CameraSession()
        self._session = session
        generation = self._generation
        self._canvas.message('正在申请视频连接…')
        self._timeout.start(100000)
        def prepare():
            if session.cancelled:
                raise CameraPreviewError('预览已取消。')
            try:
                return self._service.prepare_camera_source(self._device)
            except CameraPreviewError:
                raise
            except Exception:
                raise CameraPreviewError('摄像头视频授权失败，请重试。') from None
        def success(source):
            if not shiboken6.isValid(self) or generation != self._generation:
                session.stop()
                return
            def connect_relay():
                try:
                    url = session.start(source, quality=self._quality,
                        on_progress=lambda value: self._progress.emit(generation, value) if shiboken6.isValid(self) else None,
                        on_audio=lambda rate, data: self._pcm.emit(generation, rate, data) if shiboken6.isValid(self) else None)
                    if session.cancelled or not shiboken6.isValid(self):
                        session.stop()
                    else:
                        self._connected.emit(generation, url)
                except Exception as error:
                    session.stop()
                    if shiboken6.isValid(self):
                        safe = error if isinstance(error, CameraPreviewError) else CameraPreviewError('远程视频连接失败，请重试。')
                        self._failed.emit(generation, safe)
            threading.Thread(target=connect_relay, daemon=True, name='camera-relay-connect').start()
        def failure(error):
            session.stop()
            if shiboken6.isValid(self):
                self._on_failed(generation, error)
        self._jobs.submit(prepare, on_success=success, on_error=failure)

    def _on_connected(self, generation, url):
        if generation != self._generation or self._session is None:
            return
        self._canvas.message('正在载入画面…')
        self._url = url
        self._timeout.start(25000)
        self._player.setSource(QUrl(url))
        self._player.play()
        if not self._muted:
            self._session.command('AUDIO', 1)

    def _on_failed(self, generation, error):
        if generation == self._generation:
            self.stop()
            safe = str(error) if isinstance(error, CameraPreviewError) else '视频连接失败，请点击画面重试'
            self._canvas.message(safe)

    def _on_progress(self, generation, message):
        if generation != self._generation:
            return
        if message.startswith('ERROR '):
            self._on_failed(generation, CameraPreviewError(ERRORS.get(message[6:], '远程视频连接中断，请重试。')))
        elif message == 'NOTICE AUDIO_UNSUPPORTED':
            self._muted = True
            self._stop_audio()
            self._canvas.set_muted(True)
            self._canvas.mute.setToolTip('此设备的音频编码暂不支持')
        elif message == 'NOTICE CONTROL_FAILED':
            self._canvas.message('摄像头未能执行控制指令，请重试', clear=False)
        else:
            text = {'PHASE RELAY': '正在连接摄像头公网中继…', 'PHASE AUTH': '中继已连接，正在验证视频会话…',
                    'PHASE MEDIA': '视频授权已完成，正在等待摄像头画面…'}.get(message)
            if text:
                self._canvas.message(text)

    def _on_frame(self, frame):
        if self._session is None or self._switching_quality or not frame.isValid():
            return
        image = frame.toImage()
        if image.isNull():
            return
        self._playing = True
        self._timeout.stop()
        self._canvas.set_frame(image)
        self._video_layout.set_ratio(image.width(), image.height())
        self._canvas.set_controls_enabled(True)
        self._canvas.drag_enabled = self._device.model == 'chuangmi.camera.029a02'
        # No motor-completion acknowledgement is available. Require both a
        # settling interval and a subsequent decoded frame before another drag.
        if self._canvas.drag_busy and time.monotonic() >= self._drag_ready_at:
            self._canvas.set_drag_busy(False)
        height = frame.height()
        label = '自动' if self._quality == 0 else ('2K' if height > 1080 else f'{height}P')
        self._canvas.quality.setText(label)
        self._canvas.quality.setToolTip(f'切换画质 · 当前 {frame.width()} × {height}')

    def _on_player_error(self, error, _message):
        if self._session is not None and not self._switching_quality and error != QMediaPlayer.Error.NoError:
            self._on_failed(self._generation, CameraPreviewError('已连接视频流，但画面解码失败。点击画面重试。'))

    def _on_timeout(self):
        self.stop()
        self._canvas.message('远程预览超时，请点击画面重试')

    def _show_quality(self):
        menu = self._build_quality_menu()
        self._quality_menu = menu
        menu.aboutToHide.connect(menu.deleteLater)
        menu.ensurePolished()
        menu.adjustSize()
        menu.popup(self._canvas.quality.mapToGlobal(QPoint(0, -menu.sizeHint().height() - 6)))

    def _build_quality_menu(self):
        menu = QMenu(self._canvas)
        style_popup_menu(menu)
        known = self._device.model == 'chuangmi.camera.029a02'
        for value, label in [(0, '自动'), (1, '360P 流畅' if known else '流畅'), (2, '2K 高清' if known else '高清')]:
            action = menu.addAction(label)
            action.setFont(menu.font())
            action.setData(value)
            if value == self._quality:
                action.setIcon(qta.icon('mdi.check', color=SiColors.THEME_DIM))
            action.triggered.connect(lambda checked=False, q=value: self._select_quality(q))
        return menu

    def _select_quality(self, quality):
        if quality == self._quality:
            return
        if self._session and self._session.command('QUALITY', quality):
            self._quality = quality
            self._canvas.quality.setText({0: '自动', 1: '流畅', 2: '高清'}[quality])
            # Reopen only the local viewer so its TS header/decoder matches a codec
            # change (some cameras use a different codec for their SD stream).
            if self._url:
                self._switching_quality = True
                self._player.stop()
                self._player.setSource(QUrl())
                self._canvas.message('正在切换画质…', clear=False)
                generation = self._generation
                def reopen():
                    if generation == self._generation and self._session is not None:
                        self._switching_quality = False
                        self._timeout.start(25000)
                        self._player.setSource(QUrl(self._url))
                        self._player.play()
                QTimer.singleShot(900, self, reopen)

    def _toggle_mute(self):
        if not self._session or not self._playing:
            return
        target = not self._muted
        if self._session.command('AUDIO', 0 if target else 1):
            self._muted = target
            self._canvas.set_muted(target)
            if target:
                self._stop_audio()

    def _on_pcm(self, generation, rate, data):
        if generation != self._generation or self._muted or not self._playing:
            return
        if self._audio_sink is None:
            fmt = QAudioFormat()
            fmt.setSampleRate(rate)
            fmt.setChannelCount(1)
            fmt.setSampleFormat(QAudioFormat.Int16)
            self._audio_sink = QAudioSink(fmt, self)
            self._audio_sink.setBufferSize(rate // 2)
            self._audio_sink.setVolume(.8)
            self._audio_io = self._audio_sink.start()
        if self._audio_io and self._audio_sink.bytesFree() >= len(data):
            self._audio_io.write(data)

    def _stop_audio(self):
        if self._audio_sink is not None:
            self._audio_sink.stop()
            self._audio_sink.deleteLater()
        self._audio_sink = self._audio_io = None

    def _drag(self, direction):
        if (self._session and self._playing and self._canvas.drag_enabled
                and not self._canvas.drag_busy and not self._switching_quality):
            if self._session.command('PTZ', direction):
                self._drag_ready_at = time.monotonic() + 1.5
                self._canvas.set_drag_busy(True)

    def _toggle_fullscreen(self):
        if self._fullscreen is not None:
            self._fullscreen.reject()
            return
        window = QDialog(self.window(), Qt.Window | Qt.FramelessWindowHint)
        window.setWindowModality(Qt.WindowModal)
        window.setStyleSheet('background: black;')
        layout = QVBoxLayout(window)
        layout.setContentsMargins(0, 0, 0, 0)
        self._video_layout.removeWidget(self._canvas)
        layout.addWidget(self._canvas)
        self._fullscreen = window
        self._canvas.set_fullscreen(True)
        def restore(_):
            if not shiboken6.isValid(self):
                return
            layout.removeWidget(self._canvas)
            self._canvas.setParent(self)
            self._video_layout.addWidget(self._canvas)
            self._canvas.set_fullscreen(False)
            self._canvas.show()
            self._fullscreen = None
            window.deleteLater()
        window.finished.connect(restore)
        window.showFullScreen()

    def stop(self):
        self._generation += 1
        self._timeout.stop()
        self._playing = False
        self._switching_quality = False
        self._url = ''
        session, self._session = self._session, None
        self._player.stop()
        self._player.setSource(QUrl())
        self._stop_audio()
        if session is not None:
            session.stop()
        self._canvas.drag_enabled = False
        self._drag_ready_at = 0
        self._canvas.set_drag_busy(False)
        self._canvas.message('')
        self._canvas.set_controls_enabled(False)

    def showEvent(self, event):
        super().showEvent(event)
        if self._loaded:
            self._poll.start()
            self._refresh_power()

    def hideEvent(self, event):
        if self.window().isMinimized():
            # Minimizing is still an active viewing session. Keep the relay,
            # decoder and any pending authorization alive for instant restore.
            super().hideEvent(event)
            return
        self._poll.stop()
        self._attempted = False
        if self._fullscreen is not None:
            self._fullscreen.reject()
        self.stop()
        super().hideEvent(event)

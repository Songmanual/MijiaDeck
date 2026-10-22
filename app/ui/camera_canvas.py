# SPDX-License-Identifier: GPL-3.0-or-later
"""Aspect-preserving camera canvas with controls painted above decoded video."""
from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLayout, QPushButton, QWidget
import qtawesome as qta
import time


class AspectVideoLayout(QLayout):
    """Keep the canvas itself proportional, not only the image painted inside."""
    def __init__(self):
        super().__init__()
        self._item = None
        self._ratio = 16 / 9
        self.setContentsMargins(49, 12, 49, 0)

    def addItem(self, item):
        self._item = item
        self.invalidate()

    def count(self):
        return int(self._item is not None)

    def itemAt(self, index):
        return self._item if index == 0 else None

    def takeAt(self, index):
        if index != 0:
            return None
        item, self._item = self._item, None
        self.invalidate()
        return item

    def sizeHint(self):
        return QSize(738, 372)

    def minimumSize(self):
        return QSize(338, 147) if self._item is not None else QSize(0, 0)

    def set_ratio(self, width, height):
        if width > 0 and height > 0:
            ratio = width / height
            if abs(ratio - self._ratio) > .001:
                self._ratio = ratio
                self.invalidate()

    def setGeometry(self, rect):
        super().setGeometry(rect)
        if self._item is None:
            return
        bounds = self.contentsRect()
        width = min(bounds.width(), round(bounds.height() * self._ratio))
        height = round(width / self._ratio)
        self._item.setGeometry(QRect(bounds.x() + (bounds.width()-width)//2,
                                     bounds.y(), max(0, width), max(0, height)))


class CameraCanvas(QWidget):
    retry = Signal()
    dragged = Signal(int)
    mute_clicked = Signal()
    quality_clicked = Signal()
    fullscreen_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(240, 135)
        self._image = QImage()
        self._press = None
        self._drag_anchor = None
        self._drag_enabled = False
        self.drag_busy = False
        self._gesture_sent = False
        self._last_drag_step = 0.0
        self._notice = QLabel(self)
        self._notice.setAlignment(Qt.AlignCenter)
        self._notice.setWordWrap(True)
        self._notice.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._notice.setStyleSheet('background: transparent; color: #cbd1da; font-size: 10pt; border: none;')
        self._symbol = QLabel(self)
        self._symbol.setAlignment(Qt.AlignCenter)
        self._symbol.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._symbol.setStyleSheet('background: transparent; border: none;')
        self._symbol.setPixmap(qta.icon('mdi.camera-off', color='#8d949f').pixmap(44, 44))
        self._controls = QWidget(self)
        self._controls.setStyleSheet('background: transparent; border: none;')
        row = QHBoxLayout(self._controls)
        row.setContentsMargins(14, 0, 14, 0)
        row.setSpacing(10)
        self.mute = self._button('mdi.volume-off', '开启声音')
        self.quality = QPushButton('流畅', self._controls)
        self.quality.setFixedSize(54, 36)
        self.quality.setCursor(Qt.PointingHandCursor)
        self.quality.setToolTip('切换画质')
        self.quality.setStyleSheet('QPushButton { background: transparent; color: white; border: 1px solid rgba(255,255,255,190); border-radius: 6px; font-size: 10pt; font-weight: 600; } QPushButton:hover { background: rgba(255,255,255,25); } QPushButton:disabled { color: #646b74; border-color: #646b74; }')
        self.fullscreen = self._button('mdi.fullscreen', '全屏观看')
        row.addWidget(self.mute)
        row.addStretch()
        row.addWidget(self.quality)
        row.addStretch()
        row.addWidget(self.fullscreen)
        self.mute.clicked.connect(self.mute_clicked)
        self.quality.clicked.connect(self.quality_clicked)
        self.fullscreen.clicked.connect(self.fullscreen_clicked)
        self.message('正在读取摄像头状态…')
        self.set_controls_enabled(False)

    def _button(self, icon, tooltip):
        button = QPushButton(self._controls)
        button.setIcon(qta.icon(icon, color='white', color_disabled='#646b74'))
        button.setIconSize(QSize(28, 28))
        button.setFixedSize(42, 40)
        button.setCursor(Qt.PointingHandCursor)
        button.setToolTip(tooltip)
        button.setStyleSheet('QPushButton { background: transparent; border: none; border-radius: 7px; } QPushButton:hover { background: rgba(255,255,255,25); }')
        return button

    def message(self, text, *, clear=True, sleeping=False):
        if clear:
            self._image = QImage()
        self._notice.setText(text)
        self._notice.setVisible(bool(text))
        self._symbol.setVisible(sleeping)
        self.update()

    def set_frame(self, image):
        self._image = image
        self._notice.hide()
        self._symbol.hide()
        self.update()

    def set_muted(self, muted):
        self.mute.setIcon(qta.icon('mdi.volume-off' if muted else 'mdi.volume-high', color='white', color_disabled='#646b74'))
        self.mute.setToolTip('开启声音' if muted else '静音')

    def set_fullscreen(self, fullscreen):
        self.fullscreen.setIcon(qta.icon('mdi.fullscreen-exit' if fullscreen else 'mdi.fullscreen', color='white', color_disabled='#646b74'))
        self.fullscreen.setToolTip('退出全屏（Esc）' if fullscreen else '全屏观看')

    def set_controls_enabled(self, enabled):
        self.mute.setEnabled(enabled)
        self.quality.setEnabled(enabled)
        self.fullscreen.setEnabled(True)

    def resizeEvent(self, event):
        self._controls.setGeometry(14, max(0, self.height() - 62), max(0, self.width() - 28), 46)
        self._notice.setGeometry(24, max(0, self.height() // 2 - 15), max(0, self.width() - 48), 58)
        self._symbol.setGeometry(0, max(0, self.height() // 2 - 80), self.width(), 56)
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#080a0d'))
        if not self._image.isNull():
            size = self._image.size().scaled(self.size(), Qt.KeepAspectRatio)
            target = QRectF((self.width() - size.width()) / 2, (self.height() - size.height()) / 2, size.width(), size.height())
            painter.drawImage(target, self._image)
        gradient = QLinearGradient(0, self.height() - 100, 0, self.height())
        gradient.setColorAt(0, QColor(0, 0, 0, 0))
        gradient.setColorAt(1, QColor(0, 0, 0, 155))
        painter.fillRect(0, max(0, self.height() - 100), self.width(), 100, gradient)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.drag_busy:
                event.accept()
                return
            self._press = event.position().toPoint()
            self._drag_anchor = self._press
            self._gesture_sent = False
            self._last_drag_step = 0.0
            if self.drag_enabled:
                self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    @property
    def drag_enabled(self):
        return self._drag_enabled

    @drag_enabled.setter
    def drag_enabled(self, enabled):
        if self._drag_enabled == bool(enabled):
            return
        self._drag_enabled = bool(enabled)
        self._press = self._drag_anchor = None
        self.setCursor(Qt.OpenHandCursor if enabled else Qt.ArrowCursor)

    def _send_drag_step(self, point):
        if not self.drag_enabled or self.drag_busy or self._gesture_sent or self._drag_anchor is None:
            return
        delta = point - self._drag_anchor
        now = time.monotonic()
        if max(abs(delta.x()), abs(delta.y())) < 12 or now - self._last_drag_step < .4:
            return
        direction = (2 if delta.x() > 0 else 1) if abs(delta.x()) >= abs(delta.y()) else (4 if delta.y() > 0 else 3)
        self._drag_anchor = point
        self._last_drag_step = now
        self._gesture_sent = True
        self.dragged.emit(direction)

    def set_drag_busy(self, busy):
        self.drag_busy = bool(busy)
        if busy:
            # Discard the held gesture; unlocking never replays queued movement.
            self._press = self._drag_anchor = None
        self.setCursor(Qt.BusyCursor if busy else
                       (Qt.OpenHandCursor if self.drag_enabled else Qt.ArrowCursor))

    def mouseMoveEvent(self, event):
        if self._press is not None and event.buttons() & Qt.LeftButton:
            self._send_drag_step(event.position().toPoint())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._press is not None:
            point = event.position().toPoint()
            delta = point - self._press
            self._send_drag_step(point)
            self._press = None
            self._drag_anchor = None
            self.setCursor(Qt.BusyCursor if self.drag_busy else
                           (Qt.OpenHandCursor if self.drag_enabled else Qt.ArrowCursor))
            if not self._gesture_sent and self._image.isNull() and max(abs(delta.x()), abs(delta.y())) < 12:
                self.retry.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


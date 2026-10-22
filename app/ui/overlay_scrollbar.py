# SPDX-License-Identifier: GPL-3.0-or-later
"""An edge scrollbar that fades without changing the device viewport width."""
from PySide6.QtCore import QEvent, QObject, QPoint, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QGraphicsOpacityEffect, QScrollBar, QWidget

from app.ui.si_theme import SiColors


class OverlayScrollBar(QObject):
    def __init__(self, area, host):
        super().__init__(host)
        self.area = area
        self.host = host
        self.source = area.verticalScrollBar()
        area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.hovered = False

        # 透明热区比滑块略宽，鼠标靠近窗口右边缘即可唤出。
        self.edge = QWidget(host)
        self.edge.setStyleSheet('background: transparent;')
        self.edge.setMouseTracking(True)
        self.edge.installEventFilter(self)
        self.bar = QScrollBar(Qt.Vertical, self.edge)
        self.bar.setGeometry(4, 0, 6, 100)
        self.opacity = QGraphicsOpacityEffect(self.bar)
        self.opacity.setOpacity(0)
        self.bar.setGraphicsEffect(self.opacity)
        self.fade = QPropertyAnimation(self.opacity, b'opacity', self)
        self.fade.setDuration(180)
        self.idle = QTimer(self)
        self.idle.setSingleShot(True)
        self.idle.setInterval(1000)
        self.idle.timeout.connect(self._hide)

        self.source.rangeChanged.connect(self._sync_range)
        self.source.valueChanged.connect(self._sync_value)
        self.bar.valueChanged.connect(self.source.setValue)
        self.bar.sliderPressed.connect(self.reveal)
        self.bar.sliderReleased.connect(self._schedule_hide)
        host.installEventFilter(self)
        area.installEventFilter(self)
        area.viewport().installEventFilter(self)
        self.refresh_theme()
        self._sync_range(self.source.minimum(), self.source.maximum())

    def refresh_theme(self):
        self.bar.setStyleSheet(
            'QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }'
            f'QScrollBar::handle:vertical {{ background: {SiColors.SCROLLBAR}; border-radius: 3px; min-height: 32px; }}'
            f'QScrollBar::handle:vertical:hover {{ background: {SiColors.SCROLLBAR_HOVER}; }}'
            'QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }'
            'QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }'
        )

    def _position(self):
        top = self.area.mapTo(self.host, QPoint(0, 4)).y()
        height = max(0, self.area.height() - 16)
        self.edge.setGeometry(self.host.width() - 14, top, 12, height)
        self.bar.setGeometry(4, 0, 6, height)
        self.edge.raise_()

    def _sync_range(self, minimum, maximum):
        self.bar.setRange(minimum, maximum)
        self.bar.setPageStep(self.source.pageStep())
        self.bar.setSingleStep(self.source.singleStep())
        self.edge.setVisible(maximum > minimum)
        self._position()
        if maximum <= minimum:
            self.idle.stop()
            self.fade.stop()
            self.opacity.setOpacity(0)

    def _sync_value(self, value):
        self.bar.setValue(value)
        self.bar.setPageStep(self.source.pageStep())
        self.reveal()

    def reveal(self):
        if self.source.maximum() <= self.source.minimum():
            return
        self._position()
        self.fade.stop()
        self.fade.setStartValue(self.opacity.opacity())
        self.fade.setEndValue(1.0)
        self.fade.start()
        self._schedule_hide()

    def _schedule_hide(self):
        self.idle.stop()
        if not self.hovered and not self.bar.isSliderDown():
            self.idle.start()

    def _hide(self):
        if self.hovered or self.bar.isSliderDown():
            return
        self.fade.stop()
        self.fade.setStartValue(self.opacity.opacity())
        self.fade.setEndValue(0.0)
        self.fade.start()

    def eventFilter(self, obj, event):
        kind = event.type()
        if obj is self.edge:
            if kind == QEvent.Enter:
                self.hovered = True
                self.reveal()
            elif kind == QEvent.Leave:
                self.hovered = False
                self._schedule_hide()
        elif obj is self.area.viewport() and kind == QEvent.Wheel:
            self.reveal()
        if kind in (QEvent.Resize, QEvent.Show) and obj in (self.area, self.host):
            self._position()
            self.bar.setPageStep(self.source.pageStep())
        return super().eventFilter(obj, event)

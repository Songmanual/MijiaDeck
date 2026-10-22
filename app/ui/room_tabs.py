# SPDX-License-Identifier: GPL-3.0-or-later
"""A horizontal room strip with click-safe mouse dragging and wheel scrolling."""
from PySide6.QtCore import QEvent, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import (QAbstractButton, QApplication, QHBoxLayout, QLabel,
                              QMenu, QPushButton, QScrollArea, QSizePolicy,
                              QWidget, QWidgetAction)
from app.ui.si_theme import SiColors
from app.ui.popup_menu import style_popup_menu


class RoomTab(QAbstractButton):
    """Text-only tab; selection has an accent underline, never a filled tile."""
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet('background: transparent; font-size: 12pt;')
        font = QFont('Microsoft YaHei UI', 12, QFont.Bold)
        self.setFixedSize(QFontMetrics(font).horizontalAdvance(text) + 32, 52)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont('Microsoft YaHei UI', 12)
        font.setBold(self.isChecked())
        painter.setFont(font)
        color = QColor(SiColors.THEME if self.isChecked() else SiColors.TEXT_SECONDARY)
        if not self.isChecked():
            color.setAlphaF(0.7)
        painter.setPen(color)
        # The trailing menu icon uses the same full-height centre line.
        painter.drawText(self.rect(), Qt.AlignCenter, self.text())
        if self.isChecked():
            width = QFontMetrics(font).horizontalAdvance(self.text())
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF((self.width()-width)/2, self.height()-6, width, 2.5), 1.25, 1.25)
        painter.end()


def build_room_menu(parent, entries, current, on_select):
    """Room names and counts occupy separate columns, including long names."""
    menu = QMenu(parent)
    for name, count in entries:
        action = QWidgetAction(menu)
        action.setText(name)
        action.setData((name, count))
        row = QPushButton()
        row.setCursor(Qt.PointingHandCursor)
        row.setMinimumHeight(48)
        row.setAccessibleName(f'{name}，{count} 台设备' if count is not None else name)
        selected = name == current
        row.setStyleSheet(
            f'QPushButton {{ background: transparent; border: none; border-radius: 6px; }}'
            f'QPushButton:hover {{ background: {SiColors.BTN_HOVER}; }}')
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(24)
        title = QLabel(name)
        title.setAttribute(Qt.WA_TransparentForMouseEvents)
        title.setStyleSheet(f'background: transparent; color: {SiColors.THEME if selected else SiColors.TEXT_PRIMARY};'
                           f' font-size: 12pt; font-weight: {700 if selected else 400};')
        layout.addWidget(title)
        layout.addStretch(1)
        number = QLabel('' if count is None else str(count))
        number.setAttribute(Qt.WA_TransparentForMouseEvents)
        number.setStyleSheet(f'background: transparent; color: {SiColors.TEXT_SECONDARY}; font-size: 11pt;')
        layout.addWidget(number)
        action.setDefaultWidget(row)
        def choose(checked=False, room=name):
            menu.close()
            on_select(room)
        row.clicked.connect(choose)
        action.triggered.connect(choose)
        menu.addAction(action)
    # Adding QWidgetActions can recreate the native popup; apply flags last.
    style_popup_menu(menu)
    menu.setMinimumWidth(240)
    return menu


class RoomTabStrip(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setMinimumWidth(0)
        self.setFixedHeight(52)
        self.setStyleSheet('QScrollArea { background: transparent; border: none; }')
        self.viewport().setStyleSheet('background: transparent;')
        self._host = QWidget()
        self._host.setStyleSheet('background: transparent;')
        self.row = QHBoxLayout(self._host)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(18)
        self.setWidget(self._host)
        self._press = None
        self._dragging = False
        self.viewport().installEventFilter(self)
        self._host.installEventFilter(self)

    def watch_button(self, button):
        button.installEventFilter(self)

    def refresh(self):
        self._press = None
        self._dragging = False
        self.row.invalidate()
        self.row.activate()
        self._host.resize(self.row.sizeHint())

    def eventFilter(self, obj, event):
        kind = event.type()
        bar = self.horizontalScrollBar()
        if kind == QEvent.Wheel and bar.maximum() > 0:
            delta = event.pixelDelta()
            amount = delta.x() or delta.y()
            if not amount:
                delta = event.angleDelta()
                amount = (delta.x() or delta.y()) / 2
            bar.setValue(bar.value() - round(amount))
            event.accept()
            return True
        if kind == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            self._press = event.globalPosition().toPoint()
            self._start_value = bar.value()
            self._dragging = False
        elif kind == QEvent.MouseMove and self._press is not None:
            distance = event.globalPosition().toPoint() - self._press
            if (bar.maximum() > 0 and abs(distance.x()) >= QApplication.startDragDistance()
                    and abs(distance.x()) > abs(distance.y())):
                self._dragging = True
            if self._dragging:
                if hasattr(obj, 'setDown'):
                    obj.setDown(False)
                bar.setValue(self._start_value - distance.x())
                return True
        elif kind == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            dragged = self._dragging
            self._press = None
            self._dragging = False
            if dragged:
                if hasattr(obj, 'setDown'):
                    obj.setDown(False)
                return True
        return super().eventFilter(obj, event)

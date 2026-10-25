# SPDX-License-Identifier: GPL-3.0-or-later
"""Small everyday light controls, without the generic device editor."""
import shiboken6
from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication
from PySide6.QtWidgets import (QColorDialog, QDialog, QFrame, QHBoxLayout,
    QLabel, QPushButton, QSlider, QVBoxLayout, QWidget)
from app.core.device_controls import light_controls
from app.ui.power_button import PowerButton
from app.ui.si_theme import SiColors


class LightSlider(QSlider):
    committed = Signal()

    def __init__(self):
        super().__init__(Qt.Horizontal)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton:
            self.committed.emit()

    def wheelEvent(self, event):
        event.ignore()

    def keyReleaseEvent(self, event):
        super().keyReleaseEvent(event)
        if event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down,
                           Qt.Key_Home, Qt.Key_End, Qt.Key_PageUp, Qt.Key_PageDown):
            self.committed.emit()


class LightControlDialog(QDialog):
    power_changed = Signal(bool)

    def __init__(self, service, jobs, device, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setWindowTitle(device.name)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowModality(Qt.WindowModal if parent else Qt.NonModal)
        self._service, self._jobs, self.device = service, jobs, device
        self._closed = False
        self._busy = self._read_pending = self._loaded = False
        self._props, self._values, self._sliders, self._labels = {}, {}, {}, {}
        self._power_prop = None
        self._anchor = None
        self._last_power = None
        self._interaction_revision = 0
        self._color_button = None
        self._panel = QFrame(self)
        self._panel.setObjectName('lightPanel')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._panel)
        layout = QVBoxLayout(self._panel)
        layout.setContentsMargins(22, 18, 22, 20)
        layout.setSpacing(18)
        head = QHBoxLayout()
        self._title = QLabel(device.name)
        self._title.setFont(QFont('Microsoft YaHei UI', 12, QFont.DemiBold))
        self._title.setWordWrap(True)
        head.addWidget(self._title, 1)
        close = QPushButton('✕')
        close.setFixedSize(28, 28)
        close.setAccessibleName('关闭灯光控制')
        close.clicked.connect(self.reject)
        head.addWidget(close)
        layout.addLayout(head)
        self._body = QWidget()
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(20)
        self._body.hide()
        layout.addWidget(self._body)
        self._status = QLabel('正在读取灯光状态…')
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        self._poll = QTimer(self)
        self._poll.setInterval(2000)
        self._poll.timeout.connect(self.refresh)
        self.setFixedWidth(360)
        self.retheme()

    def _alive(self):
        return shiboken6.isValid(self) and not self._closed

    def load(self):
        if self._loaded:
            return
        self._loaded = True
        self._jobs.submit(lambda: self._service.device_detail(self.device.did),
                          on_success=self._build, on_error=self._failed)

    def _build(self, detail):
        if not self._alive():
            return
        self._props = light_controls(detail.props)
        if not self._props:
            self.reject()  # A plain on/off light never needs a second page.
            return
        self._power_prop = next((p for p in detail.props if p.type == 'bool'
            and p.writable and (p.name == 'on' or p.name.startswith(('on-', 'on_')))), None)
        if self._power_prop:
            row = QHBoxLayout()
            self._power_text = QLabel('状态待确认')
            row.addWidget(self._power_text, 1)
            self._power = PowerButton(36, 22)
            self._power.setEnabled(False)
            self._power.clicked.connect(self._toggle)
            row.addWidget(self._power)
            self._body_layout.addLayout(row)
        for kind in ('brightness', 'temperature'):
            if kind not in self._props:
                continue
            prop = self._props[kind]
            column = QVBoxLayout()
            label = QLabel('亮度' if kind == 'brightness' else '色温')
            value = QLabel('—')
            row = QHBoxLayout()
            row.addWidget(label, 1)
            row.addWidget(value)
            column.addLayout(row)
            slider = LightSlider()
            slider.setRange(0, 100 if kind == 'brightness' else 1000)
            slider.setEnabled(False)
            slider.setAccessibleName('灯光亮度' if kind == 'brightness' else '灯光色温')
            slider.sliderPressed.connect(self._begin_interaction)
            slider.valueChanged.connect(lambda _, k=kind: self._preview(k))
            slider.committed.connect(lambda k=kind: self._write(
                self._props[k].name, self._slider_value(k)))
            column.addWidget(slider)
            self._sliders[kind], self._labels[kind] = slider, value
            self._body_layout.addLayout(column)
        if 'color' in self._props:
            self._color_button = QPushButton('选择灯光颜色')
            self._color_button.setMinimumHeight(36)
            self._color_button.clicked.connect(self._choose_color)
            self._body_layout.addWidget(self._color_button)
        self._body.show()
        self.adjustSize()
        self._place_near(self._anchor or QCursor.pos())
        self.refresh()
        self._poll.start()

    def _slider_value(self, kind):
        prop, slider = self._props[kind], self._sliders[kind]
        low, high = prop.range[:2]
        value = (high * slider.value() / 100 if kind == 'brightness' else
                 low + (high - low) * slider.value() / slider.maximum())
        step = prop.range[2] if len(prop.range) > 2 and prop.range[2] else 1
        value = max(low, min(high, low + round((value - low) / step) * step))
        return float(value) if prop.type == 'float' else int(round(value))

    def _preview(self, kind):
        value = self._slider_value(kind)
        if kind == 'brightness':
            value = round(100 * value / self._props[kind].range[1])
        self._labels[kind].setText(f'{value:g}' + ('%' if kind == 'brightness' else ' K'))

    def refresh(self):
        if not self._alive() or self._busy or self._read_pending:
            return
        if any(slider.isSliderDown() for slider in self._sliders.values()):
            return
        names = [p.name for p in self._props.values() if p.readable]
        if self._power_prop and self._power_prop.readable:
            names.append(self._power_prop.name)
        self._read_pending = True
        revision = self._interaction_revision
        def success(values):
            if self._alive():
                self._read_pending = False
                if not self._busy and revision == self._interaction_revision and not any(
                        slider.isSliderDown() for slider in self._sliders.values()):
                    self._values.update(values)
                    self._render()
        def failure(error):
            if self._alive():
                self._read_pending = False
                self._failed(error)
        self._jobs.submit(lambda: self._service.read_props(self.device.did, names),
                          on_success=success, on_error=failure)

    def _render(self):
        enabled = True
        if self._power_prop:
            state = self._values.get(self._power_prop.name)
            self._power.set_state(state)
            self._power.setEnabled(state is not None and not self._busy)
            self._power_text.setText('状态待确认' if state is None else '已开启' if state else '已关闭')
            enabled = state is True
            if isinstance(state, bool) and state != self._last_power:
                self._last_power = state
                self.power_changed.emit(state)
        for kind, slider in self._sliders.items():
            prop = self._props[kind]
            value = self._values.get(prop.name)
            slider.setEnabled(enabled and value is not None and not self._busy)
            if value is None:
                continue
            low, high = prop.range[:2]
            fraction = value / high if kind == 'brightness' else (value - low) / (high - low)
            slider.blockSignals(True)
            slider.setValue(round(fraction * slider.maximum()))
            slider.blockSignals(False)
            self._preview(kind)
        if self._color_button:
            self._color_button.setEnabled(enabled and not self._busy)
        self._status.setText('')

    def _toggle(self):
        current = self._values.get(self._power_prop.name)
        if isinstance(current, bool):
            self._write(self._power_prop.name, not current)

    def _choose_color(self):
        prop = self._props['color']
        current = self._values.get(prop.name, 0xffffff)
        color = QColorDialog.getColor(QColor.fromRgb(current or 0), self, '选择灯光颜色')
        if color.isValid() and self._alive():
            self._write(prop.name, color.rgb() & 0xffffff)

    def _write(self, name, value):
        if self._busy or not self._alive():
            return
        self._busy = True
        self._begin_interaction()
        self._body.setEnabled(False)
        self._status.setText('正在设置…')
        def success(_):
            if self._alive():
                self._busy = False
                self._body.setEnabled(True)
                self._values[name] = value
                self._render()
        def failure(error):
            if self._alive():
                self._busy = False
                self._body.setEnabled(True)
                self._render()
                self._failed(error)
        self._jobs.submit(lambda: self._service.write_prop(self.device.did, name, value),
                          on_success=success, on_error=failure)

    def _begin_interaction(self):
        self._interaction_revision += 1

    def _failed(self, error):
        if self._alive():
            self._status.setText('暂时无法读取或设置灯光，请稍后重试。')

    def show_near(self, point=None):
        point = point or QCursor.pos()
        self._anchor = point
        self.adjustSize()
        self._place_near(point)
        self.show()
        self.raise_()
        self.activateWindow()

    def _place_near(self, point):
        screen = QGuiApplication.screenAt(point) or QGuiApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.move(QPoint(max(area.left(), min(point.x(), area.right() + 1 - self.width())),
                             max(area.top(), min(point.y(), area.bottom() + 1 - self.height()))))

    def done(self, result):
        self._closed = True
        self._poll.stop()
        super().done(result)

    def retheme(self):
        self._panel.setStyleSheet(
            f'QFrame#lightPanel {{ background: {SiColors.CARD}; border: 1px solid {SiColors.LINE}; border-radius: 14px; }}'
            f'QLabel {{ color: {SiColors.TEXT_PRIMARY}; background: transparent; }}'
            f'QPushButton {{ color: {SiColors.TEXT_PRIMARY}; background: {SiColors.SURFACE}; border: none; border-radius: 8px; padding: 5px; }}'
            f'QPushButton:hover {{ background: {SiColors.BTN_HOVER}; }}'
            f'QSlider::groove:horizontal {{ height: 5px; background: {SiColors.SURFACE}; border-radius: 2px; }}'
            f'QSlider::sub-page:horizontal {{ background: {SiColors.THEME}; border-radius: 2px; }}'
            f'QSlider::handle:horizontal {{ width: 16px; margin: -6px 0; border: none; border-radius: 8px; background: {SiColors.THEME}; }}')
        if hasattr(self, '_power'):
            self._power._apply()

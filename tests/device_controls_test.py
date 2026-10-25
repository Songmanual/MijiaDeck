# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only parent panels, direct light switches and the small light popup."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app.core import tray_store
from app.core.device_controls import (device_title, device_subtitle, has_device_details,
    light_controls, prepare_device_cards)
from app.core.models import DeviceInfo, PropInfo
from app.core.service import ServiceError
from app.ui.device_card import DeviceCard
from app.ui.device_dialog import DeviceDetailDialog
from app.ui.light_controls import LightControlDialog
from app.ui.main_window import MainWindow
from app.ui.tray.quick_window import TrayQuickWindow
from tools.test_light_controls import VirtualLightService, DEMO_DID


class Jobs:
    def __init__(self):
        self.pending = []

    def submit(self, fn, on_success=None, on_error=None, *, priority=10):
        self.pending.append((fn, on_success, on_error))

    def finish(self):
        fn, success, failure = self.pending.pop(0)
        try:
            result = fn()
        except Exception as error:
            if failure:
                failure(error)
        else:
            if success:
                success(result)


class DeviceControlsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for target, kwargs in (
            ('app.core._json_store.data_file', {'side_effect': lambda n: Path(self.temp.name) / n}),
            ('app.core._json_store.data_dir', {'return_value': Path(self.temp.name)}),
        ):
            p = patch(target, **kwargs)
            p.start()
            self.addCleanup(p.stop)
        self.widgets = []
        self.service = VirtualLightService()
        self.jobs = Jobs()

    def tearDown(self):
        for widget in self.widgets:
            if isinstance(widget, LightControlDialog):
                widget.reject()
            else:
                widget.hide()
            widget.deleteLater()
        self.app.processEvents()

    def panel_devices(self):
        parent = DeviceInfo('123', '吧台', 'xiaomi.switch.w3', 'Home', '吧台', True)
        children = [DeviceInfo(f'123.s{s}', f'灯{s}', parent.model, 'Home', '吧台', True)
                    for s in (2, 3, 4)]
        return prepare_device_cards([parent, *children])

    def popup(self):
        dialog = LightControlDialog(self.service, self.jobs, self.service.device)
        self.widgets.append(dialog)
        dialog.show()
        dialog.load()
        self.jobs.finish()  # supported controls
        self.jobs.finish()  # initial values
        return dialog

    def test_panel_card_has_no_power_or_details_even_with_old_cached_state(self):
        parent, *_ = self.panel_devices()
        card = DeviceCard(parent)
        self.widgets.append(card)
        card.set_power_state(True)
        card.set_metrics('24°C')
        card.set_panel_states({'123.s2': True, '123.s3': False, '123.s4': False})
        self.assertEqual(device_title(parent), '吧台面板')
        self.assertIn('设备温度 24°C', card._sub_label.text())
        self.assertIn('部分开启 · 1 路', card._sub_label.text())
        self.assertTrue(card._power_btn.isHidden())
        opened = Mock()
        card.open_requested.connect(opened)
        card.show()
        QTest.mouseClick(card, Qt.LeftButton, pos=QPoint(10, 10))
        opened.assert_not_called()

    def test_panel_unknown_temperature_is_omitted_and_unknown_channel_is_not_off(self):
        parent, *_ = self.panel_devices()
        text = device_subtitle(parent, None, {'123.s2': True, '123.s3': False})
        self.assertNotIn('温度', text)
        self.assertIn('状态待确认', text)

    def test_split_switch_and_plain_light_cannot_open_generic_editor(self):
        devices = self.panel_devices()
        devices.append(DeviceInfo('lamp', '普通灯', 'test.light.basic', 'H', 'R', True))
        for device in devices:
            self.assertFalse(has_device_details(device))
            with self.assertRaises(ValueError):
                DeviceDetailDialog(self.service, self.jobs, device)
            window = SimpleNamespace(_all_devices=[device])
            MainWindow._on_open_device(window, device.did)  # no dialog or cloud call

    def test_parent_can_be_added_to_tray_as_display_only(self):
        devices = self.panel_devices()
        tray_store.save(['123'])
        quick = TrayQuickWindow(self.service, self.jobs)
        self.widgets.append(quick)
        quick.set_devices(devices, {'123': True, '123.s2': True, '123.s3': False, '123.s4': False})
        quick.set_metrics({'123': '24°C'})
        quick._rebuild()
        row = quick._grid.itemAt(0).widget()
        self.assertIsNone(row._power_btn)
        self.assertEqual(row.cursor().shape(), Qt.ArrowCursor)
        self.assertIn('设备温度 24°C', quick._sub_labels['123'].text())
        quick._apply_power({'123.s3': True})
        self.assertIn('部分开启 · 2 路', quick._sub_labels['123'].text())

    def test_popup_only_has_everyday_controls_and_no_function_editor(self):
        dialog = self.popup()
        self.assertEqual(set(dialog._props), {'brightness', 'temperature', 'color'})
        self.assertEqual(dialog._sliders['brightness'].value(), 65)
        self.assertIn('4000', dialog._labels['temperature'].text())
        self.assertTrue(dialog._power.state())
        self.assertFalse(hasattr(dialog, '_drawer'))

    def test_sliders_preview_then_write_on_release_and_rgb_stays_in_memory(self):
        dialog = self.popup()
        slider = dialog._sliders['brightness']
        slider.setValue(80)
        self.assertEqual(self.service.values['brightness'], 65)
        slider.committed.emit()
        self.jobs.finish()
        self.assertEqual(self.service.values['brightness'], 80)
        with patch('app.ui.light_controls.QColorDialog.getColor', return_value=QColor('#3366ff')):
            dialog._choose_color()
        self.jobs.finish()
        self.assertEqual(self.service.values['color'], 0x3366ff)
        dialog._power.click()
        self.jobs.finish()
        self.assertFalse(self.service.values['on'])
        self.assertFalse(slider.isEnabled())

    def test_stale_read_does_not_reset_slider_during_drag(self):
        dialog = self.popup()
        dialog.refresh()
        slider = dialog._sliders['brightness']
        slider.setSliderDown(True)
        slider.setValue(90)
        self.jobs.finish()
        self.assertEqual(slider.value(), 90)
        slider.setSliderDown(False)

    def test_clicking_slider_track_also_commits_once(self):
        dialog = self.popup()
        self.app.processEvents()
        slider = dialog._sliders['brightness']
        QTest.mouseClick(slider, Qt.LeftButton, pos=QPoint(slider.width() - 2, slider.height() // 2))
        self.assertEqual(len(self.jobs.pending), 1)
        self.jobs.finish()
        self.assertNotEqual(self.service.values['brightness'], 65)

    def test_unsupported_and_readonly_properties_are_not_exposed(self):
        props = [PropInfo('mode', 'Mode', 'uint', True, True),
                 PropInfo('brightness', 'Brightness', 'uint', True, False, (1, 100, 1)),
                 PropInfo('color', 'Not RGB', 'uint', True, True, (0, 10, 1))]
        self.assertEqual(light_controls(props), {})

    def test_virtual_service_does_not_construct_account_client(self):
        self.assertFalse(hasattr(self.service, '_api'))
        with self.assertRaises(ServiceError):
            self.service.set_power_state('real-device', True)


if __name__ == '__main__':
    unittest.main()

"""Card roles must not expose incidental switches or generic editors."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app.core.models import DeviceInfo
from app.core.device_controls import supports_card_power, has_device_details, tray_eligible, prune_tray_selection
from app.core import tray_store
from app.ui.device_card import DeviceCard
from app.ui.device_dialog import DeviceDetailDialog
from app.ui.tray.manager_dialog import TrayManagerDialog
from app.ui.tray.quick_window import TrayQuickWindow
from tools.test_light_controls import VirtualLightService
from tests.device_controls_test import Jobs
from tests import split_switch_test
from app.core.service import ServiceError


def device(model, kind, did='test'):
    return DeviceInfo(did, '测试设备', model, '家', '测试房间', True,
                      f'urn:miot-spec-v2:device:{kind}:0000:test:1')


class CardRolesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_display_devices_ignore_old_cached_on_and_cannot_open_generic_editor(self):
        for model, kind in [('xiaomi.router.rn01', 'router'),
                            ('anseny.sensor_ht.1', 'temperature-humidity-sensor'),
                            ('test.sensor_occupy.1', 'occupancy-sensor'),
                            ('test.remote.1', 'remote-control')]:
            with self.subTest(model=model):
                d = device(model, kind)
                self.assertFalse(supports_card_power(d))
                self.assertFalse(has_device_details(d))
                card = DeviceCard(d)
                card.set_power_state(True)
                self.assertTrue(card._power_btn.isHidden())
                opened = Mock(); card.open_requested.connect(opened)
                card.show(); QTest.mouseClick(card, Qt.LeftButton, pos=QPoint(10,10))
                opened.assert_not_called()
                with self.assertRaises(ValueError):
                    DeviceDetailDialog(Mock(), Mock(), d)
                card.hide(); card.deleteLater()

    def test_camera_play_buttons_open_once_without_power_and_disable_when_offline(self):
        from dataclasses import replace
        from app.ui.tray.camera_corner_tag import CameraCornerTag
        for online in (True, False):
            d = replace(device('test.camera.1','camera','camera'), online=online)
            card = DeviceCard(d)
            opened, power = Mock(), Mock()
            card.open_requested.connect(opened)
            card.power_clicked.connect(power)
            card.show()
            QTest.mouseClick(card._play_btn, Qt.LeftButton)
            self.assertEqual(opened.call_count, int(online))
            power.assert_not_called()
            self.assertTrue(card._power_btn.isHidden())
            self.assertIsNotNone(card.findChild(CameraCornerTag))
            self.assertEqual(card._play_btn.width(),36)
            image = card._play_btn.grab().toImage()
            scale = image.devicePixelRatio()
            surface = image.pixelColor(int(18*scale), int(5*scale))
            self.assertTrue(any(image.pixelColor(int(x*scale), int(y*scale)) != surface
                                for x in range(11,25) for y in range(11,25)))
            self.assertEqual(card._play_btn._icon_size, 26)
            self.assertAlmostEqual(card._play_btn._glyph.width() /
                                   card._play_btn._glyph.devicePixelRatioF(), 26, delta=1)
            with TemporaryDirectory() as folder, patch('app.core._json_store.data_file',
                    side_effect=lambda name: Path(folder)/name):
                service = VirtualLightService()
                service.toggle_power = Mock()
                quick = TrayQuickWindow(service, Jobs())
                quick.set_devices([d], {'camera': True})
                quick._rebuild()
                row = quick._make_row(d)
                opened = Mock(); quick.open_device_requested.connect(opened)
                row.show()
                QTest.mouseClick(row._play_btn, Qt.LeftButton)
                self.assertEqual(opened.call_count, int(online))
                service.toggle_power.assert_not_called()
                self.assertIsNone(row._power_btn)
                self.assertEqual(row._play_btn.width(),28)
                self.assertIsNotNone(row.findChild(CameraCornerTag))
                row.hide(); row.deleteLater()
                quick.hide(); quick.deleteLater()
            card.hide(); card.deleteLater()

    def test_real_appliance_roles_keep_quick_power_but_not_generic_details(self):
        for model, kind in [('test.tv.1','television'), ('test.washer.1','washer'),
                            ('test.plug.1','outlet'), ('test.switch.1','switch'),
                            ('test.light.1','light')]:
            d = device(model, kind)
            self.assertTrue(supports_card_power(d))
            self.assertTrue(tray_eligible(d))
            self.assertFalse(has_device_details(d))

    def test_router_on_property_is_never_read_or_written_as_power(self):
        fixture = split_switch_test.SplitSwitchTest(); fixture.setUp()
        s = fixture.service
        s._device_index['router'] = ('xiaomi.router.rn01', 'test-spec', 'router')
        self.assertEqual(s.power_states(['router']), {'router': None})
        fixture.api.get_devices_prop.assert_not_called()
        with self.assertRaises(ServiceError):
            s.set_power_state('router', True)
        fixture.api.set_devices_prop.assert_not_called()

    def test_sensor_class_alone_does_not_qualify_without_a_supported_readout(self):
        fixture = split_switch_test.SplitSwitchTest(); fixture.setUp()
        s = fixture.service
        spec_type = 'urn:miot-spec-v2:device:occupancy-sensor:0000:test:1'
        fixture.api.get_homes_list.return_value = []
        fixture.api.get_devices_list.return_value = [
            {'did':'sensor','name':'电子围栏','model':'ainice.sensor_occupy.bt',
             'spec_type':spec_type,'isOnline':True}]
        fixture.api.get_shared_devices_list.return_value = []
        s._spec_cache[spec_type] = {'properties':[
            {'name':'occupancy','type':'bool','rw':'r'}], 'actions':[]}
        sensor = s.list_devices()[0]
        self.assertEqual(sensor.metric_features, [])
        self.assertFalse(tray_eligible(sensor))
        s._spec_cache[spec_type]['properties'].append(
            {'name':'temperature','type':'float','rw':'r'})
        self.assertTrue(tray_eligible(s.list_devices()[0]))

    def test_tray_editor_and_existing_selection_use_same_roles_preserving_scenes(self):
        router = device('xiaomi.router.rn01','router','router')
        sensor = device('test.sensor_ht.1','temperature-humidity-sensor','sensor')
        sensor.metric_features = ['temperature']
        camera = device('test.camera.1','camera','camera')
        empty_sensor = device('ainice.sensor_occupy.bt','occupancy-sensor','empty-sensor')
        empty_sensor.metric_features = []
        with TemporaryDirectory() as folder, patch('app.core._json_store.data_file',
                side_effect=lambda name: Path(folder)/name):
            tray_store.save(['router','empty-sensor','sensor','missing'])
            tray_store.save_scenes([{'scene_id':'scene','name':'场景','home_id':'1','home_name':'家'}])
            tray_store.save_order([{'type':'device','id':'router'}, {'type':'scene','id':'scene'},
                                   {'type':'device','id':'sensor'}, {'type':'device','id':'missing'}])
            prune_tray_selection([router,empty_sensor,sensor,camera])
            self.assertEqual(tray_store.load(), ['sensor','missing'])
            self.assertEqual(tray_store.load_order()[0], {'type':'scene','id':'scene'})
            self.assertEqual(len(tray_store.load_scenes()),1)
            dialog = TrayManagerDialog([router,empty_sensor,sensor,camera], scenes=[])
            self.assertEqual(set(dialog._checks), {'sensor','camera'})
            dialog.deleteLater()
            quick = TrayQuickWindow(VirtualLightService(), Jobs())
            quick.set_devices([router,sensor,camera], {'router': True, 'sensor': True})
            self.assertEqual({d.did for d in quick._devices}, {'sensor','camera'})
            quick._rebuild()
            row = next(quick._grid.itemAt(i).widget() for i in range(quick._grid.count())
                       if getattr(quick._grid.itemAt(i).widget(), '_did', None) == 'sensor')
            self.assertIsNone(row._power_btn)
            self.assertEqual(row.cursor().shape(), Qt.ArrowCursor)
            quick.hide(); quick.deleteLater()

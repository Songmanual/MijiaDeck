# SPDX-License-Identifier: GPL-3.0-or-later
"""Loading progress follows real work, survives status updates, and cancels safely."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import threading
import unittest
from unittest.mock import Mock, patch
from app import APP_NAME
from app.core.service import MijiaService
from app.ui.si_theme import SiColors
from app.ui import si_theme
from app.ui.theme_service import apply_theme
from tests import availability_test as availability_fixture
from tests.device_controls_test import Jobs
from tools.test_light_controls import VirtualLightService


class LoadingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        availability_fixture.AvailabilityTest.setUpClass()

    def setUp(self):
        app = availability_fixture.AvailabilityTest.app
        self._original_style = app.styleSheet()
        self._original_font = app.font()
        self._original_theme = si_theme.current_theme()
        self._original_accent = si_theme._accent
        self.fixture = availability_fixture.AvailabilityTest()
        self.fixture.setUp()
        self.window = self.fixture.window
        self.window._service = VirtualLightService()
        self.window._jobs = self.jobs = Jobs()
        self.window._logged_out = False
        self.window._sync_access_ui()

    def tearDown(self):
        self.fixture.tearDown()
        self.fixture.doCleanups()
        si_theme.set_theme(self._original_theme)
        si_theme.set_accent(self._original_accent)
        si_theme.sync_siui_colors()
        self.fixture.app.setStyleSheet(self._original_style)
        self.fixture.app.setFont(self._original_font)

    def test_first_login_only_central_loading_waits_for_initial_states(self):
        with patch('app.ui.main_window.device_cache.load', return_value=None):
            self.window._startup_load()
        self.assertTrue(self.window._load_active)
        self.assertIs(self.window._content_stack.currentWidget(), self.window._loading_page)
        self.assertTrue(self.window._footer.isHidden())
        self.jobs.finish()  # actual device list callback, state jobs follow
        self.assertEqual(self.window._load_pending, {'power', 'metrics'})
        self.assertTrue(self.window._footer.progress.isHidden())
        self.assertEqual(self.window._footer.status.text(), '')
        self.assertEqual(self.window._loading_page.progress.value(), 80)
        self.jobs.finish()  # initial switch state
        # A controllable light needs no sensor request; finish immediately.
        self.assertFalse(self.window._load_active)
        self.assertEqual(self.window._content_stack.currentIndex(), 0)
        self.assertFalse(self.window._footer.isHidden())
        self.assertTrue(self.window._footer.progress.isHidden())

    def test_metrics_wait_for_live_power_and_skip_offline_devices(self):
        from dataclasses import replace
        light = self.window._service.device
        sensor = replace(light, did='sensor', name='测试传感器', model='test.sensor')
        offline = replace(sensor, did='offline', online=False)
        self.window._service.power_states = Mock(return_value={light.did: True, sensor.did: None})
        self.window._service.read_metrics = Mock(return_value={sensor.did: '24°C'})
        self.window._begin_loading(full_page=True)
        self.window._on_devices_loaded([light, sensor, offline])
        self.window._service.read_metrics.assert_not_called()
        while self.window._load_active and self.jobs.pending:
            self.jobs.finish()
        self.window._service.read_metrics.assert_called_once_with([sensor.did])
        self.assertFalse(self.window._load_active)

    def test_cached_startup_refreshes_saved_power_before_dismissing_loading(self):
        device = self.window._service.device
        with patch('app.ui.main_window.device_cache.load',
                   return_value=([device], {device.did: False}, {})):
            self.window._startup_load()
        self.assertTrue(self.window._load_active)
        self.jobs.finish()
        self.assertTrue(self.window._known_power[device.did])
        self.assertFalse(self.window._load_active)

    def test_manual_refresh_keeps_content_visible_and_footer_status_cannot_erase_progress(self):
        self.window._refresh_btn.click()
        self.assertEqual(self.window._content_stack.currentIndex(), 0)
        self.window._on_loading_progress(self.window._load_generation, 45, '正在读取共享设备…')
        self.window._clear_status_hint()
        self.assertFalse(self.window._footer.progress.isHidden())
        self.assertEqual(self.window._footer.status.text(), '正在读取共享设备…')
        self.assertEqual(self.window._footer.progress.value(), 45)

    def test_refresh_timeout_stops_spinner_and_late_result_cannot_replace_new_refresh(self):
        self.window.load_devices(manual=True)
        ticket = self.window._load_generation
        self.assertTrue(self.window._loading_devices)
        self.window._on_loading_timeout()
        self.assertFalse(self.window._loading_devices)
        self.assertFalse(self.window._load_active)
        self.assertFalse(self.window._load_watchdog.isActive())
        self.assertIn('刷新超时', self.window._footer.status.text())
        self.window.load_devices(manual=True)
        current = self.window._load_generation
        self.window._accept_device_list(ticket, result=[])
        self.assertEqual(current, self.window._load_generation)
        self.assertEqual(self.window._load_pending, {'list'})
        self.jobs.finish()  # old queued result is discarded
        self.assertEqual(self.window._load_pending, {'list'})
        self.jobs.finish()  # new list may finish normally
        self.jobs.finish()
        self.jobs.finish()
        self.assertFalse(self.window._load_active)

    def test_empty_account_and_state_failure_never_leave_a_loading_page_stuck(self):
        self.window._begin_loading(full_page=True)
        self.window._on_devices_loaded([])
        self.assertFalse(self.window._load_active)
        self.window._begin_loading(full_page=True)
        self.window._prepare_loading_states()
        ticket = self.window._load_generation
        self.window._on_poll_error(RuntimeError('offline test'), load_ticket=ticket)
        self.window._on_metrics_error(RuntimeError('offline test'), ticket)
        self.assertFalse(self.window._load_active)
        self.assertEqual(self.window._content_stack.currentIndex(), 0)

    def test_disconnect_cancels_both_progress_views_and_ignores_stale_worker_events(self):
        self.window._begin_loading(full_page=True)
        ticket = self.window._load_generation
        self.window._on_network_changed(False)
        self.assertFalse(self.window._load_active)
        self.assertTrue(self.window._footer.progress.isHidden())
        self.window._on_loading_progress(ticket, 75, 'stale')
        self.assertNotEqual(self.window._footer.status.text(), 'stale')
        self.assertEqual(self.window._content_stack.currentIndex(), 0)

    def test_worker_updates_central_view_and_saved_accent_is_used(self):
        apply_theme('dark', '#8044cc')
        self.window._reapply_chrome_styles()
        self.window._begin_loading(full_page=True)
        ticket = self.window._load_generation
        worker = threading.Thread(target=lambda: self.window._loading_progress.emit(ticket, 65, '正在识别灯光控制能力…'))
        worker.start()
        worker.join(1)
        self.fixture.app.processEvents()
        self.assertTrue(self.window._footer.progress.isHidden())
        self.assertEqual(self.window._loading_page.progress.value(), 65)
        self.assertIn(SiColors.THEME, self.window._loading_page.styleSheet())
        self.assertIn(SiColors.THEME, self.window._footer.styleSheet())
        self.assertEqual(self.window._title_bar._brand_name.text(), APP_NAME)
        self.assertEqual(self.window._title_bar._brand_name.toolTip(), '')

    def test_service_stage_progress_is_emitted_around_completed_api_calls(self):
        service = MijiaService.__new__(MijiaService)
        service._device_index = {}
        service._api = Mock()
        events = []
        for name in ('get_homes_list', 'get_devices_list', 'get_shared_devices_list'):
            getattr(service._api, name).side_effect = lambda n=name: (events.append(n) or [])
        service.list_devices(progress=lambda value, _: events.append(value))
        self.assertEqual(events[:6], [8, 'get_homes_list', 25, 'get_devices_list', 45, 'get_shared_devices_list'])
        self.assertEqual(events[-1], 75)


if __name__ == '__main__':
    unittest.main()

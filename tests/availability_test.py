# SPDX-License-Identifier: GPL-3.0-or-later
"""Logged-out/offline UI must not expose cached device or speaker controls."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QNetworkInformation
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from app.core.availability import MESSAGES, NetworkMonitor, speaker_hint
from app.core.models import DeviceInfo
from app.core.service import MijiaService, ServiceError
from app.ui.main_window import MainWindow


class Monitor(QObject):
    changed = Signal(bool)
    online = True

    def check_now(self):
        pass


class AvailabilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for target, kwargs in (
            ('app.core._json_store.data_file', {'side_effect': lambda n: Path(self.temp.name) / n}),
            ('app.core._json_store.data_dir', {'return_value': Path(self.temp.name)}),
            ('app.core.availability.NetworkMonitor', {'new': Monitor}),
            ('app.ui.main_window.MijiaService', {'return_value': Mock()}),
            ('app.ui.main_window.JobExecutor', {'return_value': Mock()}),
            ('PySide6.QtWidgets.QSystemTrayIcon.show', {}),
        ):
            patcher = patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.window = MainWindow()
        self.quick = self.window._tray._quick
        self.speaker = DeviceInfo('speaker', 'Speaker', 'xiaomi.wifispeaker.test', 'Home', 'Room', True)
        self.light = DeviceInfo('light', 'Light', 'test.light.test', 'Home', 'Room', True)

    def tearDown(self):
        self.window._poll_timer.stop()
        self.window._metrics_timer.stop()
        self.window._tray._tray.hide()
        self.quick.hide()
        self.quick.deleteLater()
        self.window.hide()
        self.window.deleteLater()
        self.app.processEvents()

    def test_no_login_shows_no_cached_scenes_devices_or_speaker(self):
        self.quick.set_devices([self.speaker, self.light], {'light': True})
        self.quick.show_near_tray()
        self.assertEqual(self.quick._empty.text(), MESSAGES['signed_out'])
        self.assertTrue(self.quick._scroll.isHidden())
        self.assertTrue(self.quick._audio_bar.isHidden())
        self.assertTrue(self.quick._voice_frame.isHidden())
        self.assertTrue(self.window._scroll.isHidden())

    def test_logged_out_tray_click_opens_login_in_main_window(self):
        self.window._login_account = Mock()
        self.window._tray._on_activated(QSystemTrayIcon.Trigger)
        QTest.qWait(10)
        self.assertTrue(self.window.isVisible())
        self.window._login_account.assert_called_once()
        self.assertFalse(self.quick.isVisible())

    def test_disconnect_replaces_controls_with_message_without_reading_states(self):
        self.window._logged_out = False
        self.window._all_devices = [self.light, self.speaker]
        self.window._sync_access_ui()
        self.quick.set_devices([self.light, self.speaker], {'light': True})
        self.window._jobs.reset_mock()
        self.window._on_network_changed(False)
        self.quick.show_near_tray()
        self.assertEqual(self.quick._empty.text(), MESSAGES['offline'])
        self.assertTrue(self.quick._scroll.isHidden())
        self.assertTrue(self.quick._audio_bar.isHidden())
        self.assertTrue(self.quick._voice_frame.isHidden())
        self.assertTrue(self.quick._drag_header.isHidden())
        self.assertTrue(self.window._scroll.isHidden())
        self.assertFalse(self.window._poll_timer.isActive())
        self.assertFalse(self.window._metrics_timer.isActive())
        self.window._refresh_power_states(True)
        self.window._refresh_metrics()
        self.window._jobs.submit.assert_not_called()

    def test_reconnect_waits_for_device_refresh_before_restoring_controls(self):
        self.window._logged_out = False
        self.window._on_network_changed(False)
        self.window.load_devices = Mock()
        self.window._on_network_changed(True)
        self.assertEqual(self.window._access_state(), 'loading')
        self.window.load_devices.assert_called_once()
        self.window._on_devices_loaded([self.light])
        self.assertEqual(self.window._access_state(), 'ready')
        self.assertFalse(self.window._scroll.isHidden())

    def test_no_speaker_and_offline_speaker_have_distinct_hints(self):
        self.window._logged_out = False
        for devices, expected in (([self.light], '当前你还没有添加任何智能音箱'),
                                  ([DeviceInfo('s', 'Speaker', 'xiaomi.wifispeaker.test', 'H', 'R', False)], '智能音箱当前离线')):
            self.window._all_devices = devices
            self.window._sync_access_ui()
            self.quick.set_devices(devices, {})
            self.assertEqual(self.window._access_hint.text(), expected)
            self.assertEqual(self.quick._speaker_hint.text(), expected)
            self.assertTrue(self.quick._audio_bar.isHidden())
            self.assertTrue(self.quick._voice_frame.isHidden())
            self.assertTrue(self.window._voice_fab.isHidden())
        self.assertEqual(speaker_hint([self.speaker]), '')

    def test_blocked_service_does_not_execute_previously_queued_controls(self):
        service = MijiaService.__new__(MijiaService)
        service._api = Mock()
        service.set_control_access(MESSAGES['offline'])
        for operation in (lambda: service.set_power_state('light', True),
                          lambda: service.write_prop('light', 'on', True),
                          lambda: service.run_action('speaker', 'play'),
                          lambda: service.power_states(['light']),
                          lambda: service.read_metrics(['light'])):
            with self.assertRaises(ServiceError):
                operation()
        self.assertFalse(service._api.mock_calls)

    def test_system_network_reachability_does_not_treat_unknown_as_logout(self):
        reach = QNetworkInformation.Reachability
        for status in (reach.Disconnected, reach.Local, reach.Site):
            self.assertFalse(NetworkMonitor._is_online(status))
        for status in (reach.Unknown, reach.Online):
            self.assertTrue(NetworkMonitor._is_online(status))

    def test_failed_probe_overrides_windows_online_and_recovery_requires_http(self):
        class Reply(QObject):
            finished = Signal()
            status = None
            def attribute(self, _):
                return self.status
            def abort(self):
                self.finished.emit()

        class Backend(QObject):
            reachabilityChanged = Signal(object)
            def reachability(self):
                return QNetworkInformation.Reachability.Online

        first, second = Reply(), Reply()
        manager = Mock()
        manager.head.side_effect = [first, second]
        with patch('app.core.availability.QNetworkInformation.loadDefaultBackend'), \
             patch('app.core.availability.QNetworkInformation.instance', return_value=Backend()), \
             patch('app.core.availability.QNetworkAccessManager', return_value=manager):
            monitor = NetworkMonitor()
        self.app.processEvents()  # consume the initial scheduled probe
        changes = []
        monitor.changed.connect(changes.append)
        try:
            monitor.check_now()
            monitor.check_now()
            self.assertEqual(manager.head.call_count, 1)  # single flight
            first.finished.emit()  # no HTTP response, despite Windows Online
            self.assertFalse(monitor.online)
            monitor._changed(QNetworkInformation.Reachability.Online)
            self.assertFalse(monitor.online)
            second.status = 404  # real HTTP response, root need not be a page
            second.finished.emit()
            self.assertTrue(monitor.online)
            self.assertEqual(changes, [False, True])
            request = manager.head.call_args.args[0]
            self.assertEqual(request.url().host(), 'api.io.mi.com')
            self.assertEqual(request.transferTimeout(), 2500)
        finally:
            monitor._timer.stop()
            monitor.deleteLater()


if __name__ == '__main__':
    unittest.main()

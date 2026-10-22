# SPDX-License-Identifier: GPL-3.0-or-later
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PySide6.QtCore import QObject, Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from app.core import account_store, settings_store
from app.core.jobs import JobExecutor
from app.core.update_checker import ReleaseInfo
from app.ui.footer_bar import FooterBar


class FooterAccountTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_status_replaces_version_and_update_badge_until_finished(self):
        bar = FooterBar(30)
        bar.show()
        bar.set_release(ReleaseInfo('v0.4.0', 'https://github.com/example/project/releases/v0.4.0', 'New'))
        self.assertTrue(bar.version.isVisible())
        self.assertTrue(bar.update_button.isVisible())
        bar.set_status('正在获取设备列表…')
        self.assertFalse(bar.version.isVisible())
        self.assertFalse(bar.update_button.isVisible())
        self.assertTrue(bar.status.isVisible())
        bar.set_status('')
        self.assertTrue(bar.version.isVisible())
        self.assertTrue(bar.update_button.isVisible())
        bar.set_logged_in(False)
        self.assertEqual(bar.account.text(), '登录账号')
        self.assertTrue(bar.account.isVisible())
        bar.set_logged_in(True)
        self.assertEqual(bar.account.text(), '退出登录')
        bar.hide()
        bar.deleteLater()

    def test_preferences_are_restored_per_account_without_changing_theme(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('app.core._json_store.data_file', side_effect=lambda name: root/name):
                tray_a = {'version': 1, 'devices': ['device-a'], 'scenes': [{'scene_id':'scene-a'}]}
                (root/'tray.json').write_text(json.dumps(tray_a))
                settings_store.set_theme_color('blue')
                settings_store.set_default_speaker_did('speaker-a')
                account_store.activate('account-a')
                (root/'devices_cache.json').write_text('{}')
                account_store.deactivate()
                self.assertFalse((root/'devices_cache.json').exists())
                account_store.activate('account-b')
                self.assertEqual(json.loads((root/'tray.json').read_text()), {})
                (root/'tray.json').write_text(json.dumps({'version':1,'devices':['device-b']}))
                account_store.deactivate()
                account_store.activate('account-a')
                self.assertEqual(json.loads((root/'tray.json').read_text()), tray_a)
                self.assertEqual(settings_store.get_default_speaker_did(), 'speaker-a')
                self.assertEqual(settings_store.get_theme_color(), 'blue')

    def test_logout_only_removes_test_auth_and_clears_session_caches(self):
        from app.core.service import MijiaService
        with tempfile.TemporaryDirectory() as directory:
            auth = Path(directory)/'auth.json'
            auth.write_text('{}')
            old_api = SimpleNamespace(auth_data={'userId':'test'}, auth_data_path=auth, session=Mock())
            service = MijiaService.__new__(MijiaService)
            service._api = old_api
            service._device_cache = {'old': object()}
            service._device_index = {'old': object()}
            service._home_ids = {'old':'home'}
            with patch('app.core.account_store.activate'), patch('app.core.account_store.deactivate'), \
                 patch('app.core.service.mijiaAPI', return_value=SimpleNamespace(auth_data={})):
                service.logout()
            self.assertFalse(auth.exists())
            self.assertEqual(old_api.auth_data, {})
            old_api.session.close.assert_called_once()
            self.assertEqual(service._device_cache, {})
            self.assertEqual(service._device_index, {})
            self.assertIsNone(service._home_ids)

    def test_cancel_pending_discards_old_account_callbacks(self):
        jobs = JobExecutor()
        started, release = threading.Event(), threading.Event()
        old_result, old_queued, new_result = Mock(), Mock(), Mock()
        def running():
            started.set()
            release.wait(2)
            return 'old'
        try:
            jobs.submit(running, on_success=old_result)
            self.assertTrue(started.wait(2))
            jobs.submit(old_queued)
            jobs.cancel_pending()
            jobs.submit(lambda: 'new', on_success=new_result)
            release.set()
            for _ in range(30):
                QTest.qWait(20)
                if new_result.called:
                    break
            old_result.assert_not_called()
            old_queued.assert_not_called()
            new_result.assert_called_once_with('new')
        finally:
            release.set()
            jobs.shutdown()

    def test_automatic_update_uses_footer_without_modal_prompt(self):
        from app.ui.update_flow import check_update
        info = ReleaseInfo('v999.0.0', 'https://github.com/example/project/releases/v999.0.0', 'New')
        class Checker(QObject):
            check_finished = Signal(object, object)
            def check(self):
                self.check_finished.emit(info, None)
        parent = QWidget()
        parent._on_update_available = Mock()
        with patch('app.ui.update_flow.UpdateChecker', Checker), patch('app.ui.update_flow.prompt_new_version') as prompt:
            check_update(parent, manual=False)
            parent._on_update_available.assert_called_once_with(info)
            prompt.assert_not_called()
        parent.deleteLater()


if __name__ == '__main__':
    unittest.main()

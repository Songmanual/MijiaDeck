# SPDX-License-Identifier: GPL-3.0-or-later
"""Click sequencing and first-run guidance without a tray or cloud account."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from PySide6.QtCore import QElapsedTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QWidget
from app.core import settings_store
from app.ui.tray.controller import TrayController
from app.ui.tray_intro import start_with_tray_intro


class TrayActivationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def controller(self):
        controller = TrayController.__new__(TrayController)
        controller._last_tray_click = QElapsedTimer()
        quick = controller._quick = Mock()
        quick.isVisible.return_value = False
        quick.is_explicitly_visible.return_value = False
        return controller, quick

    def test_single_and_standalone_double_click_open_popup(self):
        for reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            controller, quick = self.controller()
            controller._on_activated(reason)
            quick.show_near_tray.assert_called_once()

    def test_tray_uses_native_tooltip_without_hover_popup(self):
        window = QWidget()
        with patch.object(TrayController, '_create_quick_window'), \
             patch.object(QSystemTrayIcon, 'show'):
            controller = TrayController(Mock(), Mock(), window)
        self.assertEqual(controller._tray.toolTip(), '单击图标打开浮窗控制设备')
        self.assertFalse(hasattr(controller, '_hover_timer'))
        controller._tray.hide()
        window.deleteLater()

    def test_windows_double_click_sequence_does_not_toggle_twice(self):
        controller, quick = self.controller()
        for reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick,
                       QSystemTrayIcon.Trigger):
            controller._on_activated(reason)
        quick.show_near_tray.assert_called_once()
        quick.hide.assert_not_called()

    def test_click_visible_popup_closes_it_and_context_click_leaves_it_alone(self):
        controller, quick = self.controller()
        quick.isVisible.return_value = True
        controller._on_activated(QSystemTrayIcon.Context)
        quick.hide.assert_not_called()
        controller._on_activated(QSystemTrayIcon.Trigger)
        quick.hide.assert_called_once()

    def test_first_run_shows_main_and_guidance_before_starting_login_jobs(self):
        with TemporaryDirectory() as folder, \
             patch('app.core._json_store.data_file', side_effect=lambda name: Path(folder) / name), \
             patch('app.core._json_store.data_dir', return_value=Path(folder)):
            settings_store.set_start_minimized(True)
            self.assertFalse(settings_store.should_start_hidden())
            window = QWidget()
            window.resize(900, 600)
            window.show()
            ready = Mock()
            guide = start_with_tray_intro(window, ready)
            self.assertTrue(guide.isVisible())
            self.assertTrue(window.isVisible())
            ready.assert_not_called()
            QTest.mouseClick(guide.dismiss, Qt.LeftButton)
            self.app.processEvents()
            ready.assert_called_once()
            self.assertTrue(settings_store.get_tray_intro_seen())
            self.assertTrue(settings_store.should_start_hidden())
            self.assertIsNone(start_with_tray_intro(window, ready))
            self.assertEqual(ready.call_count, 2)
            guide.deleteLater()
            window.close()
            window.deleteLater()


if __name__ == '__main__':
    unittest.main()

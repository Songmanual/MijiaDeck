# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistent tray placement and time to reach a popup away from the tray."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QEnterEvent, QGuiApplication, QMouseEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from app.core import settings_store
from app.ui.tray.quick_window import TrayQuickWindow


class TrayPositionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        paths = patch('app.core._json_store.data_file', side_effect=lambda name: Path(self.temp.name) / name)
        paths.start()
        self.addCleanup(paths.stop)
        self.windows = []
        self.quick = self.make_window()

    def make_window(self):
        window = TrayQuickWindow(SimpleNamespace(), SimpleNamespace(submit=Mock()))
        self.windows.append(window)
        return window

    def tearDown(self):
        for window in self.windows:
            window.abort_toggle_animation()
            window.hide()
            window.deleteLater()
        self.app.processEvents()

    def mouse(self, kind, point, button, buttons, surface=None):
        header = surface or self.quick._drag_header
        local = header.mapFromGlobal(point)
        event = QMouseEvent(kind, QPointF(local), QPointF(point), button, buttons, Qt.NoModifier)
        QApplication.sendEvent(header, event)

    def test_header_drag_saves_and_recreated_window_restores_position(self):
        q = self.quick
        q.move(50, 50)
        q.show()
        self.app.processEvents()
        start = q._drag_header.mapToGlobal(QPoint(80, 8))
        screen = SimpleNamespace(name=lambda: 'test-screen', availableGeometry=lambda: QRect(0, 0, 2000, 1200))
        with patch.object(QGuiApplication, 'screenAt', return_value=screen), \
             patch.object(QGuiApplication, 'screens', return_value=[screen]):
            self.mouse(QEvent.MouseButtonPress, start, Qt.LeftButton, Qt.LeftButton)
            self.mouse(QEvent.MouseMove, start + QPoint(80, 50), Qt.NoButton, Qt.LeftButton)
            self.mouse(QEvent.MouseButtonRelease, start + QPoint(80, 50), Qt.LeftButton, Qt.NoButton)
            self.assertEqual(q.pos(), QPoint(130, 100))
            self.assertFalse(q._dragging)
            self.assertIsNotNone(settings_store.get_tray_position())
            other = self.make_window()
            other.resize(q.size())
            self.assertEqual(other._popup_position(), q.pos())

    def test_short_header_click_does_not_save_position(self):
        self.quick.show()
        start = self.quick._drag_header.mapToGlobal(QPoint(80, 8))
        self.mouse(QEvent.MouseButtonPress, start, Qt.LeftButton, Qt.LeftButton)
        self.mouse(QEvent.MouseButtonRelease, start, Qt.LeftButton, Qt.NoButton)
        self.assertIsNone(settings_store.get_tray_position())

    def test_audio_top_padding_and_move_icon_are_drag_handles(self):
        q = self.quick
        q._audio_bar.set_speaker('test-speaker', '测试音箱')
        q.show()
        self.app.processEvents()
        self.assertFalse(q._audio_drag_handle.pixmap().isNull())
        screen = SimpleNamespace(name=lambda: 'test-screen', availableGeometry=lambda: QRect(0, 0, 2000, 1400))
        with patch.object(QGuiApplication, 'screenAt', return_value=screen):
            for surface, local in ((q._audio_bar, QPoint(30, 3)),
                                   (q._audio_bar._drag_header, QPoint(230, 5)),
                                   (q._audio_drag_handle, QPoint(8, 8))):
                with self.subTest(surface=surface):
                    q.move(80, 80)
                    start = surface.mapToGlobal(local)
                    self.mouse(QEvent.MouseButtonPress, start, Qt.LeftButton, Qt.LeftButton, surface)
                    self.mouse(QEvent.MouseMove, start + QPoint(50, 40), Qt.NoButton, Qt.LeftButton, surface)
                    self.mouse(QEvent.MouseButtonRelease, start + QPoint(50, 40), Qt.LeftButton, Qt.NoButton, surface)
                    self.assertEqual(q.pos(), QPoint(130, 120))
                    self.assertFalse(q._dragging)

    def test_speaker_button_still_opens_selection_without_dragging(self):
        q = self.quick
        q._audio_bar.set_speaker('test-speaker', '测试音箱')
        q.show()
        callback = Mock()
        q._audio_bar.speaker_requested.disconnect()
        q._audio_bar.speaker_requested.connect(callback)
        original = q.pos()
        QTest.mouseClick(q._audio_bar._speaker_btn, Qt.LeftButton)
        callback.assert_called_once()
        self.assertEqual(q.pos(), original)
        self.assertIsNone(settings_store.get_tray_position())

    def test_missing_monitor_and_changed_work_area_clamp_to_visible_screen(self):
        q = self.quick
        q.resize(300, 300)
        settings_store.set_tray_position(dict(screen='removed', x=99999, y=-99999))
        screen = SimpleNamespace(name=lambda: 'remaining', availableGeometry=lambda: QRect(-1000, 50, 800, 700))
        with patch.object(QGuiApplication, 'screens', return_value=[screen]), \
             patch.object(QGuiApplication, 'screenAt', return_value=screen):
            self.assertEqual(q._popup_position(), QPoint(-500, 50))
        settings_store.set_tray_position(dict(screen='remaining', x=99999, y=99999))
        with patch.object(QGuiApplication, 'screens', return_value=[screen]):
            self.assertEqual(q._popup_position(), QPoint(-500, 450))

    def test_reset_clears_saved_position_and_moves_open_window(self):
        self.quick.show()
        self.quick.move(70, 80)
        self.quick._save_position()
        self.quick.reset_position()
        self.assertIsNone(settings_store.get_tray_position())
        self.assertEqual(self.quick.pos(), self.quick._popup_position())

    def test_popup_allows_three_seconds_to_reach_then_short_leave_delay(self):
        q = self.quick
        q._play_show_animation()
        q.abort_toggle_animation()
        q.hide_animated = Mock()
        self.assertEqual(q._leave_timer.interval(), 3000)
        q._pointer_has_entered = False
        with patch.object(q, 'isActiveWindow', return_value=False), \
             patch.object(q, 'underMouse', return_value=False), \
             patch.object(QApplication, 'activeWindow', return_value=None):
            q._maybe_hide_on_deactivate()
        q.hide_animated.assert_not_called()
        self.assertTrue(q._leave_timer.isActive())
        event = QEnterEvent(QPointF(20, 20), QPointF(20, 20), QPointF(20, 20))
        QApplication.sendEvent(q, event)
        self.assertEqual(q._leave_timer.interval(), 300)
        self.assertFalse(q._leave_timer.isActive())
        q._dragging = True
        q._hide_after_pointer_leave()
        q.hide_animated.assert_not_called()


if __name__ == '__main__':
    unittest.main()

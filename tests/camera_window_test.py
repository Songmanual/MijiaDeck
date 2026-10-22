# SPDX-License-Identifier: GPL-3.0-or-later
"""Persistent standalone camera windows, resize hit zones, and quality defaults."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu
from app.ui.device_dialog import DeviceDetailDialog
from app.ui.main_window import MainWindow
from tests.camera_preview_test import Jobs


class CameraWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.jobs = Jobs()
        self.device = SimpleNamespace(did='test-camera', name='门口', room_name='玄关',
                                      model='chuangmi.camera.029a02', online=True)
        self.service = SimpleNamespace(power_state=Mock(return_value=False))
        self.window = DeviceDetailDialog(self.service, self.jobs, self.device)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.hide()
        self.window.deleteLater()
        self.app.processEvents()

    def test_leaving_or_deactivating_camera_does_not_close_it(self):
        self.assertIsNone(self.window._overlay)
        self.assertEqual(self.window.windowModality(), Qt.NonModal)
        QApplication.sendEvent(self.window, QEvent(QEvent.Leave))
        QApplication.sendEvent(self.window, QEvent(QEvent.WindowDeactivate))
        QTest.qWait(350)
        self.assertTrue(self.window.isVisible())

    def test_window_resizes_content_and_has_camera_title_and_icon(self):
        self.assertEqual(self.window.windowTitle(), '门口 - 玄关')
        self.assertFalse(self.window.windowIcon().isNull())
        self.assertIn('border: 1px solid', self.window._panel.styleSheet())
        margins = self.window._camera.parentWidget().layout().contentsMargins()
        self.assertEqual((margins.left(), margins.right()), (20, 20))
        image = self.window.windowIcon().pixmap(32, 32).toImage()
        self.assertFalse(image.isNull())
        solid = [image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height())
                 if image.pixelColor(x, y).alpha() > 200]
        self.assertTrue(solid)
        self.assertTrue(any(color.name() == '#ffffff' for color in solid))
        self.assertTrue(any(color.name() == '#303238' for color in solid))
        for width, height in [(650, 430), (980, 650)]:
            self.window.resize(width, height)
            self.app.processEvents()
            self.assertEqual(self.window._panel.size(), self.window.size())
            self.assertTrue(self.window._camera.rect().contains(self.window._camera._canvas.geometry()))
            canvas = self.window._camera._canvas
            self.assertAlmostEqual(canvas.width()/canvas.height(), 16/9, delta=.02)

    def test_caption_controls_and_left_aligned_power(self):
        from app.ui.window_caption import WindowCaption
        caption = self.window._title_bar
        self.assertIsInstance(caption, WindowCaption)
        camera = self.window._camera
        self.assertLess(camera._power.x() + camera._power.width(), camera._title.x())
        self.assertEqual(caption.close_button.size().width(), 46)
        original_geometry = self.window.geometry()
        QTest.mouseClick(caption.maximize_button, Qt.LeftButton)
        self.app.processEvents()
        self.assertTrue(self.window.isMaximized())
        self.assertEqual(self.window.geometry(), self.window.screen().availableGeometry())
        QTest.mouseClick(caption.maximize_button, Qt.LeftButton)
        self.app.processEvents()
        self.assertFalse(self.window.isMaximized())
        self.assertEqual(self.window.geometry(), original_geometry)
        QTest.mouseClick(caption.minimize_button, Qt.LeftButton)
        self.assertTrue(self.window.isMinimized())
        self.window.showNormal()
        QTest.mouseClick(caption.close_button, Qt.LeftButton)
        QTest.qWait(140)
        self.assertFalse(self.window.isVisible())

    def test_native_resize_edges_and_title_drag_exclude_power_button(self):
        self.assertEqual(self.window._camera_hit_test(1, 1), 13)
        self.assertEqual(self.window._camera_hit_test(self.window.width()-1, self.window.height()-1), 17)
        self.assertEqual(self.window._camera_hit_test(60, 30), 2)
        button = self.window._camera._power
        position = button.mapTo(self.window, button.rect().center())
        self.assertEqual(self.window._camera_hit_test(position.x(), position.y()), 1)

    def test_minimize_restore_and_resize_keep_the_same_stream(self):
        camera = self.window._camera
        session = SimpleNamespace(command=Mock(return_value=True), stop=Mock())
        camera._session = session
        camera._playing = camera._attempted = camera._loaded = True
        camera._power_state = True
        camera._player = Mock()
        generation = camera._generation
        for _ in range(2):
            self.window.showMinimized()
            self.app.processEvents()
            self.assertIs(camera._session, session)
            self.window.showNormal()
            self.window.resize(850, 580)
            self.app.processEvents()
            self.assertIs(camera._session, session)
            self.assertEqual(camera._generation, generation)
            self.assertTrue(camera._attempted)
        session.stop.assert_not_called()
        camera._player.stop.assert_not_called()
        camera._player.setSource.assert_not_called()
        self.assertFalse(any(getattr(job[0], '__name__', '') == 'prepare'
                             for job in self.jobs.pending))

    def test_closing_minimized_window_releases_stream(self):
        camera = self.window._camera
        session = SimpleNamespace(stop=Mock())
        camera._session = session
        camera._player = Mock()
        self.window.showMinimized()
        self.app.processEvents()
        self.window.setWindowOpacity(0)
        self.window.close()
        self.app.processEvents()
        session.stop.assert_called_once()
        self.assertIsNone(camera._session)
        self.assertFalse(camera._poll.isActive())

    def test_minimize_during_connection_keeps_pending_authorization(self):
        from unittest.mock import patch
        camera = self.window._camera
        session = SimpleNamespace(cancelled=False, stop=Mock())
        self.service.prepare_camera_source = Mock(return_value='test-source')
        with patch('app.ui.camera_preview.CameraSession', return_value=session):
            camera.start()
        prepare, _, _ = self.jobs.pending[-1]
        generation = camera._generation
        self.window.showMinimized()
        self.app.processEvents()
        self.assertEqual(prepare(), 'test-source')
        self.assertEqual(camera._generation, generation)
        session.stop.assert_not_called()
        self.window.showNormal()
        self.app.processEvents()
        self.assertIs(camera._session, session)

    def test_quality_menu_matches_home_menu_and_new_page_does_not_remember(self):
        camera = self.window._camera
        self.assertEqual(camera._quality, 1)
        menu = camera._build_quality_menu()
        home = QMenu()
        MainWindow._style_popup_menu(SimpleNamespace(), home)
        self.assertEqual(menu.styleSheet(), home.styleSheet())
        self.assertEqual(menu.font().pointSizeF(), home.font().pointSizeF())
        self.assertTrue(menu.testAttribute(Qt.WA_TranslucentBackground))
        self.assertEqual([a.data() for a in menu.actions()], [0, 1, 2])
        self.assertFalse(menu.actions()[1].icon().isNull())
        camera._session = SimpleNamespace(command=Mock(return_value=True), stop=Mock())
        camera._select_quality(2)
        self.assertEqual(camera._quality, 2)
        other = DeviceDetailDialog(self.service, self.jobs, self.device)
        self.assertEqual(other._camera._quality, 1)
        other.deleteLater()
        menu.deleteLater()
        home.deleteLater()

    def test_opening_same_camera_reuses_nonmodal_window_and_explicit_close_releases_it(self):
        main = SimpleNamespace(_service=self.service, _jobs=self.jobs, _refresh_closed_detail=Mock())
        MainWindow._open_camera_window(main, self.device)
        first = main._camera_windows[self.device.did]
        MainWindow._open_camera_window(main, self.device)
        self.assertIs(main._camera_windows[self.device.did], first)
        self.assertEqual(first.windowModality(), Qt.NonModal)
        first.setWindowOpacity(0)
        first.reject()
        self.app.processEvents()
        self.assertNotIn(self.device.did, main._camera_windows)
        main._refresh_closed_detail.assert_called_once_with(self.device.did)


if __name__ == '__main__':
    unittest.main()

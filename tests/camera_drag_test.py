# SPDX-License-Identifier: GPL-3.0-or-later
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app.ui.camera_canvas import CameraCanvas


class CameraDragTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.canvas = CameraCanvas()
        self.canvas.resize(640, 400)
        self.canvas.show()
        self.canvas.set_frame(QImage(640, 360, QImage.Format_RGB32))
        self.canvas.drag_enabled = True
        self.directions = []
        self.canvas.dragged.connect(self.directions.append)

    def tearDown(self):
        self.canvas.hide()
        self.canvas.deleteLater()
        self.app.processEvents()

    def test_all_directions_are_sent_while_dragging_before_release(self):
        for delta, expected in [(QPoint(20, 0), 2), (QPoint(-20, 0), 1),
                                (QPoint(0, 20), 4), (QPoint(0, -20), 3)]:
            with self.subTest(direction=expected):
                self.directions.clear()
                start = QPoint(300, 120)
                QTest.mousePress(self.canvas, Qt.LeftButton, pos=start)
                # New decoded frames must not cancel an active gesture.
                self.canvas.drag_enabled = True
                QTest.mouseMove(self.canvas, start + delta)
                self.assertEqual(self.directions, [expected])
                QTest.mouseRelease(self.canvas, Qt.LeftButton, pos=start + delta)
                self.assertEqual(self.directions, [expected])

    def test_short_click_and_disabled_drag_do_not_move_camera(self):
        start = QPoint(300, 120)
        QTest.mousePress(self.canvas, Qt.LeftButton, pos=start)
        QTest.mouseRelease(self.canvas, Qt.LeftButton, pos=start + QPoint(3, 2))
        self.assertEqual(self.directions, [])
        self.canvas.drag_enabled = False
        QTest.mousePress(self.canvas, Qt.LeftButton, pos=start)
        QTest.mouseMove(self.canvas, start + QPoint(60, 0))
        QTest.mouseRelease(self.canvas, Qt.LeftButton, pos=start + QPoint(60, 0))
        self.assertEqual(self.directions, [])

    def test_large_fast_drag_is_rate_limited(self):
        start = QPoint(300, 120)
        QTest.mousePress(self.canvas, Qt.LeftButton, pos=start)
        QTest.mouseMove(self.canvas, start + QPoint(20, 0))
        QTest.mouseMove(self.canvas, start + QPoint(80, 0))
        QTest.mouseRelease(self.canvas, Qt.LeftButton, pos=start + QPoint(100, 0))
        self.assertEqual(self.directions, [2])

    def test_busy_drag_is_discarded_and_requires_a_fresh_press(self):
        start = QPoint(300, 120)
        self.canvas.dragged.connect(lambda _: self.canvas.set_drag_busy(True))
        QTest.mousePress(self.canvas, Qt.LeftButton, pos=start)
        QTest.mouseMove(self.canvas, start + QPoint(20, 0))
        self.canvas.set_drag_busy(False)
        QTest.mouseMove(self.canvas, start + QPoint(80, 0))
        QTest.mouseRelease(self.canvas, Qt.LeftButton, pos=start + QPoint(80, 0))
        self.assertEqual(self.directions, [2])
        self.canvas.set_drag_busy(True)
        QTest.mousePress(self.canvas, Qt.LeftButton, pos=start)
        self.canvas.set_drag_busy(False)
        QTest.mouseMove(self.canvas, start + QPoint(-30, 0))
        QTest.mouseRelease(self.canvas, Qt.LeftButton, pos=start + QPoint(-30, 0))
        self.assertEqual(self.directions, [2])
        QTest.mousePress(self.canvas, Qt.LeftButton, pos=start)
        QTest.mouseMove(self.canvas, start + QPoint(-30, 0))
        self.assertEqual(self.directions, [2, 1])


if __name__ == '__main__':
    unittest.main()

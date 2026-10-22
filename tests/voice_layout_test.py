# SPDX-License-Identifier: GPL-3.0-or-later
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from app.ui.voice_fab import VoiceFab, BOTTOM_RESERVED_HEIGHT
from app.ui.toast import Toast


class VoiceLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.host = QWidget()
        self.host.resize(1160, 740)
        self.fab = VoiceFab(self.host)
        self.host._voice_fab = self.fab
        self.host.show()
        self.fab.show()
        self.app.processEvents()

    def tearDown(self):
        self.fab._reveal_animation.stop()
        self.fab._typewriter.stop()
        self.host.hide()
        self.host.deleteLater()
        self.app.processEvents()

    def test_input_expands_left_without_moving_button_and_submission_still_works(self):
        position = self.fab._ball.mapTo(self.host, QPoint())
        self.fab.expand()
        QTest.qWait(60)
        intermediate_width = self.fab._panel.width()
        QTest.qWait(180)
        self.assertGreater(self.fab._panel.width(), intermediate_width)
        self.assertEqual(self.fab._ball.mapTo(self.host, QPoint()), position)
        self.assertEqual(self.fab._panel.geometry().center().y(), self.fab._ball.geometry().center().y())
        self.assertLess(self.fab._panel.geometry().right(), self.fab._ball.x())
        self.assertGreaterEqual(self.host.height() - position.y() - self.fab._ball.height(), BOTTOM_RESERVED_HEIGHT)
        commands = []
        self.fab.submitted.connect(commands.append)
        self.fab._edit.setText(' 音量调整到50 ')
        QTest.keyClick(self.fab._edit, Qt.Key_Return)
        QTest.qWait(240)
        self.assertEqual(commands, ['音量调整到50'])
        self.assertFalse(self.fab._panel.isVisible())

    def test_narrow_window_and_status_stay_beside_button(self):
        self.host.resize(480, 520)
        self.fab.reposition()
        self.fab.expand()
        QTest.qWait(240)
        self.assertGreaterEqual(self.fab._panel.mapTo(self.host, QPoint()).x(), 0)
        toast = Toast(self.host, '已告诉小爱同学：你在吗')
        toast._popup(5000)
        self.app.processEvents()
        button = self.fab._ball.mapTo(self.host, QPoint())
        self.assertLess(toast.geometry().right(), button.x())
        self.assertAlmostEqual(toast.geometry().center().y(), button.y() + (self.fab._ball.height()-1)/2, delta=1)
        self.host.resize(760, 560)
        self.fab.reposition()
        self.app.processEvents()
        button = self.fab._ball.mapTo(self.host, QPoint())
        self.assertLess(toast.geometry().right(), button.x())


if __name__ == '__main__':
    unittest.main()

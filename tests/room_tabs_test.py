# SPDX-License-Identifier: GPL-3.0-or-later
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton
from app.ui.room_tabs import RoomTabStrip, RoomTab, build_room_menu


class RoomTabsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_drag_scrolls_without_activating_room_and_click_still_works(self):
        strip = RoomTabStrip()
        strip.resize(300, 48)
        clicks = []
        for i in range(12):
            button = RoomTab(str(i))
            button.setFixedSize(90, 48)
            button.clicked.connect(lambda _, index=i: clicks.append(index))
            strip.row.addWidget(button)
            strip.watch_button(button)
        strip.refresh()
        strip.show()
        self.app.processEvents()
        self.assertGreater(strip.horizontalScrollBar().maximum(), 0)
        button = strip.row.itemAt(1).widget()
        QTest.mousePress(button, Qt.LeftButton, pos=QPoint(60, 24))
        QTest.mouseMove(button, QPoint(10, 24))
        QTest.mouseRelease(button, Qt.LeftButton, pos=QPoint(10, 24))
        self.assertGreater(strip.horizontalScrollBar().value(), 0)
        self.assertEqual(clicks, [])
        QTest.mouseClick(button, Qt.LeftButton)
        self.assertEqual(clicks, [1])
        strip.hide()
        strip.deleteLater()

    def test_room_popup_keeps_counts_and_selects_the_clicked_room(self):
        selected = []
        menu = build_room_menu(None, [('场景', None), ('全屋', 29), ('办公室', 8)], '全屋', selected.append)
        self.assertEqual([a.data() for a in menu.actions()], [('场景', None), ('全屋', 29), ('办公室', 8)])
        QTest.mouseClick(menu.actions()[2].defaultWidget(), Qt.LeftButton)
        self.assertEqual(selected, ['办公室'])
        self.assertTrue(menu.windowFlags() & Qt.NoDropShadowWindowHint)
        menu.deleteLater()

    def test_room_counts_follow_current_home_and_keep_offline_devices(self):
        from app.ui.main_window import MainWindow
        devices = [SimpleNamespace(home_name='家一', room_name='办公室', online=True),
                   SimpleNamespace(home_name='家一', room_name='办公室', online=False),
                   SimpleNamespace(home_name='家一', room_name='客厅', online=True),
                   SimpleNamespace(home_name='家二', room_name='办公室', online=True)]
        window = SimpleNamespace(_displayed_devices=lambda: devices, _current_home='家一',
                                 _tab_buttons=dict.fromkeys(['场景', '全屋', '办公室', '客厅']),
                                 _current_room='全屋', _select_room=Mock())
        with patch('app.ui.main_window.build_room_menu') as build:
            MainWindow._build_room_menu(window)
            self.assertEqual(build.call_args.args[1], [('场景', None), ('全屋', 3), ('办公室', 2), ('客厅', 1)])


if __name__ == '__main__':
    unittest.main()

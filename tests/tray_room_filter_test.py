# SPDX-License-Identifier: GPL-3.0-or-later
"""Room filtering must preserve selections, scenes and the global sort order."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication

from app.core.models import DeviceInfo, SceneInfo
from app.ui.tray.manager_dialog import TrayManagerDialog


class TrayRoomFilterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        patches = [
            patch("app.ui.tray.manager_dialog.tray_store.load", return_value=["office"]),
            patch("app.ui.tray.manager_dialog.tray_store.load_order", return_value=[]),
            patch("app.ui.tray.manager_dialog.tray_store.load_scenes", return_value=[
                {"scene_id": "scene", "name": "回家", "home_id": "home", "home_name": "家"}]),
            patch("app.ui.tray.manager_dialog.settings_store.get_show_scene_tab", return_value=True),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        devices = [DeviceInfo("office", "办公室灯", "light", "家", "办公室", True),
                   DeviceInfo("bed", "卧室灯", "light", "家", "卧室", False),
                   DeviceInfo("none", "插座", "plug", "家", "", True)]
        self.dialog = TrayManagerDialog(devices, scenes=[SceneInfo("scene", "回家", "home", "家")])
        self.addCleanup(self.dialog.deleteLater)

    def test_room_menu_and_unassigned_room(self):
        menu = self.dialog._build_room_menu()
        actions = menu.actions()
        self.assertEqual(actions[0].text(), "全部房间")
        self.assertEqual(len(actions), 4)
        next(a for a in actions if a.text() == "未分配房间").trigger()
        visible = {did for did, row in self.dialog._device_rows.items() if not row.isHidden()}
        self.assertEqual(visible, {"none"})
        menu.deleteLater()

    def test_switch_rooms_keeps_checked_devices_and_saved_scene(self):
        d = self.dialog
        d._set_room_filter("卧室")
        self.assertTrue(d._device_rows["office"].isHidden())
        self.assertTrue(d._checks["office"].isChecked())
        d._checks["bed"].click()
        d._set_room_filter("办公室")
        selected = {(item["type"], item["id"]) for item in d.selected_order()}
        self.assertEqual(selected, {("device", "office"), ("device", "bed"), ("scene", "scene")})
        d._set_room_filter(None)
        self.assertTrue(all(not row.isHidden() for row in d._device_rows.values()))

    def test_tabs_and_sort_are_preserved_and_filter_only_applies_to_devices(self):
        d = self.dialog
        d._checks["bed"].click()
        d._set_room_filter("办公室")
        d._switch_tab(1)
        self.assertEqual(d._tab_dev.text(), "设备")
        self.assertEqual(d._tab_scene.text(), "场景")
        self.assertTrue(d._room_btn.isHidden())
        self.assertTrue(d._scene_checks["scene"].isChecked())
        self.assertEqual(d.selected_scene_data()[0]["scene_id"], "scene")
        d._switch_view("sort")
        self.assertEqual(set(d._sort_rows), {"office", "bed", "scene"})
        self.assertTrue(d._room_btn.isHidden())
        d._switch_view("list")
        d._switch_tab(0)
        self.assertFalse(d._room_btn.isHidden())
        self.assertEqual(d._current_room, "办公室")
        self.assertTrue(d._checks["bed"].isChecked())


if __name__ == "__main__":
    unittest.main()

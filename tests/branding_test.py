# SPDX-License-Identifier: GPL-3.0-or-later
"""Brand resources and non-destructive migration to the renamed application."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from PySide6.QtGui import QIcon, QImage
from PySide6.QtWidgets import QApplication
from app import APP_NAME, resource_path
from app.core import _json_store


class BrandingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_window_and_tray_icons_have_charcoal_background_and_white_mark(self):
        self.assertEqual(APP_NAME, 'MijiaDeck')
        for file in ('icon.png', 'tray_icon.png', 'tray_icon_light.png'):
            image = QImage(str(resource_path(f'app/ui/{file}')))
            self.assertFalse(image.isNull())
            scale = image.width() / 512
            self.assertEqual(image.pixelColor(round(256 * scale), round(30 * scale)).name(), '#303238')
            self.assertEqual(image.pixelColor(round(120 * scale), round(150 * scale)).name(), '#ffffff')
        icon = QIcon(str(resource_path('app/ui/icon.ico')))
        self.assertEqual({s.width() for s in icon.availableSizes()}, {16, 24, 32, 48, 64, 128, 256})

    def test_renamed_packaged_data_copies_old_settings_without_overwriting_new_data(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            old = root / 'MiHome-Windows'
            target = root / 'MijiaDeck'
            bundle = root / 'bundle'
            for path in (old, target, bundle):
                path.mkdir()
            (old / 'settings.json').write_text('{"theme":"dark"}', encoding='utf-8')
            (old / 'tray.json').write_text('{"source":"legacy"}', encoding='utf-8')
            (target / 'tray.json').write_text('{"source":"new"}', encoding='utf-8')
            (bundle / 'workbench.json').write_text('{"position":8}', encoding='utf-8')
            with patch.dict(os.environ, {'LOCALAPPDATA': temp}), \
                 patch('app.is_packaged', return_value=True), \
                 patch.object(_json_store, '_migrated', False), \
                 patch('sys.argv', [str(bundle / 'MijiaDeck.exe')]), \
                 patch('sys.executable', str(bundle / 'python.exe')):
                self.assertEqual(_json_store.data_file('settings.json'), target / 'settings.json')
                self.assertEqual(_json_store.read_json(target / 'settings.json', {}), {'theme': 'dark'})
                self.assertEqual(_json_store.read_json(target / 'tray.json', {}), {'source': 'new'})
                self.assertEqual(_json_store.read_json(target / 'workbench.json', {}), {'position': 8})
                self.assertTrue((old / 'settings.json').exists())

    def test_source_mode_retains_existing_local_settings_location(self):
        with patch('app.is_packaged', return_value=False):
            self.assertEqual(_json_store.data_dir(), Path(_json_store.__file__).resolve().parents[2])


if __name__ == '__main__':
    unittest.main()

# SPDX-License-Identifier: GPL-3.0-or-later
"""Tray settings restores its owner before opening the main settings layer."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from types import SimpleNamespace
from unittest.mock import Mock
import unittest
from PySide6.QtWidgets import QApplication, QWidget
from app.ui.tray.controller import TrayController


class MainHost(QWidget):
    def __init__(self):
        super().__init__()
        self.settings_calls = []

    def show_settings(self):
        self.settings_calls.append((self.isVisible(), self.isMinimized()))


class TraySettingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_hidden_and_minimized_main_are_restored_before_settings(self):
        for minimized in (False, True):
            with self.subTest(minimized=minimized):
                main = MainHost()
                if minimized:
                    main.showMinimized()
                quick = Mock()
                controller = SimpleNamespace(_main=main, _quick=quick)
                try:
                    TrayController._on_settings(controller)
                    quick.abort_toggle_animation.assert_called_once()
                    quick.hide.assert_called_once()
                    self.assertTrue(main.isVisible())
                    self.assertFalse(main.isMinimized())
                    self.assertEqual(main.settings_calls, [])
                    self.app.processEvents()
                    self.assertEqual(main.settings_calls, [(True, False)])
                finally:
                    main.hide()
                    main.deleteLater()
                    self.app.processEvents()


if __name__ == '__main__':
    unittest.main()

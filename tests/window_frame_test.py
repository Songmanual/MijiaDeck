# SPDX-License-Identifier: GPL-3.0-or-later
"""Qt owns the frame; native hit testing supports dragging and resizing."""
import ctypes
from ctypes import wintypes
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from PySide6.QtCore import QByteArray

from app.ui.main_window import MainWindow, _WM_NCHITTEST, _WM_NCLBUTTONDBLCLK, _HTCAPTION


class WindowFrameTest(unittest.TestCase):
    def test_native_title_double_click_toggles_once(self):
        msg = wintypes.MSG()
        msg.message = _WM_NCLBUTTONDBLCLK
        msg.wParam = _HTCAPTION
        window = SimpleNamespace(_toggle_maximized=Mock())
        result = MainWindow.nativeEvent(window, QByteArray(b'windows_generic_MSG'), ctypes.addressof(msg))
        self.assertEqual(result, (True, 0))
        window._toggle_maximized.assert_called_once_with()

    def test_client_frame_calculation_is_delegated_to_qt(self):
        msg = wintypes.MSG()
        msg.message = 0x0083  # WM_NCCALCSIZE
        msg.wParam = 1
        window = SimpleNamespace(_hit_test=Mock())
        result = MainWindow.nativeEvent(window, QByteArray(b'windows_generic_MSG'), ctypes.addressof(msg))
        self.assertEqual(result, (False, 0))
        window._hit_test.assert_not_called()

    def test_native_hit_testing_is_preserved(self):
        msg = wintypes.MSG()
        msg.message = _WM_NCHITTEST
        msg.lParam = 12345
        window = SimpleNamespace(_hit_test=Mock(return_value=2))
        result = MainWindow.nativeEvent(window, QByteArray(b'windows_generic_MSG'), ctypes.addressof(msg))
        self.assertEqual(result, (True, 2))
        window._hit_test.assert_called_once_with(12345)


if __name__ == '__main__':
    unittest.main()

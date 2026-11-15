# SPDX-License-Identifier: GPL-3.0-or-later
"""Qt owns the frame; native hit testing supports dragging and resizing."""
import ctypes
import sys
from ctypes import wintypes
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from PySide6.QtCore import QByteArray

from app.ui.main_window import (
    MainWindow, _WM_NCHITTEST, _WM_NCLBUTTONDBLCLK, _HTCAPTION,
    _WS_CAPTION, _WS_THICKFRAME, _WS_SYSMENU, _WS_POPUP,
)


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


class DwmShadowTest(unittest.TestCase):
    """DWM only draws a shadow for windows carrying WS_THICKFRAME/WS_CAPTION.

    FramelessWindowHint strips those bits, so the window loses its drop
    shadow. _enable_dwm_shadow puts them back without letting the system
    frame eat the client area.
    """

    def _run(self, style_before):
        window = SimpleNamespace(winId=Mock(return_value=0x1234))
        user32 = Mock()
        user32.GetWindowLongW.return_value = style_before
        dwmapi = Mock()
        fake_windll = SimpleNamespace(user32=user32, dwmapi=dwmapi)
        with patch.object(sys, 'platform', 'win32'), \
                patch('app.ui.main_window.ctypes.windll', fake_windll, create=True):
            MainWindow._enable_dwm_shadow(window)
        return user32, dwmapi

    def test_frameless_style_gains_shadow_bits(self):
        user32, dwmapi = self._run(_WS_POPUP)
        applied = user32.SetWindowLongW.call_args[0][2]
        self.assertTrue(applied & _WS_THICKFRAME, 'WS_THICKFRAME drives the DWM shadow')
        self.assertTrue(applied & _WS_CAPTION)
        self.assertTrue(applied & _WS_SYSMENU)
        self.assertFalse(applied & _WS_POPUP, 'WS_POPUP alone yields no shadow')
        dwmapi.DwmExtendFrameIntoClientArea.assert_called_once()
        user32.SetWindowPos.assert_called_once()

    def test_minimize_and_maximize_box_bits_are_not_added(self):
        """The system folds these bits into the frame size.

        Adding them made a maximized window overflow the work area by 8px
        on each side (1936x1048 on a 1920x1032 desktop). Qt and the custom
        WM_NCHITTEST handler already cover minimize/maximize.
        """
        user32, _ = self._run(_WS_POPUP)
        applied = user32.SetWindowLongW.call_args[0][2]
        self.assertFalse(applied & 0x00020000, 'WS_MINIMIZEBOX would inflate the frame')
        self.assertFalse(applied & 0x00010000, 'WS_MAXIMIZEBOX would inflate the frame')

    def test_existing_frame_is_left_untouched(self):
        user32, dwmapi = self._run(_WS_CAPTION | _WS_THICKFRAME | _WS_SYSMENU)
        user32.SetWindowLongW.assert_not_called()
        dwmapi.DwmExtendFrameIntoClientArea.assert_not_called()

    def test_other_platforms_are_a_no_op(self):
        window = SimpleNamespace(winId=Mock(return_value=0x1234))
        with patch.object(sys, 'platform', 'darwin'):
            MainWindow._enable_dwm_shadow(window)
        window.winId.assert_not_called()

    def test_dwm_failure_does_not_break_startup(self):
        window = SimpleNamespace(winId=Mock(side_effect=OSError('no hwnd')))
        with patch.object(sys, 'platform', 'win32'):
            MainWindow._enable_dwm_shadow(window)  # must not raise


if __name__ == '__main__':
    unittest.main()

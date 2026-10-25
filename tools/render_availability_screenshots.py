# SPDX-License-Identifier: GPL-3.0-or-later
"""Render speaker availability examples with fictional data and no network."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import sys
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication
from app.core import settings_store, tray_store
from app.core.models import DeviceInfo
from app.ui.main_window import MainWindow
from app.ui.theme_service import apply_theme
from tools.render_demo_screenshots import DemoJobs, DemoTray


def main():
    os.environ['QT_SCALE_FACTOR'] = '1'
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    for name in ('msyh.ttc', 'msyhbd.ttc', 'segoeui.ttf'):
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + name)
    app.setFont(QFont('Microsoft YaHei UI', 9))
    output = ROOT.parents[1] / 'outputs/verification/speaker-examples'
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as temp, ExitStack() as stack:
        stack.enter_context(patch('app.core._json_store.data_file', side_effect=lambda n: Path(temp) / n))
        stack.enter_context(patch('app.core._json_store.data_dir', return_value=Path(temp)))
        stack.enter_context(patch('app.core.availability.NetworkMonitor.check_now'))
        stack.enter_context(patch('app.ui.main_window.MijiaService', return_value=Mock()))
        stack.enter_context(patch('app.ui.main_window.JobExecutor', DemoJobs))
        stack.enter_context(patch('app.ui.main_window.TrayController', DemoTray))
        settings_store.set_theme_mode('light')
        settings_store.set_theme_color('blue')
        apply_theme('light', 'blue')
        lights = [DeviceInfo('demo-1', '客厅主灯', 'demo.light.sample', '示例家庭', '客厅', True),
                  DeviceInfo('demo-2', '书桌台灯', 'demo.light.sample', '示例家庭', '书房', True),
                  DeviceInfo('demo-3', '窗帘', 'demo.curtain.sample', '示例家庭', '卧室', True)]
        for scenario, devices in (
            ('no-speaker', lights),
            ('speaker-offline', lights + [DeviceInfo('demo-speaker', '客厅音箱',
                                      'demo.wifispeaker.sample', '示例家庭', '客厅', False)]),
        ):
            tray_store.save([d.did for d in devices])
            window = MainWindow()
            window._logged_out = False
            window._network_online = True
            window._default_size_applied = True
            window._clamp_to_screen = lambda: None
            window.resize(960, 620)
            window._known_power = {'demo-1': True, 'demo-2': False}
            window._apply_devices(devices)
            window._footer.set_logged_in(True)
            window.show()
            app.processEvents()
            assert window.grab().save(str(output / (scenario + '-main.png')))
            quick = window._tray._quick
            quick.show_near_tray()
            app.processEvents()
            assert quick.grab().save(str(output / (scenario + '-tray.png')))
            quick.hide()
            quick.deleteLater()
            window.hide()
            window.deleteLater()
            app.processEvents()
    print(output)


if __name__ == '__main__':
    main()

# SPDX-License-Identifier: GPL-3.0-or-later
"""Render the real UI using fictional devices, temporary settings and no network."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import sys
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QEvent, QTimer
from PySide6.QtGui import QFont, QFontDatabase, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel
from app.core.models import DeviceInfo
from app.ui import main_window
from app.ui.tray.quick_window import TrayQuickWindow
from app.ui.theme_service import apply_theme


class DemoJobs:
    def __init__(self, parent=None):
        pass

    def submit(self, *args, **kwargs):
        pass  # Never execute a cloud job or read an account credential.

    def shutdown(self):
        pass


class DemoTray:
    def __init__(self, service, jobs, main):
        self._quick = TrayQuickWindow(service, jobs)
        self._quick.speaker_changed.connect(main._update_voice_fab)
        self._tray = Mock()
        self._hover_timer = QTimer(main)

    def set_tray_visible(self, value):
        pass

    def set_devices(self, devices, power):
        self._quick.set_devices(devices, power)

    def set_metrics(self, metrics):
        self._quick.set_metrics(metrics)

    def hide_quick(self):
        self._quick.hide()


SAMPLES = [
    ('客厅主灯', '客厅', 'light'), ('客厅音箱', '客厅', 'wifispeaker'),
    ('空气净化器', '客厅', 'airpurifier'), ('温湿度计', '客厅', 'sensor_ht'),
    ('窗帘', '客厅', 'curtain'), ('吸顶灯', '卧室', 'light'),
    ('床头灯', '卧室', 'light'), ('卧室摄像头', '卧室', 'camera'),
    ('加湿器', '卧室', 'humidifier'), ('智能插座', '卧室', 'plug'),
    ('书桌台灯', '书房', 'light'), ('书房音箱', '书房', 'wifispeaker'),
    ('空调伴侣', '书房', 'acpartner'), ('温湿度计', '书房', 'sensor_ht'),
    ('打印机插座', '书房', 'plug'), ('厨房灯', '厨房', 'light'),
    ('净水器', '厨房', 'waterpurifier'), ('冰箱', '厨房', 'fridge'),
    ('门窗传感器', '厨房', 'magnet'), ('洗衣机', '阳台', 'washer'),
    ('阳台灯', '阳台', 'light'), ('玄关灯', '玄关', 'light'),
    ('门口摄像头', '玄关', 'camera'), ('门锁', '玄关', 'lock'),
    ('人体传感器', '玄关', 'motion'),
]


def render(mode, output):
    from app.core import settings_store, tray_store
    settings_store.set_theme_mode(mode)
    settings_store.set_theme_color('blue')
    devices = [DeviceInfo(f'demo-{i}', name, f'demo.{kind}.sample', '示例家庭', room, i != 23)
               for i, (name, room, kind) in enumerate(SAMPLES)]
    tray_store.save([devices[i].did for i in (1, 3, 4, 7, 10, 19, 22, 24)])
    apply_theme(mode, 'blue')
    window = main_window.MainWindow()
    window._default_size_applied = True
    window._clamp_to_screen = lambda: None
    window.resize(1160, 740)
    window.show()
    power = {d.did: (i % 3 != 0) for i, d in enumerate(devices)
             if SAMPLES[i][2] not in ('sensor_ht', 'motion', 'magnet', 'lock')}
    window._known_power = power
    window._metrics = {'demo-3': '24.5°C 52%', 'demo-13': '23.8°C 48%'}
    window._apply_devices(devices)
    window._footer.set_logged_in(True)
    app = QApplication.instance()
    QTest.qWait(220)
    app.processEvents()
    assert window.grab().save(str(output / f'main-{mode}.png'))
    quick = window._tray._quick
    quick._rebuild()
    quick._update_audio_bar()
    quick._update_voice_bar()
    # Avoid the small virtual screen's production height cap for documentation.
    quick.resize(412, 574)
    quick.show()
    quick._audio_bar._slider.setValue(60)
    quick._audio_bar._vol_label.setText('60')
    quick._audio_bar._set_enabled(True)
    quick._audio_bar._muted = False
    quick._audio_bar._refresh_play_style()
    app.processEvents()
    assert quick.grab().save(str(output / f'tray-{mode}.png'))
    quick.abort_toggle_animation()
    quick.hide()
    quick.deleteLater()
    window._force_quit = True
    window.close()
    window.deleteLater()
    app.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def render_camera(mode, output):
    from app.ui.device_dialog import DeviceDetailDialog
    apply_theme(mode, 'blue')
    device = DeviceInfo('demo-camera', '米家智能摄像机 · 示例',
                        'chuangmi.camera.029a02', '示例家庭', '示例客厅', True)
    window = DeviceDetailDialog(Mock(), DemoJobs(), device)
    window._camera_positioned = True
    window.resize(900, 600)
    window.show()
    app = QApplication.instance()
    app.processEvents()
    camera = window._camera
    frame = QImage(str(output / 'camera-demo-scene.jpg'))
    if frame.isNull():
        raise RuntimeError('Missing fictional camera demonstration frame')
    camera._power.set_state(True)
    camera._canvas.set_frame(frame)
    camera._canvas.set_controls_enabled(True)
    label = QLabel('示意画面 · AI 生成', camera._canvas)
    label.setStyleSheet('color: white; background: rgba(0,0,0,105); padding: 5px 9px; border-radius: 5px; font-size: 8pt;')
    label.adjustSize()
    label.move(camera._canvas.width() - label.width() - 12, 12)
    label.show()
    QTest.qWait(120)
    app.processEvents()
    assert window.grab().save(str(output / f'camera-{mode}.jpg'), 'JPG', 91)
    window.hide()
    window.deleteLater()
    app.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()


def main():
    if '--theme' not in sys.argv:
        import subprocess
        for mode in ('light', 'dark'):
            command = [sys.executable, str(Path(__file__).resolve()), '--theme', mode]
            if '--camera-only' in sys.argv:
                command.append('--camera-only')
            subprocess.run(command, check=True)
        return
    # SiliconUI's import reads Windows DPI; override before creating QApplication.
    os.environ['QT_SCALE_FACTOR'] = '1.5'
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    for file in ('msyh.ttc', 'msyhbd.ttc', 'segoeui.ttf'):
        QFontDatabase.addApplicationFont(f'C:/Windows/Fonts/{file}')
    app.setFont(QFont('Microsoft YaHei UI', 9))
    output = ROOT / 'docs' / 'images'
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as temp, ExitStack() as stack:
        stack.enter_context(patch('app.core._json_store.data_file',
                                  side_effect=lambda name: Path(temp) / name))
        stack.enter_context(patch('app.core._json_store.data_dir', return_value=Path(temp)))
        stack.enter_context(patch.object(main_window, 'MijiaService', return_value=Mock()))
        stack.enter_context(patch.object(main_window, 'JobExecutor', DemoJobs))
        stack.enter_context(patch.object(main_window, 'TrayController', DemoTray))
        mode = sys.argv[sys.argv.index('--theme') + 1]
        if mode not in ('light', 'dark'):
            raise ValueError('Unknown screenshot theme')
        if '--camera-only' in sys.argv:
            render_camera(mode, output)
        else:
            render(mode, output)
    print('Demo screenshots saved to docs/images (fictional data; no account/network access)')


if __name__ == '__main__':
    main()

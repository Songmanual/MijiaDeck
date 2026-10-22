# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline checks for a distributed executable; never create an account client."""
import json
import os
import sys
from pathlib import Path


def check_package(report_path: str) -> int:
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    report = {'ok': False, 'checks': []}
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QIcon
        from PySide6.QtMultimedia import QMediaPlayer
        from PySide6.QtMultimediaWidgets import QVideoWidget
        import qtawesome
        import qrcode
        from app import __version__, is_packaged, resource_path
        from app.core.service import MijiaService
        from app.ui.main_window import MainWindow
        from app.ui.theme_service import apply_theme
        from app.ui.volume_slider import VolumeSlider

        application = QApplication.instance() or QApplication([])
        for name in ['icon.png', 'icon.ico', 'tray_icon.png', 'tray_icon_light.png']:
            path = resource_path('app/ui/' + name)
            if not path.is_file() or QIcon(str(path)).pixmap(32, 32).isNull():
                raise RuntimeError('Missing or unreadable resource: ' + name)
        for path in ['app/ui/icons/tray-move.svg', 'app/ui/icons/mijiadeck.svg']:
            if not resource_path(path).is_file():
                raise RuntimeError('Missing resource: ' + path)
        report['checks'].append('bundled-icons')
        if qtawesome.icon('mdi6.keyboard', color='#ffffff').pixmap(24, 24).isNull():
            raise RuntimeError('QtAwesome font rendering failed')
        report['checks'].append('qtawesome-font')
        for theme in ['light', 'dark']:
            apply_theme(theme, '#2563eb')
            slider = VolumeSlider()
            slider.resize(320, 42)
            slider.setValue(60)
            application.processEvents()
            if slider.grab().isNull():
                raise RuntimeError('Widget rendering failed: ' + theme)
            slider.close()
            slider.deleteLater()
        report['checks'].append('light-dark-widget-rendering')
        player = QMediaPlayer()
        video = QVideoWidget()
        player.setVideoOutput(video)
        report['checks'].append('qt-multimedia-initialization')
        qr = qrcode.QRCode()
        qr.add_data('MijiaDeck offline package check')
        qr.make(fit=True)
        report['checks'].append('qr-login-dependency')
        java = resource_path('tools/camera_relay/runtime/bin/java.exe')
        relay = resource_path('tools/camera_relay/camera-relay.jar')
        if java.exists() or relay.exists():
            import subprocess
            result = subprocess.run([str(java), '-cp', str(relay), 'CameraRelay', '--check'],
                                    capture_output=True, text=True, timeout=20,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode != 0 or 'CAMERA_RELAY_2' not in result.stdout:
                raise RuntimeError('Bundled camera relay offline check failed')
            report['checks'].append('camera-relay-offline-check')
        report.update(ok=True, version=__version__, packaged=is_packaged(),
                      python=sys.version.split()[0])
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
    Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['ok'] else 1

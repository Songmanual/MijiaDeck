# SPDX-License-Identifier: GPL-3.0-or-later
"""Relocate the ZIP and validate it offline with an isolated user directory."""
import json
import os
import subprocess
import tempfile
import sys
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import __version__


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--previous-zip', type=Path,
                        help='Extract an old release first, then overwrite it with this build')
    options = parser.parse_args()
    archive = ROOT / f'dist/portable/MijiaDeck-v{__version__}-windows-x64.zip'
    # Windows may briefly retain a loaded per-user font after the process exits.
    with tempfile.TemporaryDirectory(prefix='MijiaDeck-check-', ignore_cleanup_errors=True) as temporary:
        folder = Path(temporary) / '便携版 验证'
        if options.previous_zip:
            with ZipFile(options.previous_zip) as previous:
                previous.extractall(folder)
        with ZipFile(archive) as package:
            package.extractall(folder)
        user = Path(temporary) / 'user'
        user.mkdir()
        preserved = user / 'Local/MijiaDeck/settings.json'
        preserved.parent.mkdir(parents=True)
        preserved.write_text('{"upgrade_test_marker":"preserve-me"}', encoding='utf-8')
        original_settings = preserved.read_bytes()
        env = os.environ.copy()
        system_root = env.get('SYSTEMROOT', r'C:\Windows')
        env.update(HOME=str(user), USERPROFILE=str(user),
                   LOCALAPPDATA=str(user / 'Local'), APPDATA=str(user / 'Roaming'),
                   SYSTEMROOT=system_root, WINDIR=system_root,
                   PATH=system_root + r'\System32', QT_QPA_PLATFORM='offscreen')
        for key in ['PYTHONHOME', 'PYTHONPATH', 'QT_PLUGIN_PATH', 'QML2_IMPORT_PATH']:
            env.pop(key, None)
        report = ROOT / 'build/packaged-check.json'
        process = subprocess.run([str(folder / 'MijiaDeck/MijiaDeck.exe'),
                                  '--check-package', str(report)], cwd=folder,
                                 env=env, timeout=45)
        data = json.loads(report.read_text(encoding='utf-8'))
        print(json.dumps({'mode': 'overwrite-upgrade' if options.previous_zip else 'fresh-extraction',
                          'exit_code': process.returncode,
                          'zip_mb': round(archive.stat().st_size / 1048576, 1),
                          'report': data}, ensure_ascii=False, indent=2))
        if process.returncode or not data['ok'] or not data['packaged']:
            raise SystemExit(1)
        info = json.loads((folder / 'MijiaDeck/build-info.json').read_text(encoding='utf-8'))
        if info['camera_backend_included'] and 'camera-relay-offline-check' not in data['checks']:
            raise RuntimeError('Camera backend was bundled but not validated')
        startup_report = ROOT / 'build/startup-check.json'
        startup_report.unlink(missing_ok=True)
        # Keep the windowed bootloader's absent streams; never redirect them to
        # a log before importing dependencies, which hid the v1.0.1 crash.
        process = subprocess.run([str(folder / 'MijiaDeck/MijiaDeck.exe'),
                                  '--check-startup', str(startup_report)],
                                 cwd=folder, env=env, timeout=30)
        startup = json.loads(startup_report.read_text(encoding='utf-8'))
        print(json.dumps({'startup_exit_code': process.returncode, 'report': startup},
                         ensure_ascii=False, indent=2))
        if process.returncode or not startup['ok'] or not startup['packaged']:
            raise RuntimeError('Windowed main-window startup failed')
        if preserved.read_bytes() != original_settings:
            raise RuntimeError('Existing user settings changed during package validation')
        print('Existing user settings preserved')


if __name__ == '__main__':
    main()

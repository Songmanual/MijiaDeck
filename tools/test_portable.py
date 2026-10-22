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
    archive = ROOT / f'dist/portable/MijiaDeck-v{__version__}-windows-x64.zip'
    # Windows may briefly retain a loaded per-user font after the process exits.
    with tempfile.TemporaryDirectory(prefix='MijiaDeck-check-', ignore_cleanup_errors=True) as temporary:
        folder = Path(temporary) / '便携版 验证'
        with ZipFile(archive) as package:
            package.extractall(folder)
        user = Path(temporary) / 'user'
        user.mkdir()
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
        print(json.dumps({'exit_code': process.returncode,
                          'zip_mb': round(archive.stat().st_size / 1048576, 1),
                          'report': data}, ensure_ascii=False, indent=2))
        if process.returncode or not data['ok'] or not data['packaged']:
            raise SystemExit(1)
        info = json.loads((folder / 'MijiaDeck/build-info.json').read_text(encoding='utf-8'))
        if info['camera_backend_included'] and 'camera-relay-offline-check' not in data['checks']:
            raise RuntimeError('Camera backend was bundled but not validated')


if __name__ == '__main__':
    main()

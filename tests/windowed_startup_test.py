# SPDX-License-Identifier: GPL-3.0-or-later
"""Import the production entrypoint with pythonw/PyInstaller standard streams."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WindowedStartupTest(unittest.TestCase):
    def test_show_main_flag_overrides_saved_tray_start_without_changing_preference(self):
        code = '''
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from unittest.mock import patch
from PySide6.QtWidgets import QWidget
import run
class Window(QWidget):
    def start(self): pass
def ready(app, window):
    app.exit(0 if window.isVisible() else 1)
sys.argv = ['run.py', '--show-main']
with patch.object(run, 'MainWindow', Window), patch('app.core.settings_store.should_start_hidden', return_value=True), patch('app.core.settings_store.mark_version_started'):
    raise SystemExit(run.main(ready))
'''
        result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, timeout=20)
        self.assertEqual(result.returncode, 0)

    def test_dependency_import_with_all_standard_streams_absent(self):
        code = '''
import runpy, sys
sys.stdin = sys.stdout = sys.stderr = None
runpy.run_path('run.py', run_name='windowed_import_check')
assert sys.stdout is not None and isinstance(sys.stdout.isatty(), bool)
assert sys.stderr is not None and isinstance(sys.stderr.isatty(), bool)
assert sys.stdin is not None and sys.stdin.read() == ''
'''
        result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, timeout=20)
        self.assertEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()

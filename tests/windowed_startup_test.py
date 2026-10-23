# SPDX-License-Identifier: GPL-3.0-or-later
"""Import the production entrypoint with pythonw/PyInstaller standard streams."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WindowedStartupTest(unittest.TestCase):
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

# SPDX-License-Identifier: GPL-3.0-or-later
"""Fetch versioned upstream license texts for the release (not executable code)."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'Qt-LGPL-3.0.txt': 'https://raw.githubusercontent.com/pyside/pyside-setup/v6.8.3/LICENSES/LGPL-3.0-only.txt',
    'FFmpeg-LGPL-2.1.txt': 'https://raw.githubusercontent.com/FFmpeg/FFmpeg/n7.1/COPYING.LGPLv2.1',
    'Qt-FFmpeg-attributions.json': 'https://raw.githubusercontent.com/qt/qtmultimedia/v6.8.3/src/3rdparty/ffmpeg/qt_attribution.json',
    'FontAwesome-6.7.2.txt': 'https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.7.2/LICENSE.txt',
    'FontAwesome-5.15.4.txt': 'https://raw.githubusercontent.com/FortAwesome/Font-Awesome/5.15.4/LICENSE.txt',
    'MaterialDesign-6.9.96.txt': 'https://raw.githubusercontent.com/Templarian/MaterialDesign-Webfont/v6.9.96/LICENSE',
    'MaterialDesign-5.9.55.txt': 'https://raw.githubusercontent.com/Templarian/MaterialDesign-Webfont/v5.9.55/LICENSE',
    'Codicons-0.0.36.txt': 'https://raw.githubusercontent.com/microsoft/vscode-codicons/0.0.36/LICENSE',
    'RemixIcon-2.5.0.txt': 'https://raw.githubusercontent.com/Remix-Design/RemixIcon/v2.5.0/License',
    'QtAwesome-font-sources.md': 'https://raw.githubusercontent.com/spyder-ide/qtawesome/v1.4.2/README.md',
    'Phosphor.txt': 'https://raw.githubusercontent.com/phosphor-icons/web/legacy/LICENSE',
}


def main():
    target = ROOT / 'docs/licenses'
    target.mkdir(parents=True, exist_ok=True)

    def fetch(item):
        name, url = item
        cached = target / name
        if cached.is_file():
            content = cached.read_bytes()
            return name, {'url': url, 'sha256': hashlib.sha256(content).hexdigest()}
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        if len(response.content) < 100:
            raise RuntimeError('Incomplete license text: ' + name)
        (target / name).write_bytes(response.content)
        return name, {'url': url, 'sha256': hashlib.sha256(response.content).hexdigest()}

    with ThreadPoolExecutor(max_workers=4) as pool:
        manifest = dict(pool.map(fetch, SOURCES.items()))
    (target / 'sources.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('Collected', len(manifest), 'upstream license documents.')


if __name__ == '__main__':
    main()

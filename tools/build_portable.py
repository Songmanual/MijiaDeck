# SPDX-License-Identifier: GPL-3.0-or-later
"""Build a Windows x64 directory bundle without a C compiler or personal data."""
import hashlib
import importlib.metadata
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import __version__


def main():
    if sys.platform != 'win32':
        raise SystemExit('Build on Windows x64 with Python 3.12 / PySide6 6.8.3.')
    import PyInstaller
    with_camera = '--with-camera' in sys.argv
    output = ROOT / 'dist' / 'portable'
    output.mkdir(parents=True, exist_ok=True)
    version_file = ROOT / 'build/windows-version.txt'
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_tuple = tuple(map(int, __version__.split('.'))) + (0,)
    version_file.write_text(
        'VSVersionInfo(ffi=FixedFileInfo(filevers=' + repr(version_tuple) +
        ', prodvers=' + repr(version_tuple) +
        ', mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0,0)), '
        'kids=[StringFileInfo([StringTable("040904B0", ['
        'StringStruct("ProductName", "MijiaDeck"),'
        'StringStruct("FileDescription", "MijiaDeck - Xiaomi Mi Home Desktop"),'
        'StringStruct("FileVersion", "' + __version__ + '"),'
        'StringStruct("ProductVersion", "' + __version__ + '"),'
        'StringStruct("OriginalFilename", "MijiaDeck.exe")])]),'
        'VarFileInfo([VarStruct("Translation", [1033,1200])])])', encoding='utf-8')
    # An explicit allowlist: no project-directory or account/config folder copying.
    args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir', '--windowed',
            '--name', 'MijiaDeck', '--icon', str(ROOT / 'app/ui/icon.ico'),
            '--version-file', str(version_file),
            '--distpath', str(output), '--workpath', str(ROOT / 'build/portable'),
            '--specpath', str(ROOT / 'build'), '--paths', str(ROOT),
            '--collect-submodules', 'app', '--collect-data', 'qtawesome',
            '--copy-metadata', 'mijiaAPI', '--exclude-module', 'tkinter',
            '--exclude-module', 'pytest', '--exclude-module', 'matplotlib']
    for name in ['icon.png', 'icon.ico', 'tray_icon.png', 'tray_icon_light.png']:
        args += ['--add-data', f'{ROOT / "app/ui" / name};app/ui']
    args += ['--add-data', f'{ROOT / "app/ui/icons"};app/ui/icons', str(ROOT / 'run.py')]
    if '--repack' not in sys.argv:
        subprocess.run(args, cwd=ROOT, check=True)
    bundle = output / 'MijiaDeck'
    camera_target = bundle / '_internal/tools/camera_relay'
    if with_camera:
        backend = ROOT / 'tools/camera_relay'
        if not (backend / 'camera-relay.jar').is_file() or not (backend / 'runtime/bin/java.exe').is_file():
            raise RuntimeError('Build the camera backend with tools/install_camera_backend.py first')
        camera_target.mkdir(parents=True, exist_ok=True)
        for name in ['camera-relay.jar', 'README.md', 'UPSTREAM-README.md']:
            shutil.copy2(backend / name, camera_target / name)
        shutil.copytree(backend / 'runtime', camera_target / 'runtime', dirs_exist_ok=True)
    elif camera_target.exists():
        raise RuntimeError('Existing camera files found; use a fresh build for a backend-free package')
    for name in ['LICENSE', 'THIRD_PARTY_NOTICES.md', 'README.md']:
        shutil.copy2(ROOT / name, bundle / name)
    shutil.copytree(ROOT / 'docs/licenses', bundle / 'licenses/upstream', dirs_exist_ok=True)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    (bundle / 'licenses/Python').mkdir(parents=True, exist_ok=True)
    shutil.copy2(python_license, bundle / 'licenses/Python/LICENSE.txt')
    shutil.copy2(ROOT / 'docs/DEPENDENCY_SOURCES.md', bundle / 'DEPENDENCY_SOURCES.md')
    (bundle / '使用说明.txt').write_text(
        'MijiaDeck ' + __version__ + '\n\n'
        '请先完整解压，再运行 MijiaDeck.exe，无需安装 Python。\n'
        '不能单独移动 EXE；_internal 文件夹是必需的运行组件。\n'
        '支持 Windows 10 1809+ / Windows 11 x64；不支持 Win7 / Win8。\n'
        '使用米家 APP 扫码登录。\n'
        '配置保存在 %LOCALAPPDATA%\\MijiaDeck；登录凭据在用户目录 .config\\mijia-api。\n'
        + ('本包包含实验性摄像头组件和独立 Java 运行时，无需另装 Java。\n'
           '仅支持兼容摄像头；上游 micam 分发许可尚未明确，详见 THIRD_PARTY_NOTICES.md。\n'
           if with_camera else '本包未附带实验性摄像头传输组件，无法直接播放摄像头视频。\n') +
        '项目与源码：https://github.com/Songmanual/MijiaDeck\n', encoding='utf-8-sig')
    # Preserve installed license texts and versions for bundled dependencies.
    versions = {}
    for dist in importlib.metadata.distributions():
        name = dist.metadata['Name']
        if name.lower() in {'mihome-windows', 'mijiadeck', 'pip', 'setuptools'}:
            continue
        versions[name] = dist.version
        for item in dist.files or []:
            lower = str(item).lower()
            if '.dist-info/' not in lower or not any(p in item.name.lower() for p in ['license', 'copying', 'notice']):
                continue
            source = Path(dist.locate_file(item))
            if source.is_file():
                target = bundle / 'licenses' / name / str(item).split('.dist-info/', 1)[-1]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    # Preserve the fonts' embedded authorship, copyright and license notices.
    import qtawesome
    for font in (Path(qtawesome.__file__).parent / 'fonts').glob('*.ttf'):
        data = font.read_bytes()
        count = struct.unpack_from('>H', data, 4)[0]
        for i in range(count):
            tag, _, offset, _ = struct.unpack_from('>4sIII', data, 12 + i * 16)
            if tag != b'name':
                continue
            _, records, strings = struct.unpack_from('>HHH', data, offset)
            notices = []
            for j in range(records):
                platform, _, _, name_id, length, start = struct.unpack_from('>HHHHHH', data, offset + 6 + j * 12)
                if name_id not in (0, 8, 9, 11, 13, 14):
                    continue
                text = data[offset + strings + start:offset + strings + start + length].decode(
                    'utf-16-be' if platform in (0, 3) else 'latin-1', errors='replace')
                if text and text not in notices:
                    notices.append(text)
            if notices:
                target = bundle / 'licenses/fonts' / (font.stem + '.txt')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('\n\n'.join(notices), encoding='utf-8')
            break
    (bundle / 'build-info.json').write_text(json.dumps({
        'version': __version__, 'python': sys.version.split()[0],
        'packager': 'PyInstaller ' + PyInstaller.__version__, 'dependencies': versions,
        'camera_backend_included': with_camera,
        'camera_source_commit': '2cc9d9e7607014d1d05c17bc5676544fbb0d5d24' if with_camera else None,
        'camera_upstream_license': 'not confirmed' if with_camera else None,
        'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    forbidden = {'auth.json', 'settings.json', 'tray.json', 'workbench.json',
                 'devices_cache.json', 'account_profiles.json', 'device_icons.json'}
    for path in bundle.rglob('*'):
        allowed_relay = with_camera and (path == camera_target / 'camera-relay.jar' or
                                         path.is_relative_to(camera_target / 'runtime'))
        if path.is_file() and (path.name in forbidden or (path.suffix == '.jar' and not allowed_relay)):
            raise RuntimeError('Unexpected private or camera backend file: ' + str(path.relative_to(bundle)))
    archive = output / f'MijiaDeck-v{__version__}-windows-x64.zip'
    with ZipFile(archive, 'w', ZIP_DEFLATED, compresslevel=6) as package:
        for path in sorted(bundle.rglob('*')):
            if path.is_file():
                package.write(path, 'MijiaDeck/' + path.relative_to(bundle).as_posix())
    with archive.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest + '  ' + archive.name + '\n', encoding='ascii')
    print(archive)
    print('SHA256:', digest)


if __name__ == '__main__':
    main()

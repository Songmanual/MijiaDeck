"""Build the experimental CS2 relay locally from pinned upstream source."""
import argparse
import hashlib
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile

COMMIT = '2cc9d9e7607014d1d05c17bc5676544fbb0d5d24'
SOURCE_URL = 'https://codeload.github.com/eugeneRover/micam/zip/' + COMMIT
SOURCE_HASH = '8f2685016c430cdc325ce46127420cfebadb2e88316a1fde6ed228eaa158754b'
JDK_URL = ('https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/'
           'OpenJDK21U-jdk_x64_windows_hotspot_21.0.12.1_1.zip')
JDK_HASH = 'f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e'


def extract(url, checksum, target):
    request = urllib.request.Request(url, headers={'User-Agent': 'MiHome-Windows'})
    with urllib.request.urlopen(request, timeout=240) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != checksum:
        raise RuntimeError('Camera component archive checksum mismatch')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            if not (target / name).resolve().is_relative_to(target.resolve()):
                raise RuntimeError('Invalid archive path')
        archive.extractall(target)
    return next(target.iterdir())


def install(jdk=None):
    tools = Path(__file__).resolve().parent
    target = tools / 'camera_relay'
    with tempfile.TemporaryDirectory(prefix='mihome-camera-') as folder:
        build = Path(folder)
        source = extract(SOURCE_URL, SOURCE_HASH, build / 'source')
        if jdk is None:
            jdk = extract(JDK_URL, JDK_HASH, build / 'jdk')
        jdk = Path(jdk)
        classes = build / 'classes'
        classes.mkdir()
        files = [str(p) for package in ('miss', 'pppp', 'server')
                 for p in (source / 'src/main/java/micam' / package).glob('*.java')]
        # No upstream CLI, cloud login, credential store, or third-party Java libraries.
        files.append(str(target / 'CameraRelay.java'))
        subprocess.run([str(jdk / 'bin/javac.exe'), '--release', '21', '-encoding', 'UTF-8',
                        '-d', str(classes), *files], check=True)
        subprocess.run([str(jdk / 'bin/jar.exe'), '--create', '--file', str(target / 'camera-relay.jar'),
                        '-C', str(classes), '.'], check=True)
        if not (target / 'runtime').exists():
            subprocess.run([str(jdk / 'bin/jlink.exe'), '--add-modules', 'java.base,jdk.httpserver,jdk.crypto.ec',
                            '--strip-debug', '--no-header-files', '--no-man-pages', '--compress=zip-6',
                            '--output', str(target / 'runtime')], check=True)
        # Preserve notices for the locally built upstream component.
        shutil.copyfile(source / 'README.md', target / 'UPSTREAM-README.md')
        subprocess.run([str(target / 'runtime/bin/java.exe'), '-cp', str(target / 'camera-relay.jar'),
                        'CameraRelay', '--check'], check=True)
    print('Camera remote relay installed (local experimental build)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--jdk', type=Path, help='Existing Windows JDK 21 or newer')
    install(parser.parse_args().jdk)

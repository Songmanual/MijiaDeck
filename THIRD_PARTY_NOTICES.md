# Third-party notices / 开源致谢

MijiaDeck is a third-party desktop client and is not affiliated with Xiaomi.

## MiHome-Windows

Source: https://github.com/huanyuejue/MiHome-Windows

This project is derived from MiHome-Windows. Existing copyright notices are retained. The project remains under GPL-3.0-or-later; see LICENSE.

## mijiaAPI and UI dependencies

- mijiaAPI: https://github.com/Do1e/mijia-api
- PySide6-SiliconUI: https://github.com/H1DDENADM1N/PySide6-SiliconUI
- Qt / PySide6: https://www.qt.io/qt-for-python
- QtAwesome: https://github.com/spyder-ide/qtawesome
- NumPy: https://numpy.org/

Dependencies keep their respective licenses and notices. A binary distribution must include the applicable notices and required license materials for its exact bundled versions. Dependency references here do not replace those materials.

## Experimental camera transport: micam

Source: https://github.com/eugeneRover/micam

Pinned reference commit: 2cc9d9e7607014d1d05c17bc5676544fbb0d5d24

CameraRelay.java is the local adapter used for experimental testing. The upstream transport source is not checked into this repository. No explicit redistribution license was found at the pinned revision. Attribution alone is not redistribution permission.

The maintainer has elected to include the compiled camera-relay.jar and its linked upstream transport classes in the v1.0.1 full distribution. **Upstream redistribution permission has not been confirmed.** The project being free of charge, non-commercial and open source does not itself grant that permission. This notice records the unresolved status; it does not replace permission or relicense upstream code under MijiaDeck's GPL. Generated binaries remain excluded from the Git source tree. See tools/camera_relay/README.md.

The full distribution includes a reduced Temurin/OpenJDK 21 runtime. Its `legal/` notices and `release` metadata are preserved next to its files. OpenJDK source is available from https://github.com/adoptium/temurin21-binaries and https://github.com/openjdk/jdk21u ; consult the bundled runtime metadata for its build version. No system-wide Java installation is required.

## Branding

The MijiaDeck symbol is derived from the vector artwork supplied by the project maintainer. References to Mijia, Mi Home and Xiaomi identify the supported ecosystem and do not imply official endorsement.

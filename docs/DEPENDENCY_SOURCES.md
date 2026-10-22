# Bundled libraries, notices and corresponding sources

MijiaDeck is GPL-3.0-or-later. Its corresponding source and build scripts are available beside the release at https://github.com/Songmanual/MijiaDeck (select the matching release tag). Dependency versions for this binary are recorded in `build-info.json`; unmodified installed license texts are collected under `licenses/`.

## Qt / PySide6 / Shiboken 6.8.3

Copyright The Qt Company Ltd. and other contributors. The open-source libraries are distributed under their applicable LGPL/GPL and third-party terms. The LGPLv3 text is in `licenses/upstream/Qt-LGPL-3.0.txt`; GPLv3 is in the root `LICENSE`. No commercial Qt license is claimed. The upstream commercial-license notice is preserved alongside other upstream notices.

Exact source archives, including upstream third-party notices and build scripts:

- Qt 6.8.3: https://download.qt.io/archive/qt/6.8/6.8.3/single/qt-everywhere-src-6.8.3.tar.xz
- PySide6 / Shiboken 6.8.3: https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.8.3-src/pyside-setup-everywhere-src-6.8.3.tar.xz
- Qt notices: https://doc.qt.io/qt-6.8/licenses-used-in-qt.html
- Qt for Python notices: https://doc.qt.io/qtforpython-6.8/licenses.html

The directory bundle dynamically loads Qt/PySide shared libraries from `_internal`. You may replace these libraries with interface-compatible modified versions and rebuild the application using the provided source and build scripts. Reverse engineering for debugging such modifications is not prohibited by this project.

## FFmpeg

Qt Multimedia includes FFmpeg shared libraries, copyright the FFmpeg developers. The Qt 6.8.3 upstream attribution and LGPLv2.1 text are in `licenses/upstream/`. Qt's pinned FFmpeg source and its constituent licenses: https://github.com/FFmpeg/FFmpeg/tree/n7.1 ; Qt build instructions: https://github.com/qt/qt5/tree/v6.8.3/coin/provisioning . Libraries are dynamically linked and may be replaced with compatible builds.

## Python and icon fonts

Python's license is in `licenses/Python/`. QtAwesome's MIT notice and each font's embedded copyright/author/license information are under `licenses/`. Additional versioned Font Awesome, Material Design, Codicons and Remix Icon notices are in `licenses/upstream/`. The QtAwesome upstream README there identifies the font projects and their licenses. Font files have not been modified.

## Camera backend

The micam-based relay JAR and Java runtime are **not included**. See `THIRD_PARTY_NOTICES.md` for the experimental camera backend's separate distribution status.

# SPDX-License-Identifier: GPL-3.0-or-later
"""Rebuild PNG/ICO assets from the editable MijiaDeck SVG. Requires Pillow."""
import os
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PIL import Image
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication


def main():
    app = QApplication.instance() or QApplication([])
    ui = Path(__file__).resolve().parents[1] / 'app' / 'ui'
    renderer = QSvgRenderer(str(ui / 'icons' / 'mijiadeck.svg'))
    if not renderer.isValid():
        raise ValueError('Invalid branding SVG')
    for name, size in [('icon.png', 512), ('tray_icon.png', 256), ('tray_icon_light.png', 256)]:
        image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
        image.fill(0)
        painter = QPainter(image)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        if not image.save(str(ui / name)):
            raise OSError(f'Cannot write {name}')
    with Image.open(ui / 'icon.png') as image:
        image.save(ui / 'icon.ico', format='ICO',
                   sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)])
    print('MijiaDeck SVG -> application, tray and multi-size ICO assets: OK')


if __name__ == '__main__':
    main()

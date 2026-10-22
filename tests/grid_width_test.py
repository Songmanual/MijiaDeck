# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from types import SimpleNamespace
from app.ui.main_window import MainWindow


class GridWidthTest(unittest.TestCase):
    def test_full_rows_fill_viewport_including_rounding_remainders(self):
        for available in (702, 980, 1100, 1101, 1102, 1103, 1400, 1901):
            with self.subTest(viewport=available):
                window = SimpleNamespace(_grid=SimpleNamespace(spacing=lambda: 8),
                    _scroll=SimpleNamespace(viewport=lambda: SimpleNamespace(width=lambda: available)))
                columns = MainWindow._columns_for_width(window, available)
                widths = [MainWindow._grid_card_width(window, columns, col) for col in range(columns)]
                self.assertEqual(sum(widths) + (columns-1)*8, available)
                self.assertLessEqual(max(widths)-min(widths), 1)
                self.assertGreaterEqual(min(widths), 212)


if __name__ == '__main__':
    unittest.main()

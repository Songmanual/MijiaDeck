# SPDX-License-Identifier: GPL-3.0-or-later
"""Every selectable color provides separate light/dark interaction roles."""
import unittest
from app.ui import si_theme


class ThemeColorTest(unittest.TestCase):
    def tearDown(self):
        si_theme.set_accent('green')
        si_theme.set_theme('light')

    def test_each_color_has_distinct_surface_and_interaction_roles(self):
        from app.ui.settings_dialog import _THEME_COLORS
        for accent in ('green', 'pink', 'yellow', 'blue'):
            modes = []
            for mode in ('light', 'dark'):
                with self.subTest(accent=accent, mode=mode):
                    si_theme.set_accent(accent)
                    si_theme.set_theme(mode)
                    roles = si_theme.accent_colors()
                    self.assertEqual(roles['THEME'], _THEME_COLORS[accent][1])
                    self.assertEqual(len({roles['THEME'], roles['THEME_HOVER'], roles['THEME_PRESSED']}), 3)
                    self.assertNotEqual(roles['THEME'], roles['ACCENT_SURFACE'])
                    self.assertNotEqual(roles['ON_THEME_TEXT'], roles['THEME'])
                    self.assertIn(roles['THEME'], si_theme.build_qss())
                    self.assertEqual(si_theme.SiColors.THEME, roles['THEME'])
                    modes.append(roles)
            self.assertNotEqual(modes[0]['ACCENT_SURFACE'], modes[1]['ACCENT_SURFACE'])

    def test_invalid_choice_cannot_replace_current_color(self):
        si_theme.set_accent('blue')
        with self.assertRaises(ValueError):
            si_theme.set_accent('invalid')
        self.assertEqual(si_theme.current_accent(), 'blue')

    def test_custom_colors_have_readable_text_in_both_modes(self):
        for color in ('#333333', '#000000', '#ffffff', '#eab308', '#aabbcc', '#67837e', '#00c788', '#3ce5ff'):
            for mode in ('light', 'dark'):
                with self.subTest(color=color, mode=mode):
                    si_theme.set_accent(color)
                    si_theme.set_theme(mode)
                    roles = si_theme.accent_colors()
                    self.assertEqual(roles['THEME'], color)
                    self.assertIn(roles['ON_THEME_TEXT'], ('#ffffff', '#000000'))
                    self.assertGreaterEqual(si_theme._contrast(roles['ON_THEME_TEXT'], roles['THEME']), 4.5)
                    self.assertGreaterEqual(si_theme._contrast(roles['THEME_DIM'], roles['ACCENT_SURFACE']), 4.5)
                    self.assertIn(roles['THEME'], si_theme.build_qss())


if __name__ == '__main__':
    unittest.main()

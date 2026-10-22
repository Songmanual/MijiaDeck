# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared styling for the home picker and compact popup menus."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from app.ui.si_theme import SiColors


def style_popup_menu(menu):
    menu.setWindowFlags(menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
    menu.setAttribute(Qt.WA_TranslucentBackground, True)
    font = QFont('Microsoft YaHei UI', 9)
    menu.setFont(font)
    menu.setMinimumWidth(160)
    for action in menu.actions():
        action.setFont(font)
    menu.setStyleSheet(
        f'QMenu {{ background: {SiColors.CARD}; color: {SiColors.TEXT_PRIMARY};'
        f' border: 1px solid {SiColors.LINE}; border-radius: 10px; padding: 6px; font-size: 9pt; }}'
        f'QMenu::item {{ padding: 8px 16px 8px 10px; border-radius: 6px;'
        f' color: {SiColors.TEXT_PRIMARY}; font-size: 9pt; }}'
        f'QMenu::item:selected {{ background: {SiColors.BTN_HOVER}; }}'
        'QMenu::icon { padding-left: 8px; }'
        f'QMenu::separator {{ height: 1px; background: {SiColors.LINE}; margin: 5px 10px; }}')

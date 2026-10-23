# SPDX-License-Identifier: GPL-3.0-or-later
"""One-time desktop overlay explaining the tray's click-only controls."""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from app import resource_path
from app.ui.si_theme import SiColors


class TrayIntroDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setWindowModality(Qt.ApplicationModal)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle('MijiaDeck 托盘使用说明')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addStretch()
        self.card = QFrame()
        self.card.setObjectName('trayIntroCard')
        self.card.setMaximumWidth(520)
        self.card.setStyleSheet(
            f'QFrame#trayIntroCard {{ background: {SiColors.WINDOW_BG}; '
            f'border: 1px solid {SiColors.LINE}; border-radius: 20px; }}')
        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(32, 30, 32, 28)
        layout.setSpacing(18)
        heading = QHBoxLayout()
        icon = QLabel()
        icon.setFixedSize(40, 40)
        icon.setPixmap(QPixmap(str(resource_path('app/ui/tray_icon.png'))).scaled(
            40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        heading.addWidget(icon)
        title = QLabel('从托盘快速操作 MijiaDeck')
        title.setWordWrap(True)
        title.setStyleSheet(f'color: {SiColors.TEXT_PRIMARY}; font-size: 14pt; font-weight: 600;')
        heading.addWidget(title, 1)
        layout.addLayout(heading)
        for text in ('单击或双击托盘图标：打开 / 收起快捷浮窗',
                     '右键托盘图标：打开菜单，选择「显示主窗口」',
                     '鼠标经过图标不会再弹窗。开启托盘常驻时，关闭主窗口仍可从托盘操作。',
                     '找不到图标？请点击任务栏右侧的「显示隐藏图标」按钮。'):
            label = QLabel(text)
            label.setWordWrap(True)
            label.setStyleSheet(f'color: {SiColors.TEXT_SECONDARY}; font-size: 10pt; background: transparent;')
            layout.addWidget(label)
        self.dismiss = QPushButton('知道了')
        self.dismiss.setMinimumHeight(40)
        self.dismiss.setDefault(True)
        self.dismiss.setCursor(Qt.PointingHandCursor)
        self.dismiss.setStyleSheet(f'background: {SiColors.THEME}; color: white; border: none; border-radius: 12px; font-size: 10pt;')
        self.dismiss.clicked.connect(self.accept)
        layout.addWidget(self.dismiss)
        outer.addWidget(self.card, 0, Qt.AlignHCenter)
        outer.addStretch()

    def showEvent(self, event):
        screen = self.parentWidget().screen() if self.parentWidget() else self.screen()
        self.setGeometry(screen.geometry())
        self.card.setFixedWidth(min(520, max(240, self.width() - 48)))
        super().showEvent(event)
        self.raise_()
        self.activateWindow()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(10, 18, 32, 125))
        painter.end()


def start_with_tray_intro(window, on_ready):
    """Finish guidance before starting jobs that might show the login dialog."""
    from app.core.settings_store import get_tray_intro_seen, set_tray_intro_seen
    if get_tray_intro_seen():
        on_ready()
        return None
    guide = TrayIntroDialog(window)
    window._tray_intro = guide

    def finished(_):
        set_tray_intro_seen(True)
        QTimer.singleShot(0, window, on_ready)

    guide.finished.connect(finished)
    guide.open()
    return guide

# SPDX-License-Identifier: GPL-3.0-or-later
"""Audio state follows external changes without overwriting local edits."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace
import unittest

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.ui.tray.audio_bar import _TrayAudioBar


class Jobs:
    def __init__(self):
        self.pending = []

    def submit(self, function, on_success=None, on_error=None):
        self.pending.append((function, on_success, on_error))

    def finish(self):
        function, success, error = self.pending.pop(0)
        success(function())


class AudioSyncTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.volume = 64
        self.jobs = Jobs()
        self.service = SimpleNamespace(
            device_detail=lambda did: SimpleNamespace(props=[]),
            read_props=lambda did, names: {"volume": self.volume, "mute-2": False},
            write_prop=lambda did, name, value: setattr(self, "volume", value),
        )
        self.bar = _TrayAudioBar(self.service, self.jobs)
        self.bar.set_speaker("speaker-a", "音箱 A")
        self.jobs.finish()

    def tearDown(self):
        self.bar.close()
        self.bar.deleteLater()
        self.app.processEvents()

    def test_visible_poll_reads_external_volume_and_stops_when_hidden(self):
        self.volume = 50
        QTest.qWait(2150)
        self.assertEqual(len(self.jobs.pending), 1)
        self.jobs.finish()
        self.assertEqual(self.bar._vol_label.text(), "50")
        self.assertEqual(self.bar._slider.value(), 50)
        self.bar.hide()
        self.assertFalse(self.bar._poll_timer.isActive())
        self.volume = 35
        self.bar.show()
        self.jobs.finish()
        self.assertEqual(self.bar._vol_label.text(), "35")

    def test_refresh_is_single_flight(self):
        self.bar.refresh_state()
        self.bar.refresh_state()
        self.assertEqual(len(self.jobs.pending), 1)

    def test_old_read_does_not_override_slider_drag_or_pending_write(self):
        self.bar.refresh_state()
        self.bar._slider.setSliderDown(True)
        self.bar._slider.setValue(75)
        self.jobs.finish()
        self.assertEqual(self.bar._vol_label.text(), "75")
        self.bar.refresh_state()
        self.assertEqual(len(self.jobs.pending), 0)
        self.bar._slider.setSliderDown(False)
        self.bar.refresh_state()
        self.assertEqual(len(self.jobs.pending), 1)  # write only
        self.jobs.finish()
        self.assertIsNone(self.bar._pending_volume)
        self.assertEqual(self.volume, 75)

    def test_text_command_schedules_readback_for_selected_speaker(self):
        self.bar.refresh_after_command("another-speaker")
        self.assertFalse(any(t.isActive() for t in self.bar._command_refresh_timers))
        self.volume = 50
        self.bar.refresh_after_command("speaker-a")
        self.assertTrue(all(t.isActive() for t in self.bar._command_refresh_timers))
        QTest.qWait(800)
        self.jobs.finish()
        self.assertEqual(self.bar._vol_label.text(), "50")

    def test_missing_cloud_value_preserves_last_known_volume(self):
        self.service.read_props = lambda did, names: {"volume": None, "mute-2": None}
        self.bar.refresh_state()
        self.jobs.finish()
        self.assertEqual(self.bar._vol_label.text(), "64")

    def test_stale_cloud_read_after_write_does_not_make_slider_jump_back(self):
        self.bar._slider.setValue(40)
        self.bar._on_slider_commit()
        self.jobs.finish()
        # 服务已接受 40，但云端短时间仍返回旧的 64。
        self.volume = 64
        self.bar.refresh_state()
        self.jobs.finish()
        self.assertEqual(self.bar._slider.value(), 40)
        self.assertEqual(self.bar._vol_label.text(), "40")
        self.volume = 40
        self.bar.refresh_state()
        self.jobs.finish()
        self.assertIsNone(self.bar._volume_confirmation)
        # 确认后，外部音量变化继续正常同步。
        self.volume = 25
        self.bar.refresh_state()
        self.jobs.finish()
        self.assertEqual(self.bar._slider.value(), 25)

    def test_unconfirmed_write_expires_and_new_voice_command_cancels_guard(self):
        self.bar._slider.setValue(40)
        self.bar._on_slider_commit()
        self.jobs.finish()
        self.bar._volume_confirmation = (40, 0)
        self.volume = 60
        self.bar.refresh_state()
        self.jobs.finish()
        self.assertEqual(self.bar._slider.value(), 60)
        self.assertIsNone(self.bar._volume_confirmation)
        self.bar._volume_confirmation = (40, float("inf"))
        self.bar.refresh_after_command("speaker-a")
        self.assertIsNone(self.bar._volume_confirmation)


if __name__ == "__main__":
    unittest.main()

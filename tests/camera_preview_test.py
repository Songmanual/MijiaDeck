# SPDX-License-Identifier: GPL-3.0-or-later
"""Camera authorization, cancellation and preview lifecycle without a real account."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

from Crypto.PublicKey import ECC
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from app import resource_path
from app.core.camera_access import CameraSource, build_camera_source
from app.core.camera_preview import CameraPreviewError, CameraSession
from app.ui.camera_preview import CameraPreviewPanel


class CameraAccessTest(unittest.TestCase):
    def test_signed_source_has_matching_ephemeral_keys_and_device(self):
        request = Mock(return_value={"vendor": {"vendor": 4, "vendor_params": {
            "p2p_id": "ABC-123-TEST", "init_string": "example-init"}}, "public_key": "ab" * 32,
                                     "sign": "temporary/sign+test"})
        source = build_camera_source("123", "chuangmi.camera.029a02", request)
        key = ECC.construct(curve="Curve25519", seed=bytes.fromhex(source.client_private))
        self.assertEqual(source.client_public, key.public_key().export_key(format="raw").hex())
        self.assertEqual(source.uid, "ABC-123-TEST")
        self.assertEqual(source.sign, "temporary/sign+test")
        self.assertNotIn(source.client_private, repr(source))
        self.assertEqual(request.call_args.args[0], "/v2/device/miss_get_vendor")
        self.assertEqual(request.call_args.args[1]["app_pubkey"], source.client_public)
        self.assertEqual(request.call_args.args[1]["did"], "123")

    def test_pipe_injection_in_cloud_fields_is_rejected(self):
        request = Mock(return_value={"vendor": {"vendor": 4, "vendor_params": {
            "p2p_id": "ABC-123-TEST\nINJECT", "init_string": "example-init"}},
            "public_key": "ab" * 32, "sign": "test"})
        with self.assertRaises(CameraPreviewError):
            build_camera_source("123", "test.camera.model", request)

    def test_incomplete_or_unsupported_authorization_is_rejected(self):
        for result in ({"vendor": {"vendor": 9}}, {"vendor": {"vendor": 4}},
                       {"vendor": {"vendor": 1}, "public_key": "ab" * 32, "sign": "test"}):
            with self.subTest(result=result), self.assertRaises(CameraPreviewError):
                build_camera_source("123", "test.camera.model", lambda *_: result)

    def test_backend_errors_do_not_expose_signed_source(self):
        session = CameraSession()
        with patch.object(session, "_start", side_effect=RuntimeError("secret-private-key")):
            with self.assertRaises(CameraPreviewError) as error:
                session.start("xiaomi://private?sign=secret-private-key")
        self.assertNotIn("secret-private-key", str(error.exception))
        self.assertTrue(session.cancelled)

    @unittest.skipUnless(resource_path("tools/camera_relay/runtime/bin/java.exe").exists(), "optional local relay")
    def test_real_helper_cancels_without_leaving_a_process_or_exposing_keys(self):
        session = CameraSession()
        started = threading.Event()
        errors = []
        # A decodes to an empty rendezvous list: no camera or external server is contacted.
        source = CameraSource("ABCDEF-123456-GHIJK", "A", "ab" * 32, "cd" * 32, "ef" * 32, "temporary-sign")

        def run():
            try:
                session.start(source, on_progress=lambda _: started.set())
            except CameraPreviewError as error:
                errors.append(error)

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        try:
            self.assertTrue(started.wait(5), "helper must reach its relay stage")
            process = session._process
            self.assertNotIn(source.client_private, str(process.args))
            self.assertNotIn(source.sign, str(process.args))
        finally:
            session.stop()
            worker.join(timeout=3)
        self.assertFalse(worker.is_alive())
        self.assertIsNotNone(process.poll())
        self.assertTrue(errors)


class Jobs:
    def __init__(self):
        self.pending = []

    def submit(self, function, on_success=None, on_error=None):
        self.pending.append((function, on_success, on_error))


class CameraPanelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.jobs = Jobs()
        self.device = SimpleNamespace(online=True, did="camera-test", name="测试摄像头", room_name="客厅", model="chuangmi.camera.029a02")
        self.service = SimpleNamespace(prepare_camera_source=Mock(return_value="signed-source"),
                                       power_state=Mock(return_value=False), set_power_state=Mock())
        self.backend = SimpleNamespace(cancelled=False, start=Mock(return_value="rtsp://127.0.0.1:1/test"))
        self.backend.command = Mock(return_value=True)
        self.backend.stop = Mock(side_effect=lambda: setattr(self.backend, "cancelled", True))
        self.factory = patch("app.ui.camera_preview.CameraSession", return_value=self.backend)
        self.factory.start()
        self.panel = CameraPreviewPanel(self.service, self.jobs, self.device)
        self.panel._player = Mock()
        self.panel.show()
        self.app.processEvents()

    def tearDown(self):
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()
        self.factory.stop()

    def test_close_while_queued_skips_cloud_and_ignores_late_result(self):
        self.panel.start()
        function, success, failure = self.jobs.pending.pop()
        self.panel.hide()
        with self.assertRaises(CameraPreviewError):
            function()
        self.service.prepare_camera_source.assert_not_called()
        success("rtsp://127.0.0.1:1/late")
        self.panel._player.play.assert_not_called()
        self.assertIsNone(self.panel._session)
        self.assertFalse(self.panel._timeout.isActive())

    def test_success_plays_and_stop_releases_connection(self):
        self.panel.start()
        function, success, failure = self.jobs.pending.pop()
        success(function())
        QTest.qWait(30)
        self.panel._player.play.assert_called_once()
        self.assertIs(self.panel._session, self.backend)
        self.panel.stop()
        self.backend.stop.assert_called()
        self.assertIsNone(self.panel._session)
        self.assertFalse(self.panel._canvas.mute.isEnabled())

    def test_offline_never_starts_job(self):
        self.device.online = False
        self.panel.start()
        self.assertEqual(self.jobs.pending, [])
        self.assertIn("离线", self.panel._status.text())

    def test_timeout_allows_retry(self):
        self.panel.start()
        self.panel._on_timeout()
        self.assertIsNone(self.panel._session)
        self.assertIn("预览超时", self.panel._status.text())
        self.assertFalse(self.panel._canvas.mute.isEnabled())

    def test_connection_stage_is_visible_and_old_progress_is_ignored(self):
        self.panel.start()
        generation = self.panel._generation
        self.panel._on_progress(generation, "PHASE AUTH")
        self.assertIn("验证视频会话", self.panel._status.text())
        self.panel._on_progress(generation, "ERROR RELAY")
        self.assertIn("公网中继", self.panel._status.text())
        self.panel._on_progress(generation, "PHASE MEDIA")
        self.assertIn("公网中继", self.panel._status.text())

    def finish_job(self):
        function, success, failure = self.jobs.pending.pop(0)
        success(function())

    def test_sleeping_camera_never_starts_video_until_woken(self):
        self.panel.load()
        self.finish_job()
        self.assertFalse(self.panel._power.state())
        self.assertIn('休眠', self.panel._status.text())
        self.service.prepare_camera_source.assert_not_called()
        self.panel._toggle_power()
        self.assertTrue(self.panel._power_busy)
        self.finish_job()
        self.service.set_power_state.assert_called_once_with('camera-test', True)
        self.assertTrue(self.panel._power.state())
        self.assertEqual(len(self.jobs.pending), 1)  # fresh authorization queued after wake

    def test_close_only_stops_viewing_not_physical_camera(self):
        self.panel._apply_power(True)
        self.panel.hide()
        self.backend.stop.assert_called()
        self.service.set_power_state.assert_not_called()

    def test_quality_mute_and_drag_use_existing_session_commands(self):
        self.panel._session = self.backend
        self.panel._playing = True
        self.panel._canvas.drag_enabled = True
        self.panel._select_quality(2)
        self.backend.command.assert_called_with('QUALITY', 2)
        self.panel._toggle_mute()
        self.assertFalse(self.panel._muted)
        self.backend.command.assert_called_with('AUDIO', 1)
        self.panel._toggle_mute()
        self.backend.command.assert_called_with('AUDIO', 0)
        self.panel._drag(2)
        self.backend.command.assert_called_with('PTZ', 2)
        count = self.backend.command.call_count
        self.panel._drag(2)
        self.assertEqual(self.backend.command.call_count, count)

    def test_fullscreen_reuses_canvas_and_escape_keeps_stream(self):
        from PySide6.QtCore import Qt
        self.panel._session = self.backend
        generation = self.panel._generation
        self.panel._toggle_fullscreen()
        self.app.processEvents()
        window = self.panel._fullscreen
        self.assertIs(self.panel._canvas.parentWidget(), window)
        QTest.keyClick(window, Qt.Key_Escape)
        self.app.processEvents()
        self.assertIsNone(self.panel._fullscreen)
        self.assertIs(self.panel._canvas.parentWidget(), self.panel)
        self.assertEqual(self.panel._generation, generation)
        self.backend.stop.assert_not_called()

    def test_drag_waits_for_settling_and_a_new_frame_without_queuing(self):
        from PySide6.QtGui import QImage
        from PySide6.QtMultimedia import QVideoFrame
        self.panel._session = self.backend
        frame = QVideoFrame(QImage(640, 360, QImage.Format_RGB32))
        self.panel._on_frame(frame)
        with patch('app.ui.camera_preview.time.monotonic', return_value=100):
            self.panel._drag(1)
        self.assertTrue(self.panel._canvas.drag_busy)
        self.panel._drag(2)
        with patch('app.ui.camera_preview.time.monotonic', return_value=101):
            self.panel._on_frame(frame)
        self.assertTrue(self.panel._canvas.drag_busy)
        self.backend.command.assert_called_once_with('PTZ', 1)
        with patch('app.ui.camera_preview.time.monotonic', return_value=102):
            self.panel._on_frame(frame)
            self.assertFalse(self.panel._canvas.drag_busy)
            self.backend.command.assert_called_once_with('PTZ', 1)
            self.panel._drag(3)
        self.backend.command.assert_called_with('PTZ', 3)
        self.panel.stop()
        self.assertFalse(self.panel._canvas.drag_busy)

    def test_failed_drag_write_does_not_lock_input(self):
        self.panel._session = self.backend
        self.panel._playing = True
        self.panel._canvas.drag_enabled = True
        self.backend.command.return_value = False
        self.panel._drag(1)
        self.assertFalse(self.panel._canvas.drag_busy)

    def test_quality_switch_reopens_local_viewer_without_new_remote_session(self):
        self.panel._session = self.backend
        self.panel._url = 'http://127.0.0.1:1/camera-test.ts'
        generation = self.panel._generation
        self.panel._select_quality(2)
        self.assertTrue(self.panel._switching_quality)
        QTest.qWait(1000)
        self.assertFalse(self.panel._switching_quality)
        self.panel._player.play.assert_called_once()
        self.assertEqual(self.panel._generation, generation)
        self.backend.start.assert_not_called()

    def test_muted_and_stale_audio_cannot_open_audio_output(self):
        with patch('app.ui.camera_preview.QAudioSink') as audio:
            self.panel._playing = True
            self.panel._on_pcm(self.panel._generation, 8000, bytes(160))
            self.panel._muted = False
            self.panel._on_pcm(self.panel._generation - 1, 8000, bytes(160))
            audio.assert_not_called()

    def test_frame_updates_actual_quality_and_renders_without_layout_overflow(self):
        from PySide6.QtGui import QImage, QColor
        from PySide6.QtMultimedia import QVideoFrame
        self.panel._session = self.backend
        self.panel._quality = 1
        image = QImage(640, 360, QImage.Format_RGB32)
        image.fill(QColor('blue'))
        self.panel._on_frame(QVideoFrame(image))
        self.assertTrue(self.panel._playing)
        self.assertEqual(self.panel._canvas.quality.text(), '360P')
        self.assertTrue(self.panel._canvas.mute.isEnabled())
        self.assertFalse(self.panel._canvas._image.isNull())
        self.assertTrue(self.panel.rect().contains(self.panel._canvas.geometry()))


if __name__ == "__main__":
    unittest.main()

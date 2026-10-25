import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import threading
import unittest
from unittest.mock import patch
import requests
from PySide6.QtWidgets import QApplication
from app.core.jobs import JobExecutor
from app.core.http_timeout import DEFAULT_TIMEOUT, TimeoutRequests, TimeoutSession


class RefreshQueueTest(unittest.TestCase):
    def test_refresh_runs_before_queued_decoration_without_parallel_session_use(self):
        app = QApplication.instance() or QApplication([])
        jobs = JobExecutor()
        entered, release, finished = (threading.Event() for _ in range(3))
        order = []
        def running():
            entered.set()
            release.wait(3)
            order.append('running')
        try:
            jobs.submit(running, priority=20)
            self.assertTrue(entered.wait(2))
            jobs.submit(lambda: order.append('icon1'), priority=20)
            jobs.submit(lambda: (order.append('icon2'), finished.set()), priority=20)
            jobs.submit(lambda: order.append('refresh'), priority=0)
            release.set()
            self.assertTrue(finished.wait(2))
            self.assertEqual(order, ['running', 'refresh', 'icon1', 'icon2'])
        finally:
            release.set()
            jobs.shutdown()

    def test_sdk_requests_are_bounded_and_explicit_login_long_poll_is_preserved(self):
        proxy = TimeoutRequests()
        with patch.object(requests, 'get') as get:
            proxy.get('https://example.invalid')
            self.assertEqual(get.call_args.kwargs['timeout'], DEFAULT_TIMEOUT)
            proxy.get('https://example.invalid', timeout=120)
            self.assertEqual(get.call_args.kwargs['timeout'], 120)
        with patch.object(requests.Session, 'request') as request:
            proxy.Session().post('https://example.invalid')
            self.assertEqual(request.call_args.kwargs['timeout'], DEFAULT_TIMEOUT)
        self.assertIsNot(requests.Session, TimeoutSession)

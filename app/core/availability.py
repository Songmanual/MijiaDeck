# SPDX-License-Identifier: GPL-3.0-or-later
"""Network availability and shared UI wording; probes never use account data."""
from PySide6.QtCore import QObject, Signal, QTimer, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkInformation, QNetworkRequest

MESSAGES = {
    'signed_out': '请先登录小米账号，登录后即可控制设备',
    'offline': '网络异常，请连接网络后重试。',
    'loading': '正在同步设备，请稍候…',
    'unavailable': '网络异常，请连接网络后重试。',
}


def speaker_hint(devices) -> str:
    from .models import is_speaker
    speakers = [device for device in devices if is_speaker(device)]
    if not speakers:
        return '当前你还没有添加任何智能音箱'
    return '' if any(device.online for device in speakers) else '智能音箱当前离线'


class NetworkMonitor(QObject):
    changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        QNetworkInformation.loadDefaultBackend()
        self._backend = QNetworkInformation.instance()
        self.online = self._is_online(self._backend.reachability()) if self._backend else True
        self._manager = QNetworkAccessManager(self)
        self._reply = None
        self._timer = QTimer(self)
        self._timer.setInterval(5000)
        self._timer.timeout.connect(self.check_now)
        self._timer.start()
        if self._backend:
            self._backend.reachabilityChanged.connect(self._changed)
        QTimer.singleShot(0, self, self.check_now)

    @staticmethod
    def _is_online(reachability):
        # Unknown/backend unavailable is not proof of disconnection. Actual
        # request failures still surface normally; never infer logout from them.
        return reachability in (QNetworkInformation.Reachability.Unknown,
                                QNetworkInformation.Reachability.Online)

    def _changed(self, reachability):
        # A VPN/virtual adapter can leave Windows reporting Online after Wi-Fi
        # is disconnected. Only a fresh HTTPS result can restore availability.
        if not self._is_online(reachability):
            self._set_online(False)
        self.check_now()

    def _set_online(self, online):
        if online != self.online:
            self.online = online
            self.changed.emit(online)

    def check_now(self):
        if self._reply is not None:
            return
        # HEAD has no body, credentials or device identifiers. An actual HTTP
        # response (even 401/404) proves transport works; never reuse disk cache.
        request = QNetworkRequest(QUrl('https://api.io.mi.com/'))
        request.setTransferTimeout(2500)
        request.setAttribute(QNetworkRequest.CacheLoadControlAttribute,
                             QNetworkRequest.AlwaysNetwork)
        self._reply = reply = self._manager.head(request)
        deadline = QTimer(reply)
        deadline.setSingleShot(True)
        deadline.timeout.connect(reply.abort)
        deadline.start(2500)
        reply.finished.connect(lambda: self._probe_finished(reply))

    def _probe_finished(self, reply):
        if reply is not self._reply:
            return
        self._reply = None
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        self._set_online(isinstance(status, int) and 200 <= status < 500)
        reply.deleteLater()

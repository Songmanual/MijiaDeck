# SPDX-License-Identifier: GPL-3.0-or-later
"""Bound SDK HTTP waits without altering requests globally or TLS policy."""
import requests

DEFAULT_TIMEOUT = (3.05, 8)


class TimeoutSession(requests.Session):
    def request(self, method, url, **kwargs):
        if kwargs.get('timeout') is None:
            kwargs['timeout'] = DEFAULT_TIMEOUT
        return super().request(method, url, **kwargs)


class TimeoutRequests:
    """Only assigned to the two SDK modules' local requests references.

    Explicit waits, including QR login's 120-second long poll, are preserved.
    Other libraries continue using the original requests module unchanged.
    """
    Session = TimeoutSession

    def __getattr__(self, name):
        original = getattr(requests, name)
        if name not in ('get', 'post', 'request'):
            return original
        def bounded(*args, **kwargs):
            if kwargs.get('timeout') is None:
                kwargs['timeout'] = DEFAULT_TIMEOUT
            return original(*args, **kwargs)
        return bounded

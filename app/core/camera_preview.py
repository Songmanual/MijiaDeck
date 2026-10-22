# SPDX-License-Identifier: GPL-3.0-or-later
"""Owned CS2 remote relay. Only an unguessable loopback stream reaches the player."""
import os
import base64
import queue
import socket
import subprocess
import threading
import time
import uuid
from app import resource_path


class CameraPreviewError(Exception):
    pass


ERRORS = {
    "CONFIG": "远程播放组件初始化失败，请重新安装组件。",
    "RELAY": "未能连接摄像头的公网中继，请确认摄像头在线、当前网络允许 UDP 通信后重试。",
    "AUTH": "已连接中继，但摄像头视频会话授权未通过；请先关闭米家中的观看页面再重试。",
    "MEDIA": "中继和视频授权已完成，但未收到画面；请确认摄像头镜头已开启后重试。",
    "STREAM": "摄像头视频连接已中断，请重试。",
}


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class CameraSession:
    def __init__(self):
        self._cancelled = threading.Event()
        self._lock = threading.Lock()
        self._process = None
        self._ready = False

    @property
    def cancelled(self):
        return self._cancelled.is_set()

    def start(self, source, on_progress=lambda _: None, *, quality=1, on_audio=None) -> str:
        """Run on a dedicated worker, so relay negotiation cannot block cloud controls."""
        try:
            return self._start(source, on_progress, quality, on_audio)
        except CameraPreviewError:
            self.stop()
            raise
        except Exception:
            self.stop()
            raise CameraPreviewError("远程视频连接启动失败，请稍后重试。") from None

    def _start(self, source, on_progress, quality, on_audio):
        java = resource_path("tools/camera_relay/runtime/bin/java.exe")
        jar = resource_path("tools/camera_relay/camera-relay.jar")
        if not java.exists() or not jar.exists():
            raise CameraPreviewError("缺少远程摄像头组件，请安装后重试。")
        port, path = _free_port(), "/camera-" + uuid.uuid4().hex + ".ts"
        fields = [str(port), path, source.uid, source.init_string, source.client_public,
                  source.client_private, source.device_public, source.sign, str(quality)]
        if quality not in (0, 1, 2):
            raise CameraPreviewError("不支持的画质档位。")
        if any(not isinstance(v, str) or not v or "\n" in v or "\r" in v for v in fields):
            raise CameraPreviewError("远程视频授权格式无效，请重新获取。")
        with self._lock:
            if self.cancelled:
                raise CameraPreviewError("预览已取消。")
            process = subprocess.Popen(
                [str(java), "-Xmx96m", "-XX:ErrorFile=NUL", "-cp", str(jar), "CameraRelay"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8", bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            self._process = process
        messages = queue.Queue()

        def read_status():
            error_seen = False
            try:
                for raw in process.stdout:
                    message = raw.strip()
                    if message.startswith("AUDIO 8000 ") and on_audio and not self.cancelled:
                        try:
                            pcm = base64.b64decode(message[11:], validate=True)
                            if len(pcm) <= 16384:
                                on_audio(8000, pcm)
                        except ValueError:
                            pass
                        continue
                    if message in {"NOTICE AUDIO_UNSUPPORTED", "NOTICE CONTROL_FAILED"}:
                        if not self.cancelled:
                            on_progress(message)
                        continue
                    if message == "READY" or message in {"PHASE RELAY", "PHASE AUTH", "PHASE MEDIA"} or (
                            message.startswith("ERROR ") and message[6:] in ERRORS):
                        messages.put(message)
                        if message.startswith("ERROR "):
                            error_seen = True
                            if self._ready and not self.cancelled:
                                on_progress(message)
            finally:
                process.stdout.close()
                messages.put("EXIT")
                if self._ready and not self.cancelled and not error_seen:
                    on_progress("ERROR STREAM")

        threading.Thread(target=read_status, daemon=True, name="camera-relay-status").start()
        # Ephemeral keys go through a pipe, never process arguments or a config file.
        process.stdin.write("\n".join(fields) + "\n")
        process.stdin.flush()
        deadline = time.monotonic() + 90
        while not self.cancelled and time.monotonic() < deadline:
            try:
                message = messages.get(timeout=.1)
            except queue.Empty:
                continue
            if message == "READY":
                if self.cancelled or process.poll() is not None:
                    break
                self._ready = True
                return f"http://127.0.0.1:{port}{path}"
            if message.startswith("ERROR "):
                raise CameraPreviewError(ERRORS[message[6:]])
            if message == "EXIT":
                raise CameraPreviewError("远程播放组件意外退出，请重试。")
            on_progress(message)
        raise CameraPreviewError("预览已取消。" if self.cancelled else "远程视频连接超时，请重试。")

    def command(self, name, value):
        allowed = {"QUALITY": (0, 1, 2), "AUDIO": (0, 1), "PTZ": (1, 2, 3, 4)}
        if name not in allowed or value not in allowed[name]:
            return False
        with self._lock:
            process = self._process
            if self.cancelled or process is None or process.poll() is not None:
                return False
            try:
                process.stdin.write(f"{name} {value}\n")
                process.stdin.flush()
                return True
            except (OSError, ValueError):
                return False

    def stop(self):
        self._cancelled.set()
        with self._lock:
            process, self._process = self._process, None
        if process is not None:
            if process.poll() is None:
                try:
                    process.stdin.write("STOP\n")
                    process.stdin.flush()
                    process.wait(timeout=.35)
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=.35)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=1)
            if process.stdin:
                try:
                    process.stdin.close()
                except OSError:
                    pass

"""User-run real-camera check. Never records pictures, video, or login credentials."""
import json
import logging
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer, QUrl, qInstallMessageHandler
from PySide6.QtMultimedia import QMediaPlayer, QVideoSink
from app.core.camera_preview import CameraPreviewError, CameraSession
from app.core.service import MijiaService


def decode_frames(url):
    player, sink, loop = QMediaPlayer(), QVideoSink(), QEventLoop()
    player.setVideoOutput(sink)
    result = {"frames": 0}

    def received(frame):
        if frame.isValid():
            result.update(frames=result["frames"] + 1, width=frame.width(), height=frame.height())
            if result["frames"] >= 3:
                loop.quit()

    sink.videoFrameChanged.connect(received)
    player.errorOccurred.connect(lambda *_: loop.quit())
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    timeout.start(25000)
    player.setSource(QUrl(url))
    player.play()
    loop.exec()
    player.stop()
    player.setSource(QUrl())
    timeout.stop()
    return result


def main(output):
    logging.disable(logging.CRITICAL)
    qInstallMessageHandler(lambda *_: None)
    app = QCoreApplication([])
    results = []
    try:
        service = MijiaService()
        devices = [d for d in service.list_devices() if ".camera." in d.model][:2]
    except Exception:
        print("无法读取现有米家登录或设备列表，请先在主程序确认已登录。", flush=True)
        return 1
    if not devices:
        print("当前账号没有摄像头设备。", flush=True)
        return 1
    for device in devices:
        print(f"\n正在测试：{device.name}（{device.model}）", flush=True)
        result = {"name": device.name, "model": device.model, "online": device.online}
        session = CameraSession()
        started = time.monotonic()

        def progress(message):
            stage = {"PHASE RELAY": "连接公网中继", "PHASE AUTH": "验证视频会话",
                     "PHASE MEDIA": "等待摄像头画面", "ERROR STREAM": "连接中断"}.get(message)
            if stage:
                result["stage"] = stage
                print(stage, flush=True)

        try:
            source = service.prepare_camera_source(device)
            print("米家视频授权已取得", flush=True)
            url = session.start(source, on_progress=progress)
            result.update(decode_frames(url))
            result["success"] = result["frames"] >= 3
            print("已解码画面" if result["success"] else "视频流已连接，但播放器未取得有效画面", flush=True)
            if result["success"]:
                print(f"画面尺寸：{result['width']} × {result['height']}", flush=True)
        except CameraPreviewError as error:
            result.update(success=False, error=str(error))
            print(str(error), flush=True)
        except Exception:
            result.update(success=False, error="测试组件意外失败")
            print("测试组件意外失败", flush=True)
        finally:
            session.stop()
            result["seconds"] = round(time.monotonic() - started, 1)
            results.append(result)
    output = Path(output)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n测试完成，结果已保存：{output}", flush=True)
    return 0 if all(r.get("success") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "camera-remote-test.json"))

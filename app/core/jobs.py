# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""串行任务执行器：所有米家网络调用都排进这一个后台线程。

不采用并发的原因：上游库的 requests.Session 没有线程安全承诺，且每次
操作自带防限流延时，并发只会带来竞态而不会更快。单线程队列天然节流；
结果经 Qt 信号送回主线程，界面永不因网络等待而卡顿。
"""

import logging
import queue
from collections.abc import Callable
from typing import Any, NamedTuple

from PySide6.QtCore import QObject, QThread, Signal

logger = logging.getLogger(__name__)


class _Task(NamedTuple):
    fn: Callable[[], Any]
    on_success: Callable[[Any], None] | None
    on_error: Callable[[Exception], None] | None
    generation: int


class JobExecutor(QObject):
    """提交同步函数到后台线程执行，回调自动回到主线程。

    用法:
        jobs.submit(service.list_devices,
                    on_success=self._fill_list,
                    on_error=self._show_error)
    """

    # 回调先发信号、由主线程槽执行，保证 UI 操作永远在主线程
    _succeeded = Signal(object, object)  # (on_success, 结果)
    _failed = Signal(object, Exception)  # (on_error, 异常)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: queue.Queue[_Task | None] = queue.Queue()
        self._generation = 0
        self._thread = QThread(self)
        self._thread.run = self._work_loop  # 循环体很短，不值得单独建 worker 类
        self._succeeded.connect(self._run_success_cb)
        self._failed.connect(self._run_error_cb)
        self._thread.start()

    def submit(
        self,
        fn: Callable[[], Any],
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        self._queue.put(_Task(fn, on_success, on_error, self._generation))

    def cancel_pending(self) -> None:
        """Discard queued work and callbacks belonging to the previous account.

        An in-flight request finishes normally; a subsequent logout runs after
        it in this same serial queue, without terminating a network thread.
        """
        self._generation += 1
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def shutdown(self) -> None:
        # 毒丸对象让循环自然退出，避免线程销毁时还在跑任务
        self._queue.put(None)
        if not self._thread.wait(3000):
            # 卡在长轮询（扫码等待最长两分钟）等网络调用时等不到自然
            # 退出；带着运行中的线程销毁 QThread 会让进程在解释器关闭
            # 阶段崩溃，强制终止是两害相权的选择
            logger.warning("后台任务线程 3 秒内未退出，强制终止")
            self._thread.terminate()
            self._thread.wait(500)

    def _work_loop(self) -> None:
        while True:
            task = self._queue.get()
            if task is None:
                return
            try:
                result = task.fn()
            except Exception as exc:  # 后台线程的异常必须全部拦下转成回调
                # 单行警告即可：设备离线、spec 缺失这类失败是常态，
                # 全栈日志只会淹没真正需要关注的问题
                logger.warning("后台任务失败: %s", exc)
                self._failed.emit((task.generation, task.on_error), exc)
            else:
                self._succeeded.emit((task.generation, task.on_success), result)

    def _run_success_cb(self, callback: object, result: object) -> None:
        generation, fn = callback
        if generation == self._generation and fn is not None:
            fn(result)

    def _run_error_cb(self, callback: object, error: Exception) -> None:
        generation, fn = callback
        if generation == self._generation and fn is not None:
            fn(error)

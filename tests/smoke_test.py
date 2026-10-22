# SPDX-License-Identifier: GPL-3.0-or-later
"""升级 mijiaAPI 后的兼容性自检。

用法: .venv\\Scripts\\python.exe -m tests.smoke_test

静态检查适配层依赖的全部上游接口是否仍然存在且可调用，
全部通过说明本次升级大概率无需改动代码；任何一项失败都需要
先修复 app/core/service.py 再使用 GUI。
"""

import inspect


def main() -> int:
    failures: list[str] = []

    try:
        import mijiaAPI as mijia_api_module
        from mijiaAPI import mijiaAPI as MijiaApiClass
    except ImportError as exc:
        print(f"[FAIL] 无法导入 mijiaAPI: {exc}")
        return 1

    def check(owner: object, name: str, label: str) -> None:
        if not hasattr(owner, name):
            failures.append(f"{label}: 缺少 {name}")
            return
        attr = getattr(owner, name)
        if inspect.isfunction(attr) or inspect.ismethod(attr):
            try:
                inspect.signature(attr)
            except (TypeError, ValueError):
                failures.append(f"{label}: {name} 签名不可解析")

    # 登录与列表接口（含扫码登录的两步组合）
    check(MijiaApiClass, "available", "mijiaAPI")
    for name in (
        "_get_qr_login_data", "_complete_qr_login",
        "get_homes_list", "get_devices_list", "get_shared_devices_list",
        "get_scenes_list", "run_scene",
    ):
        check(MijiaApiClass, name, "mijiaAPI")

    # 上游版本号：service.api_version 读取它供关于页展示，缺失会让版本行少一段
    check(mijia_api_module, "__version__", "mijiaAPI")

    # 设备控制接口与元数据字段
    from mijiaAPI import mijiaDevice
    from mijiaAPI.devices import DevAction, DevProp  # 未在顶层导出，走子模块路径
    for name in ("get", "set", "run_action"):
        check(mijiaDevice, name, "mijiaDevice")
    # prop_list / action_list 是构造时赋值的实例属性，只能在 __init__ 源码中确认
    device_init_source = inspect.getsource(mijiaDevice.__init__)
    for name in ("prop_list", "action_list", "sleep_time"):
        if name not in device_init_source:
            failures.append(f"mijiaDevice.__init__: 未初始化 {name}")
    # 共享设备路径在 service 层手工组装实例，依赖这些可写实例属性
    for attr in ("api", "did", "model", "name", "prop_list", "action_list"):
        if f"self.{attr}" not in device_init_source:
            failures.append(f"mijiaDevice.__init__: 缺少实例属性 self.{attr}")
    init_source = inspect.getsource(DevProp.__init__)
    for key in ('"name"', '"description"', '"type"', '"rw"', '"range"', '"value-list"'):
        if key not in init_source:
            failures.append(f"DevProp.__init__: 未读取字段 {key}")
    action_source = inspect.getsource(DevAction.__init__)
    for key in ('"name"', '"description"', '"method"'):
        if key not in action_source:
            failures.append(f"DevAction.__init__: 未读取字段 {key}")

    # 上游行为假设：mijiaDevice(did=) 只查自有设备列表，共享设备由
    # service 层自行组装（get_devices_list 结果不含 shared）
    for name in ("get_devices_list", "get_shared_devices_list"):
        if name not in inspect.getsource(MijiaApiClass):
            failures.append(f"mijiaAPI: 缺少独立接口 {name}")

    # 异常体系（包顶层导出）
    for exc_name in ("LoginError", "DeviceGetError", "DeviceSetError",
                     "DeviceActionError", "DeviceNotFoundError"):
        if not hasattr(mijia_api_module, exc_name):
            failures.append(f"异常类缺失: {exc_name}")

    # 适配层自身可加载（导入即验证）
    try:
        from app.core.service import MijiaService, ServiceError
        assert MijiaService is not None and ServiceError is not None
    except Exception as exc:
        failures.append(f"app.core.service 加载失败: {exc}")

    if failures:
        print("发现以下兼容性问题:")
        for item in failures:
            print(f"  [FAIL] {item}")
        return 1
    print("[OK] 适配层依赖的上游接口全部在位")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

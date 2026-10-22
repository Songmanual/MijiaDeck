# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""MIoT 属性/动作名 → 中文兜底表。

上游 5.x 起中文描述取自 miot-spec.org 的 comment 字段，部分品类
（音箱、温湿度计等）官方数据缺该字段，界面会退化成纯英文。这里按
属性/动作短名兜底补全：表的属性部分来自 4.x 时代 home.miot-spec.com
已验证的中文翻译（当时按型号抓取时逐条提取），动作部分是标准 SI
动作的直译。匹配与设备型号无关，同名标准属性在所有设备上共用翻译。

匹配两级：先精确匹配（如 on-2 是"按键"，与 on"开关"语义不同，
必须分开），未命中再去掉尾部数字后缀重试（如 on-10 → on）。
"""

import re

# 属性短名 -> 中文；键含数字后缀的是历史去重名，语义可能与基名不同
PROPERTY_ZH: dict[str, str] = {
    "volume": "音量",
    "mute-2": "静音",
    "mute-4": "静音",
    "playing-state": "播放状态",
    "text-content": "文本内容",
    "silent-execution": "指令静默执行",
    "sleep-mode": "睡眠模式",
    "audio-id": "音频ID",
    "download-speed": "下载速度",
    "upload-speed": "上传速度",
    "connected-device-number": "连接设备数",
    "network-connection-type": "上网方式",
    "ip-address": "IP地址",
    "status": "工作状态",
    "fault": "故障",
    "ppp-username": "拨号上网用户名",
    "ppp-encrypted-password": "拨号上网加密密码",
    "static-ip-address": "静态IP上网IP地址",
    "subnet-mask": "子网掩码",
    "gateway-ip-address": "网关IP地址",
    "dns-ip-address": "DNS服务地址",
    "dns-auto-mode": "DNS自动配置",
    "access-mode": "接入方式",
    "rssi": "信号强度",
    "wifi-band-combine": "WiFi双频合一",
    "online-time": "在线时长",
    "wifi-ssid-3": "WiFi网络名称",
    "wifi-encrypted-password-3": "WiFi网络加密密码",
    "on-3": "开关",
    "wifi-ssid-hidden": "隐藏WiFi",
    "encrypted-strength-3": "加密强度",
    "signal-strength-3": "发射信号强度",
    "wifi-channel-3": "WiFi网络信道",
    "wifi-bandwidth-3": "WiFi信道带宽",
    "on-4": "开关",
    "wifi-ssid-4": "WiFi网络名称",
    "wifi-encrypted-password-4": "WiFi网络加密密码",
    "encrypted-strength-4": "加密强度",
    "signal-strength-4": "发射信号强度",
    "wifi-channel-4": "WiFi网络信道",
    "wifi-bandwidth-4": "WiFi信道带宽",
    "speed-control": "限速控制",
    "max-upload-speed": "最大上传速度",
    "max-download-speed": "最大下载速度",
    "on-5": "开关",
    "mode": "模式",
    "brightness": "亮度",
    "color": "颜色",
    "color-temperature": "色温",
    "flow": "流光功能",
    "saturability": "饱和度",
    "on": "开关",
    "default-power-on-state": "默认上电状态",
    "save-state": "恢复断电前灯光",
    "delay-time": "延时时间",
    "delay-off-countdown": "延时关灯倒计时",
    "delay-off-enable": "延时关灯功能开关",
    "kid-mode": "儿童模式控制开关",
    "double-click-enable": "自定义双击功能开关",
    "double-click": "定义双击触发的功能",
    "scene-mode": "切换灯上的模式",
    "pomodoro-enable": "专注模式开关",
    "work-minutes": "专注模式的工作时间",
    "break-minutes": "专注模式休息时间",
    "work-countdown-sec": "工作结束倒计时",
    "break-countdown-sec": "休息时间倒计时",
    "mode-one-bright": "模式1的亮度",
    "mode-one-ct": "模式1的色温",
    "mode-two-bright": "模式2亮度",
    "mode-two-ct": "模式2的色温",
    "mode-three-bright": "模式3的亮度",
    "mode-three-ct": "模式3的色温",
    "mode-four-bright": "模式4的亮度",
    "mode-four-ct": "模式4的色温",
    "double-click-mode": "双击启动的模式",
    "eco": "背光开关",
    "off-delay": "点动功能",
    "toggle": "切换",
    "temperature": "温度",
    "relative-humidity": "湿度",
    "battery-level": "电池电量",
    "on-2": "按键",
    "on-10": "开关",
    "version": "设备版本号",
    "mode-2": "模式",
    "anti-flicker": "防闪烁模式",
    "wiring-method": "接线方式",
    "mode-3": "模式",
    "mode-4": "模式",
    "mode-5": "模式",
    "power-consumption": "功耗参数",
    "electric-power": "电功率",
    "power-consumption-accumulation-way": "耗电量使用累加形式",
    "on-7": "开关",
}

# 动作短名 -> 中文
ACTION_ZH: dict[str, str] = {
    "play": "播放",
    "pause": "暂停",
    "next": "下一首",
    "previous": "上一首",
    "play-text": "朗读文本",
    "play-music": "播放音乐",
    "play-radio": "播放电台",
    "execute-text-directive": "执行文本指令",
    "stop-alarm": "停止闹钟",
    "wake-up": "唤醒",
    "toggle": "切换",
    "turn-on": "开启",
    "turn-off": "关闭",
    "reboot": "重启",
    "set-default": "恢复默认",
    "apply-scene": "应用场景",
    "bright-circle": "亮度循环",
    "bright-increase": "调高亮度",
    "bright-decrease": "调低亮度",
    "bright-on-circle": "亮度循环开关",
    "ct-circle": "色温循环",
    "ct-increase": "调高色温",
    "ct-decrease": "调低色温",
    "ct-on-circle": "色温循环开关",
    "delay-off": "延时关灯",
    "fan-speed-up": "风速调高",
    "fan-speed-down": "风速调低",
    "temperature-up": "温度调高",
    "temperature-down": "温度调低",
}

_NUM_SUFFIX = re.compile(r"-\d+$")


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def lookup_zh(name: str, table: dict[str, str]) -> str | None:
    """按名查中文：先精确匹配，未中再去掉尾部数字后缀重试。"""
    if name in table:
        return table[name]
    stripped = _NUM_SUFFIX.sub("", name)
    return table.get(stripped) if stripped != name else None


def backfill_description(name: str, desc: str, table: dict[str, str]) -> str:
    """补一条描述的中文；已有中文、空描述或表未覆盖时原样返回。

    描述统一为「英文 / 中文」格式，与上游数据格式保持一致，界面层
    无需感知来源。device_detail 的对象路径与 spec dict 路径共用它。
    """
    desc = desc or ""
    if _has_cjk(desc):
        return desc
    zh = lookup_zh(name, table)
    if not zh:
        return desc
    return f"{desc} / {zh}" if desc else zh


def prop_desc_zh(name: str, desc: str) -> str:
    return backfill_description(name, desc, PROPERTY_ZH)


def action_desc_zh(name: str, desc: str) -> str:
    return backfill_description(name, desc, ACTION_ZH)


def apply_fallback(info: dict) -> None:
    """就地补齐 spec dict 中缺中文的描述（_specs_for 内存缓存路径）。"""
    for item in info.get("properties", []):
        item["description"] = prop_desc_zh(
            str(item.get("name") or ""), str(item.get("description") or ""))
    for item in info.get("actions", []):
        item["description"] = action_desc_zh(
            str(item.get("name") or ""), str(item.get("description") or ""))

# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""托盘快捷项的本地持久化。

与 workbench.json 同目录，单独文件 tray.json，默认空列表，由用户
在管理对话框中自主添加。devices/scenes 记录成员集合（设备存 did；
场景存必要快照 scene_id/name/home_id/home_name，执行只认 id 与
home_id，快照名保证离线/未刷新时快捷窗口仍可显示）；order 记录
两类项目混排后的统一展示顺序，快捷窗口按它渲染。
"""

from app.core import _json_store

_VERSION = 1
_FILENAME = "tray.json"
_SCENE_KEYS = ("scene_id", "name", "home_id", "home_name")


def _empty() -> dict:
    return {"version": _VERSION, "devices": [], "scenes": [], "order": []}


def _read_raw() -> dict:
    raw = _json_store.read_json(_json_store.data_file(_FILENAME), _empty())
    if raw.get("version") != _VERSION:
        return _empty()
    devices = raw.get("devices")
    if not isinstance(devices, list) or not all(isinstance(d, str) for d in devices):
        return _empty()
    return raw


def _write_raw(raw: dict) -> None:
    _json_store.write_json(_json_store.data_file(_FILENAME), raw)


def load() -> list[str]:
    """托盘设备 did 列表（与 order 中设备的相对顺序一致）。"""
    return list(_read_raw().get("devices", []))


def load_scenes() -> list[dict]:
    """托盘的场景快照列表（与 order 中场景的相对顺序一致）；非法条目直接丢弃。"""
    raw = _read_raw().get("scenes")
    if not isinstance(raw, list):
        return []
    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if not str(item.get("scene_id") or ""):
            continue
        result.append({k: str(item.get(k) or "") for k in _SCENE_KEYS})
    return result


def save(dids: list[str]) -> None:
    raw = _read_raw()
    # 去重保序
    seen: set[str] = set()
    uniq: list[str] = []
    for d in dids:
        s = str(d)
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    raw["devices"] = uniq
    _write_raw(raw)


def save_scenes(scenes: list[dict]) -> None:
    raw = _read_raw()
    seen: set[str] = set()
    uniq: list[dict] = []
    for item in scenes:
        sid = str(item.get("scene_id") or "")
        if not sid or sid in seen:
            continue
        seen.add(sid)
        uniq.append({k: str(item.get(k) or "") for k in _SCENE_KEYS})
    raw["scenes"] = uniq
    _write_raw(raw)


def load_order() -> list[dict]:
    """设备与场景混排后的统一展示顺序，元素为 {"type","id"}。

    旧数据没有 order 字段时合成（设备在前、场景在后），与历史快捷
    窗口的显示顺序一致，用户无需重新排序。
    """
    raw = _read_raw().get("order")
    if isinstance(raw, list):
        result = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            t = str(item.get("type") or "")
            i = str(item.get("id") or "")
            if t in ("device", "scene") and i:
                result.append({"type": t, "id": i})
        if result:
            return result
    return ([{"type": "device", "id": d} for d in load()] +
            [{"type": "scene", "id": s["scene_id"]} for s in load_scenes()])


def save_order(order: list[dict]) -> None:
    raw = _read_raw()
    seen: set[tuple[str, str]] = set()
    uniq: list[dict] = []
    for item in order:
        t = str(item.get("type") or "")
        i = str(item.get("id") or "")
        if t not in ("device", "scene") or not i or (t, i) in seen:
            continue
        seen.add((t, i))
        uniq.append({"type": t, "id": i})
    raw["order"] = uniq
    _write_raw(raw)


def add(did: str) -> None:
    dids = load()
    if str(did) not in dids:
        dids.append(str(did))
        save(dids)


def remove(did: str) -> None:
    dids = load()
    s = str(did)
    if s in dids:
        dids.remove(s)
        save(dids)


def contains(did: str) -> bool:
    return str(did) in load()

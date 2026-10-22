# SPDX-License-Identifier: GPL-3.0-or-later
# MiHome-Windows: 米家设备的 Windows 桌面控制端
# Copyright (C) 2026 MiHome-Windows contributors
"""设备工作台个性化配置的本地持久化。

每个 did 独立保存有序的功能键列表，决定详情页展示哪些模块及顺序。
文件与 devices_cache.json 同目录。
"""

from app.core import _json_store

_VERSION = 1
_FILENAME = "workbench.json"

# 模块键：单属性用 prop.name，分组用 group:<key>，动作用 __actions__
KEY_ACTIONS = "__actions__"


def _empty() -> dict:
    return {"version": _VERSION, "devices": {}}


def _read_raw() -> dict:
    raw = _json_store.read_json(_json_store.data_file(_FILENAME), _empty())
    if raw.get("version") != _VERSION or not isinstance(raw.get("devices"), dict):
        return _empty()
    return raw


def _write_raw(raw: dict) -> None:
    _json_store.write_json(_json_store.data_file(_FILENAME), raw)


def load(did: str) -> list[str] | None:
    """该设备的工作台配置；None 表示无个性化（空状态）。"""
    raw = _read_raw()
    val = raw.get("devices", {}).get(str(did))
    if isinstance(val, list) and all(isinstance(k, str) for k in val):
        return list(val)
    return None


def save(did: str, keys: list[str]) -> None:
    raw = _read_raw()
    raw["devices"][str(did)] = list(keys)
    _write_raw(raw)


def remove_device(did: str) -> None:
    raw = _read_raw()
    if str(did) in raw["devices"]:
        del raw["devices"][str(did)]
        _write_raw(raw)

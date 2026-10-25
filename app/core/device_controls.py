# SPDX-License-Identifier: GPL-3.0-or-later
"""Common, user-facing card roles; no editable raw MIoT property lists."""
import re


def is_light(device):
    return ':device:light:' in getattr(device, 'spec_type', '') or any(
        part in device.model.split('.') for part in ('light', 'lamp', 'bulb'))


def is_switch(device):
    return ':device:switch:' in getattr(device, 'spec_type', '') or '.switch.' in device.model


def is_direct_power(device):
    return is_switch(device) or any(part in device.model.split('.') for part in ('plug', 'outlet')) or ':device:outlet:' in getattr(device, 'spec_type', '')


def prepare_device_cards(devices):
    for device in devices:
        device.switch_channels = [child.did for child in devices
            if is_switch(device) and child.did.startswith(device.did + '.s')
            and re.fullmatch(r'[0-9]+', child.did[len(device.did) + 2:])]
    return devices


def device_title(device):
    if device.switch_channels and not device.name.endswith('面板'):
        return device.name + '面板'
    return device.name


def has_device_details(device):
    if device.switch_channels or is_direct_power(device):
        return False
    return bool(device.light_features) if is_light(device) else is_camera(device)


def device_kinds(device):
    """Cloud class/model identifies roles; editable names do not."""
    parts = set(device.model.lower().split('.'))
    match = re.search(r':device:([^:]+):', getattr(device, 'spec_type', ''))
    if match:
        parts.add(match[1])
    return parts


def is_camera(device):
    return bool(device_kinds(device) & {'camera', 'ip-camera'})


def supports_card_power(device):
    """Real appliance power, not router LEDs or sensor enable flags."""
    if device.switch_channels:
        return False
    if is_light(device) or is_direct_power(device):
        return True
    return bool(device_kinds(device) & {
        'television', 'tv', 'washer', 'washing-machine', 'dryer',
        'air-conditioner', 'aircondition', 'airconditioner',
        'fan', 'air-purifier', 'airpurifier', 'purifier',
        'humidifier', 'dehumidifier', 'heater', 'water-heater',
    })


def tray_eligible(device):
    if device.switch_channels or supports_card_power(device) or is_camera(device):
        return True
    if device_kinds(device) & {'speaker', 'wifispeaker'}:
        return True
    return bool(device.metric_features)


def is_status_candidate(device):
    return bool(device_kinds(device) & {
        'sensor', 'temperature-humidity-sensor',
        'temperature-sensor', 'humidity-sensor', 'motion', 'motion-sensor',
        'magnet', 'contact-sensor', 'door', 'door-sensor', 'occupancy-sensor',
        'occupancy', 'presence', 'presence-sensor', 'human', 'air-monitor',
        'smoke', 'smoke-sensor', 'gas-sensor', 'water-leak-sensor', 'waterleak',
        'plant-monitor', 'plantmonitor',
    })


def prune_tray_selection(devices):
    """Remove known ineligible cards, preserving missing devices and scenes."""
    from . import tray_store
    excluded = {device.did for device in devices if not tray_eligible(device)
                and not (is_status_candidate(device) and device.metric_features is None)}
    selected = tray_store.load()
    if not excluded.intersection(selected):
        return
    order = tray_store.load_order()
    tray_store.save([did for did in selected if did not in excluded])
    tray_store.save_order([item for item in order
        if item['type'] != 'device' or item['id'] not in excluded])


def light_property_kind(name):
    name = re.sub(r'-[0-9]+$', '', name.replace('_', '-'))
    return {'brightness': 'brightness', 'color-temperature': 'temperature',
            'color': 'color', 'rgb': 'color'}.get(name)


def light_controls(props):
    """Only expose supported, writable everyday light controls."""
    selected = {}
    for prop in props:
        kind = light_property_kind(prop.name)
        if not kind or not prop.writable or prop.type not in ('uint', 'int', 'float'):
            continue
        if kind != 'color' and (not prop.range or len(prop.range) < 2 or prop.range[0] >= prop.range[1]):
            continue
        if kind == 'color' and prop.type not in ('uint', 'int'):
            continue
        if kind == 'color' and (prop.value_list or (prop.range and (
                prop.range[0] > 0 or prop.range[1] < 0xffffff))):
            continue
        selected.setdefault(kind, prop)
    return selected


def panel_status(device, states):
    values = [states.get(did) for did in device.switch_channels]
    if not values or any(value is None for value in values):
        return '状态待确认'
    count = sum(value is True for value in values)
    if not count:
        return '全部关闭'
    return f'全部开启 · {count} 路' if count == len(values) else f'部分开启 · {count} 路'


def device_subtitle(device, metrics=None, states=None):
    if not device.online:
        return f'{device.room_name} · 离线'
    if device.switch_channels:
        location = device.room_name
        if metrics:
            location += f' · 设备温度 {metrics}'
        return location + '\n' + panel_status(device, states or {})
    return f'{device.room_name} | {metrics}' if metrics else device.room_name

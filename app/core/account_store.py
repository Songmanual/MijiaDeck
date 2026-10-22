# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep account-owned card preferences separate while sharing appearance settings."""
import hashlib
import json
import os
from . import _json_store, settings_store

_FILES = ('tray.json', 'workbench.json')


def _write(name, value):
    # Profile backups must succeed before active preferences are cleared.
    path = _json_store.data_file(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(temporary, path)


def _state():
    return _json_store.read_json(_json_store.data_file('account_profiles.json'), {})


def _snapshot():
    result = {name: _json_store.read_json(_json_store.data_file(name), {}) for name in _FILES}
    result['speaker'] = settings_store.get_default_speaker_did()
    return result


def _restore(profile):
    for name in _FILES:
        _write(name, profile.get(name, {}))
    settings_store.set_default_speaker_did(profile.get('speaker', ''))
    _json_store.data_file('devices_cache.json').unlink(missing_ok=True)


def activate(account_id):
    if not account_id:
        return
    key = hashlib.sha256(str(account_id).encode()).hexdigest()
    state = _state()
    if not state:
        # First upgrade adopts existing preferences without deleting anything.
        _write('account_profiles.json', {'owner': key, 'profiles': {}})
        return
    if state.get('owner') == key:
        return
    profiles = state.setdefault('profiles', {})
    if state.get('owner'):
        profiles[state['owner']] = _snapshot()
    _write('account_profiles.json', state)
    _restore(profiles.get(key, {}))
    state['owner'] = key
    _write('account_profiles.json', state)


def deactivate():
    state = _state()
    owner = state.get('owner')
    if owner:
        state.setdefault('profiles', {})[owner] = _snapshot()
    state['owner'] = None
    _write('account_profiles.json', state)
    _restore({})

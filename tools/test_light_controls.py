# SPDX-License-Identifier: GPL-3.0-or-later
"""Local-only virtual light. No login, cloud, hardware or persistent app data."""
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QObject, Signal, QTimer
from app.core.models import DeviceDetail, DeviceInfo, PropInfo
from app.core.service import MijiaService, ServiceError

DEMO_DID = 'local-virtual-color-light'
DEMO_PROPS = [
    PropInfo('on', '开关', 'bool', True, True),
    PropInfo('brightness', '亮度', 'uint', True, True, (1, 100, 1)),
    PropInfo('color-temperature', '色温', 'uint', True, True, (2700, 6500, 1)),
    PropInfo('color', '颜色', 'uint', True, True, (0, 0xffffff, 1)),
]


class VirtualLightService(MijiaService):
    def __init__(self):
        # Deliberately do not construct mijiaAPI or read authentication files.
        self.values = {'on': True, 'brightness': 65, 'color-temperature': 4000, 'color': 0xffb86c}
        self.device = DeviceInfo(DEMO_DID, '虚拟调光调色灯', 'local.light.demo',
            '本地测试', '测试房间', True, light_features=['brightness', 'temperature', 'color'])

    def login_status(self):
        return True

    def account_id(self):
        return 'local-virtual-light-test'

    def list_devices(self, progress=None):
        if progress:
            progress(65, '正在准备虚拟灯光设备…')
        return [deepcopy(self.device)]

    def device_detail(self, did):
        self._check(did)
        return DeviceDetail(did, self.device.name, self.device.model, deepcopy(DEMO_PROPS), [])

    def _check(self, did):
        self._require_control_access()
        if did != DEMO_DID:
            raise ServiceError('本地测试只允许操作虚拟灯')

    def power_states(self, dids):
        for did in dids:
            self._check(did)
        return {did: self.values['on'] for did in dids}

    def set_power_state(self, did, state):
        self._check(did)
        self.values['on'] = bool(state)

    def read_props(self, did, names):
        self._check(did)
        return {name: self.values.get(name) for name in names}

    def write_prop(self, did, name, value):
        self._check(did)
        prop = next((p for p in DEMO_PROPS if p.name == name), None)
        if prop is None or (prop.range and not prop.range[0] <= value <= prop.range[1]):
            raise ServiceError('无效的虚拟灯参数')
        self.values[name] = value

    def read_metrics(self, dids):
        return {did: None for did in dids}

    def icon_urls(self, models):
        return {}

    def scene_list(self, home_name=None):
        return []

    def localized_product_names(self, dids, names):
        return {}

    def logout(self):
        raise ServiceError('这是免登录的虚拟测试，请直接退出测试程序')


class LocalNetwork(QObject):
    changed = Signal(bool)
    online = True

    def check_now(self):
        pass


def main():
    import run
    from app.core import settings_store, tray_store, account_store
    with TemporaryDirectory(prefix='MijiaDeck-light-test-') as folder, ExitStack() as stack:
        stack.enter_context(patch('app.core._json_store.data_dir', return_value=Path(folder)))
        stack.enter_context(patch('app.core._json_store.data_file', side_effect=lambda n: Path(folder) / n))
        stack.enter_context(patch('app.ui.main_window.MijiaService', VirtualLightService))
        stack.enter_context(patch('app.core.availability.NetworkMonitor', LocalNetwork))
        settings_store.set_check_update_enabled(False)
        settings_store.set_start_minimized(False)
        settings_store.set_tray_intro_seen(True)
        account_store.activate('local-virtual-light-test')
        tray_store.save([DEMO_DID])
        print('虚拟灯测试：不登录账号、不连接云端、不操作真实设备，关闭后不保留测试数据。')
        if '--check' not in sys.argv:
            return run.main()
        report_path = Path(sys.argv[sys.argv.index('--check') + 1]).resolve()
        report = {'ok': False, 'virtual_only': True}
        def ready(app, window):
            try:
                assert [device.did for device in window.devices()] == [DEMO_DID]
                assert not hasattr(window._service, '_api')
                window._open_light_window(window.devices()[0])
                def verify():
                    try:
                        dialog = window._light_windows[DEMO_DID]
                        assert set(dialog._props) == {'brightness', 'temperature', 'color'}
                        assert dialog._values['brightness'] == 65
                        dialog.reject()
                        report.update(ok=True, controls=['power', 'brightness', 'temperature', 'color'])
                    except Exception as error:
                        report['error'] = type(error).__name__
                    finally:
                        window.request_force_quit()
                        window.close()
                        app.quit()
                QTimer.singleShot(300, verify)
            except Exception as error:
                report['error'] = type(error).__name__
                window.request_force_quit()
                window.close()
                app.quit()
        run.main(ready)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

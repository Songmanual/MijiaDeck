# SPDX-License-Identifier: GPL-3.0-or-later
"""Split switch cards must address their own service on the parent hardware."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.core.service import MijiaService, ServiceError


SPEC = {
    "name": "Three-channel switch",
    "properties": [
        {"name": f"on-{s}", "description": "Switch", "type": "bool",
         "rw": "rw", "range": None, "value-list": None,
         "method": {"siid": s, "piid": 1}}
        for s in (2, 3, 4)
    ] + [{"name": "temperature", "description": "Temperature", "type": "float",
          "rw": "r", "range": None, "method": {"siid": 8, "piid": 1}}],
    "actions": [{"name": f"toggle-{s}", "description": "Toggle",
                 "method": {"siid": s, "aiid": 1}} for s in (2, 3, 4)],
}


class SplitSwitchTest(unittest.TestCase):
    def setUp(self):
        self.service = MijiaService.__new__(MijiaService)
        self.service._device_cache = {}
        self.service._device_index = {
            did: ("xiaomi.switch.w3", "test-spec", f"Channel {did}")
            for did in ("123", "123.s2", "123.s3", "123.s4", "123.s99")
        }
        self.service._spec_cache = {"test-spec": deepcopy(SPEC)}
        self.api = Mock(auth_data_path=Path("unused/auth.json"))
        self.service._api = self.api

        def read(queries):
            single = isinstance(queries, dict)
            items = [queries] if single else queries
            results = [{**q, "code": 0, "value": q["siid"] != 3} for q in items]
            return results[0] if single else results

        def write(queries):
            items = [queries] if isinstance(queries, dict) else queries
            results = [{**q, "code": 0} for q in items]
            return results[0] if isinstance(queries, dict) else results

        self.api.get_devices_prop.side_effect = read
        self.api.set_devices_prop.side_effect = write

    def test_three_cards_read_distinct_channels_from_parent(self):
        states = self.service.power_states(["123.s2", "123.s3", "123.s4"])
        self.assertEqual(states, {"123.s2": True, "123.s3": False, "123.s4": True})
        self.assertEqual(self.api.get_devices_prop.call_args.args[0], [
            {"did": "123", "siid": s, "piid": 1} for s in (2, 3, 4)])

    def test_initial_list_reuses_metadata_instead_of_fetching_lists_again(self):
        self.service._device_index.clear()
        self.api.get_homes_list.return_value = []
        self.api.get_devices_list.return_value = [
            {"did": "123.s3", "model": "xiaomi.switch.w3", "spec_type": "test-spec",
             "name": "Light", "isOnline": True}]
        self.api.get_shared_devices_list.return_value = []
        self.service.list_devices()
        self.assertEqual(self.service.power_state("123.s3"), False)
        self.api.get_devices_list.assert_called_once_with()
        self.api.get_shared_devices_list.assert_called_once_with()

    def test_parent_is_read_only_and_split_cards_keep_distinct_states(self):
        states = self.service.power_states(["123", "123.s2", "123.s3"])
        self.assertEqual(states, {"123": None, "123.s2": True, "123.s3": False})
        self.assertEqual(len(self.api.get_devices_prop.call_args.args[0]), 2)

    def test_toggle_writes_only_selected_channel(self):
        self.assertTrue(self.service.toggle_power("123.s3"))
        self.api.set_devices_prop.assert_called_once_with([
            {"did": "123", "siid": 3, "piid": 1, "value": True}])

    def test_missing_channel_does_not_fall_back_to_another_light(self):
        self.assertEqual(self.service.power_states(["123.s99"]), {"123.s99": None})
        with self.assertRaises(ServiceError):
            self.service.set_power_state("123.s99", True)
        self.api.set_devices_prop.assert_not_called()

    def test_specs_are_filtered_without_mutating_shared_cache(self):
        specs = self.service._specs_for(["123.s3", "123.s4", "123"])
        self.assertEqual([p["name"] for p in specs["123.s3"]["properties"]], ["on-3"])
        self.assertEqual([p["name"] for p in specs["123.s4"]["properties"]], ["on-4"])
        self.assertEqual(self.service._spec_cache["test-spec"], SPEC)
        self.assertEqual(specs["123"], SPEC)

    def test_detail_reads_and_writes_use_parent_but_preserve_card_id(self):
        with patch("app.core.service.get_device_info", return_value=deepcopy(SPEC)):
            detail = self.service.device_detail("123.s4")
        self.assertEqual(detail.did, "123.s4")
        self.assertEqual([p.name for p in detail.props], ["on-4"])
        self.assertEqual([a.name for a in detail.actions], ["toggle-4"])
        dev = self.service._device_cache["123.s4"]
        dev.sleep_time = 0
        self.assertEqual(self.service.read_props("123.s4", ["on-4"]), {"on-4": True})
        self.assertTrue(self.service.read_prop("123.s4", "on_4"))
        self.service.write_prop("123.s4", "on-4", False)
        self.api.set_devices_prop.assert_called_once_with(
            {"did": "123", "siid": 4, "piid": 1, "value": False})
        with self.assertRaises(ServiceError):
            self.service.write_prop("123.s4", "on-2", True)

    def test_failed_read_is_unknown_and_recovers(self):
        self.api.get_devices_prop.side_effect = None
        self.api.get_devices_prop.return_value = [
            {"did": "123", "siid": 3, "piid": 1, "code": -1}]
        self.assertEqual(self.service.power_states(["123.s3"]), {"123.s3": None})
        self.api.get_devices_prop.return_value = [
            {"did": "123", "siid": 3, "piid": 1, "code": 0, "value": False}]
        self.assertEqual(self.service.power_states(["123.s3"]), {"123.s3": False})

    def test_poll_retries_cached_unknown_but_skips_offline(self):
        from app.ui.main_window import MainWindow
        devices = [SimpleNamespace(did="123.s3", online=True),
                   SimpleNamespace(did="offline", online=False)]
        window = SimpleNamespace(
            _visible_devices=lambda: devices, _known_power={"123.s3": None},
            _jobs=Mock(), _service=self.service,
            _apply_power_states=Mock(), _on_poll_error=Mock())
        for force in (False, True):
            MainWindow._refresh_power_states(window, force)
            result = window._jobs.submit.call_args.args[0]()
            self.assertEqual(result, {"123.s3": False})


if __name__ == "__main__":
    unittest.main()

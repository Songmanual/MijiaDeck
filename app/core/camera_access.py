# SPDX-License-Identifier: GPL-3.0-or-later
"""Fresh video authorization for CS2 remote relay; never requires a LAN address."""
import re
from dataclasses import dataclass
from Crypto.PublicKey import ECC
from .camera_preview import CameraPreviewError


@dataclass(repr=False)
class CameraSource:
    uid: str
    init_string: str
    client_public: str
    client_private: str
    device_public: str
    sign: str


def build_camera_source(did: str, model: str, cloud_request) -> CameraSource:
    key = ECC.generate(curve="Curve25519")
    public = key.public_key().export_key(format="raw").hex()
    response = cloud_request("/v2/device/miss_get_vendor", {
        "did": str(did), "app_pubkey": public, "support_vendors": "TUTK_CS2_MTP"})
    vendor = response.get("vendor") or {}
    if vendor.get("vendor") != 4:
        raise CameraPreviewError("当前远程预览仅支持 CS2 摄像头，该设备的视频传输方式暂未接入。")
    params = vendor.get("vendor_params") or {}
    values = [params.get("p2p_id"), params.get("init_string"), public, key.seed.hex(),
              response.get("public_key"), response.get("sign")]
    if any(not isinstance(v, str) or not v or len(v) > 16384 or "\n" in v or "\r" in v for v in values):
        raise CameraPreviewError("米家未返回完整的远程视频授权或中继地址，请确认摄像头在线后重试。")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", values[4]):
        raise CameraPreviewError("米家返回的视频密钥格式不完整，请重试。")
    return CameraSource(*values)

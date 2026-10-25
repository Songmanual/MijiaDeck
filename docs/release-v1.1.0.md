# MijiaDeck v1.1.0

针对不同设备提供更合适的卡片展示与快捷控制，让 Windows 上的米家日常操作更直接。

## 本次更新

- 按设备类型优化卡片应用：普通灯、分路开关和插座直接控制，面板本体展示各路状态及支持的设备温度，传感器展示可用读数。
- 新增灯光小控制窗，兼容设备支持亮度、色温和颜色调节，仅显示设备实际支持的项目。
- 优化摄像头快捷入口，主界面与托盘卡片支持一键打开预览。
- 托盘卡片清单按可用操作和读数筛选，便于集中管理常用设备。
- 修复多路智能开关的分路识别、状态读取与控制问题，改善首次操作和设备刷新响应。

## 下载与升级

下载 **MijiaDeck-v1.1.0-windows-x64.zip**，完整解压后运行 `MijiaDeck.exe`，无需安装 Python 或 Java。支持 Windows 10 1903+ / Windows 11 x64。

从旧版升级时，请先从托盘菜单退出程序，再完整解压并覆盖原目录，保留 `_internal` 文件夹。登录和个人设置保存在用户数据目录中，不包含在发布包里。

摄像头为实验性功能；灯光调节和其他控制能力取决于设备型号、固件及米家接口。复杂设置和自动化请在米家 APP 中完成。

## English

- Device-specific cards and quick controls for lights, outlets, multi-channel switches, camera previews and supported sensor readings.
- Compact light controls for brightness, color temperature and RGB color, where supported by the device.
- Tray selection now focuses on usable controls and supported readouts.
- Fixed multi-channel switch routing and state handling; improved initial control and refresh response.

Windows 10 1903+ / Windows 11 x64 portable ZIP. Exit the running app before extracting the complete archive over an older version. Keep the `_internal` directory.

MijiaDeck is an independent, free and open-source project based on [MiHome-Windows](https://github.com/huanyuejue/MiHome-Windows), with camera transport based on [micam](https://github.com/eugeneRover/micam). It is not affiliated with Xiaomi or Mi Home. [Source code and updates](https://github.com/Songmanual/MijiaDeck).

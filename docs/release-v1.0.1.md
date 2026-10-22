# MijiaDeck v1.0.1 · 摄像头完整版

开源免费的第三方米家 Windows 桌面客户端，让常用智能家居操作直接在电脑上完成。

## 本次更新

- **摄像头远程查看**：完整版携带实验性传输组件和独立 Java 运行时，无需另装 Java。兼容设备可通过公网中继查看实时画面，不要求和电脑处于同一个局域网。
- **鼠标拖动云台**：在视频区域按住鼠标拖动，调整兼容云台摄像头的上下、左右角度；支持画质切换、静音和全屏。最小化后还原保持连接，减少重复加载。
- **托盘选择小爱音箱**：下拉切换要控制的音箱，播放、暂停、上一首、下一首与音量控制跟随所选设备；不会改变电脑的系统音频输出设备。
- **给小爱发文字指令**：不方便开口时，在主窗口或托盘输入指令，让所选小爱音箱执行。
- 继续提供设备卡片、家庭与房间分类、温湿度读数、手动场景、深浅色与自定义主题色。

## 下载与使用

下载 `MijiaDeck-v1.0.1-windows-x64.zip`，完整解压后运行 `MijiaDeck.exe`。无需安装 Python 或 Java，请保留 `_internal` 文件夹。米家 APP 扫码登录后使用。

目标系统为 Windows 10 1903+ / Windows 11 x64。此前 v1.0.0 不含摄像头播放组件，可继续在旧版本中下载。

本包会进行界面交互回归、隔离用户目录与中文路径下的独立启动检查，以及摄像头组件离线初始化检查。离线检查不代表所有摄像头型号、网络环境或 Windows 版本均已实机验证；真实登录、视频连接和设备操作仍欢迎反馈。

## 摄像头来源与限制

远程传输基于 [eugeneRover/micam](https://github.com/eugeneRover/micam)，固定提交 `2cc9d9e7607014d1d05c17bc5676544fbb0d5d24`。**上游未找到明确分发许可证，授权尚未确认。** 维护者选择随完整版提供该编译组件；本项目免费、非商业和开源不代表取得上游授权。本项目的 GPL 不自动适用于该上游代码。来源、版本和 Java 许可文件随包保留。

摄像头预览仍为实验功能，仅支持兼容型号；不包含官方 APP 的全部摄像头功能，不保证所有型号可用。

## 后续计划

macOS 版本已列入后续适配计划，目前尚未发布，不承诺具体上线日期。

## English

MijiaDeck is a free, open-source **Windows desktop client for Xiaomi Mi Home (Mijia)**. View compatible cameras remotely and drag to pan/tilt, choose a XiaoAI speaker from the system tray, control playback and volume, and send text commands to the selected speaker. The full ZIP includes the experimental camera relay and a private Java runtime. Upstream micam redistribution permission remains unconfirmed; see the bundled third-party notices. A macOS edition is planned but not yet available. The current UI is primarily in Chinese.

基于 [MiHome-Windows](https://github.com/huanyuejue/MiHome-Windows) 改进，保留原作者与依赖项目署名。MijiaDeck 与小米、米家官方没有隶属关系。项目源码与更新：[Songmanual/MijiaDeck](https://github.com/Songmanual/MijiaDeck)。

<p align="center"><img src="app/ui/icon.png" width="88" alt="MijiaDeck logo"></p>

# MijiaDeck · 米家 / 小米智能设备 Windows 桌面控制台

**让米家智能设备，在 Windows 上更方便地查看、管理和控制。**

[项目介绍与下载](https://songmanual.github.io/MijiaDeck/) · [English website](https://songmanual.github.io/MijiaDeck/en/) · [最新版程序包](https://github.com/Songmanual/MijiaDeck/releases/latest) · [兼容性记录](docs/COMPATIBILITY.md)

MijiaDeck 是开源免费的第三方米家 Windows 桌面客户端，为希望在电脑上完成常用米家操作的用户提供桌面替代方案。工作、学习或听音乐时，不必反复拿起手机：开关设备、查看温湿度、执行场景、远程看摄像头，或者直接给小爱音箱输入文字指令，都可以在电脑上完成。

**摄像头远程查看 · 托盘切换小爱音箱 · 播放与音量控制 · 小爱文字指令**

摄像头预览支持兼容设备的实时画面和鼠标拖动云台，不要求电脑与摄像头处于同一个局域网。托盘下拉菜单可选择要控制的小爱音箱，播放、暂停、切歌、音量调整和文字指令跟随所选音箱，方便在多个房间的设备之间切换。

**A free, open-source Windows desktop client for Xiaomi Mi Home (Mijia).** Control smart-home devices, view compatible cameras remotely with mouse-drag pan/tilt, choose a XiaoAI speaker from the system tray, control playback and volume, run scenes and send text commands to the selected speaker. Light/dark themes and custom accent colors make it fit your desktop. The current interface is primarily in Chinese. A macOS edition is planned, but not yet available.

基于 [MiHome-Windows](https://github.com/huanyuejue/MiHome-Windows) 改进，延续 GPL-3.0-or-later 许可证并保留上游署名。MijiaDeck 与小米、米家官方没有隶属关系。

## 常见问题 / FAQ

### Windows 怎么控制米家设备，需要安卓模拟器吗？

不需要。MijiaDeck 是开源免费的第三方米家电脑版，下载 Windows x64 免安装 ZIP，完整解压后运行 `MijiaDeck.exe`，再用米家 APP 扫码登录即可。设备操作按型号和已适配能力提供。

### 电脑怎么看小米摄像头，可以在外网查看吗？

对兼容型号，点击摄像头卡片或播放按钮打开独立实时预览窗口。支持远程中继，不要求电脑和摄像头在同一个局域网；摄像头需在线，网络须允许传输。可切换画质、静音、全屏，支持云台的型号可拖动画面调整角度。摄像头为实验性功能，不保证所有型号。

### 电脑上能给小爱同学发文字指令、控制小爱音箱吗？

可以。选择账号下在线的小爱音箱后，输入文字指令让该音箱执行。托盘也支持所选音箱的播放、暂停、切歌和音量调节。这是控制米家音箱，不是切换电脑音频输出设备。

### 是小米官方米家 Windows 客户端吗？所有设备都支持吗？

不是官方客户端，也不保证所有设备。MijiaDeck 聚焦 Windows 上的日常查看、控制和场景执行；高级设置、定时和自动化请继续使用米家 APP。设备型号、固件和账号权限会影响可用性；[兼容性记录](docs/COMPATIBILITY.md) 区分实机反馈、接口识别和模拟测试。

### 有英文版或 macOS 版吗？

网站提供[完整英文介绍](https://songmanual.github.io/MijiaDeck/en/)，程序界面目前主要为中文。macOS 版在计划中，尚无发布包。当前 Windows 包面向 Windows 10 1903+ / Windows 11 x64，不支持 Win7 / Win8。

**English:** MijiaDeck is an unofficial Xiaomi Mi Home Windows desktop app, with no Android emulator required. It offers supported device controls, experimental remote camera previews and XiaoAI speaker controls/text commands from the system tray. Compatibility depends on the model, firmware and account permissions. The app UI is currently primarily Chinese; a macOS build is not available yet. See the [English website](https://songmanual.github.io/MijiaDeck/en/) and [compatibility records](docs/COMPATIBILITY.md).

## 界面预览 / Screenshots

以下截图使用实际界面和**虚构示例数据**渲染，不包含真实账号、家庭或摄像头画面。设备种类仅为界面演示，不代表全部型号均已适配。

### 主界面 / Main window

![MijiaDeck 米家 Windows 桌面客户端浅色模式：设备卡片、房间分类和小爱文字控制](docs/images/main-light.png)

### 托盘快捷控制 / System tray quick controls

<p><img src="docs/images/tray-light.png" width="310" alt="米家托盘快捷控制"></p>

### 摄像头独立窗口 / Remote camera preview

实际摄像头窗口界面，展示静音、画质切换、全屏与拖动云台提示。**客厅画面为 AI 生成的虚构示意图，不是真实设备录像，也不作为型号兼容性证明。**

![MijiaDeck 米家摄像头 Windows 远程预览窗口：鼠标拖动云台、画质切换和全屏，画面为 AI 生成示意](docs/images/camera-light.jpg)

### 外观设置 / Appearance settings

支持浅色、深色与跟随系统，提供四种主题色、自定义色值和界面缩放。深色效果在设置截图中展示。

![MijiaDeck 米家 Windows 客户端外观设置：深色模式、主题色和界面缩放](docs/images/settings-dark.jpg)

## 为什么做 MijiaDeck

坐在电脑前时，开关设备、查看房间状态等操作，也应该能直接在桌面完成。

- **桌面设备卡片**：按家庭和房间查看设备，区分在线状态和开关状态；支持的温湿度设备直接显示读数。
- **按设备类型提供快捷操作**：灯和插座直接开关，多路面板展示各路状态，摄像头一键预览；托盘添加清单按可用操作和读数筛选。
- **灯光小控制窗**：兼容的智能灯支持亮度、色温和颜色调节，仅显示设备实际支持的控件。高级设置与自动化请在米家 APP 中完成。
- **房间导航**：横向滚动和拖动浏览房间；右侧列表可直接跳转，并显示对应设备数量。
- **托盘快捷操作**：把常用设备和手动场景放进托盘，不必每次打开主窗口；支持单列、双列和排序。
- **可移动的托盘悬浮窗**：拖动顶部空白区调整位置，重启后记忆；托盘右键可还原窗口位置。
- **小爱同学文字指令**：不方便开口时，也能输入“打开客厅灯”等指令，让所选小爱音箱执行；主窗口与托盘共享音箱选择。
- **托盘切换音箱与播放控制**：在下拉菜单选择要控制的房间音箱，调整音量、播放、暂停、上一首或下一首，不必打开主窗口。这是切换受控小爱音箱，不是切换电脑本身的音频输出。
- **远程摄像头预览（实验性）**：在电脑上查看兼容米家摄像头的实时画面，拖动画面调整云台角度；支持画质切换、静音和全屏。v1.0.1 完整版随包提供传输组件和独立 Java 运行时，适配与来源说明见下文。
- **适应日常使用的界面**：浅色、深色、跟随系统；四种主题色和自定义 HEX 色值；支持高 DPI 和界面缩放调整。
- **清晰的状态反馈**：底栏显示当前版本；刷新设备时暂时切换为获取状态；支持退出登录。

摄像头预览为实验性功能，不同设备实际可用功能取决于其型号、米家接口和固件。本项目提供常用桌面操作，不承诺与官方 APP 的全部功能一致。

## 支持系统 / System requirements

| 项目 | 说明 |
|---|---|
| 目标系统 | Windows 10 1903 及以上、Windows 11，64 位 x64 |
| Win7 / Win8 | 不支持当前版本 |
| ARM Windows | 暂不提供原生 ARM64 发布包 |
| 高 DPI | 跟随 Windows 缩放，并可在设置中额外调整 |
| 网络 | 登录、设备控制及相关云端功能需要联网 |
| 源码环境 | Python >= 3.10；当前开发环境为 Python 3.12 / PySide6 6.8.3 |

系统范围依据当前 Qt 6.8 的平台要求确定；Windows 11 的完整实机回归尚待补充，不代表所有设备型号均已经过测试。

## 下载和使用 / Download & use

**v1.1.0**提供 **Windows x64 绿色免安装 ZIP**，包含实验性摄像头组件。[前往 Releases 下载](https://github.com/Songmanual/MijiaDeck/releases)。请选择 `MijiaDeck-v1.1.0-windows-x64.zip`；GitHub 自动提供的 `Source code` 是源码，不是可直接运行的软件。此前的 v1.0.0 不含摄像头传输组件。

1. 下载并解压完整压缩包。
2. 运行目录中的 `MijiaDeck.exe`，无需安装 Python。
3. 使用米家 APP 扫码登录。
4. 在设置和托盘“编辑卡片”中选择自己的常用设备。

不要只复制 EXE：旁边的 `_internal` 文件夹包含运行所需的 Qt、Python 和资源。便携包已通过本机隔离用户目录、移除 Python 开发路径、中文空格路径解压后的离线检查；这不等同于全新 Windows 虚拟机验证。Win11 完整实机回归、首次扫码登录与真实设备操作仍需要用户反馈。

### “绿色版”和“完全便携”的区别

这里的绿色版指**免安装、不需要管理员权限即可正常启动**。配置和登录凭据保存在当前 Windows 用户目录，移动整个程序目录不会自动把账号带到另一台电脑。

- 应用配置与缓存：`%LOCALAPPDATA%\MijiaDeck\`
- 登录凭据：`~/.config/mijia-api/auth.json`
- 源码运行时的配置：项目根目录

首次运行打包版会从旧版 `MiHome-Windows` 数据目录或旧 EXE 同目录复制已有配置；不删除旧文件、不覆盖 MijiaDeck 已有配置。开机自启动是可选设置，仅打包版提供。

请勿上传 `auth.json`、设备缓存、`settings.json`、`tray.json`、`workbench.json`、`account_profiles.json` 等个人数据文件。

### 覆盖升级

先从托盘菜单退出旧程序，再将新 ZIP 的**全部内容**解压覆盖到原程序文件夹，保留 `_internal` 运行组件；不要只替换 EXE。设置、托盘项目和登录信息位于用户目录，不随程序文件覆盖而删除。也可以解压到新文件夹测试，两种方式都会沿用这台电脑已有的用户数据。

## 摄像头预览 / Experimental camera preview

**坐在电脑前，也能远程看看家里的情况。** 对于兼容型号，可从设备卡片打开独立预览窗口，通过公网中继查看实时画面，不要求电脑与摄像头处于同一个局域网。v1.0.1 完整版已携带所需组件，无需另装 Java。使用方式类似米家 APP 中的实时查看；这是第三方实验实现，并不具备官方 APP 的全部摄像头功能。

- **实时查看与云台控制**：在视频区域按住鼠标拖动，调整兼容云台摄像头的上下、左右角度。
- **独立预览窗口**：支持画质切换、静音和全屏；默认优先流畅画质。
- **减少重复加载**：调整窗口大小、最小化后还原保持当前连接；关闭预览窗口后释放视频连接。
- **连接条件**：摄像头需在线，当前网络允许相应的远程传输；首次授权和中继连接可能需要等待。

**Experimental remote camera viewing for compatible Xiaomi Mi Home cameras.** The v1.0.1 full distribution includes the relay and a private Java runtime. View a live stream over an Internet relay, drag the picture to pan/tilt compatible cameras, switch quality and use fullscreen. Resizing or minimizing the preview keeps the session alive. This is a third-party implementation, not full feature parity with the official Mi Home app.

- 当前已测试的型号包括 `chuangmi.camera.029a02`，不承诺所有米家摄像头都支持。
- 云台没有可靠的“到位”反馈，目前采用单次拖动指令、短暂冷却和后续视频帧解锁。
- 远程传输基于 [eugeneRover/micam](https://github.com/eugeneRover/micam) 的固定版本。**尚未找到明确的上游分发许可证，相关授权未确认。** 维护者选择随完整版提供编译组件；免费、非商业用途和来源注明不等于获得上游许可，也不会把上游代码自动变为本项目的 GPL 代码。见 [第三方说明](THIRD_PARTY_NOTICES.md)。
- Git 源码树不包含上游源文件、生成的 JAR 或 Java 运行时；构建脚本从固定源码版本生成组件，完整包保留来源、版本与 Java 的许可文件。

任何演示摄像头画面都应明确标为示意，避免被误认为真实设备录像或型号兼容性证明。

## 从源码运行 / Run from source

进入项目目录后运行 `start.bat`，或手动执行：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe run.py
```

首发便携包使用 PyInstaller 目录模式构建，不需要 C 编译器。建议使用 Python 3.12 x64 / PySide6 6.8.3：

```powershell
.venv\Scripts\python.exe -m pip install pyinstaller==6.16.0 PySide6==6.8.3
.venv\Scripts\python.exe tools/install_camera_backend.py
.venv\Scripts\python.exe tools/build_portable.py --with-camera
.venv\Scripts\python.exe tools/test_portable.py
```

产物位于 `dist/portable/`，包含 ZIP 与 SHA256 校验文件。脚本使用资源白名单，不复制个人配置或账号；`--with-camera` 明确加入生成的摄像头 JAR 和独立运行时。依赖版本和源码提交写入包内 `build-info.json`，许可文本、源码地址及共享库替换说明见 [依赖源码说明](docs/DEPENDENCY_SOURCES.md)。更新随包许可文本可执行 `python tools/collect_release_licenses.py`。

另一条构建路线是 `build.ps1`（Nuitka standalone 目录版，需要 VS Build Tools 2022）。

重绘品牌图标：`python tools/generate_brand_icons.py`（额外需要 Pillow）。

生成示例截图：`python tools/render_demo_screenshots.py`；脚本使用虚构设备、临时配置和禁用网络的任务执行器，不读取真实登录信息。

## 后续计划 / Roadmap

- **macOS 客户端**：计划适配窗口、菜单栏快捷控制、设备卡片和相关交互；当前尚未发布 macOS 安装包，具体进度后续公布。
- 持续改善摄像头连接体验，补充兼容型号和真实设备验证。

## 开源致谢 / Credits

- [huanyuejue/MiHome-Windows](https://github.com/huanyuejue/MiHome-Windows)：原始桌面客户端基础。
- [Do1e/mijia-api](https://github.com/Do1e/mijia-api)：米家账号和设备接口。
- [PySide6-SiliconUI](https://github.com/H1DDENADM1N/PySide6-SiliconUI)：界面组件基础。
- [eugeneRover/micam](https://github.com/eugeneRover/micam)：实验性摄像头远程传输参考；分发许可待确认。
- Qt / PySide6、QtAwesome、NumPy 等基础组件。

完整说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本项目代码遵循 [GPL-3.0-or-later](LICENSE)，第三方代码和组件遵循各自许可证。

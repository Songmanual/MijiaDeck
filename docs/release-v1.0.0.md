# MijiaDeck v1.0.0

米家 / 小米智能设备的 Windows 桌面控制台。

在电脑上集中查看和控制米家设备：常用设备卡片、房间分类、系统托盘快捷操作，以及发给小爱同学的文字指令。

## 本次发布亮点

- 重新梳理主界面与托盘布局，适配浅色、深色和高 DPI。
- 房间分类保留横向滚动，支持列表跳转与设备数量展示。
- 托盘支持常用设备、手动场景、音箱控制及文字指令。
- 托盘悬浮窗可拖动、记住位置，并可通过右键菜单还原。
- 主窗口与托盘使用一致的小爱音箱选择和状态反馈。
- 可选的实验性摄像头远程预览：实时画面、兼容云台拖动、画质切换与全屏；最小化和还原保持连接。需单独摄像头组件，首发公开便携包暂不附带。
- 四种预设主题色及自定义 HEX 色值，在深浅模式中使用一致主色。
- 统一 MijiaDeck 名称和灰黑底白色标志。

## 系统与使用方式

目标支持 Windows 10 1809+ / Windows 11 x64；Win11 完整实机验证尚待补充。下载完整 ZIP，解压后运行 `MijiaDeck.exe`，米家 APP 扫码登录。

这是免安装目录版，不能只移动一个 EXE；配置与凭据保存在当前 Windows 用户目录。不同设备功能以实际支持情况为准。

## 下载

下载附件 `MijiaDeck-v1.0.0-windows-x64.zip`，完整解压后运行目录中的 `MijiaDeck.exe`。`Source code` 是源码包，不能直接运行。旁边的 `.sha256` 文件供校验下载完整性。

## 已验证与限制

- 70 项界面和交互回归检查完成：69 项通过，1 项因平台条件跳过。
- ZIP 解压到中文与空格路径、隔离用户目录、移除 Python 开发路径后，图标、深浅色控件、Qt 多媒体初始化及二维码依赖检查通过。
- 尚未完成全新 Windows 虚拟机、Windows 11 实机和该便携包的真实扫码/设备操作验证，欢迎反馈。
- 摄像头预览需额外组件。分发许可尚未确认，**本公开包不附带 micam 传输 JAR 和 Java 运行时，不能直接播放摄像头视频**。

MijiaDeck is a third-party Windows dashboard for Xiaomi Mi Home (Mijia). This release includes device cards, system tray quick controls, scenes, XiaoAI text commands and light/dark themes. Download the Windows x64 ZIP, extract the entire folder and run `MijiaDeck.exe`; Python installation is not required. The optional experimental camera streaming backend is not bundled.

源码与第三方说明：https://github.com/Songmanual/MijiaDeck 。基于 MiHome-Windows 改进，遵循 GPL-3.0-or-later。

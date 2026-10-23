# MijiaDeck v1.0.2

修复 Windows 便携版双击启动时报错的问题，保留摄像头远程查看、云台拖动、设备卡片、托盘音箱控制与小爱文字指令。

## 修复内容

- 修复无控制台环境下，米家接口依赖初始化触发 `'NoneType' object has no attribute 'isatty'`，导致主窗口无法打开。
- 统一正常启动和打包检查的标准输入输出处理，移除曾掩盖问题的检查模式输出重定向。
- 增加缺失标准流的依赖导入回归，以及解压后 EXE 创建主窗口、绘制界面并运行事件循环的检查。检查隔离配置、禁用账号客户端和网络任务，不读取真实登录信息。
- 项目介绍新增摄像头窗口和外观设置截图，使用虚构示例信息；摄像头中的客厅画面明确标注为 AI 生成示意。

## 下载与使用

下载 **MijiaDeck-v1.0.2-windows-x64.zip**，完整解压到新文件夹后运行 `MijiaDeck.exe`。请保留 `_internal` 文件夹，无需安装 Python 或 Java。推荐 v1.0.0 / v1.0.1 用户升级到此版本。

目标系统：Windows 10 1903+ / Windows 11 x64。macOS 版本尚在计划中，未发布。

发布检查覆盖离线界面回归、中文解压路径、无控制台启动、主窗口绘制及摄像头组件初始化；不代表所有摄像头型号或真实网络环境均已验证。

## 第三方来源

基于 [huanyuejue/MiHome-Windows](https://github.com/huanyuejue/MiHome-Windows) 改进。实验性摄像头传输基于 [eugeneRover/micam](https://github.com/eugeneRover/micam)，固定提交 `2cc9d9e7607014d1d05c17bc5676544fbb0d5d24`，上游分发许可仍未确认；免费、非商业和开源不代表获得上游授权，来源与 Java 许可文件随包保留。仅兼容部分设备，不包含官方 APP 的全部摄像头功能。MijiaDeck 与小米、米家官方无隶属关系。

## English

Fixes the Windows portable application's startup crash (`NoneType.isatty`) when launched without a console. Adds a regression for missing standard streams and a relocated executable check that creates and renders the real main window with offline, isolated services. Camera viewing, pan/tilt and XiaoAI speaker controls remain included. Download the ZIP and extract it fully before running MijiaDeck.exe. See bundled third-party notices for camera component limitations and unresolved upstream redistribution permission.

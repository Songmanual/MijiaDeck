# 兼容性与验证记录 / Compatibility

记录版本：MijiaDeck v1.1.0。此页区分实机反馈、接口识别和模拟测试，不将“能看到设备”视为所有操作都已验证。

## 已有证据

| 类型 / Device type | 已验证或已实现的内容 | 验证范围与边界 |
|---|---|---|
| 多路智能开关 | 分路识别、独立开关及状态回填；面板本体展示各路状态 | `xiaomi.switch.w3` 有本地实机操作反馈。其他型号仍需逐一反馈；面板温度是设备属性，不保证代表室内温度。 |
| 温湿度设备 | 卡片读取并显示温度、湿度；有可用读数的设备可加入托盘 | 本地使用中已读取 `anseny.sensor_ht.0314b`、`miaomiaoce.sensor_ht.t2`、`miaomiaoce.sensor_ht.t9` 的规格与读数。固件版本未统一记录，不保证同品牌全部型号。 |
| 摄像头 | 实时预览、画质切换、静音、全屏；兼容云台型号支持拖动 | `chuangmi.camera.029a02` 有本地实机使用反馈。摄像头传输为实验性功能，固件、权限及网络均可能影响结果。 |
| 调光、色温、RGB 灯 | 按可写属性显示亮度、色温和颜色控件，遵守属性范围 | 小控制窗已通过模拟设备交互测试；这些测试不是对应灯具的实机兼容性证明，欢迎补充真实型号反馈。 |
| 小爱音箱 | 音箱选择、播放、暂停、切歌、音量和文字指令 | 有本地日常使用反馈；不同音箱、内容服务和账号权限可能有差别。型号列表仍待社区逐一验证。 |
| 插座、电视、洗衣机等 | 按设备类别和可写电源属性提供快捷开关 | 不能将“读取到电源属性”视为开机、唤醒或所有控制功能均已验证。洗衣机电源不等于开始洗涤。 |

The table distinguishes local hardware feedback, metadata recognition and simulated-device testing. A visible card or an available property is not proof of complete compatibility. Dimming/color-temperature/RGB controls currently have simulated interaction coverage and still need broader physical-device testing.

## 当前边界

- 路由器目前只在主界面展示，不提供快捷电源操作，也不进入托盘添加清单。
- 存在感应、门窗等设备如果没有当前版本已实现的读数或操作，只展示名称、房间和在线状态；不因其类别名为“传感器”就进入托盘清单。
- 普通灯和分路开关直接操作；面板本体展示状态。空调等设备的专用小控制窗尚未提供。
- 只执行账号中已有的米家手动场景。高级设备设置、定时和自动化配置请在米家 APP 中完成。
- 当前程序界面主要为中文。macOS 在计划中，尚无发布包。
- 当前发布包面向 Windows 10 1903+ / Windows 11 x64；完整 Win11 实机回归尚待补充，不支持 Win7 / Win8。
- 文档和网站截图使用虚构示例数据；摄像头截图中的画面为 AI 生成示意，不能作为型号适配证明。

## 如何反馈型号 / Report compatibility

请在 [GitHub Issues](https://github.com/Songmanual/MijiaDeck/issues) 提供：

1. MijiaDeck 版本、Windows 版本。
2. 设备型号（例如 `xiaomi.switch.w3`）和固件版本；不知道的字段可以写“未记录”。
3. 具体操作、预期结果和实际结果；注明米家 APP 中同一功能是否正常。
4. 如有截图，先遮住家庭名称、设备 ID、登录二维码和摄像头真实画面。

不要提交账号凭据、登录文件、签名视频地址或完整个人设备缓存。We only need the model, firmware, app/OS version, action and observed result—not account credentials, private device identifiers or camera footage.

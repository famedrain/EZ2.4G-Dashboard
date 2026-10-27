# EZ2.4G Dashboard

Windows 10/11 x64 的 2.4G 无线外设电量工具：**一个托盘图标，点击查看所有设备的 Dashboard**。

基于 [Ap0LoG1zE/EZ2.4G](https://github.com/Ap0LoG1zE/EZ2.4G) 的公开 Fork，保留上游设备读取与抓包适配能力。运行时使用 Python 标准库（ctypes + tkinter），无需第三方 Python 包。

## 已通过基础实机测试的型号

| 型号 | 连接方式 / 接收器 ID | 已验证结果 |
| --- | --- | --- |
| 迈从 MCHOSE G75 Pro 键盘 | 2.4G / `3554:FA09` | 真实接口连续返回 100%，用户确认未充电；已修正为“已充满”而非“充电中” |
| 雷柏 Rapoo VT3S 鼠标 | 2.4G / `24AE:1411` | 用户 Dashboard 实测显示 70%、69%；暂未上报时保留并注明上次电量 |

这里的“通过测试”指基础电量读取，不代表所有模式或同品牌型号兼容。真实充电切换、低电量耗尽、蓝牙/有线模式和长期休眠唤醒尚未完整验证。协议来源与实机证据见 [适配记录](docs/protocols.md)。

## 使用

1. 从本仓库 [Releases](https://github.com/famedrain/EZ2.4G-Dashboard/releases) 下载 `EZ2.4G-Dashboard.exe` 并运行；不需要 Python。开发版构建可在 [Actions](https://github.com/famedrain/EZ2.4G-Dashboard/actions) 的 Windows build 中下载。
2. 程序静默驻留托盘。即使没有设备，也保留一个图标；Windows 可能将它放进托盘折叠菜单。
3. 拔插需要添加的 USB 接收器，在确认弹窗里选择添加。启动时不会自动添加所有 HID 设备。
4. 左键单击托盘图标打开 Dashboard，再次点击可收起。首次在托盘附近展开；拖动标题栏后记住位置，收起重开及退出重启均恢复到该位置。屏幕变化时将窗口限制在可用工作区内。按 Esc、关闭按钮或点击其他应用可收起。
5. 右键托盘图标可以打开 Dashboard、立即刷新、切换开机自启或退出。

面板显示设备名称、类别标识、电量、充电/休眠/未连接状态及时间，可滚动查看多台设备。双击设备名称重命名，右键卡片删除。类别按名称推断；不确定时显示通用标识，可在重命名时加入“鼠标”“键盘”“耳机”等词。

面板采用更大的文字、按钮和电量数字；状态行简化为连接状态及更新时间，避免长诊断文本挤占卡片。

托盘仍只有一个图标，恢复为电量圆环：默认显示已连接设备中最低的有效电量，随该值变化；没有有效值时为灰色空环。上次电量可参与显示，悬停提示会明确标注，已断开的设备不参与。低于 **10%**（不含 10%）时圆环变红。

新读到未充电设备低于 10% 时请求 Windows 系统提醒。历史值和充电状态不触发低电量通知；同一设备在一次低电量期间只提醒一次，充电或恢复到至少 12% 后重新允许提醒。Windows 的通知/勿扰设置会影响实际提醒显示。悬停还可查看各设备电量摘要。

## 开机自启

**可选，默认不创建。** 在 Dashboard 或托盘右键菜单中勾选“开机自启”即可，启动后不弹出面板。取消勾选可关闭。程序退出后停止查询电量。

- 自启项：当前用户启动目录中的 `EZ2.4G Dashboard.lnk`。
- 配置：`%APPDATA%\BatteryTrayDashboard\config.json`。
- 拖动位置保存为配置中的 `panel_position`，不影响已添加设备或协议。
- 与原版的配置、自启项和单实例标识分开。初次使用需重新添加设备；如需沿用原版协议，可在两边都退出后，手动复制原版 `%APPDATA%\BatteryTray\config.json` 到上述新目录。
- 不建议同时运行两个版本查询同一个接收器。

## 从源码运行

安装 Windows x64 Python 3.10+，需包含 tkinter。下载整个源码目录，保持 `my_devices.py`、`dashboard_state.py`、`vendor_battery.py` 在同一目录：

```bat
python my_devices.py             :: 静默驻留单图标托盘
python my_devices.py --panel     :: 只打开 Dashboard，关闭即退出
python my_devices.py --once      :: 读取一次并打印
python my_devices.py --list      :: 列出 HID 接口
python my_devices.py --install   :: 主动创建自启项及桌面入口
```

也可以双击 `启动.bat`，通过系统 Python Launcher 或 PATH 中的 pythonw 启动。脚本不再依赖原作者电脑上的固定 Python 路径。

## 设备协议与抓包

能否读取电量取决于设备协议，不能保证所有 2.4G 外设都可用。

- 新增官方网页协议适配：迈从 G75 Pro 无线接收器 `3554:FA09`、雷柏 VT3S 无线接收器 `24AE:1411`。G75 Pro 已取得真实 100% 回复，雷柏由用户截图反馈 70%；充电切换等场景仍需验证。协议依据、实机证据和边界见 [适配记录](docs/protocols.md)。
- 第三预览版修正 G75 Pro 的充电状态位序：`01` 表示已充满但未充电，`10` 才表示充电；并在同一轮内为未响应的查询增加一次有界重试。
- 已添加这两台设备时，升级后无需删除重加。关闭厂家网页驱动，唤醒设备后点击刷新。雷柏目前被动监听电量上报；未收到有效报告时显示“等待设备电量”，不会生成电量或假装休眠。
- 标准 HID 电量可读时，自动保存标准协议。
- 未知协议会显示“协议未知”，可以点击卡片的“协议帮助”进入上游抓包助手。
- 抓包需安装 [USBPcap](https://desowin.org/usbpcap/)、重启，并允许抓包助手以管理员权限运行。正常查看面板不要求管理员权限。
- 抓包前先关闭厂家驱动；开始抓包后打开厂家驱动，让它显示一次电量，再停止并填写实际百分比。
- 多个字节符合时，换一个相差较大的电量再抓一次。保存后回读验证；无法验证的协议会被移除。
- 加密、私有握手和特殊复合接收器仍可能无法适配。电量精度受设备上报限制。

## 验证与构建

```bat
python -m unittest discover -s tests -v
python -m py_compile my_devices.py dashboard_state.py vendor_battery.py
python -m pip install pyinstaller==6.16.0
python -m PyInstaller --clean --noconfirm --onefile --windowed --name EZ2.4G-Dashboard --icon app.ico my_devices.py
```

构建产物位于 `dist/EZ2.4G-Dashboard.exe`。PyInstaller 仅用于打包，不是运行时依赖。Windows CI 会运行上述测试、构建 EXE 并上传构建附件；`v*` 标签构建成功后上传到本仓库 Releases。

测试覆盖最低电量环与 10% 边界、通知内容和防重复、位置保存与边界修正、原生图标绘制、100/150/200% 隐藏 Tk 画布的字体和文本边界，以及设备协议解析。自动测试不会轮询真实外设、读取桌面或修改自启项。

尚需实机手动验收：真实鼠标/键盘/耳机的电量与抓包协议、托盘点击与外部点击收起、多显示器与混合 DPI、系统注销后自启、打包 EXE 的交互表现。隐藏画布测试不等同于完整视觉验收。

## 已知边界与来源

- 设备身份沿用上游 VID + PID，两个相同型号接收器可能合并；此次修改未扩展为按序列号识别。
- Windows 托盘提示长度有限，设备很多时需打开 Dashboard 查看。
- `docs/panel.png`、`docs/tray.png` 是保留的上游历史截图，不代表本 Fork 当前界面。
- 上游当前未提供 LICENSE 文件。本 Fork 保留原 Git 历史和作者归属，不另行授予上游代码的使用、分发或商业授权。

# G75 Pro 与 VT3S 协议适配记录

本页记录官方网页驱动的静态分析结果。分析日期：2026-10-27。
没有运行厂家网页脚本，没有连接或向真实设备发送指令。测试帧为依据代码结构构造的合成数据，不是实机抓包。

## 迈从 G75 Pro 无线接收器

- 用户提供的[官方驱动链接](https://www.mchose.com.cn/#/keyboard?deviceName=2.4G+Wireless+Receiver-G75_Pro&isGoUpgradePage=false)明确包含型号 G75_Pro。
- 用户 Dashboard 显示 VID:PID `3554:FA09`，厂商 HID 页面 `FF02`。
- [官网核心模块](https://www.mchose.com.cn/assets/purify.es-CxLZ1Htw.js)中，G75_Pro 的无线 Report ID 为 19（`13`），getBattery 命令为 `4A`。
- 请求为 19 字节的 `13 4A 01 00 ...`，追加包含 Report ID 在内的字节和低八位 `5E`，共 20 字节。仅发送此电量查询，不实现任何设置/升级命令。
- WebHID 回复数据先解析 commandParams、total、current，再从第 4 字节后组装数据。单包电量回复应对应 `4A 01 00`；组装后的第一个字节是百分比，下一字节低四位为 chargeStatus，高四位为 fullStatus。
- Windows 的输入缓冲区包含 Report ID，因此百分比在完整报告索引 5，状态在索引 6。
- 仅打开此 VID:PID 下的 `FF02` 接口，并验证 Report ID、命令、包数、序号、长度、电量及标志范围。

`3554:FA09` 被厂家多个键盘型号复用。此版本的依据是用户提供的 G75 Pro 路由及 G-series 官方通用 getBattery 实现，不能据此宣布所有共享 ID 的键盘均已实测支持。

## 雷柏 VT3S 无线接收器

- [官方网页驱动](https://hub.rapoo.cn/)引用的[主模块](https://hid.rapoo.cn/AHUB_WEB/dist/assets/js/index-3ShGzFuu.js)将 VID 9390、PID 5137（`24AE:1411`）列入 `VT3S` 型号。
- 对应驱动类为 `VT_nrf54L`，配置接口为 Usage Page `FF00`、Usage `0002`。升级接口 Usage 14 和 1 不属于电量读取范围。
- 官方 handleReport 处理 Report ID `07`。去除 Report ID 后，状态位于数据索引 6，电量位于数据索引 7。状态 1 为有效电量，2 为充电。
- 此版仅被动监听该输入报告，不发送查询、设置、EEPROM 或固件命令。与此前其他开源项目的 `BB` 报告不是同一套解析，未混用。
- 若鼠标当时不主动上报，短时监听可能没有结果。请唤醒/移动鼠标并刷新；持续无法取得时仍需补充实机证据，不将其伪装成成功。

## 验证边界

- 合成测试验证组包、充电状态解析、错误命令/越界值拒绝、设备和接口过滤、只发送允许的命令，以及失败后关闭句柄。
- 没有执行真实外设 I/O；测试通过不等于用户这两台设备已经可以正常读取。
- 首次使用新版建议关闭两个网页驱动标签页，避免接收器接口占用。程序中已经添加的设备无需删除重加。
- 需要用户对照厂家驱动确认百分比、充电状态和多次刷新。若仍“等待设备电量”，保留该状态并继续检查，USBPcap 仍是后备手段。

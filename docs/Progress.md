# Progress — WPSPDF

## Current State

**PDF 侧端到端已验证**：页签「PDF转表格」→ 任务窗格（引擎在线 / 当前 PDF 路径 / 开始转换 / 日志）→ 提交任务 → 产物落盘。
验证方式为**服务端驱动**（加载项轮询 `/cmd`，我从引擎下发指令），全程未移动鼠标、未切换前台窗口；
截图用 `PrintWindow` 抓取，不抢焦点。

实测读数（2026-11-26 16:05）：
- `selftest`：`path` 拿到完整绝对路径，`hasRibbon=true`
- `convert`：job `9c3ca77ee5a3`，**113 秒**跑完 18 页，产物 `output\…_.xlsx.xlsx` 覆盖写成功

## Recent Changes

- 2026-11-26 16:25：图标问题定位并修复。用 4 色象限标定图实测：**WPS 没裁切，是把这个 32px 图缩到约 16px 显示**；原先的细线条 SVG/线稿缩到 16px 基本看不见，所以像"只剩左上角"。改为实心粗笔画 PNG（`images/{convert,batch,check}.png`，相对路径 + `size="large"`）后渲染正常（`evidence/icons-final-b.png`）。
  同时新增 `/cmd activatetab`（`Application.ribbonUI.ActivateTab`）用于无鼠标切换页签验证。

- 2026-11-26 16:06：修任务窗格白屏——`CreateTaskPane` 必须传**带 scheme+host 的绝对 URL**（原来传 `/pdf/ui/...` 站内路径）。
  同时把 `convertCurrent()` 从同步 XHR 改为 `fetch`：CEF 后台页会拦同步 XHR，这是先前「点了没反应」的真因。
- 2026-11-26 16:03：加 `/cmd` 服务端驱动通道（`GET /cmd` 取指令、`POST /cmd` 下发、`POST /log` 回报），用于无鼠标验证。
- 2026-11-26 15:55：PDF 页签达成（`type="pdf"` 独立包）。


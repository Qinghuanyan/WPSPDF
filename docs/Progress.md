# Progress — WPSPDF

## Current State

**PDF 侧端到端已验证**：页签「PDF转表格」→ 任务窗格（引擎在线 / 当前 PDF 路径 / 开始转换 / 日志）→ 提交任务 → 产物落盘。
验证方式为**服务端驱动**（加载项轮询 `/cmd`，我从引擎下发指令），全程未移动鼠标、未切换前台窗口；
截图用 `PrintWindow` 抓取，不抢焦点。

实测读数（2026-11-26 16:05）：
- `selftest`：`path` 拿到完整绝对路径，`hasRibbon=true`
- `convert`：job `9c3ca77ee5a3`，**113 秒**跑完 18 页，产物 `output\…_.xlsx.xlsx` 覆盖写成功

## Recent Changes

- 2026-11-26 19:27：完成自动打开改成**引擎侧**（`opened: true` 实测，WPS 表格窗口标题变为 `...xlsx.xlsx - WPS Office`）；
  子进程改无缓冲后进度真实递增（5/18→12/18，ETA 126s→44s）。
- 2026-11-26 17:10：引擎 v1.2 常驻 + 快捷方式 + 开机自启；`/job` 带 ETA。
- 2026-11-26 17:05：查明 WPS 个人版拦截加载项起进程，改为常驻引擎方案。

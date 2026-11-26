# Progress — WPSPDF

## Current State

**PDF 侧端到端已验证**：页签「PDF转表格」→ 任务窗格（引擎在线 / 当前 PDF 路径 / 开始转换 / 日志）→ 提交任务 → 产物落盘。
验证方式为**服务端驱动**（加载项轮询 `/cmd`，我从引擎下发指令），全程未移动鼠标、未切换前台窗口；
截图用 `PrintWindow` 抓取，不抢焦点。

实测读数（2026-11-26 16:05）：
- `selftest`：`path` 拿到完整绝对路径，`hasRibbon=true`
- `convert`：job `9c3ca77ee5a3`，**113 秒**跑完 18 页，产物 `output\…_.xlsx.xlsx` 覆盖写成功

## Recent Changes

- 2026-11-26 17:10：引擎 v1.2 落地：`/job` 返回页数与 ETA、`/jobs`、`/cmd` 通道、常驻模式（`IDLE_TIMEOUT=0`）；
  安装脚本改为在线双条目（et+pdf）+ 快捷方式 + 开机自启，卸载脚本同步清理。
- 2026-11-26 17:05：查明**WPS 个人版拦截加载项起进程**（ShellExecute 返回 OK 无效果，CoCreateInstance 报 can not create），
  因此改为「常驻引擎 + 桌面快捷方式」，不再尝试从页签拉起进程。
- 2026-11-26 17:00：修 CEF 缓存问题——`main.js` 里 `document.write` 在动态脚本中会清空文档，改为 `onload` 链式插入并带 `?v=` 版本号；
  此前改了 JS 不生效、指令被旧实例吞掉，根因都在这里。

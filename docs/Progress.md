# Progress — WPSPDF

## Current State

**v1.4：页签本地常驻，引擎按需启动，WPS 关了引擎就退。**

- 页签：离线本地包 `jsaddons\WPSPDFPdf_1.0.0\` + `publish.xml` 的 `jsplugin url="WPSPDFPdf_1.0.0"`；
  **引擎停止时页签照常出现**（`evidence/offline-localpkg-tabrow.png`）。
- 引擎：计划任务 `WPSPDF-EngineOnDemand` 每分钟检查，WPS 文档进程在跑才拉起；`.run/idle_timeout=20`，
  WPS 关掉后 `idle 22s → shutdown`。开机自启已取消。
- 数据侧（v1.3.0 起不变）：18 页 → 578 行 × 10 列；序号 1–568 连续；第 10 列 568/577；
  `仍有墨未识别 0`；25 个低置信度格进「需校对」表。

## Recent Changes

- 2026-11-27 00:25 **v1.4.0：页签改为离线本地包 + 引擎按需启动**。
  关键发现：wpsjs 离线安装格式里 `url` 是 `jsaddons` 下的**目录名**（`build.js:163`），
  照它落地后引擎完全停止也有页签。引擎改由每分钟的计划任务按需拉起（不常驻），
  判活只看文档进程并剔除 `wpsoffice.exe` 空壳，idle 20s；开机自启取消。
  另实测坐实「加载项页面无法起进程」：`ShellExecute` 静默无效、`CreateObject` `Load dll fail`、
  `CoCreateInstance` `cannot create`。
- 2026-11-27 00:00 **查清页签注册时机与关闭卡死归属**。
  页签只在 WPS **进程启动**时注册一次：引擎没起→无 ribbon.xml→无页签；引擎后起或改过 publish.xml，
  已在跑的 WPS 不会补注册（同一窗口重开文档也不行，必须退干净重开）。
  「关闭卡死」A/B 验证：禁用加载项后行为相同 → 是 WPS 留空「WPS Office」窗口，关掉它 1 秒退出，与插件无关。
  另实测：离线本地目录注册（`jsplugin` + 本地 path）在本机 WPS 不出页签，只能走 http 托管。
  新增 `tools/check-engine.bat`；`poll.js`/`tp.js` 加 beforeunload/pagehide 清理。
- 2026-11-26 23:37 **引擎 v1.3.1：修 PDF 卡死与页签时有时无**。
  卡死根因：旧 `poll.js` 在引擎不可达时每 15s 调 `wps.OAAssist.ShellExecute`（WPS 个人版静默拦截，
  同步调用拖死宿主 UI）。已删除自动拉起，改指数退避；删掉 `util.js` 同步 XHR 死代码；循环加单例守卫。
  页签消失根因：引擎空闲退出后 WPS 取不到 `ribbon.xml`。改为**引擎生存期跟随 WPS**，并补注册开机自启
  （此前 HKCU Run 无该条目）。实测：页签行 `阅读 | 增值服务 | PDF转表格`，`jsver=1.3.1`，`taskpane ok`。
- 2026-11-26 23:00 **引擎 v1.3.0：修三处静默丢字 + 提速**。
  ① 跨页并集列边界 —— 「正式答辩时段」整列曾因后 17 页缺右边框被判网格外丢弃（577 行里 540 行空）；
  ② 同线块按 y 聚类再按 x 排 —— 长标题 `《城垣万象古城池数字化复原》` 曾颠倒；
  ③ `text_score` 0.5→0.35 —— 「恒我」整页分 0.40 被阈值吃掉；
  另加空单元格二次识别（内缩判墨 + 多档留白）、序号序列校验、页级 OCR 缓存、需校对工作表。
- 2026-11-26 19:27：完成自动打开改成引擎侧（`opened: true` 实测）；子进程无缓冲后进度真实递增。
- 2026-11-26 17:10：引擎 v1.2 常驻 + 快捷方式 + 开机自启；`/job` 带 ETA。
- 2026-11-26 17:05：查明 WPS 个人版拦截加载项起进程，改为常驻引擎方案。
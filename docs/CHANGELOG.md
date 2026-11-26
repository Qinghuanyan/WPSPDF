# CHANGELOG — WPSPDF

## v1.4.0 — 2026-11-27

**架构调整：页签本地常驻 + 引擎按需启动（不再常驻、不再开机自启）**

用户要求：引擎「按需启用」，不要一直常驻，WPS 关了引擎就关。

- **页签脱离引擎**：PDF 侧加载项改成官方「离线本地包」形式——
  `jsaddons\WPSPDFPdf_1.0.0\` + `publish.xml` 里
  `<jsplugin name="WPSPDFPdf" type="pdf" url="WPSPDFPdf_1.0.0" version="1.0.0"/>`。
  `url` 是**目录名**不是网址（依据 wpsjs `src/lib/build.js:163`）。
  **实测：引擎完全停止（38731 无响应）时，页签仍出现**（`evidence/offline-localpkg-tabrow.png`）。
  此前试过的两种写法都失败并已记录：本地 Windows 路径（`jsplugin url="D:/..."`）、
  `file:///`（`evidence/offline-test-tabrow.png`、`file-test-tabrow.png`）。
- **引擎按需启动**：新增计划任务 `WPSPDF-EngineOnDemand`（每 1 分钟跑 `tools/watch_once.py`，
  几百毫秒即退出，不常驻）：仅当 WPS 文档进程在跑且引擎不在时才拉起引擎。
  实测：WPS 在跑、引擎停 → 任务自动拉起（`在线：版本 1.3.1 … 已运行 6s`）。
- **引擎不常驻**：判活口径收紧为**文档进程**（`wpspdf/et/wpp/wps`），剔除 `wpsoffice.exe`
  （关文档后它会留空壳窗口，用它会把这引擎焊死）。`.run/idle_timeout` 设 **20 秒**，
  watchdog 轮询 20s→5s。实测：WPS 关掉后 `idle 22s → shutdown`，端口释放。
- **取消开机自启**（`autostart.ps1 -Action unregister`）——页签不再需要引擎先起。
- 新增：
  - `tools/install-offline.ps1`（离线本地包 register/unregister/status，自动合并 `publish.xml`）
  - `tools/register-watchdog-task.ps1`（计划任务 register/unregister/status）
  - `tools/register-pdf-menu.ps1` + `tools/open-with-wpspdf.bat` + `tools/open_pdf.py`
    （PDF 右键菜单：起引擎 → 用 WPS 打开该 PDF）
  - `tools/watch_once.py`、`tools/check-engine.bat` + `tools/check_engine.py`
  - `一键安装.bat` / `一键卸载.bat` 改为编排上述四步
- **「在 WPS 里点按钮起引擎」实测封死**（活页面逐条验证）：`ShellExecute` 返回成功但不执行、
  `Application/wps.CreateObject` 报 `Load dll fail`、`CoCreateInstance` 报 `cannot create`。
- 坑记录：`$action` 变量与 PowerShell 参数 `-Action` 撞名导致 `New-ScheduledTaskAction` 注册失败；
  XmlElement 的 `.Name` 在 PowerShell 里被同名属性覆盖，写 `publish.xml` 必须用 `.LocalName`。

## v1.3.2 — 2026-11-27

**把「页签为什么不出现」和「关闭是不是卡死」两件事查到底，并留证据**

- **页签注册时机（实测）**：功能区页签只在 **WPS 进程启动**时注册一次。
  - 引擎未起 → `ribbon.xml` 取不到 → 无页签（`GET /pdf/ribbon.xml 200` 是唯一判据）；
  - 引擎后起、或改过 `publish.xml` 之后，**已在运行的 WPS 进程不会补注册**，
    必须完全退出 WPS（不是只关文档）再开。实测：同一进程里重开文档，`page-loaded` 有、
    `ribbon.xml` 也 200，但页签仍是旧的「阅读 / 增值服务」；杀掉 WPS 重开 → `阅读 | 增值服务 | PDF转表格`。
- **「关闭卡死」A/B 结论：与插件无关**。关闭这份 24MB 大 PDF 后进程不退出（界面 `Hung=False`，CPU 增量 0），
  原因是 WPS 留了一个空的「WPS Office」窗口；**关掉空窗口 → 进程 1s 退出**。
  禁用加载项（`enable="disable"`）重复同一操作，25s 后进程同样不退出 → 排除插件。
- **离线本地包注册失败**（记录以免重复尝试）：把 `publish.xml` 写成
  `jsplugin url="D:/Github/WPSPDF/addon-pdf/"` 本地目录后打开 PDF，页签不出现
  （`evidence/offline-test-tabrow.png`）。本机 WPS 只认 http 托管的 `jspluginonline`，
  所以「不依赖引擎也能出页签」这条路在本版本走不通。
- 插件加固：`poll.js` 的 `beforeunload`/`pagehide` 置 `STOPPED` 并停轮询；`tp.js` `pagehide` 清定时器。
- 新增 `tools/check-engine.bat` + `tools/check_engine.py`：一键判断引擎是否在线（38731–38734 轮询 `/ping`）。
- 引擎版本仍 1.3.1（本次只改加载项与工具，服务端未变）。

## v1.3.1 — 2026-11-26

**修「PDF 窗口卡死」与「页签时有时无」两个线上问题**

- **卡死（用户报「WPS 的 PDF 还卡死了」）**：旧 `poll.js` 在引擎不可达时，每 15 秒向 PDF 宿主调一次
  `wps.OAAssist.ShellExecute` 想拉起引擎。WPS 个人版对该调用是**静默拦截**（返回成功但不执行），
  这次同步调用停在宿主内部 → 页面与 UI 线程被拖死。时间线吻合：引擎 23:14 空闲退出后窗口开始卡死。
  修：**彻底删除自动拉起**，失败只做指数退避（1.2s→15s 封顶）并上报一次 `engine-down`；
  同时删掉 `util.js` 里的同步 XHR 死代码（`xhr.open(...,false)` 在 CEF 后台页会被拦，端口不通时会阻塞），
  改为 `fetch` + `AbortController` 超时；`loop()` 加单例守卫，避免重复注入跑多个循环。
- **页签时有时无**：加载项的 `ribbon.xml` 与页面都由本地引擎 http 托管。引擎默认 300 秒空闲退出后，
  WPS 再打开 PDF 取不到 `ribbon.xml` → **页签直接不出现**（用户截图里只剩「阅读 / 增值服务」就是这个）。
  修：引擎生存期改为**跟随 WPS 进程**（`wpsoffice/wpspdf/et/wpp` 任一在跑就常驻），WPS 全关后才算空闲；
  并补注册开机自启（此前 HKCU Run **根本没有**该条目，是页签消失的另一半原因）。
- **实测链路（23:35–23:37）**：`GET /pdf/ribbon.xml 200` → `page-loaded` → 页签行出现
  `阅读 | 增值服务 | PDF转表格`（`evidence/wps-pdf-tabrow-now.png`）→ `/cmd` 轮询稳定 →`jsver` 回报 **1.3.1**
  → `taskpane ok`（`evidence/wps-pdf-pane.png`）。
- 口径：`增值服务` 是 WPS 自带页签，第三方加载项**无法插按钮进去**，只能并列一个自己的页签；
  这是 WPS 的扩展边界，不是配置问题。
- 引擎版本 1.3.0 → **1.3.1**。

## v1.3.0 — 2026-11-26

**数据完整性（这一版修的是「静默丢字」，不是体验）**

- **修「正式答辩时段」整列丢失**：根因是第 1 页有 10 条矢量列边界（xs 到 786），第 2–18 页只画到 694，
  x≈739 的每行文字被判「网格外」直接丢弃——577 行里 540 行为空。改为**跨页并集列边界** +
  `xs_is_subset` 结构校验（页内边界是并集子集时才补齐，版式不同的页不硬套）。
  实测：第 10 列非空 37 → **568/577**（差额 9 行是原 PDF 自带的分组间隔行）。
- **修长标题换行颠倒**：原来按 `(y, x)` 排序，同一文本行的两块 y 只差 0.1pt 就会把右边的块排到前面
  （xlsx 第 98 行曾读出 `古城池数字化复原》《城垣万象`）。改为**先按 y 聚类成行（LINE_TOL 3pt）、行内按 x 排**。
  实测：`《城垣万象古城池数字化复原》` 顺序正确。
- **修「恒我」这类短文本整块被滤**：RapidOCR 默认 `text_score=0.5`，该格整页识别分只有 0.40 被丢弃。
  降阈值到 **0.35**；低分格由标黄 + 校对清单兜底，不静默混入。
- **空单元格二次识别**：只对「该行有内容、该格没文字、且格内有墨」的格子做单元格级 OCR（300dpi）。
  判墨必须**内缩 1.5pt**——不内缩会把格子的 1px 边框当成墨，空格全被判有墨（假阳性）且白跑推理。
  留白要多档试 `pad=(2.0, 0.0, 3.0)`：贴边常被判「无文本」，留 2pt 才稳。
  实测补回 `李瑞`（p7 r8 指导教师）、`六章`（p13 r12 标题）等 10 格。
- **序号序列校验**：`093` 被 OCR 读成 `E60`（前后是 092/094），按「前后只差一行」补回。
  实测序号 **1–568 连续、零断点、无非数字**。
- **质量自检指标**：转换日志新增「未落格 / 空单元格补救 / 仍有墨未识别 / 低置信度 / 序号修复」，
  其中「仍有墨未识别」实测为 **0**（= 没墨的格确实空，有墨的格都出了字）。

**可校对性**

- 低于 `LOW_SCORE=0.55` 的单元格标黄，并新增第二个工作表 **「需校对」**（页 / 行号 / 列名 / 当前内容 / 置信度），
  本样本 25 处，例如 `胡`（应 `胡赟`）、`郸区`（应 `刘峥`）——这类是 OCR 模型极限，标出来让人一眼核对，
  比再猜一次更诚实。
- 首行冻结 + 自动筛选，578 行可直接筛。

**性能**

- **页级 OCR 缓存**：键 = 文件内容哈希 + 页号 + dpi，落 `.run/ocr_cache/`。
  同一份 PDF 重转：113s（v1）→ **9–19s**（含 xlsx 写出）。
- **多进程实测无收益**：本机 32 逻辑核 / 3.6 GB 空闲下 2 进程 120.9s、1 进程 118.5s，
  且 4 进程会因内存争用变慢（255s）。改为默认单进程，`WPSPDF_WORKERS` 可覆盖。

**其它**

- 引擎版本号 1.2.0 → **1.3.0**。
- 证据：`evidence/diag-p2-top.png`（038 行确有「恒我」）、`diag-residual-*`、`diag-low-*`。
- 复核：集成测试走引擎 `POST /convert` → 18 页 19 秒（缓存暖）→ 产物写入 `output\`。

## v1.2.2 — 2026-11-26

- 引擎空闲自动退出：超时优先级 `WPSPDF_IDLE_TIMEOUT`（环境变量）> `.run/idle_timeout`（文件，写秒数）> **默认 300 秒**；`0` = 常驻。
  ｜加载项页面每 1.2s 轮询会持续保活，所以 **WPS 开着不会退**；WPS 关掉后 5 分钟自动退出。
- 实测：隔离实例（端口 38735、idle=15s）在 25 秒无访问后自行退出；正式实例自报 `idle_timeout_s: 300`。
- 占用参考：常驻时 `pythonw.exe` 约 51 MB、7 分钟累计 CPU 0.4 秒。

## v1.2.1 — 2026-11-26

- **完成后由引擎自动打开产物**（`os.startfile`），不再依赖窗格页面：窗格是后台页，CEF 会节流其定时器，页面侧「感知完成→打开」不可靠。
  `/convert` 支持 `{"open": false}` 关闭该行为；`/job` 返回 `opened` / `open_error`。
- **进度/ETA 修正**：转换子进程改为 `-u` 无缓冲（`PYTHONUNBUFFERED=1`），否则 `pages_done` 一直是 0、ETA 不会收紧。
  实测：5/18 时 ETA 126s → 12/18 时 44s，稳定 7.4 秒/页。

## v1.2.0 — 2026-11-26

- 引擎：`/job` 增加 `pages_total/pages_done/elapsed_s/eta_s/percent`；新增 `/jobs`、`/cmd`、`/evalcode`（devmode 下）。
- 引擎生命周期：`WPSPDF_IDLE_TIMEOUT` 默认 0（常驻）；`tools/engine-silent.vbs` 静默启动；`stop-engine.bat` 停止。
- 安装：publish.xml 写 et + pdf 两条在线条目；创建桌面/开始菜单「启动引擎 / 停止引擎」快捷方式；注册 HKCU Run 自启（`-NoAutostart` 可跳过）。
- 前端：`main.js` 改用 onload 链式加载并带 `?v=` 缓存击穿（`document.write` 在动态脚本中会清空页面）；窗格复用不再重建；进度以引擎为准，重开窗格自动接管。
- 实测结论：WPS 个人版拦截加载项启动外部进程（ShellExecute 无效、CoCreateInstance 不可用）。

## v1.1.1 — 2026-11-26

- 功能区图标：`addon-pdf/images/{convert,batch,check}.png`（32×32 实心笔画），`GetImage` 返回相对路径，`ribbon.xml` 用 `size="large"`。
- 实测结论：WPS PDF 宿主把 32px 图标缩到约 16px 渲染，细线条稿会消失；必须用实心/粗笔画。
- 引擎新增 `/cmd`（含 `activatetab`）与 `/addinlog`，用于无鼠标、无前台切换的验证通道。

## v1.1.0 — 2026-11-26

- **PDF 侧入口**：新增 `addon-pdf/` 独立包，`publish.xml` 条目 `type="pdf"`，页签「PDF转表格」出现在 WPS PDF 阅读窗口。
  ribbon 回调遵循 PDF 宿主约束（`Application.ribbonUI` 不可重定义 → 句柄存 `WPSPDF_RIBBON`；不使用 `getImage`）。
- `addon-pdf/js/util.js`：`currentPdfPath()` 逐字段试探 `ActiveDocument.FullName` / `Path`+`Name`。
- **引擎 v1.1.0**：单进程同时托管 `/et/*`、`/pdf/*` 静态资源 + `POST /convert` 任务 + `GET /job/<id>` 轮询 + `GET /open?path=` 打开产物；端口 38731 起自动顺延。
- `engine/convert.py`：落盘改为临时文件 + 原子替换，被占用时改存 `<name>-HHMMSS.xlsx`；输出 `OUT=<path>` 供引擎解析。
- `engine/floatbar.py`：置顶悬浮条（备用入口，吸附 WPS 窗口右上角，只在 WPS 前台时出现）。
- `tools/convert-here.bat`：把 PDF 拖上去即转换。
- 修复：`manifest.xml` 缺 `<Functions>` 导致只加载页面、不注册页签。

## v1.0.0-P0 — 2026-11-26

- 新建 WPS 表格加载项骨架：`ribbon.xml`、`index.html` + `main.js`、`js/util.js`、`js/ribbon.js`、`ui/taskpane.html`、`images/*.svg`、`manifest.xml`。
- 本地引擎 `engine/server.py`（v1.0.0）：`/ping` `/version` `/status` `/shutdown` `/convert`(501)。
- 安装/卸载：`tools/install.ps1`（备份 publish.xml + 合并条目 + 标记）、`tools/uninstall.ps1`（安全断言 + 精确移除）、`一键安装.bat` / `一键卸载.bat`。
- 证据：`evidence/baseline-*.txt`、`evidence/install-pre-*.json`。

## v1.4.1 — 2026-11-27

**窗格里加「启动引擎」按钮；并查清「页签忽然消失」的第三个原因**

- 窗格 `tp.js` / `taskpane.html`：
  - 引擎未就绪时显示 **「启动引擎」** 按钮与说明；点击后进入等待态，每 2 秒自检，就绪即自动接管（不需要再点第二次）。
  - 新增 5 秒健康检查：引擎中途挂掉/恢复，面板都会自己切换，不停留在过期状态。
  - 按钮**不能直接创建进程**（见下），语义是「已请求 + 等待系统按需拉起」，最多 60 秒。
- **又堵死三条通道**（活页面实测，与前三条一起构成完整结论）：`<a href="wpspdf://...">` 点击无效、
  `window.open('wpspdf://...')` 被拦（返回 null）、`wps.OpenWebUrl` 对 `wpspdf://` 与 `file://...bat` 均不触发。
  已注册 `HKCU\Software\Classes\wpspdf` 协议处理器做对照，标记文件 `protocol-hit.txt` 从未生成。
- **「页签忽然消失」的第三个原因：WPS 的加载项完整性校验**。
  在 WPS 运行期间覆盖 `jsaddons\WPSPDFPdf_1.0.0` 会弹
  「加载项 "WPSPDFPdf" 已经被修改，是否…」（`evidence/pane-now-dialog.png`），确认前**页签被扣住**。
  → `tools/install-offline.ps1` 增加保护：检测到 WPS 进程在跑就直接报错退出，要求先完全退出。
- 记录：本次自查时 `PrintWindow` 对功能区抓图会返回**同一张旧位图**（两次抓图 sha256 完全相同），
  不能作为「页签是否出现」的判据；以用户实机截图/`GET /pdf/ribbon.xml` 日志为准。

## v1.5.0 — 2026-11-27

**按参考实现的分层结构重做「按需启动」：删掉每分钟轮询，改为轻量加载器 + 真·一键按钮**

背景：用户指出「计划任务每分钟检查」本身就是常驻轮询，不满足按需。查证后确认这不是本项目独有难题，
开源实现 LocalReadTranslate 的
[iteration-14「Word/WPS 自动加载与完整服务按需启动」](https://raw.githubusercontent.com/Yan-ShiBo/LocalReadTranslate/main/docs/iteration-14-2026-07-29-addin-on-demand-startup.md)
把同一问题总结为「循环依赖」：页面由本地服务提供、服务不跑就看不到启动按钮。
它的解法是**两层结构**，本轮照此落地。

- **新增轻量加载器** `engine/loader.py`（127.0.0.1:38730）：
  只导入 Python 标准库，不加载 OCR/模型；实测 `pythonw` **27 MB / 5 线程 / 3 秒 CPU 增量 0**。
  端点：`GET /ping`、`POST /start`（拉起引擎）、`GET /status`、`POST /shutdown`。
  登录自启：`%APPDATA%\...\Startup\WPSPDF Add-in Loader.lnk`（`tools/install-loader.ps1`）。
- **窗格按钮变成真的一键**：引擎离线时点「启动引擎」→ `POST 127.0.0.1:38730/start`
  → 加载器创建进程 → 引擎就绪 → 窗格自动接管（每 2 秒自检，不用点第二次）。
  实测：离线 → `POST /start` → **3.7 秒**内 `started:true, port:38731`。
- **删除计划任务 `WPSPDF-EngineOnDemand`**（每分钟轮询）——用户指出它等于常驻。
  现在常驻的只有加载器；**重引擎依然只在点按钮时启动，且 WPS 关了 20 秒自行退出**。
- 加载器两处坑（都已修）：
  1. `/ping` 里同步探测引擎（4 端口 ×1s）→ 客户端 3s 超时必失败；改成 0.2s×4，实测 0.84s 返回。
  2. `allow_reuse_address` 开着时 Windows 允许两个实例同时 bind 38730 → 双实例争抢；
     关闭该选项 + 增加单实例守卫（启动先探测 `/ping`，已有则退出）。
- 协议通道尝试全部无效并已清理：注册 `wpspdf://` + 标记文件对照，
  `wps.OpenWebUrl('wpspdf://…')`、`<a href>` 点击、`window.open` 均不触发；注册表项已删除。

## v1.6.0 — 2026-11-27

**定为「零常驻」方案：只保留 PDF 右键菜单入口；菜单项补上图标**

用户选定：保留右键菜单，零常驻（不留加载器），并给菜单加图标。

- **零常驻**：`tools/install-loader.ps1 -Action unregister` → 启动项快捷方式删除、加载器退出。
  复核：`38730` 无监听、Startup 目录无 WPSPDF 条目、无计划任务。系统里不再有本项目任何常驻进程。
- **右键菜单图标**：Windows 右键菜单只认 `.ico`，原先指向 `.png` 所以显示通用文档图标。
  新增 `addon-pdf/images/wpspdf.ico`：1024 画布矢量式绘制（品牌蓝圆角底 + 白色表格网格 + 绿色对勾）
  再下采样，含 **16/20/24/32/40/48/64/128/256** 九个尺寸；`register-pdf-menu.ps1` 改为写
  `Icon = <路径>.ico,0`（路径不加引号，最兼容）。
  校验：`ExtractIconEx` 返回可读，导出 32px 预览见 `evidence/menu-icon-128.png`。
- 窗格文案改为引导右键入口（零常驻下加载器不存在，按钮只能等待）。
- `一键安装.bat` 改为「离线包 + 右键菜单」两步，并注明想要一键按钮时可另行安装加载器；
  `一键卸载.bat` 增加移除计划任务与加载器自启两步。

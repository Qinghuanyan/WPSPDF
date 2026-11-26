# CHANGELOG — WPSPDF

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

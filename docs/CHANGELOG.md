# CHANGELOG — WPSPDF

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

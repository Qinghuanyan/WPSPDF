# CHANGELOG — WPSPDF

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

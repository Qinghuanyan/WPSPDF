# Project — WPSPDF

把「文字已转曲、WPS 搜不到」的 PDF 表格，还原成可筛选的 WPS 表格。
入口在 **WPS 里**（PDF 窗口 + 表格窗口各一个页签），转换由本机 Python 引擎完成。

## 现状（2026-11-26）

- 引擎：`engine/`，v1.1.0，单进程同时做「静态托管 + 转换任务 + 打开产物」，只绑 `127.0.0.1:38731`（占用则顺延 38732–38734）。
- 加载项：两套包，两种 `type`
  - `addon/` → `type="et"` → 出现在 **WPS 表格**（页签「PDF转表格」）
  - `addon-pdf/` → `type="pdf"` → 出现在 **WPS PDF 阅读窗口**（页签「PDF转表格」）
- 本机 WPS：**12.8.2.18913**，装在 `D:\WPS Office\12.8.2.18913\office6`
- 加载项部署点：`%APPDATA%\kingsoft\wps\jsaddons\publish.xml`，条目形如
  `<jspluginonline name type url debug enable install customDomain/>`，`type` 取 `et` / `pdf` / `wps` / `wpp`。

## 关键链路（实测有效）

1. WPS 启动 → 读 `jsaddons\publish.xml` → 按 `type` 分发到对应组件
2. 组件拉取包的 `manifest.xml`（**必须有 `<Functions>` 段**，否则只加载页面、不注册页签）
   → `ribbon.xml` → `index.html` → `main.js` → `js/*.js`
3. 点击按钮 → `OnAction(control)` → 同步 XHR 调 `127.0.0.1:38731`
4. `POST /convert {path}` 建任务 → `GET /job/<id>` 轮询 → `GET /open?path=` 用 WPS 表格打开产物

## PDF 宿主的特殊约束（来自实测与 LocalReadTranslate 记录）

- `Application.ribbonUI` **不可重定义** → 句柄只存模块变量（`WPSPDF_RIBBON`）
- 图标不要用 `getImage` 返回相对路径（会被拼错），当前直接不给图标
- 选区文本入口是 `Application.ActiveDocument.Selection.Text()`；
  文档路径字段各版本不一致，`util.js:currentPdfPath()` 逐字段试探（`FullName` → `Path` + `Name`）

## 转换管线（`engine/convert.py`）

```
PDF → 矢量框线聚类出 (ys, xs) 行列边界（grid.py，坐标精确、不受 OCR 误差影响）
    → 整页 200dpi 栅格化 → RapidOCR(det+rec) → 文本框
    → 文本框中心落格 → 单元格文本（多行按 y 排序拼接）
    → openpyxl 写出（列宽按网格宽、字号 9pt 宋体）
```
基准样本：18 页、0 字体、0 文本对象、约 1100 条矢量路径/页。第 1 页实测 38 行 × 10 列、OCR 398 块、约 13 秒。

## 回退

| 层面 | 回退方式 |
|---|---|
| 加载项 | `一键卸载.bat`（删 `jsaddons\WPSPDF_1.0.0`、清 publish.xml 条目、空目录一并删）；装前状态在 `evidence\install-pre-*.json` |
| 引擎/悬浮条进程 | 直接结束进程；无注册表项、无开机自启 |
| 全局包 | `npm uninstall -g wpsjs` |
| 产物 | `output\*.xlsx` |

## 已知限制

- 合并单元格未还原（跨列文本会落到右侧列）
- 多行单元格的换行顺序偶有颠倒
- 扫描件（整页位图）走同一条 OCR 路径，但没有矢量框线，网格会退化成页框 → 需要后续版本单独处理
- 转换 ≈ 8–13 秒/页（CPU），18 页约 2–3 分钟；无缓存

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

## 转换管线（`engine/convert.py` v1.3）

```
PDF → 各页竖线 → 跨页并集列边界 canon（补齐「某页末列没画右边框」缺的列；
       仅当页内边界是 canon 子集时才套用，版式不同的页不硬套）
    → 每页横线聚类出 ys（行边界）
    → 整页 200dpi 栅格化 → RapidOCR(det+rec, text_score=0.35) → 文本框（页级缓存到 .run/ocr_cache/）
    → 文本框中心落格（locate）
    → 空单元格二次识别：该行有内容 && 该格无字 && 格内有墨（内缩 1.5pt 判墨、pad 2/0/3 多档）
    → 单元格文本：先按 y 聚类成行（LINE_TOL 3pt），行内按 x 排，行间按 y 排
    → 序号序列校验（非数字格按前后值补回）
    → openpyxl 写出（列宽按网格宽、9pt 宋体、首行冻结、自动筛选、低分标黄 + 「需校对」工作表）
```
基准样本：18 页、0 字体、0 文本对象、约 1100 条矢量路径/页。
v1.3.0 实测：578 行 × 10 列；序号 1–568 连续；第 10 列 568/577 有值；`仍有墨未识别 0`；
首次 118 秒（单进程）、缓存命中 9–19 秒。

## 回退

| 层面 | 回退方式 |
|---|---|
| 加载项 | `一键卸载.bat`（删 `jsaddons\WPSPDF_1.0.0`、清 publish.xml 条目、空目录一并删）；装前状态在 `evidence\install-pre-*.json` |
| 引擎/悬浮条进程 | 直接结束进程；无注册表项、无开机自启 |
| 全局包 | `npm uninstall -g wpsjs` |
| 产物 | `output\*.xlsx` |
| OCR 缓存 | 删 `.run\ocr_cache\`（下次转换重跑 OCR） |

## 已知限制

- 真正「一格横跨两列」的合并版式无样本、未实现；本样本只在第 1 页末列出现「横线缺失」，
  数据逐行重复，按行落值更利于筛选，故不做合并
- 低置信度格（<0.55）可能读错（如 `胡赟`→`胡`、`刘峥`→`郸区`）：标黄 + 「需校对」工作表列出，需人工确认
- 扫描件（整页位图）走同一条 OCR 路径，但没有矢量框线，网格会退化成页框 → 需要后续版本单独处理
- 速度：首次约 6.5 秒/页（200dpi 单进程）；多进程实测无收益（onnxruntime 已多线程 + 内存争用）

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

# P0 实测结论（2026-11-26 15:17–15:40）

## 做了什么

1. 基线快照：`baseline-20261126-151724.txt`（`jsaddons` 目录**原本不存在**，WPS 未运行，无 Run 项）
2. 全局装 `wpsjs@2.2.3`（可 `npm uninstall -g wpsjs` 撤销）
3. 从 `wpsjs` 源码确认加载项部署契约（非猜测）：
   - `src/lib/build.js`：`jsaddons\<name>_<version>\` + `jsaddons\publish.xml`，
     条目 `<jsplugin name type url version enable install customDomain>`，`type` = `addonType`（`et`/`wps`/`wpp`）
   - `src/lib/debug_publish.js`：线上调试形态是 `<jspluginonline ... url="http://127.0.0.1:PORT/" debug="" enable="enable_dev" ...>`
4. 写加载项：`ribbon.xml`（PDF 工具 / 4 按钮）、`index.html`+`main.js`、`js/util.js`、`js/ribbon.js`、`ui/taskpane.html`、`images/*.svg`、`manifest.xml`
5. 写引擎：`engine/server.py`（127.0.0.1:38731，`/ping` `/version` `/status` `/shutdown` `/convert`=501，端口 38731→38734 回退）
6. 写安装/卸载：`tools/install.ps1`、`tools/uninstall.ps1`、`一键安装.bat`、`一键卸载.bat`

## 已验证通过

| 项 | 证据 |
|---|---|
| 引擎只监听回环 | `netstat` 仅 `127.0.0.1:38731 LISTENING`；`curl /ping` 返回 `{"ok":true,...}` |
| 安装可执行 | `install.ps1` 退出码 0，生成 `jsaddons\WPSPDF_1.0.0\` + `publish.xml` + 标记 |
| **回退可执行** | `uninstall.ps1` 后 `jsaddons` 目录整体消失（`Test-Path = False`），与基线一致 |
| 离线(`jsplugin`)形态 | 未加载：CEF 缓存里无页面引用 |
| **在线(`jspluginonline`)形态** | **加载项页面确实被加载**：`.../jsapi/cache` 中出现 `127.0.0.1:38740`、`WPSPDF`、`index.html`、`main.js`、`ribbon.xml` 引用 |

## 未通过（P0 门禁卡点）

**已解决**：原因是 `manifest.xml` 缺少 `<Functions>` 段。
补上 `<Functions><Uri>/functions.json</Uri><Namespace>WPSPDF</Namespace></Functions>` 并放置
`functions.json`（`{"functions": []}`）后重启，WPS 表格页签行出现 **「PDF转表格」**（截图 `wps-p0-10-tabrow.png`，位于「自定义」右侧）。

结论口径：
- `publish.xml` 条目 → 只是“让 WPS 加载这个页面”；
- `manifest.xml` 的 `<Functions>` → 决定“是否注册为功能区插件（ribbon）”。
两者都齐才出页签；先前的失败正是只满足前者。

## 仍然存在的限制（架构级，非配置问题）

~~**WPS 的 PDF 阅读组件不加载 jsaddons 页签。**~~
**该结论已于 2026-11-26 15:55 被推翻。** 依据
[LocalReadTranslate 的 WPS PDF 加载项迭代记录](https://github.com/Yan-ShiBo/LocalReadTranslate/blob/main/docs/iteration-9-2026-07-23-wps-pdf-addin.md)，
并用本机 WPS 12.8.2.18913 实测：

- `publish.xml` 里的 `<jspluginonline type="pdf" url="...">` 会被 **PDF 组件**读取；
- PDF 会拉取包的 `manifest.xml` / `ribbon.xml` / `index.html` / `main.js`；
- 页签确实出现在 PDF 窗口（`evidence/pdf-addin-03.png`：`阅读 | 增值服务 | PDF转表格`）。

PDF 宿主的两条特有约束：
1. `Application.ribbonUI` 不可重定义 → ribbon 句柄只存模块变量（`WPSPDF_RIBBON`）；
2. 图标别用 `getImage` 返回相对路径（会被拼到包路径后面出错），当前直接不给图标。

教训：**不要把「组件没有文档对象模型」等同于「组件不能挂加载项」**——两者是不同层面的事，
前者只影响能读什么，后者决定有没有入口。



## 当前机器状态（如需立刻复原）

- `%APPDATA%\kingsoft\wps\jsaddons\` 存在（本工具创建）：`WPSPDF_1.0.0\`、`publish.xml`（**线上形态**，指向 `http://127.0.0.1:38740/`）、`.wpspdf-installed`
- 常驻进程：引擎 `127.0.0.1:38731`（后台 job）、静态服务 `127.0.0.1:38740`（`py -m http.server`）
- 复原：`一键卸载.bat` → 删 `addon` 部署产物；停两个进程；WPS 重启

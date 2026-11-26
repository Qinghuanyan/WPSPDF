// PDF 宿主的公共工具（WPS PDF 组件）
// 注意：PDF 里 Application.ribbonUI 不可重定义 → ribbon 句柄只存模块变量
// 注意：**不要在这里用同步 XHR**（xhr.open(..., false)）——CEF 后台页会把它拦住，
//      引擎端口不通时同步请求会卡住宿主 UI 线程（2026-11-26 实测表现为 PDF 窗口卡死）。
//      一律用 async fetch + AbortController 超时。
var WPSPDF_RIBBON = null;
const ENGINE_PORTS = [38731, 38732, 38733, 38734];

function engineBase() {
    return "http://127.0.0.1:" + ENGINE_PORTS[0];
}

function apiJson(path, opts) {
    const ctl = new AbortController();
    const t = setTimeout(function () { ctl.abort(); }, (opts && opts.timeoutMs) || 4000);
    return fetch(engineBase() + path, {
        method: (opts && opts.method) || "GET",
        headers: { "Content-Type": "application/json" },
        body: opts && opts.body ? JSON.stringify(opts.body) : undefined,
        signal: ctl.signal,
        cache: "no-store"
    }).then(function (r) { clearTimeout(t); return r.json(); })
      .catch(function (e) { clearTimeout(t); throw e; });
}

// 取当前 PDF 的完整路径（不同版本字段名不一致，逐个试）
function currentPdfPath() {
    try {
        const doc = Application.ActiveDocument;
        if (!doc) return "";
        const cands = ["FullName", "Path"];
        for (let i = 0; i < cands.length; i++) {
            try {
                const v = doc[cands[i]];
                if (v && typeof v === "string" && /\.pdf$/i.test(v)) return v;
            } catch (e) {}
        }
        try {
            const p = doc.Path, n = doc.Name;
            if (p && n) return p.replace(/[\\\/]$/, "") + "\\" + n;
        } catch (e) {}
        return "";
    } catch (e) {
        return "";
    }
}

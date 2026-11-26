// PDF 宿主的公共工具（WPS PDF 组件）
// 注意：PDF 里 Application.ribbonUI 不可重定义 → ribbon 句柄只存模块变量
var WPSPDF_RIBBON = null;
const ENGINE_PORTS = [38731, 38732, 38733, 38734];

function engineBase() {
    return "http://127.0.0.1:" + ENGINE_PORTS[0];
}

function httpJson(method, url, body, timeoutMs) {
    const xhr = new XMLHttpRequest();
    xhr.open(method, url, false);
    xhr.timeout = timeoutMs || 3000;
    if (body) xhr.setRequestHeader("Content-Type", "application/json");
    try { xhr.send(body ? JSON.stringify(body) : null); } catch (e) { return { ok: false, error: String(e) }; }
    if (xhr.status !== 200) return { ok: false, status: xhr.status, error: xhr.responseText };
    try { return { ok: true, data: JSON.parse(xhr.responseText) }; } catch (e) { return { ok: false, error: "bad json" }; }
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

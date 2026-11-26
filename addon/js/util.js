// 公共工具：枚举、路径、本地引擎探测
var WPS_Enum = {
    msoCTPDockPositionLeft: 0,
    msoCTPDockPositionRight: 2
};

function GetUrlPath() {
    let e = document.location.toString();
    return -1 != (e = decodeURI(e)).indexOf("/") && (e = e.substring(0, e.lastIndexOf("/"))), e;
}

// ── 本地引擎（Python，stdlib HTTP）──────────────────────────────
// 端口与 engine/server.py 保持同步；多个备选用于端口占用时自动试探
const ENGINE_PORTS = [38731, 38732, 38733, 38734];

function engineBase() {
    try {
        let cached = window.Application.PluginStorage.getItem("engineBase");
        if (cached) return cached;
    } catch (e) { /* 任务窗格上下文可能拿不到 PluginStorage */ }
    return "http://127.0.0.1:" + ENGINE_PORTS[0];
}

// 同步 XHR：OnAction 回调需要同步返回结果，fetch 是异步的
function engineCallSync(path, timeoutMs) {
    const ports = ENGINE_PORTS;
    for (let i = 0; i < ports.length; i++) {
        const url = "http://127.0.0.1:" + ports[i] + path;
        try {
            const xhr = new XMLHttpRequest();
            xhr.open("GET", url, false);
            xhr.timeout = timeoutMs || 1500;
            xhr.send(null);
            if (xhr.status === 200) {
                try { window.Application.PluginStorage.setItem("engineBase", "http://127.0.0.1:" + ports[i]); } catch (e) {}
                return { ok: true, port: ports[i], body: xhr.responseText };
            }
        } catch (e) { /* 换下一个端口 */ }
    }
    return { ok: false, port: -1, body: "" };
}

function engineAlive() {
    return engineCallSync("/ping", 800);
}

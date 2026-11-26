// 服务端驱动通道（v1.3.1）
//
// 教训（2026-11-26 实机）：PDF 宿主里**绝对不能**反复调 wps.OAAssist.ShellExecute。
// 引擎空闲退出后，旧版每 15 秒调一次 ShellExecute 想拉起引擎，WPS 个人版会静默拦截，
// 这次同步调用停在宿主内部，把 PDF 窗口拖到卡死。
// 所以本版：不自动拉起进程、失败退避、循环单例、永不阻塞。

const CMD_PORTS = [38731, 38732, 38733, 38734];
let CMD_BASE = null;
let pollCount = 0;
let failStreak = 0;
let reportedDown = false;
const INST = Date.now().toString(36);

function post(path, obj) {
    try {
        fetch((CMD_BASE || "http://127.0.0.1:" + CMD_PORTS[0]) + path, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(obj || {})
        }).catch(function () { });
    } catch (e) { }
}

function report(obj) { obj.inst = INST; post("/log", obj); }

function getText(path) {
    return new Promise(function (resolve) {
        const ports = CMD_BASE ? [CMD_BASE] : CMD_PORTS.map(p => "http://127.0.0.1:" + p);
        let i = 0;
        function next() {
            if (i >= ports.length) { resolve(null); return; }
            const base = ports[i++];
            const ctl = new AbortController();
            const t = setTimeout(function () { ctl.abort(); }, 1000);
            fetch(base + path, { signal: ctl.signal, cache: "no-store" })
                .then(function (r) { clearTimeout(t); if (!r.ok) throw new Error(r.status); CMD_BASE = base; return r.text(); })
                .then(resolve)
                .catch(function () { clearTimeout(t); next(); });
        }
        next();
    });
}

function selftest() {
    try {
        const d = Application.ActiveDocument;
        report({
            ev: "selftest",
            docName: d ? (d.Name || "") : "(no ActiveDocument)",
            path: currentPdfPath(),
            hasRibbon: !!WPSPDF_RIBBON
        });
    } catch (e) {
        report({ ev: "selftest-error", err: String(e && e.message ? e.message : e) });
    }
}

function handleCmd(cmd) {
    report({ ev: "cmd-recv", cmd: cmd });
    if (cmd === "selftest") { selftest(); return; }
    if (cmd === "convert") { convertCurrent(); return; }
    if (cmd === "taskpane") { report({ ev: "taskpane", ok: openPane() }); return; }
    if (cmd === "activatetab") {
        let r = "";
        try { Application.ribbonUI.ActivateTab("tabWpsPdfReader"); r = "ok"; }
        catch (e) { r = String(e.message || e); }
        report({ ev: "activatetab", r: r });
        return;
    }
    if (cmd === "jsdiag") {
        let info = {};
        try { info.wps = typeof wps; } catch (e) { info.wps = "ERR:" + e.message; }
        try { info.appKeys = Object.keys(Application).slice(0, 25).join(","); } catch (e) { info.appKeys = "ERR:" + e.message; }
        report({ ev: "jsdiag", info: info });
        return;
    }
    if (cmd === "eval") {      // 仅调试通道：必须由引擎显式下发才执行
        fetch((CMD_BASE || ("http://127.0.0.1:" + CMD_PORTS[0])) + "/evalcode", { cache: "no-store" })
            .then(function (r) { return r.text(); })
            .then(function (code) {
                try { report({ ev: "eval-ok", out: String(eval(code)) }); }
                catch (e) { report({ ev: "eval-err", err: String(e && e.message ? e.message : e) }); }
            })
            .catch(function (e) { report({ ev: "eval-fetch-err", err: String(e) }); });
        return;
    }
    if (cmd === "jsver") { report({ ev: "jsver", ver: "1.3.1" }); }
}

function loop() {
    // 单例：避免脚本被重复注入后多个循环同时抢 /cmd
    if (window.__WPSPDF_LOOPING) return;
    window.__WPSPDF_LOOPING = true;

    function tick() {
        pollCount++;
        getText("/cmd").then(function (txt) {
            if (txt === null) {
                // 引擎不在：只退避，不拉起进程（拉起会卡死 PDF 宿主）
                failStreak++;
                if (!reportedDown) {
                    reportedDown = true;
                    report({ ev: "engine-down", streak: failStreak });
                }
                const wait = Math.min(15000, 1200 * Math.pow(2, Math.min(failStreak, 4)));
                setTimeout(tick, wait);
                return;
            }
            if (reportedDown) { reportedDown = false; report({ ev: "engine-up", after: failStreak }); }
            failStreak = 0;
            let cmd = null;
            try { cmd = JSON.parse(txt).cmd; } catch (e) { }
            if (cmd) { try { handleCmd(cmd); } catch (e) { report({ ev: "cmd-error", err: String(e && e.message ? e.message : e) }); } }
            setTimeout(tick, 1200);
        });
    }
    setTimeout(tick, 800);
}

report({ ev: "page-loaded", href: String(location.href) });
loop();

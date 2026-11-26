// 服务端驱动通道 + 引擎自动拉起
// 说明：CEF 页面不能 spawn 进程，只能用 WPS 的 OAAssist.ShellExecute 拉起本地脚本
const CMD_PORTS = [38731, 38732, 38733, 38734];
const LAUNCHER = "D:\\Github\\WPSPDF\\tools\\engine-silent.vbs";
let CMD_BASE = null;
let pollCount = 0;
let lastLaunch = 0;
let launched = 0;

function post(path, obj) {
    try {
        fetch((CMD_BASE || "http://127.0.0.1:" + CMD_PORTS[0]) + path, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(obj || {})
        }).catch(function () { });
    } catch (e) { }
}

function report(obj) { post("/log", obj); }

function launchEngine() {
    const now = Date.now();
    if (now - lastLaunch < 15000) return;   // 15s 内不重复拉起
    lastLaunch = now;
    launched++;
    const tries = [
        'C:/Windows/System32/wscript.exe "' + LAUNCHER + '"',
        'cmd /c start "" /min wscript.exe "' + LAUNCHER + '"',
        LAUNCHER
    ];
    for (let i = 0; i < tries.length; i++) {
        try {
            wps.OAAssist.ShellExecute(tries[i]);
            report({ ev: "engine-launch", n: launched, form: i });
            return;
        } catch (e) {
            report({ ev: "engine-launch-fail", form: i, err: String(e && e.message ? e.message : e) });
        }
    }
}

function getText(path) {
    return new Promise(function (resolve) {
        const ports = CMD_BASE ? [CMD_BASE] : CMD_PORTS.map(p => "http://127.0.0.1:" + p);
        let i = 0;
        function next() {
            if (i >= ports.length) { resolve(null); return; }
            const base = ports[i++];
            const ctl = new AbortController();
            const t = setTimeout(function () { ctl.abort(); }, 1200);
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

function loop() {
    setTimeout(function () {
        pollCount++;
        getText("/cmd").then(function (txt) {
            if (txt === null) { launchEngine(); loop(); return; }   // 引擎不在 → 拉起
            CMD_BASE = CMD_BASE || ("http://127.0.0.1:" + CMD_PORTS[0]);
            if (pollCount === 1) { report({ ev: "poll-ok", base: CMD_BASE }); }
            let cmd = null;
            try { cmd = JSON.parse(txt).cmd; } catch (e) { }
            if (cmd) {
                report({ ev: "cmd-recv", cmd: cmd });
                if (cmd === "selftest") { selftest(); }
                else if (cmd === "convert") { convertCurrent(); }
                else if (cmd === "taskpane") { report({ ev: "taskpane", ok: openPane() }); }
                else if (cmd === "activatetab") {
                    let r = "";
                    try { Application.ribbonUI.ActivateTab("tabWpsPdfReader"); r = "ok"; }
                    catch (e) { r = String(e.message || e); }
                    report({ ev: "activatetab", r: r });
                }
                else if (cmd === "shelltest") {
                    try {
                        wps.OAAssist.ShellExecute('cmd /c echo shelltest-ok > "D:/Github/WPSPDF/.run/shelltest.txt"');
                        report({ ev: "shelltest", ok: true });
                    } catch (e) {
                        report({ ev: "shelltest", ok: false, err: String(e && e.message ? e.message : e) });
                    }
                }
                else if (cmd === "jsdiag") {
                    let info = {};
                    try { info.wps = typeof wps; } catch (e) { info.wps = "ERR:" + e.message; }
                    try { info.wpsOA = (typeof wps !== "undefined" && wps && wps.OAAssist) ? Object.keys(wps.OAAssist).join(",") : "none"; } catch (e) { info.wpsOA = "ERR:" + e.message; }
                    try { info.appOA = (typeof Application !== "undefined" && Application && Application.OAAssist) ? "yes" : "no"; } catch (e) { info.appOA = "ERR:" + e.message; }
                    try { info.appKeys = Object.keys(Application).slice(0, 25).join(","); } catch (e) { info.appKeys = "ERR:" + e.message; }
                    report({ ev: "jsdiag", info: info });
                }
                else if (cmd === "jsver") { report({ ev: "jsver", ver: "1.2.0" }); }
            }
            loop();
        });
    }, 1200);
}

report({ ev: "page-loaded", href: String(location.href) });
getText("/ping").then(function (t) { if (t === null) launchEngine(); });
loop();

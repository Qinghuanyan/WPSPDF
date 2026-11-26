// WPS PDF 加载项：功能区回调
// 约束：PDF 里 Application.ribbonUI 不可重定义 → 句柄只存模块变量
//     图标不要用 getImage（相对路径会被拼错）

function OnAddinLoad(ribbonUI) {
    WPSPDF_RIBBON = ribbonUI;
    return true;
}

function OnAction(control) {
    const id = control.Id;
    if (id === "btnPdfConvert" || id === "btnPdfBatch") { openPane(); return true; }
    if (id === "btnPdfCheck") { openPane(); return true; }
    return true;
}

// 图标：PDF 宿主对图标路径的解析方式各版本不同，这里返回根相对路径
// （引擎同时把 /images/* 与 /pdf/images/* 都指向同一份文件，两种解析都能命中）
function GetImage(control) {
    var map = {
        btnPdfConvert: "images/convert.png",
        btnPdfBatch: "images/batch.png",
        btnPdfCheck: "images/check.png"
    };
    return map[control.Id] || "images/convert.png";
}

// 打开右侧任务窗格（真正的可见界面，不依赖 alert）
function paneUrl() {
    // 必须是带 scheme+host 的绝对地址，否则 WPS 会当成相对路径导致白屏
    const href = String(location.href);
    return href.replace(/[^\/]*$/, "") + "ui/taskpane.html?v=" + Date.now();
}

function openPane() {
    try {
        let id = null;
        try { id = Application.PluginStorage.getItem("wpspdf_pane_id"); } catch (e) { }
        if (id) {
            try {
                const p = Application.GetTaskPane(id);
                if (p) { p.Visible = true; return true; }   // 复用，不重建 → 转换进度不丢
            } catch (e) { }
        }
        const pane = Application.CreateTaskPane(paneUrl());
        id = pane.ID;
        try { Application.PluginStorage.setItem("wpspdf_pane_id", id); } catch (e) { }
        pane.Visible = true;
        try { pane.Width = 380; } catch (e) { }
        try { pane.DockPosition = 2; } catch (e) { }
        return true;
    } catch (e) {
        return String(e && e.message ? e.message : e);
    }
}

// 提交转换：CEF 后台页里同步 XHR 会被拦，必须用 fetch（异步）
function convertCurrent() {
    const path = currentPdfPath();
    if (!path) {
        if (typeof report === "function") report({ ev: "convert-nopath" });
        return false;
    }
    try {
        fetch(engineBase() + "/convert", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: path })
        }).then(function (r) { return r.json(); })
          .then(function (d) {
              if (typeof report === "function") report({ ev: "convert-submitted", ok: !!d.ok, job: d.job || null, err: d.error || null });
          })
          .catch(function (e) {
              if (typeof report === "function") report({ ev: "convert-error", err: String(e) });
          });
    } catch (e) {
        if (typeof report === "function") report({ ev: "convert-throw", err: String(e) });
        return false;
    }
    return true;
}

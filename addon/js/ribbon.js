// WPSPDF 加载项：Ribbon 回调（WPS 表格 / et）
// 注意：这些函数必须是全局函数，WPS 通过 ribbon.xml 的 onLoad/onAction 直接调用

function OnAddinLoad(ribbonUI) {
    if (typeof (window.Application.ribbonUI) != "object") {
        window.Application.ribbonUI = ribbonUI;
    }
    if (typeof (window.Application.Enum) != "object") {
        window.Application.Enum = WPS_Enum;
    }
    try { window.Application.PluginStorage.setItem("WPSPDFVersion", "1.0.0"); } catch (e) {}
    return true;
}

function OnAction(control) {
    const id = control.Id;
    switch (id) {
        case "btnConvert":
        case "btnBatch":
            showTaskPane();
            break;

        case "btnSelfCheck": {
            const r = engineAlive();
            if (r.ok) {
                alert("本地引擎在线\n端口: " + r.port + "\n响应: " + r.body);
            } else {
                alert("本地引擎未响应\n\n请先启动引擎：\nD:\\Github\\WPSPDF\\tools\\start-engine.bat\n\n（端口已试: " + ENGINE_PORTS.join(", ") + "）");
            }
            break;
        }

        case "btnAbout": {
            const lines = [
                "WPSPDF 1.0.0",
                "",
                "把「文字已转曲、搜不到」的 PDF 表格",
                "还原成可筛选的 WPS 表格。",
                "",
                "项目: D:\\Github\\WPSPDF",
                "回退: tools\\uninstall.ps1"
            ].join("\n");
            alert(lines);
            break;
        }
        default:
            break;
    }
    return true;
}

function showTaskPane() {
    try {
        let tsId = window.Application.PluginStorage.getItem("wpspdf_taskpane_id");
        if (!tsId) {
            const tskpane = window.Application.CreateTaskPane(GetUrlPath() + "/ui/taskpane.html");
            tsId = tskpane.ID;
            window.Application.PluginStorage.setItem("wpspdf_taskpane_id", tsId);
            tskpane.Visible = true;
        } else {
            const tskpane = window.Application.GetTaskPane(tsId);
            tskpane.Visible = !tskpane.Visible;
        }
        try {
            tskpane.Width = 380;
            tskpane.DockPosition = 2; // 右侧
        } catch (e) {}
    } catch (e) {
        alert("无法创建任务窗格: " + e.message);
    }
}

function GetImage(control) {
    switch (control.Id) {
        case "btnConvert": return "images/convert.svg";
        case "btnBatch": return "images/batch.svg";
        case "btnSelfCheck": return "images/check.svg";
        default: return "images/about.svg";
    }
}

function OnGetEnabled(control) {
    return true;
}

function OnGetVisible(control) {
    return true;
}

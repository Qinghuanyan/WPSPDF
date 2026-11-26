# -*- coding: utf-8 -*-
"""按需启动引擎，然后用 WPS 打开指定 PDF。

用途：WPS 的加载项页面**不能**起进程（2026-11-27 实测：ShellExecute 静默无效、
CreateObject 报 Load dll fail、CoCreateInstance 报 cannot create），
所以「按需启动」的入口只能放在 Windows 侧：右键菜单 / 快捷方式调用本脚本。

行为：
  1) 引擎没在线 → 拉起 tools/engine-silent.vbs（静默无黑窗），最多等 20 秒确认 /ping
  2) 用默认程序（WPS PDF）打开该 PDF —— 此时 WPS 是新进程，功能区才会注册「PDF转表格」页签
  3) 引擎随后跟随 WPS 存活；WPS 全关后按 .run/idle_timeout（默认 20s）自动退出

用法：
  py -3 tools/open_pdf.py "D:\\path\\to\\file.pdf"
  py -3 tools/open_pdf.py            # 无参数 → 弹文件选择框
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORTS = (38731, 38732, 38733, 38734)
VBS = ROOT / "tools" / "engine-silent.vbs"


def engine_port(timeout: float = 1.5) -> int:
    for p in PORTS:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{p}/ping", timeout=timeout) as r:
                if json.loads(r.read().decode("utf-8")).get("app") == "WPSPDF":
                    return p
        except Exception:
            continue
    return 0


def ensure_engine(wait_s: float = 20.0) -> int:
    port = engine_port()
    if port:
        return port
    print("[WPSPDF] 引擎未启动，正在拉起…")
    try:
        subprocess.Popen(["wscript", "//nologo", str(VBS)], close_fds=True)
    except Exception as e:  # noqa: BLE001
        print(f"[WPSPDF] 拉起失败：{e}")
        return 0
    t0 = time.time()
    while time.time() - t0 < wait_s:
        time.sleep(0.4)
        port = engine_port(1.0)
        if port:
            print(f"[WPSPDF] 引擎就绪（端口 {port}，用时 {time.time()-t0:.1f}s）")
            return port
    print("[WPSPDF] 引擎启动超时；PDF 仍会打开，但本次不会有页签")
    return 0


def pick_pdf() -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        p = filedialog.askopenfilename(title="选择要转表格的 PDF",
                                       filetypes=[("PDF", "*.pdf")])
        root.destroy()
        return p or ""
    except Exception:
        return ""


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else pick_pdf()
    if not path:
        print("没有指定 PDF")
        return 2
    if not Path(path).exists():
        print(f"文件不存在：{path}")
        return 2
    ensure_engine()
    os.startfile(path)  # noqa: S606  用默认程序（WPS PDF）打开
    print(f"[WPSPDF] 已交给默认程序打开：{Path(path).name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""WPSPDF 悬浮条：贴在 WPS PDF 窗口右上方，打开 PDF 时点一下就能转表格。

为什么不是 WPS 加载项：WPS 的 PDF 阅读组件不加载 jsaddons 页签（架构限制），
PDF 侧入口只能由外部置顶窗提供。本工具：
  - 不写注册表、不改 WPS 配置，关掉即消失（进程退出即无痕）
  - 只在 WPS 窗口处于前台时出现，贴在窗口右上方，随窗口移动/缩放
  - 「转换当前 PDF」→ 调 engine/convert.py → 产物 xlsx → 用 WPS 表格打开
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

ROOT = Path(__file__).resolve().parent.parent
CONVERT = ROOT / "engine" / "convert.py"
CACHE = ROOT / ".run" / "recent.json"
OUTDIR = ROOT / "output"

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

WPS_PROCS = {"wpsoffice.exe", "wps.exe", "et.exe", "wpp.exe", "ket.exe"}
SEARCH_DIRS = [
    Path.home() / "Desktop",
    Path.home() / "Downloads",
    Path(r"D:\xwechat_files"),
    Path(r"D:\Lenovo\Desktop"),
    Path(ROOT / "tests"),
]

BAR_W, BAR_H = 320, 92
BG = "#1f2430"
FG = "#e6e6e6"
ACCENT = "#2f81f7"
MUTED = "#8b949e"

WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def window_text(hwnd) -> str:
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def proc_name(hwnd) -> str:
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wt.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return Path(buf.value).name.lower()
        return ""
    finally:
        kernel32.CloseHandle(h)


def find_wps_pdf_window():
    """枚举所有可见窗口，返回 (pdf窗口hwnd, 标题) 或 (0, "")。"""
    found = []

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = window_text(hwnd)
        if not title:
            return True
        if proc_name(hwnd) in WPS_PROCS:
            found.append((hwnd, title))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    # 优先带 .pdf 的窗口
    for hwnd, title in found:
        if re.search(r"\.pdf", title, re.I):
            return hwnd, title
    return (found[0] if found else (0, ""))


def window_rect(hwnd):
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def pdf_name_from_title(title: str) -> str | None:
    m = re.search(r"([^\\/:*?\"<>|]+\.pdf)", title, re.I)
    return m.group(1).strip() if m else None


class Bar:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BG)
        self.root.withdraw()

        self.status = tk.StringVar(value="等待 WPS…")
        self.detail = tk.StringVar(value="")
        self.target_pdf: Path | None = None
        self.last_hwnd = 0

        head = tk.Frame(self.root, bg=BG)
        head.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(head, text="PDF 转表格", bg=BG, fg=FG,
                 font=("Microsoft YaHei", 10, "bold")).pack(side="left")
        tk.Label(head, textvariable=self.status, bg=BG, fg=MUTED,
                 font=("Microsoft YaHei", 8)).pack(side="right")

        tk.Label(self.root, textvariable=self.detail, bg=BG, fg=MUTED,
                 font=("Microsoft YaHei", 8), anchor="w",
                 wraplength=BAR_W - 20).pack(fill="x", padx=10)

        btns = tk.Frame(self.root, bg=BG)
        btns.pack(fill="x", padx=10, pady=(4, 8))
        self.btn_go = tk.Button(btns, text="转换当前 PDF", command=self.do_convert,
                                bg=ACCENT, fg="white", relief="flat",
                                font=("Microsoft YaHei", 9), cursor="hand2")
        self.btn_go.pack(side="left", ipadx=10, ipady=3)
        tk.Button(btns, text="选文件…", command=self.pick_file, bg="#30363d",
                  fg=FG, relief="flat", font=("Microsoft YaHei", 9),
                  cursor="hand2").pack(side="left", padx=(6, 0), ipadx=8, ipady=3)
        tk.Button(btns, text="✕", command=self.root.destroy, bg="#30363d", fg=FG,
                  relief="flat", font=("Microsoft YaHei", 8), cursor="hand2").pack(
            side="right", ipadx=6, ipady=3)

        self.tick()
        self.root.mainloop()

    def tick(self):
        try:
            hwnd, title = find_wps_pdf_window()
            fg = user32.GetForegroundWindow()
            if hwnd and (fg == hwnd or self.last_hwnd == fg):
                self.last_hwnd = hwnd
                left, top, right, bottom = window_rect(hwnd)
                x, y = right - BAR_W - 26, top + 92
                self.root.geometry(f"{BAR_W}x{BAR_H}+{x}+{y}")
                if self.root.state() == "withdrawn":
                    self.root.deiconify()
                pdf = pdf_name_from_title(title)
                if pdf:
                    found = self.find_pdf(pdf)
                    self.target_pdf = found
                    self.status.set("WPS PDF")
                    self.detail.set(Path(found).name if found else f"{pdf}（用「选文件…」定位）")
                    self.btn_go.configure(state="normal" if found else "disabled")
                else:
                    self.target_pdf = None
                    self.status.set("WPS 已打开")
                    self.detail.set("当前不是 PDF；切到 PDF 页签即可")
                    self.btn_go.configure(state="disabled")
            else:
                if self.root.state() != "withdrawn":
                    self.root.withdraw()
        except Exception:
            pass
        self.root.after(400, self.tick)

    def find_pdf(self, name: str) -> Path | None:
        key = name.lower()
        cache = {}
        if CACHE.exists():
            try:
                cache = json.loads(CACHE.read_text("utf-8"))
            except Exception:
                cache = {}
        hit = cache.get(key)
        if hit and Path(hit).exists():
            return Path(hit)
        for d in SEARCH_DIRS:
            if not d.exists():
                continue
            it = d.rglob(name) if "xwechat_files" in str(d) else d.glob(name)
            for p in it:
                if p.is_file():
                    cache[key] = str(p)
                    CACHE.parent.mkdir(exist_ok=True)
                    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), "utf-8")
                    return p
        return None

    def pick_file(self):
        p = filedialog.askopenfilename(title="选择 PDF", filetypes=[("PDF", "*.pdf")])
        if p:
            self.target_pdf = Path(p)
            self.detail.set(Path(p).name)
            self.btn_go.configure(state="normal")
            self.do_convert()

    def do_convert(self):
        if not self.target_pdf or not self.target_pdf.exists():
            messagebox.showwarning("PDF转表格", "没有可转换的文件")
            return
        src = self.target_pdf
        OUTDIR.mkdir(exist_ok=True)
        out = OUTDIR / (src.stem[:60] + ".xlsx")
        self.btn_go.configure(state="disabled", text="转换中…")
        self.status.set("正在转换")

        def work():
            try:
                proc = subprocess.run(
                    [sys.executable, str(CONVERT), str(src), "-o", str(out)],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                )
                ok = proc.returncode == 0 and out.exists()
                lines = (proc.stdout or "").strip().splitlines()
                msg = lines[-1] if lines else (proc.stderr or "")[-200:]
            except Exception as e:  # noqa: BLE001
                ok, msg = False, str(e)
            self.root.after(0, lambda: self.done(ok, msg, out))

        threading.Thread(target=work, daemon=True).start()

    def done(self, ok: bool, msg: str, out: Path):
        self.btn_go.configure(text="转换当前 PDF", state="normal")
        if ok:
            self.status.set("完成")
            self.detail.set(msg[:70])
            try:
                os.startfile(out)
            except Exception:
                pass
        else:
            self.status.set("失败")
            self.detail.set(msg[:80])
            messagebox.showerror("PDF转表格", msg)


if __name__ == "__main__":
    Bar()

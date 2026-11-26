# -*- coding: utf-8 -*-
"""轻量加载器（Add-in Loader）——只做一件事：接收「启动引擎」请求，按需拉起重引擎。

依据 LocalReadTranslate 的分层启动结构（docs/iteration-14-2026-07-29-addin-on-demand-startup.md）：
  加载项页面无法创建进程（WPS 个人版拦截 ShellExecute/CreateObject/CoCreateInstance/自定义协议），
  所以必须有一个**能被页面 HTTP 调用**的本地小服务，由它来创建进程。
  这个加载器只导入 Python 标准库，不加载 OCR 模型、不占 CPU；
  重引擎（engine/server.py，含 RapidOCR）仍然只在用户点按钮时启动，空闲 20 秒自行退出。

端点（只监听 127.0.0.1）：
  GET  /ping         → {"ok":true,"app":"WPSPDF-Loader","engine":<bool>}
  POST /start        → 拉起引擎，返回 {"ok":true,"started":<bool>}
  GET  /status       → 引擎是否在线
  POST /shutdown     → 停加载器自身

用法：
  pyw -3 engine/loader.py            # 静默常驻
  py -3 engine/loader.py --once      # 调试：只处理一次请求就退出
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP = "WPSPDF-Loader"
VERSION = "1.0.0"
PORT = 38730
ROOT = Path(__file__).resolve().parent.parent
VBS = ROOT / "tools" / "engine-silent.vbs"
ENGINE_PORTS = (38731, 38732, 38733, 38734)


def engine_port(timeout: float = 0.2) -> int:
    """探测重引擎是否在线。

    超时必须很小：本函数会被 /ping 调用，而 /ping 是窗格高频探测的端点，
    同步等 4×1 秒会让客户端超时（实测 3 秒超时必失败）。
    """
    for p in ENGINE_PORTS:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{p}/ping", timeout=timeout) as r:
                if json.loads(r.read().decode("utf-8")).get("app") == "WPSPDF":
                    return p
        except Exception:
            continue
    return 0


def start_engine() -> bool:
    if engine_port():
        return True
    try:
        subprocess.Popen(["wscript", "//nologo", str(VBS)], close_fds=True)
    except Exception:
        return False
    t0 = time.time()
    while time.time() - t0 < 25:
        time.sleep(0.4)
        if engine_port():
            return True
    return False


class Handler(BaseHTTPRequestHandler):
    server_version = f"{APP}/{VERSION}"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, code: int, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        if path == "/ping":
            self._json(200, {"ok": True, "app": APP, "version": VERSION,
                             "engine": bool(engine_port()), "pid": __import__("os").getpid()})
        elif path == "/status":
            self._json(200, {"ok": True, "engine": bool(engine_port())})
        elif path == "/shutdown":
            self._json(200, {"ok": True})
            __import__("threading").Thread(target=self.server.shutdown, daemon=True).start()
        else:
            self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self):  # noqa: N802
        path = self.path.split("?")[0]
        if path == "/start":
            ok = start_engine()
            self._json(200, {"ok": ok, "started": ok, "port": engine_port()})
        elif path == "/shutdown":
            self._json(200, {"ok": True})
            __import__("threading").Thread(target=self.server.shutdown, daemon=True).start()
        else:
            self._json(404, {"ok": False, "error": "not found"})

    def log_message(self, fmt, *args):  # 静默：不写 stderr
        pass


def main() -> int:
    # 单实例：已有加载器在跑就直接退出（避免两个实例抢同一端口，Windows 的 SO_REUSEADDR 允许双方都 bind）
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/ping", timeout=1.0) as r:
            if json.loads(r.read().decode("utf-8")).get("app") == APP:
                print(f"[{APP}] already running on {PORT}, skip", flush=True)
                return 0
    except Exception:
        pass

    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    srv.allow_reuse_address = False   # 必须关掉，否则重复实例能同时 bind 同一端口
    print(f"[{APP}] v{VERSION} http://127.0.0.1:{PORT} pid={__import__('os').getpid()}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

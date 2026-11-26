#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WPSPDF 本地引擎 v1.2

职责（单进程，只绑 127.0.0.1）：
  1) 托管加载项静态资源：/et/* → addon/ ，/pdf/* → addon-pdf/ ，/images/* → 图标
  2) 转换任务：POST /convert {path} → job；GET /job/<id> 查进度（含页数与 ETA）；GET /jobs 查活动任务
  3) 打开产物：GET /open?path=...
  4) 无鼠标验证通道：POST /cmd 下发、GET /cmd 取指令、POST /log 回报、GET /addinlog 读日志
  5) 生命周期：加载项页面可用 OAAssist 拉起本进程；无请求且无任务时自动退出（随 WPS 关闭而退）
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import socket
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

APP = "WPSPDF"
VERSION = "1.3.1"
ROOT = Path(__file__).resolve().parent.parent
RUNDIR = ROOT / ".run"
OUTDIR = ROOT / "output"
CONVERT = ROOT / "engine" / "convert.py"
STATIC_ROOTS = {
    "/et/": ROOT / "addon",
    "/pdf/": ROOT / "addon-pdf",
    "/images/": ROOT / "addon-pdf" / "images",
}
def _idle_timeout() -> float:
    """空闲多久自动退出（秒）。优先级：环境变量 > .run/idle_timeout > 300；0 = 常驻。"""
    env = os.environ.get("WPSPDF_IDLE_TIMEOUT")
    if env not in (None, ""):
        try:
            return float(env)
        except ValueError:
            pass
    cfg = RUNDIR / "idle_timeout"
    try:
        if cfg.exists():
            return float(cfg.read_text(encoding="utf-8").strip())
    except Exception:
        pass
    return 300.0


IDLE_TIMEOUT = _idle_timeout()

START_TS = time.time()
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
CMD_QUEUE: list[dict] = []
LAST_SEEN = time.time()

RUNDIR.mkdir(exist_ok=True)
OUTDIR.mkdir(exist_ok=True)


def _update(jid: str, **kw):
    with JOBS_LOCK:
        JOBS.setdefault(jid, {}).update(kw)


def _page_count(pdf_path: str) -> int:
    try:
        import fitz
        with fitz.open(pdf_path) as d:
            return d.page_count
    except Exception:
        return 0


def start_job(pdf_path: str, open_when_done: bool = True) -> str:
    jid = uuid.uuid4().hex[:12]
    src = Path(pdf_path)
    out = OUTDIR / (src.stem[:60] + ".xlsx")
    total = _page_count(pdf_path)
    _update(jid, state="running", src=str(src), name=src.name, out=str(out),
            started=time.time(), pages_total=total, pages_done=0, log=[],
            open_when_done=bool(open_when_done))

    def run():
        try:
            proc = subprocess.Popen(
                [sys.executable, "-u", str(CONVERT), str(src), "-o", str(out)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
            )
            for line in proc.stdout:
                line = line.rstrip()
                with JOBS_LOCK:
                    JOBS[jid]["log"].append(line)
                if line.startswith("OUT="):
                    _update(jid, out=line[4:].strip())
                m = re.search(r"\[page (\d+)\]", line)
                if m:
                    done = int(m.group(1))
                    _update(jid, pages_done=done, last=line)
            code = proc.wait()
            if code == 0 and Path(JOBS[jid]["out"]).exists():
                _update(jid, state="done", finished=time.time())
                if JOBS[jid].get("open_when_done"):
                    try:
                        os.startfile(JOBS[jid]["out"])  # noqa: S606  产物用默认程序（WPS 表格）打开
                        _update(jid, opened=True)
                    except Exception as e:  # noqa: BLE001
                        _update(jid, opened=False, open_error=str(e))
            else:
                tail = " | ".join(JOBS[jid]["log"][-3:])
                _update(jid, state="error", msg=tail or f"exit {code}", finished=time.time())
        except Exception as e:  # noqa: BLE001
            _update(jid, state="error", msg=str(e), finished=time.time())

    threading.Thread(target=run, daemon=True).start()
    return jid


def job_view(jid: str) -> dict:
    with JOBS_LOCK:
        j = dict(JOBS.get(jid) or {})
    if not j:
        return {}
    j.pop("log", None)
    now = time.time()
    done = int(j.get("pages_done") or 0)
    total = int(j.get("pages_total") or 0)
    started = float(j.get("started") or now)
    elapsed = max(0.1, (j.get("finished") or now) - started)
    if j.get("state") == "running":
        j["elapsed_s"] = round(elapsed, 1)
        if done > 0:
            per = elapsed / done
            j["eta_s"] = int(round(per * max(0, total - done))) if total else None
            j["per_page_s"] = round(per, 1)
        else:
            j["eta_s"] = int(round(8.0 * total)) if total else None
        if total:
            j["percent"] = round(min(99.0, 100.0 * done / total), 1)
    else:
        j["percent"] = 100.0 if j.get("state") == "done" else j.get("percent", 0)
    return j


def active_job() -> dict:
    with JOBS_LOCK:
        items = [(jid, dict(v)) for jid, v in JOBS.items()]
    running = [(jid, v) for jid, v in items if v.get("state") == "running"]
    if running:
        jid = max(running, key=lambda x: x[1].get("started", 0))[0]
        return job_view(jid)
    if items:
        jid = max(items, key=lambda x: x[1].get("started", 0))[0]
        return job_view(jid)
    return {}


class Handler(BaseHTTPRequestHandler):
    server_version = f"{APP}/{VERSION}"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        global LAST_SEEN
        LAST_SEEN = time.time()
        try:
            with open(RUNDIR / "engine.log", "a", encoding="utf-8") as f:
                f.write("%s %s\n" % (time.strftime("%H:%M:%S"), fmt % args))
        except Exception:
            pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _text(self, txt: str):
        body = txt.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path):
        if not path.is_file():
            self._json(404, {"ok": False, "error": "not found"})
            return
        data = path.read_bytes()
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        suf = path.suffix.lower()
        ctype = {".js": "application/javascript; charset=utf-8",
                 ".html": "text/html; charset=utf-8",
                 ".xml": "text/xml; charset=utf-8",
                 ".json": "application/json; charset=utf-8",
                 ".png": "image/png", ".svg": "image/svg+xml"}.get(suf, ctype)
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---------- GET ----------
    def do_GET(self):
        u = urlparse(self.path)
        p = u.path
        if p == "/ping":
            self._json(200, {"ok": True, "app": APP, "version": VERSION,
                             "port": self.server.server_address[1],
                             "uptime_s": round(time.time() - START_TS, 1),
                             "idle_timeout_s": int(IDLE_TIMEOUT)})
        elif p == "/status":
            j = active_job()
            self._json(200, {"ok": True, "version": VERSION,
                             "job": j.get("id") if j else None,
                             "state": j.get("state") if j else "idle",
                             "percent": j.get("percent") if j else 0})
        elif p == "/job":
            j = active_job()
            self._json(200, {"ok": True, "job": j} if j else {"ok": True, "job": None})
        elif p.startswith("/job/"):
            jid = p.split("/job/")[-1]
            v = job_view(jid)
            self._json(200, v) if v else self._json(404, {"ok": False, "error": "no such job"})
        elif p == "/jobs":
            with JOBS_LOCK:
                ids = list(JOBS.keys())
            self._json(200, {"ok": True, "jobs": [job_view(i) for i in ids]})
        elif p == "/cmd":
            with JOBS_LOCK:
                item = CMD_QUEUE.pop(0) if CMD_QUEUE else {"cmd": None}
            self._json(200, item)
        elif p == "/evalcode":
            if not (RUNDIR / "devmode").exists():
                self._json(403, {"ok": False, "error": "devmode off"})
            else:
                f = RUNDIR / "evalcode.js"
                self._text(f.read_text("utf-8", errors="replace") if f.exists() else "")
        elif p == "/addinlog":
            f = RUNDIR / "addin.log"
            self._text(f.read_text("utf-8", errors="replace")[-6000:] if f.exists() else "")
        elif p == "/open":
            q = parse_qs(u.query)
            target = unquote(q.get("path", [""])[0])
            if not target or not Path(target).exists():
                self._json(404, {"ok": False, "error": "file not found"})
            else:
                try:
                    os.startfile(target)  # noqa: S606
                    self._json(200, {"ok": True, "opened": target})
                except Exception as e:  # noqa: BLE001
                    self._json(500, {"ok": False, "error": str(e)})
        elif p == "/shutdown":
            self._json(200, {"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        else:
            for prefix, root in STATIC_ROOTS.items():
                if p.startswith(prefix):
                    rel = p[len(prefix):] or "index.html"
                    target = (root / rel).resolve()
                    rr = root.resolve()
                    if rr not in target.parents and target != rr:
                        self._json(403, {"ok": False, "error": "forbidden"})
                        return
                    self._file(target)
                    return
            self._json(404, {"ok": False, "error": "not found", "path": p})

    # ---------- POST ----------
    def do_POST(self):
        u = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if u.path == "/log":
            try:
                payload = json.loads(raw or b"{}")
            except Exception:
                payload = {"raw": raw[:200].decode("utf-8", "replace")}
            try:
                with open(RUNDIR / "addin.log", "a", encoding="utf-8") as f:
                    f.write("%s %s\n" % (time.strftime("%H:%M:%S"), json.dumps(payload, ensure_ascii=False)))
            except Exception:
                pass
            self._json(200, {"ok": True})
        elif u.path == "/cmd":
            try:
                payload = json.loads(raw or b"{}")
            except Exception:
                payload = {}
            with JOBS_LOCK:
                CMD_QUEUE.append(payload)
            self._json(200, {"ok": True, "queued": payload, "depth": len(CMD_QUEUE)})
        elif u.path == "/convert":
            try:
                payload = json.loads(raw or b"{}")
            except Exception:
                payload = {}
            path = payload.get("path") or ""
            if not path or not Path(path).exists():
                self._json(400, {"ok": False, "error": "path not found", "path": path})
                return
            jid = start_job(path, open_when_done=bool(payload.get("open", True)))
            self._json(200, {"ok": True, "job": jid, "src": path})
        else:
            self._json(404, {"ok": False, "error": "not found"})


def pick_port(preferred: int) -> int:
    for p in range(preferred, preferred + 4):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


WPS_IMAGES = {"wpsoffice.exe", "wpspdf.exe", "et.exe", "wpp.exe", "wps.exe"}


def wps_running() -> bool:
    """WPS 任一组件在跑 → 宿主活着，引擎就该活着。

    加载项页面与 ribbon.xml 都靠本引擎 http 托管：引擎提前退出，WPS 再打开 PDF 时
    取不到 ribbon.xml 就**不出页签**（2026-11-26 实机表现：页签时有时无）。
    所以生存期改为「跟随 WPS」：WPS 全关掉之后才开始算空闲。
    """
    try:
        import psutil
        for p in psutil.process_iter(["name"]):
            if (p.info.get("name") or "").lower() in WPS_IMAGES:
                return True
        return False
    except Exception:
        pass
    try:
        out = subprocess.run(["tasklist", "/NH"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stdout.lower()
        return any(n in out for n in WPS_IMAGES)
    except Exception:
        return False


def watchdog(server):
    """WPS 还在跑就常驻；WPS 全关后空闲到点退出。"""
    while True:
        time.sleep(20)
        with JOBS_LOCK:
            running = any(j.get("state") == "running" for j in JOBS.values())
        if running:
            continue
        if IDLE_TIMEOUT <= 0:
            continue
        if wps_running():
            continue
        if time.time() - LAST_SEEN > IDLE_TIMEOUT:
            try:
                with open(RUNDIR / "engine.log", "a", encoding="utf-8") as f:
                    f.write("%s idle %.0fs → shutdown\n" % (time.strftime("%H:%M:%S"), time.time() - LAST_SEEN))
            except Exception:
                pass
            server.shutdown()
            return


def _already_running(preferred: int) -> int:
    """已有实例在跑就返回其端口，避免拉起第二个进程。"""
    import urllib.request
    for p in range(preferred, preferred + 4):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{p}/ping", timeout=0.6) as r:
                data = json.loads(r.read().decode("utf-8"))
                if data.get("app") == APP:
                    return p
        except Exception:
            continue
    return 0


def main() -> int:
    global LAST_SEEN
    preferred = int(sys.argv[1]) if len(sys.argv) > 1 else 38731
    alive = _already_running(preferred)
    if alive:
        print(f"[{APP}] already running on {alive}, skip", flush=True)
        return 0
    port = pick_port(preferred)
    (RUNDIR / "engine.pid").write_text(str(os.getpid()), encoding="utf-8")
    LAST_SEEN = time.time()
    ThreadingHTTPServer.allow_reuse_address = False
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=watchdog, args=(srv,), daemon=True).start()
    print(f"[{APP}] v{VERSION} http://127.0.0.1:{port} pid={os.getpid()} idle_timeout={int(IDLE_TIMEOUT)}s", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

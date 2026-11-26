# -*- coding: utf-8 -*-
"""按需拉起引擎：只在「WPS 在跑」且「引擎没在跑」时启动它。

设计意图（用户要求：不要一直常驻、WPS 关了引擎就关）：
  - 本脚本由计划任务每分钟跑一次，跑完立即退出（不是常驻进程）
  - 引擎只在 WPS 运行期间存在；WPS 全关后按 .run/idle_timeout（默认 20s）自动退出
  - 页签本身由离线本地包提供，不依赖引擎，所以引擎晚起也不影响入口

退出码：0 = 无事可做或已拉起，1 = 拉起失败
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORTS = (38731, 38732, 38733, 38734)
WPS_IMAGES = ("wpspdf.exe", "et.exe", "wpp.exe", "wps.exe")  # 不含 wpsoffice.exe：关文档后它会留空壳


def engine_up() -> int:
    for p in PORTS:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{p}/ping", timeout=1.0) as r:
                if json.loads(r.read().decode("utf-8")).get("app") == "WPSPDF":
                    return p
        except Exception:
            continue
    return 0


def wps_running() -> bool:
    try:
        import psutil
        return any((p.info.get("name") or "").lower() in WPS_IMAGES
                   for p in psutil.process_iter(["name"]))
    except Exception:
        pass
    try:
        out = subprocess.run(["tasklist", "/NH"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stdout.lower()
        return any(n in out for n in WPS_IMAGES)
    except Exception:
        return False


def main() -> int:
    if not wps_running():
        return 0                      # WPS 没开：什么都不做（引擎自己会按 idle 退出）
    if engine_up():
        return 0                      # 引擎已在跑：什么都不做
    vbs = ROOT / "tools" / "engine-silent.vbs"
    try:
        subprocess.Popen(["wscript", "//nologo", str(vbs)], close_fds=True)
        print(f"[{__import__('time').strftime('%H:%M:%S')}] WPS 在跑、引擎不在 → 已拉起")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"拉起失败：{e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

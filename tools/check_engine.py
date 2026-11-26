# -*- coding: utf-8 -*-
"""检查本地引擎是否在线（供 check-engine.bat 调用）。

退出码：0 在线，1 离线。
"""
import json
import sys
import urllib.request

PORTS = (38731, 38732, 38733, 38734)

for port in PORTS:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/ping", timeout=2) as r:
            d = json.loads(r.read().decode("utf-8"))
        print(f"  在线：版本 {d.get('version')}  端口 {d.get('port')}  "
              f"已运行 {int(d.get('uptime_s', 0))}s  空闲超时 {d.get('idle_timeout_s')}s")
        sys.exit(0)
    except Exception:
        continue

print("  离线：引擎没在跑（38731–38734 均无响应）")
sys.exit(1)

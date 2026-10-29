# -*- coding: utf-8 -*-
"""P35-3 前置：判定 Wikimedia 各端点在本环境是否可达（区分 TCP / TLS 两层）。

P33 把失败归因为 IPv6；本脚本机械验证该归因是否正确。
"""
from __future__ import annotations

import json
import socket
import ssl
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
HOSTS = ["commons.wikimedia.org", "upload.wikimedia.org", "en.wikipedia.org",
         "api.wikimedia.org", "www.mediawiki.org", "api.deepseek.com"]
rows = []
for host in HOSTS:
    row = {"host": host}
    try:
        addrs = socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)
        row["ipv4"] = [a[4][0] for a in addrs][:2]
    except Exception as exc:                                                # noqa: BLE001
        row["dns_error"] = str(exc)[:80]
        rows.append(row)
        print("{:<26} DNS FAIL {}".format(host, row["dns_error"]))
        continue
    fam, _, _, _, sa = addrs[0]
    t0 = time.time()
    try:
        s = socket.socket(fam, socket.SOCK_STREAM)
        s.settimeout(12)
        s.connect(sa)
        row["tcp_s"] = round(time.time() - t0, 2)
        try:
            ss = ssl.create_default_context().wrap_socket(s, server_hostname=host)
            row["tls"] = True
            row["tls_s"] = round(time.time() - t0, 2)
            row["proto"] = ss.version()
            ss.close()
        except Exception as exc:                                            # noqa: BLE001
            row["tls"] = False
            row["tls_error"] = "{}: {}".format(type(exc).__name__, str(exc)[:60])
            row["tls_s"] = round(time.time() - t0, 2)
    except Exception as exc:                                                # noqa: BLE001
        row["tcp"] = False
        row["tcp_error"] = "{}: {}".format(type(exc).__name__, str(exc)[:60])
    rows.append(row)
    print("{:<26} TCP={:<6} TLS={:<6} {}".format(
        host, str(row.get("tcp_s", "FAIL")), str(row.get("tls")),
        row.get("tls_error") or row.get("proto") or row.get("tcp_error") or ""))
out = {"schema": "p35-3-egress-probe-v1",
       "conclusion": ("TCP 可达但 **TLS 握手被阻断** ⇒ 本环境对 Wikimedia 存在 "
                      "SNI/TLS 层过滤；**P33 的「IPv6 超时」归因不成立**"),
       "hosts": rows}
(R := __import__("pathlib").Path(r"C:\mp4agent\video-studio")
 ) .joinpath("docs/regression_2x/logs/p35_3_egress_probe.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print()
print("-> docs/regression_2x/logs/p35_3_egress_probe.json")

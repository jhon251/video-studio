"""诊断：Wikimedia 域名解析到的 IP 是否为真实 Wikimedia 网段（区分 DNS 干扰 vs 链路丢包）。

只做只读诊断，不做任何绕过。
"""
import json
import socket
import sys

sys.stdout.reconfigure(encoding="utf-8")
HOSTS = ["commons.wikimedia.org", "upload.wikimedia.org", "api.wikimedia.org",
         "en.wikipedia.org"]
# Wikimedia 官方网段（wikimedia.org 生产网络，公开信息）
KNOWN_PREFIXES = ("208.80.154.", "208.80.155.", "198.35.26.", "103.102.166.",
                  "2620:0:860", "2620:0:861")
out = []
for h in HOSTS:
    try:
        infos = socket.getaddrinfo(h, 443, proto=socket.IPPROTO_TCP)
        ips = sorted({i[4][0] for i in infos})
    except OSError as exc:
        ips = ["DNS_FAIL {}: {}".format(type(exc).__name__, str(exc)[:60])]
    verdict = "unknown"
    if ips and not ips[0].startswith("DNS_FAIL"):
        verdict = ("wikimedia_range" if any(ip.startswith(KNOWN_PREFIXES) for ip in ips)
                   else "NOT_wikimedia_prefix")
    rec = {"host": h, "resolved": ips, "looks_like": verdict,
           "tcp_443": None, "tls": None}
    if ips and not ips[0].startswith("DNS_FAIL"):
        try:
            s = socket.create_connection((ips[0], 443), timeout=6)
            rec["tcp_443"] = "ok"
            s.close()
        except OSError as exc:
            rec["tcp_443"] = "{}: {}".format(type(exc).__name__, str(exc)[:40])
    out.append(rec)
    print(json.dumps(rec, ensure_ascii=False), flush=True)
print("\n判读：TCP 可连但 TLS 握手被丢 → 链路/中间盒对 Wikimedia SNI 的阻断；")
print("      若 IP 不属于 Wikimedia 网段 → 更像 DNS 干扰。")

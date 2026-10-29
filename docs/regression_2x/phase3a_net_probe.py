"""Distinguish Wikimedia-specific failure from general outbound HTTPS failure."""
import socket
import ssl
import sys
import time

HOSTS = [
    ("commons.wikimedia.org", 443),
    ("upload.wikimedia.org", 443),
    ("api.deepseek.com", 443),
    ("speech.platform.bing.com", 443),
    ("www.baidu.com", 443),
    ("www.example.com", 443),
]

sys.stdout.reconfigure(encoding="utf-8")
for host, port in HOSTS:
    t0 = time.time()
    tcp = tls = None
    try:
        s = socket.create_connection((host, port), timeout=10)
        tcp = round(time.time() - t0, 2)
        try:
            ctx = ssl.create_default_context()
            ctx.wrap_socket(s, server_hostname=host)
            tls = round(time.time() - t0, 2)
        finally:
            s.close()
        print("{:28s} TCP {:>6}s  TLS {:>6}s  OK".format(host, tcp, tls), flush=True)
    except Exception as exc:                                    # noqa: BLE001
        print("{:28s} TCP {:>6}  TLS {:>6}  FAIL {}: {}".format(
            host, tcp if tcp is not None else "-", tls if tls is not None else "-",
            type(exc).__name__, str(exc)[:80]), flush=True)

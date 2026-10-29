"""诊断：Wikimedia 的 TLS 阻断是否与 TLS 版本/SNI 相关（不是绕过，只是判断可用传输）。"""
import socket
import ssl
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
HOSTS = ["commons.wikimedia.org", "upload.wikimedia.org", "api.wikimedia.org",
         "en.wikipedia.org"]


def attempt(host: str, label: str, ctx: ssl.SSLContext, sni: bool = True) -> str:
    t0 = time.time()
    try:
        raw = socket.create_connection((host, 443), timeout=8)
    except OSError as exc:
        return "{:22s} {:28s} TCP_FAIL {}: {}".format(host, label, type(exc).__name__,
                                                      str(exc)[:60])
    try:
        s = ctx.wrap_socket(raw, server_hostname=host if sni else None)
        info = "OK {} {}".format(s.version(), s.cipher()[0] if s.cipher() else "")
        s.close()
        return "{:22s} {:28s} {} ({:.2f}s)".format(host, label, info, time.time() - t0)
    except Exception as exc:                                     # noqa: BLE001
        return "{:22s} {:28s} TLS_FAIL {}: {} ({:.2f}s)".format(
            host, label, type(exc).__name__, str(exc)[:50], time.time() - t0)
    finally:
        try:
            raw.close()
        except OSError:
            pass


ctx12 = ssl.create_default_context()
ctx12.maximum_version = ssl.TLSVersion.TLSv1_2
ctx13 = ssl.create_default_context()
ctx13.minimum_version = ssl.TLSVersion.TLSv1_3
ctxdef = ssl.create_default_context()
ctxdef.set_ciphers("DEFAULT:@SECLEVEL=0") if hasattr(ctxdef, "set_ciphers") else None
ctxnosni = ssl.create_default_context()

for h in HOSTS:
    print(attempt(h, "default(1.2|1.3)", ctxdef), flush=True)
    print(attempt(h, "max=TLS1.2", ctx12), flush=True)
    print(attempt(h, "min=TLS1.3", ctx13), flush=True)
    print(attempt(h, "no-SNI(default)", ctxnosni, sni=False), flush=True)
    print("-" * 90, flush=True)

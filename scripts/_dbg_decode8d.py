import sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, "src")
from video_studio.tools.search_provider import _decode_response


class R:
    encoding = "iso-8859-1"
    content = ('\ufeff<html><head><meta charset="utf-8"><title>测试</title>'
               '</head><body>正文内容内容内容</body></html>').encode("utf-8")


t = _decode_response(R())
assert not t.startswith("\ufeff"), "BOM not stripped"
assert "正文内容" in t, "content not decoded"
print("BOM stripped:", not t.startswith("\ufeff"), "| head:", repr(t[:24]))

# 无 BOM 的 utf-8 不受影响
class R2:
    encoding = "iso-8859-1"
    content = '<html><head><meta charset="utf-8"><title>测试</title></head></html>'.encode("utf-8")
t2 = _decode_response(R2())
assert "测试" in t2 and not t2.startswith("\ufeff")
print("no-BOM utf-8 ok:", repr(t2[:20]))

# gb18030 回退仍工作
class R3:
    encoding = "iso-8859-1"
    content = "<html><meta charset=gb2312><title>中国脑科学</title></html>".encode("gb18030")
t3 = _decode_response(R3())
assert "中国脑科学" in t3
print("gb18030 fallback ok:", repr(t3[:20]))
print("ALL PASS")

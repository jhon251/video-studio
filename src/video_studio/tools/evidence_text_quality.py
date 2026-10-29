"""V2.1 Stage 8D：evidence_text_quality（5 类状态 + JS 壳内容打捞；数据无关、确定性）。

- 状态枚举：valid / js_shell / empty / encoding_error / low_content。
- extract_body(html)：HTML→正文；js_shell 时尝试通用内容打捞（meta description / og / title /
  noscript / JSON-LD），打捞可用则返回打捞文本（salvaged=True），否则保留原状。
- 保留原始 HTML 与最终正文（调用方负责存原始 HTML；本模块只派生）。
- 编码处理（decode_bytes）：BOM→charset→utf-8 严格→gb18030，无任何 URL/domain 特例。
"""

from __future__ import annotations

import re
import unicodedata

from .search_provider import _strip_tags

JS_SHELL_MARKERS = (
    "enable javascript and cookies", "just a moment", "verifying your connection",
    "recaptcha", "captcha", "window._cf_chl", "cf-chl", "vercel security checkpoint",
    "you need to enable javascript to run this app", "enable javascript and cookies to continue",
    "百度安全验证", "请启用 javascript", "安全验证", "js disabled",
)

_LATIN1 = re.compile(r"[\u0080-\u00ff]")
_CJK = re.compile(r"[\u4e00-\u9fff]")
_ALNUM = re.compile(r"[a-z0-9\u4e00-\u9fff]")


def plain_text(html: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", _strip_tags(html or ""))).strip()


def salvage_text(html: str) -> str:
    """js_shell 通用内容打捞：meta description / og / title / noscript / JSON-LD。"""
    out = []
    for pat in (r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']{20,})["\']',
                r'<meta[^>]+content=["\']([^"\']{20,})["\'][^>]+(?:name|property)=["\'](?:description|og:description)["\']',
                r"<title[^>]*>(.*?)</title>",
                r"<noscript[^>]*>([\s\S]{20,}?)</noscript>",
                r'"headline"\s*:\s*"([^"]{20,})"',
                r'"description"\s*:\s*"([^"]{40,})"'):
        m = re.search(pat, html or "", re.I | re.S)
        if m:
            out.append(_strip_tags(m.group(1)))
    best = max(out, key=lambda s: len(s), default="")
    return re.sub(r"\s+", " ", best).strip()


def _ratios(text: str):
    n = max(len(text), 1)
    return len(_CJK.findall(text)) / n, len(_ALNUM.findall(text)) / n, \
        len(_LATIN1.findall(text)) / n


def quality(text: str) -> dict:
    """5 类正文质量判定（输入为待判文本，可为 HTML 或纯文本）。"""
    t = plain_text(text)
    cjk, alnum, latin1 = _ratios(t)
    latin1_count = len(_LATIN1.findall(t))
    low = t.lower()
    if any(m in low for m in JS_SHELL_MARKERS):
        return {"status": "js_shell", "confidence": "high",
                "rationale": "命中反爬/JS 壳标记", "metrics": {"len": len(t)}}
    if "\ufffd" in t or (cjk == 0.0 and (latin1_count >= 12 or latin1 > 0.25)):
        return {"status": "encoding_error", "confidence": "high",
                "rationale": "替换符或高密度 Latin-1 乱码", "metrics": {"len": len(t)}}
    if len(t) == 0:
        return {"status": "empty", "confidence": "high",
                "rationale": "正文为空", "metrics": {"len": 0}}
    if len(t) < 40:
        return {"status": "low_content", "confidence": "high",
                "rationale": "正文过短（<40）", "metrics": {"len": len(t)}}
    return {"status": "valid", "confidence": "medium",
            "rationale": "存在正文内容", "metrics": {"len": len(t), "cjk": round(cjk, 3)}}


def extract_body(html: str) -> dict:
    """HTML → 正文（含 js_shell 打捞）。返回 {status, text, salvaged, rationale}。"""
    t = plain_text(html)
    q = quality(t)
    if q["status"] == "js_shell":
        s = salvage_text(html)
        if len(plain_text(s)) >= 40:
            return {"status": "js_shell", "text": s, "salvaged": True,
                    "rationale": "js_shell 已打捞出内容"}
    return {"status": q["status"], "text": t, "salvaged": False,
            "rationale": q["rationale"]}


def decode_bytes(raw: bytes, charset_hint: str | None = None) -> tuple[str, str]:
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    if raw.startswith(b"\xff\xfe"):
        return raw.decode("utf-16-le"), "utf-16-le"
    if charset_hint:
        for enc in (charset_hint, charset_hint.replace("-", ""), charset_hint.replace("_", "-")):
            try:
                return raw.decode(enc), enc
            except (LookupError, UnicodeDecodeError):
                continue
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("gb18030"), "gb18030"

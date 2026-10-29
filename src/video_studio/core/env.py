"""极简 .env 加载器（零依赖）。API 密钥只从环境变量读取，禁止硬编码。"""

from __future__ import annotations

import os
from pathlib import Path


def _clean_value(value: str) -> str:
    """去掉**行内注释/误粘文字**，只保留尾部连续 ASCII 可打印内容。

    **踩坑（P47-1 实测）**：`.env` 里 `VLM_API_KEY` 这一行末尾被粘上了中文注释
    （「素材密钥（启用；仅存于 .env，禁止硬编码到代码/配置）」）⇒ 值多出 23 个
    非 ASCII 字符（总长 162）。后果：
      · `urllib` 直接报 `UnicodeEncodeError: 'latin-1' codec can't encode ...`
        （HTTP 头必须是 latin-1）；
      · 更隐蔽的是 HTTP 客户端可能把坏凭据发出去而**静默 401**。
    修法：若值含非 ASCII，则取「**最后一个非 ASCII 字符之后** 的 ASCII 尾巴」；
    若拿不到干净尾巴，再按行内 `#` 切分。**行首 `#` 注释不受影响**（原逻辑已跳过）。
    """
    if not value:
        return value
    if any(ord(c) > 126 for c in value):
        cut = 0
        for i, c in enumerate(value):
            if ord(c) > 126:
                cut = i + 1
        tail = value[cut:].strip()
        if tail and all(32 <= ord(c) <= 126 for c in tail):
            return tail
        return value.split("#", 1)[0].strip()
    return value


def check_credentials(env: dict | None = None) -> list[dict]:
    """**P50-3② 凭据健全性告警**（只读、不抛异常、不改环境）。

    规则：任何 `*_API_KEY` / `*_TOKEN` / `*_SECRET` 的值若
      · 含 **非 ASCII** 或控制字符，或
      · 含**空白**（说明粘了多余内容），或
      · 长度异常（< 16），
    则产出一条 `warning` 记录（**不回显密钥值**，只报名称与问题类型）。
    供启动/阶段脚本调用 —— 防止 P47-D1 那类**静默污染**再次发生。
    """
    src = env if env is not None else dict(os.environ)
    out = []
    for k, v in sorted(src.items()):
        ku = str(k).upper()
        if not (ku.endswith("_API_KEY") or ku.endswith("_TOKEN")
                or ku.endswith("_SECRET") or "APIKEY" in ku):
            continue
        s = str(v or "")
        if not s:
            continue
        problems = []
        if any(ord(c) > 126 or ord(c) < 32 for c in s):
            problems.append("contains_non_ascii_or_control")
        if any(c.isspace() for c in s):
            problems.append("contains_whitespace")
        if len(s) < 16:
            problems.append("suspiciously_short")
        if problems:
            out.append({"name": k, "length": len(s), "problems": problems,
                        "advice": "检查 .env 该行是否粘了注释/多余文字（勿回显密钥值）"})
    return out


def load_env(path: str | Path = ".env") -> dict:
    """解析 KEY=VALUE 到 os.environ（已存在的环境变量优先，不覆盖）。返回加载的键值。"""
    p = Path(path)
    if not p.is_file():
        return {}
    loaded = {}
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), _clean_value(value.strip().strip('"').strip("'"))
        if not key:
            continue
        loaded[key] = value
        os.environ.setdefault(key, value)
    return loaded

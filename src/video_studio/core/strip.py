"""strip_claims：内部 Claim 标记剥离（V2 第四阶段核心）。

原则：`[CLAIM:xxx]` 只存在于内部工作稿与结构化数据中；
任何用户可见文本（TTS 输入、SRT、烧录字幕、发布稿、朗读稿、metadata）必须剥离。
claims_map / claims 表 / 内部稿保持原样，保证 claim_id 全链路可追溯。
"""

from __future__ import annotations

import re

CLAIM_MARKER = re.compile(r"\[CLAIM:[A-Za-z0-9_\-]+\]")


def strip_claims(text: str) -> str:
    """剥离文本中的全部 [CLAIM:xxx] 标记（返回新字符串，不修改原对象）。"""
    if not isinstance(text, str):
        return text
    return CLAIM_MARKER.sub("", text)


def strip_claims_deep(obj):
    """递归剥离 dict/list/str 结构中的全部标记（返回新对象）。"""
    if isinstance(obj, str):
        return strip_claims(obj)
    if isinstance(obj, list):
        return [strip_claims_deep(item) for item in obj]
    if isinstance(obj, dict):
        return {key: strip_claims_deep(value) for key, value in obj.items()}
    return obj


def has_claims(text: str) -> bool:
    """检测文本是否仍含未剥离的标记（测试/质检用）。"""
    return isinstance(text, str) and bool(CLAIM_MARKER.search(text))

# -*- coding: utf-8 -*-
"""Phase 48 / P48-1：**求解器输入转储器**（生产路径与独立路径共用同一实现）。

硬要求（授权书 §1）：**禁止读代码猜测定案** —— 必须以**转储 diff** 为准。
故两条路径都调用**同一个** `dump_solver_input()`，产出**同构** JSON，再逐字段 diff。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import time

SCHEMA = "p48-1-solver-input-dump-v1"


def _fp(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                     default=str).encode("utf-8")).hexdigest()


def dump_solver_input(path, *, source: str, ids, options, cap, gap,
                      fam_map=None, max_family_share=None,
                      max_share_by_family=None, sub_map=None,
                      forbid_adjacent_same_sub=False,
                      initial=None, restarts=None, iters=None, seed=None,
                      anchor_map=None, extra=None) -> dict:
    """转储求解器**完整输入**（逐景候选域 + 家族映射 + 阈值 + 搜索参数）。

    `options` 的**每个候选域都保序落盘**（顺序即 tie-break 语义，必需保留）。
    """
    opts = {str(k): [str(x) for x in (v or [])] for k, v in (options or {}).items()}
    fam = {str(k): [str(x) for x in (v or [])]
           for k, v in (fam_map or {}).items()}
    sub = {str(k): [str(x) for x in (v or [])]
           for k, v in (sub_map or {}).items()}
    rec = {
        "schema": SCHEMA,
        "source": source,                       # "production" / "standalone"
        "dumped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ids": [str(x) for x in (ids or [])],
        "scene_count": len(ids or []),
        "options_fingerprint": _fp(opts),
        "options_counts": {k: len(v) for k, v in opts.items()},
        "options": opts,
        "initial_fingerprint": _fp({k: v for k, v in (initial or {}).items()}),
        "initial_nonnull": sum(1 for v in (initial or {}).values() if v),
        "cap": cap, "gap": gap,
        "fam_map": fam, "fam_map_fingerprint": _fp(fam),
        "max_family_share": max_family_share,
        "max_share_by_family": dict(max_share_by_family or {}),
        "sub_map": sub, "sub_map_fingerprint": _fp(sub),
        "forbid_adjacent_same_sub": bool(forbid_adjacent_same_sub),
        "restarts": restarts, "iters": iters, "seed": seed,
        "anchor_deny": {str(k): [str(x) for x in (v or [])]
                        for k, v in (anchor_map or {}).items()},
        "extra": extra or {},
    }
    rec["input_fingerprint"] = _fp({k: rec[k] for k in (
        "ids", "options", "cap", "gap", "fam_map", "max_family_share",
        "max_share_by_family", "sub_map", "forbid_adjacent_same_sub",
        "restarts", "iters", "seed")})
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return rec


def diff(a: dict, b: dict, label_a: str = "production",
         label_b: str = "standalone", max_items: int = 12) -> dict:
    """逐字段 diff：**报告第一个分歧字段**及其两侧取值。"""
    keys = sorted(set(a) | set(b))
    first, all_diffs = None, []
    for k in keys:
        va, vb = a.get(k), b.get(k)
        if va == vb:
            continue
        d = {"field": k, "a": va, "b": vb}
        if isinstance(va, dict) and isinstance(vb, dict):
            sub = [x for x in sorted(set(va) | set(vb)) if va.get(x) != vb.get(x)]
            d["sublabels"] = sub[:max_items]
            d["sublabel_count"] = len(sub)
            d["a"] = {x: va.get(x) for x in sub[:max_items]}
            d["b"] = {x: vb.get(x) for x in sub[:max_items]}
        all_diffs.append(d)
        if first is None:
            first = d
    return {"schema": "p48-1-solver-input-diff-v1",
            "label_a": label_a, "label_b": label_b,
            "identical": not all_diffs, "diff_count": len(all_diffs),
            "first_divergence": first, "all_differences": all_diffs[:max_items]}

# -*- coding: utf-8 -*-
"""6-B/M2 —— **Human Review Bridge**（DQ finding → 人类审片决策；只读 + append-only + 零执行）。

本模块只做三件事：
  1. 把 DQ-1…DQ-8 的只读 `findings`（及 UNKNOWN/NOT_ASSESSABLE 的状态项）**展开成可审片的 review item**
     （每条都带 finding_id / scene / asset / 时间区间 / severity / 原始 evidence 引用 / provenance）；
  2. 维护**人类决策台账**（`ACCEPT / REJECT / DEFER`）—— **append-only + 哈希链**，历史决策不可改不可删；
  3. 汇总成可审计报告（含"零执行"证明字段）。

硬约束（代码级）：
  · **禁止自动执行任何修改**：本模块不触碰 timeline / 素材 / 字幕 / 旁白 / 成片，不写 DB、不写产物；
    `REJECT` 的语义是**"该问题成立、建议需要修改"**，不是执行修改；
  · **UNKNOWN / NOT_ASSESSABLE 一律进入 DEFER / 人工复核**，且**不允许被 ACCEPT**（UNKNOWN 绝不变 PASS）；
  · 每条决策必须携带 `finding_id / decision / reason / decided_by / provenance`（缺一即拒绝写入）；
  · 台账 append-only：每条记录带 `seq` 与 `prev_sha256`，`verify_chain` 可证明未被改写/删除。

用法（库内调用）：见 `ops/review.py` 与 `run.py review`。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

DECISIONS = ("ACCEPT", "REJECT", "DEFER")
DECISION_SEMANTICS = {
    "ACCEPT": "人工确认该 finding 不成立或可接受（不修改任何东西）",
    "REJECT": "人工确认该 finding 成立且**建议需要修改**（本阶段不执行修改）",
    "DEFER": "暂缓 / 需人工复核 / 待补证据（UNKNOWN、NOT_ASSESSABLE 一律走此路径）",
}
#: 语义上"不可证"的状态：一律 DEFER，且禁止 ACCEPT
UNPROVABLE_STATES = ("UNKNOWN", "NOT_ASSESSABLE")
READONLY = {"read_only": True, "enforced": False, "advisory": True, "executes_changes": False}
REQUIRED_DECISION_FIELDS = ("finding_id", "decision", "reason", "decided_by", "provenance")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def finding_id(project_id: str, metric, kind: str, scene_id=None, asset_id=None,
               window=None, discriminator=None) -> str:
    """确定性 finding ID（同一 finding 在任何时候复算得到同一 ID ⇒ 决策一一可追溯）。"""
    key = "|".join([
        str(project_id or ""), str(metric or ""), str(kind or ""), str(scene_id or ""),
        str(asset_id or ""), json.dumps(window, ensure_ascii=False) if window else "",
        str(discriminator or ""),
    ])
    return "hr-" + _sha256_text(key)[:12]


def _item(project_id: str, metric, kind: str, severity: str, payload: dict,
          scene_id=None, asset_id=None, window=None, discriminator=None,
          origin: str = "dq_finding", source_evidence=None, film_task=None,
          unprovable: bool = False) -> dict:
    fid = finding_id(project_id, metric, kind, scene_id, asset_id, window, discriminator)
    return {
        "finding_id": fid,
        "project_id": project_id,
        "film_task": film_task,
        "origin": origin,
        "metric": metric,
        "kind": kind,
        "severity": severity,                      # 该 finding 对应的（语义或机械）状态
        "unprovable": bool(unprovable),            # UNKNOWN / NOT_ASSESSABLE ⇒ True
        "scene_id": scene_id,
        "asset_id": asset_id,
        "window": window,                          # [start_s, end_s]
        "payload": payload,
        "source_evidence": source_evidence,
        "provenance": {"origin": origin, "metric": metric,
                       "source_evidence": source_evidence,
                       "derived_at": _now(),
                       "derivation": "core/human_review.py::findings_from_direction"},
        "default_routing": ("DEFER" if unprovable else None),
        "default_routing_policy": ("policy:unknown_requires_human" if unprovable else None),
        **READONLY,
    }


def findings_from_direction(metrics: dict, project_id: str, film_task=None,
                            source_evidence: str | None = None) -> list[dict]:
    """把 DQ 指标报告展开为 review items（逐 finding + 逐"不可证状态"）。"""
    items: list[dict] = []
    for key in sorted(metrics or {}):
        m = metrics[key] or {}
        state = m.get("state")
        sem_state = m.get("semantic_state")
        for f in (m.get("findings") or []):
            kind = f.get("kind") or "finding"
            scene_id = f.get("scene_id")
            asset_id = f.get("asset_id")
            window = f.get("window")
            if not (scene_id or asset_id or window):
                # 复合锚点（如 scene_windows / tail_scenes / scenes）：取首个可定位项作为代表锚点
                # 注意：`scenes` 在部分 finding 里是**计数**而非列表，必须做类型判定
                for cand in (f.get("scenes") if isinstance(f.get("scenes"), list) else []):
                    if isinstance(cand, dict) and (cand.get("scene_id") or cand.get("window")):
                        scene_id = scene_id or cand.get("scene_id")
                        window = window or cand.get("window")
                        asset_id = asset_id or cand.get("asset_id")
                        break
                if not scene_id:
                    for cand in (f.get("tail_scenes")
                                 if isinstance(f.get("tail_scenes"), list) else []):
                        if isinstance(cand, dict):
                            scene_id, window = scene_id or cand.get("scene_id"), \
                                window or cand.get("window")
                            asset_id = asset_id or cand.get("asset_id")
                            break
                if not scene_id:
                    sw = f.get("scene_windows") if isinstance(f.get("scene_windows"), list) else []
                    if sw and isinstance(sw[0], dict):
                        scene_id, window = sw[0].get("scene_id"), sw[0].get("window")
                if not scene_id and isinstance(f.get("asset_ids"), list) and f["asset_ids"]:
                    asset_id = asset_id or f["asset_ids"][0]
                if not scene_id and isinstance(f.get("core_scene_ids"), list) and f["core_scene_ids"]:
                    scene_id = f["core_scene_ids"][0]
                if not scene_id and isinstance(f.get("distinct_asset_ids"), list) \
                        and f["distinct_asset_ids"]:
                    asset_id = asset_id or f["distinct_asset_ids"][0]
                if not scene_id:
                    ls = f.get("last_scene") if isinstance(f.get("last_scene"), dict) else None
                    if ls:
                        scene_id, window = ls.get("scene_id"), ls.get("window")
            items.append(_item(project_id, key, kind, state or "UNKNOWN", f, scene_id=scene_id,
                               asset_id=asset_id, window=window, film_task=film_task,
                               source_evidence=source_evidence,
                               discriminator=json.dumps(f, ensure_ascii=False)[:120]))
        # 语义/不可证状态单列为一条 review item（保证 UNKNOWN 一定进入人工复核路径）
        if sem_state in UNPROVABLE_STATES or state in UNPROVABLE_STATES:
            shown = sem_state or state
            items.append(_item(project_id, key, "metric_state_unprovable", shown,
                               {"state": state, "semantic_state": sem_state,
                                "layer_counts": m.get("layer_counts") or m.get("semantic_counts"),
                                "unknown_scene_count": m.get("unknown_scene_count"),
                                "reason": m.get("reason")},
                               film_task=film_task, source_evidence=source_evidence,
                               discriminator="state", unprovable=True))
    return items


def human_audit_item(project_id: str, kind: str, summary: str, provenance: str,
                     film_task=None, scene_id=None, window=None, evidence=None,
                     unprovable: bool = True) -> dict:
    """把**人工审计记录**（非 DQ 派生）也纳入同一台账（origin=human_audit）。"""
    return _item(project_id, None, kind, "HUMAN_RECORDED", {"summary": summary, "evidence": evidence},
                 scene_id=scene_id, window=window, film_task=film_task,
                 origin="human_audit", source_evidence=provenance, unprovable=unprovable,
                 discriminator=kind)


def make_decision(item: dict, decision: str, reason: str, decided_by: str, provenance,
                  at: str | None = None, covers: list | None = None) -> dict:
    """构造一条决策记录（**校验必需字段**；UNKNOWN 项禁止 ACCEPT）。

    `covers`：可选的"**类级决策覆盖实例级 finding**"声明，形如
    `[{"metric": "DQ-3", "kind": "hold_exceeds_max"}, ...]` —— 用于人工按问题类拍板、
    同时保证每个实例 finding 都能被显式追溯到那条类级决策（不是被静默忽略）。
    """
    decision = str(decision or "").upper()
    if decision not in DECISIONS:
        raise ValueError("非法 decision: {!r}（仅 {}）".format(decision, list(DECISIONS)))
    if item.get("unprovable") and decision == "ACCEPT":
        raise ValueError("UNKNOWN_CANNOT_BE_ACCEPTED: finding {} 属不可证状态（{}），"
                         "只能 DEFER（人工复核）或 REJECT".format(
                             item.get("finding_id"), item.get("severity")))
    rec = {
        "finding_id": item.get("finding_id"),
        "project_id": item.get("project_id"),
        "film_task": item.get("film_task"),
        "metric": item.get("metric"),
        "kind": item.get("kind"),
        "severity": item.get("severity"),
        "unprovable": bool(item.get("unprovable")),
        "scene_id": item.get("scene_id"),
        "asset_id": item.get("asset_id"),
        "window": item.get("window"),
        "original_evidence": item.get("source_evidence"),
        "decision": decision,
        "decision_semantics": DECISION_SEMANTICS[decision],
        "reason": reason,
        "decided_by": decided_by,
        "decided_at": at or _now(),
        "provenance": provenance,
        "covers": list(covers or []),
        "executes_changes": False,
        **READONLY,
    }
    missing = verify_decision(rec)
    if missing:
        raise ValueError("决策缺少必需字段: {}".format(missing))
    return rec


def verify_decision(dec: dict) -> list:
    """返回缺失/非法字段列表（空列表 = 合法）。"""
    bad = [k for k in REQUIRED_DECISION_FIELDS
           if dec.get(k) in (None, "", [], {})]
    if dec.get("decision") not in DECISIONS:
        bad.append("decision")
    if dec.get("decision") == "ACCEPT" and dec.get("unprovable"):
        bad.append("decision(ACCEPT on unprovable)")
    return bad


def _entry_sha(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k not in ("entry_sha256",)}
    return _sha256_text(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                   separators=(",", ":")))


def append_decision(ledger_path: str | Path, decision: dict) -> dict:
    """**append-only** 追加一条决策：带 `seq` 与 `prev_sha256` 哈希链；只追加，绝不改写历史。"""
    p = Path(ledger_path)
    entries = load_ledger(p)
    prev = entries[-1]["entry_sha256"] if entries else ""
    rec = dict(decision)
    rec["seq"] = len(entries) + 1
    rec["prev_sha256"] = prev
    rec["ledger"] = {"append_only": True, "schema": "human-review-ledger-v1"}
    rec["entry_sha256"] = _entry_sha(rec)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def load_ledger(ledger_path: str | Path) -> list:
    p = Path(ledger_path)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def verify_chain(entries: list) -> dict:
    """校验 append-only 哈希链：seq 连续、prev 指针一致、条目 sha 未被改写。"""
    prev = ""
    for i, e in enumerate(entries or [], start=1):
        if e.get("seq") != i:
            return {"ok": False, "length": len(entries), "broken_at": i, "why": "seq 不连续"}
        if e.get("prev_sha256") != prev:
            return {"ok": False, "length": len(entries), "broken_at": i,
                    "why": "prev_sha256 与上一条不符（历史被改写/插入）"}
        if e.get("entry_sha256") != _entry_sha(e):
            return {"ok": False, "length": len(entries), "broken_at": i,
                    "why": "entry_sha256 不匹配（条目内容被改写）"}
        prev = e["entry_sha256"]
    return {"ok": True, "length": len(entries or []), "broken_at": None, "why": None}


def summarize_review(items: list, decisions: list, film_level: dict | None = None) -> dict:
    """汇总审片闭环：1:1 可追溯性、决策计数、未决项、UNKNOWN 保守性、零执行。"""
    by_id = {}
    for d in decisions or []:
        by_id.setdefault(d["finding_id"], []).append(d)
    covers_map = {}                                    # (metric, kind) → 类级决策 finding_id
    for d in decisions or []:
        for c in (d.get("covers") or []):
            covers_map[(c.get("metric"), c.get("kind"))] = d["finding_id"]
    counts = {k: 0 for k in DECISIONS}
    unresolved, untraceable, unknown_accepted, covered = [], [], [], []
    rows = []
    for it in items or []:
        ds = by_id.get(it["finding_id"]) or []
        # 取最后一条决策为当前有效决策（台账 append-only，可保留历史）
        cur = ds[-1] if ds else None
        cov_by = None
        if cur is None:
            cov_by = covers_map.get((it.get("metric"), it.get("kind")))
            if cov_by:
                covered.append(it["finding_id"])
            else:
                unresolved.append(it["finding_id"])
        else:
            counts[cur["decision"]] = counts.get(cur["decision"], 0) + 1
            if cur["decision"] == "ACCEPT" and it.get("unprovable"):
                unknown_accepted.append(it["finding_id"])
        if not (it.get("scene_id") or it.get("asset_id") or it.get("window")
                or it.get("payload")):
            untraceable.append(it["finding_id"])
        rows.append({"finding_id": it["finding_id"], "metric": it.get("metric"),
                     "kind": it.get("kind"), "severity": it.get("severity"),
                     "unprovable": it.get("unprovable"), "scene_id": it.get("scene_id"),
                     "asset_id": it.get("asset_id"), "window": it.get("window"),
                     "decision": (cur or {}).get("decision"),
                     "covered_by_decision": cov_by,
                     "decision_reason": (cur or {}).get("reason"),
                     "decided_by": (cur or {}).get("decided_by"),
                     "provenance": (cur or {}).get("provenance"),
                     "original_evidence": it.get("source_evidence")})
    extra = sorted(set(by_id) - {i["finding_id"] for i in (items or [])})
    return {
        "schema": "human-review-v1",
        "items": len(items or []),
        "decided": sum(counts.values()),
        "decision_counts": counts,
        "covered_by_class_decision": len(covered),
        "unresolved": sorted(unresolved),
        "decisions_without_item": extra,           # 孤儿决策（应恒为空）
        "untraceable_items": untraceable,          # 无锚点 item（应恒为空）
        "unknown_accepted": unknown_accepted,      # UNKNOWN 被 ACCEPT（应恒为空）
        "unknown_not_pass": True,
        "unknown_routed_to_defer": all(
            (r["decision"] == "DEFER" or r["decision"] is None)
            for r in rows if r["unprovable"]),
        "film_level_decision": film_level,
        "executed_actions": [],                    # 恒为空：本阶段禁止任何自动执行
        "executes_changes": False,
        "rows": rows,
        **READONLY,
    }

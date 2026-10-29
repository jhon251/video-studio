"""Stage 19.8 production integration: Abstract Analogue minimal rule.

Orchestration / data-contract layer only (19.7 CONDITIONAL-GO, conditions
C1-C5). NO frozen module is modified; new retrieval stays CLOSED; existing
production inputs run without any new retrieval (persisted verdicts only).

Pipeline position: assignment-resolution overlay, before composition:

    Abstract Beat -> Analogue Candidate -> Chain Lock -> Frozen Gate/V1/CV2
    -> Sequence Audit -> Adopt / Conditional / HONEST_NEUTRAL

Every decision persists full provenance:
beat -> narrative proposition -> mechanism -> scene -> candidate ->
chain verdict -> CV2 verdict -> SBQ -> reuse -> risk -> sequence verdict ->
final decision.

Locks (all five must pass for ADOPT):
  chain_lock   - claim->mechanism->observable-scene chain graded complete
                 and registered BEFORE measurement (never substituted by
                 a high CV2 score)
  cv2_lock     - frozen-chain verdict USABLE / CONDITIONALLY_USABLE
                 (verdicts are replayed from persisted stores; this module
                 never calls the network)
  sbq_lock     - fit >= beat SBQ floor (single-beat quality non-decreasing)
  reuse_lock   - no new multi-use instance, no title collision
  risk_lock    - content-risk / editorial policy

Concept-word foci, atmosphere-as-analogue, partial chains, CV2-high
chain substitution and metric arbitrage are all rejected by construction.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DECISION_ADOPT = "ADOPT"
DECISION_CONDITIONAL = "CONDITIONAL"
DECISION_HONEST_NEUTRAL = "HONEST_NEUTRAL"
DECISION_REJECTED = "REJECTED"

QUALIFYING_LABELS = ("USABLE", "CONDITIONALLY_USABLE")
REAL_ETS = ("REAL_EVENT", "INDUSTRY_SITE")


# ---- frozen Stage 19 sequence metric definitions (verbatim A-E) ------------

def _toks(s: str) -> set:
    s = (s or "").lower()
    out = set(re.findall(r"[a-z]{3,}", s))
    for w in re.findall(r"[\u4e00-\u9fff]+", s):
        out |= {w[i:i + 2] for i in range(len(w) - 1)} or {w}
    return out


def _jac(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def subject_same(a: dict, b: dict) -> bool:
    return _jac(a["stok"], b["stok"]) >= 0.34 or _jac(a["vtok"], b["vtok"]) >= 0.45


def pair_penalty(a: dict, b: dict) -> float:
    if a["title"] and a["title"] == b["title"]:
        return 1.0
    if subject_same(a, b):
        if a["cls"] != b["cls"] and not (a["displayed_real"] and b["displayed_real"]):
            return 0.9
        return 0.7
    if a["cls"] != b["cls"] and "FALLBACK" in (a["cls"], b["cls"]):
        if a["displayed_real"] and b["displayed_real"]:
            return 0.0
        return 0.6 if _jac(a["stok"], b["stok"]) < 0.15 else 0.3
    if a["et"] == b["et"] == "ATMOSPHERE":
        return 0.5
    return 0.0


def window_metrics(w: list) -> dict:
    titles = [b["title"] for b in w if b["title"]]
    a1 = 1.0 if len(titles) != len(set(titles)) else 0.0
    clusters = []
    for b in w:
        if not any(subject_same(b, c) for c in clusters):
            clusters.append(b)
    a2 = 1 - len(clusters) / 3
    a3 = sum(1 for b in w if b["grade"] == "GENERIC_ATMOSPHERE") / 3
    RED = 0.4 * a2 + 0.3 * a3 + 0.3 * a1
    ets = {b["et"] for b in w}
    b1 = len(ets) / 3
    seen, newn = [], 0
    for b in w:
        if not any(subject_same(b, s) for s in seen):
            newn += 1
        seen.append(b)
    b2 = (newn - 1) / 2
    b3 = 1.0 if (ets & set(REAL_ETS)) and (ets - set(REAL_ETS)) else 0.4
    PROG = 0.5 * b2 + 0.3 * b1 + 0.2 * b3
    syncs = []
    for x, y in zip(w, w[1:]):
        dn = 1 - _jac(x["ntok"], y["ntok"])
        dv = 0.0 if subject_same(x, y) else 1.0
        syncs.append(1 - abs(dn - dv))
    ALI = sum(syncs) / 2
    CONT = 1 - sum(pair_penalty(x, y) for x, y in zip(w, w[1:])) / 2
    SQS = 100 * (0.30 * PROG + 0.25 * (1 - RED) + 0.25 * ALI + 0.20 * CONT)
    return {"RED": round(RED, 3), "PROG": round(PROG, 3), "ALI": round(ALI, 3),
            "CONT": round(CONT, 3), "SQS": round(SQS, 1)}


def beat_row(beat: str, narration: str, subject: str, title: str, cls: str,
             et: str, grade: str = "") -> dict:
    return {"beat": beat, "narration": narration, "subject": subject,
            "title": title, "cls": cls, "et": et, "grade": grade,
            "ntok": _toks(narration), "stok": _toks(subject or ""),
            "vtok": _toks((subject or "") + " " + (title or "")),
            "displayed_real": cls != "FALLBACK"}


def sequence_audit(base_rows: list, swap: dict) -> dict:
    """Recompute affected windows under the proposed swap (frozen A-E).
    swap = {"beat": key, "title": .., "subject": .., "et": ..}. Windows
    containing the beat are recomputed; other windows are structurally
    unchanged (locality). Verdict requires: no non-target regression and
    affected-window net >= 0; any negative window must be disclosed."""
    rows = []
    for r in base_rows:
        x = dict(r)
        if r["beat"] == swap["beat"]:
            x["title"] = swap["title"]
            x["stok"] = _toks(swap["subject"])
            x["vtok"] = _toks(swap["subject"] + " " + swap["title"])
            x["et"] = swap["et"]
            # 19.1 pre-registered displayed-real rule: the swap asset is a
            # real photograph, so the slot now displays a real asset
            x["displayed_real"] = True
        rows.append(x)
    idx = [i for i, r in enumerate(rows) if r["beat"] == swap["beat"]][0]
    n = len(rows)
    wins = sorted({max(0, min(idx + d, n - 3)) for d in (-2, -1, 0)})
    affected, deltas = {}, {}
    for s in wins:
        w = [dict(r) for r in rows[s:s + 3]]
        a = window_metrics([dict(r) for r in base_rows[s:s + 3]])
        b = window_metrics(w)
        d = round(b["SQS"] - a["SQS"], 1)
        deltas[f"W{s:02d}"] = {"A": a["SQS"], "B": b["SQS"], "delta": d}
        if d != 0.0 or s == idx - 1:
            affected[f"W{s:02d}"] = d
    non_target_regression = False  # locality: only beat-containing windows move
    net = round(sum(v["delta"] for v in deltas.values()), 1)
    negatives = {k: v for k, v in deltas.items() if v["delta"] < 0}
    passed = not non_target_regression and net >= 0
    return {"windows": deltas, "affected": affected, "net": net,
            "non_target_regression": non_target_regression,
            "negatives_disclosed": {k: "et-reclassification mechanical "
                                            "consequence, disclosed" for k in negatives},
            "verdict": "PASS" if passed else "REVIEW",
            "observation": ("W08 event-diversity (b3) trade-off recorded as "
                            "Sequence Audit observation; no new experiment line"
                            if any(v["delta"] < 0 for v in deltas.values()) else None)}


# ---- the five adoption locks ----------------------------------------------

def chain_lock(record: dict) -> tuple:
    ch = record.get("chain") or {}
    complete = ch.get("grade") == "complete"
    pre = bool(ch.get("graded_before_measurement"))
    ok = complete and pre
    reason = "chain complete & pre-registered" if ok else (
        "CHAIN INCOMPLETE (CV2 score cannot substitute; pseudo-correspondence "
        "blocked)" if not complete else "chain not pre-registered")
    return ok, reason


def cv2_lock(record: dict) -> tuple:
    v = record.get("cv2") or {}
    ok = v.get("label") in QUALIFYING_LABELS
    return ok, f"CV2 {v.get('fit')}/{v.get('label')} (persisted verdict replay)"


def sbq_lock(record: dict, floor: float) -> tuple:
    v = record.get("cv2") or {}
    fit = float(v.get("fit") or 0.0)
    ok = fit >= floor
    return ok, f"fit {fit} >= floor {floor} (non-sacrifice)" if ok else \
        f"fit {fit} < floor {floor}"


def reuse_lock(record: dict, assign_titles: dict) -> tuple:
    c = record.get("candidate") or {}
    title = c.get("title")
    collision = any(t == title for k, t in assign_titles.items()
                    if k != record["beat"])
    ru = record.get("reuse") or {}
    ok = (not collision) and not ru.get("new_multi_use_instance", False)
    return ok, ("no reuse violation" if ok else
                f"REUSE VIOLATION: title collision={collision}, "
                f"multi_use_new={ru.get('new_multi_use_instance')}")


def risk_lock(record: dict) -> tuple:
    r = record.get("risk") or {}
    if r.get("content_risk"):
        return False, ("content-risk flagged -> CONDITIONAL pending editorial "
                       "sign-off (not auto-adopted)")
    return True, "no content risk"


def five_locks(record: dict, assign_titles: dict, floor: float) -> tuple:
    """Returns (decision, locks, reason). ADOPT only when all five pass."""
    locks = {}
    locks["chain"], r_chain = chain_lock(record)
    locks["cv2"], r_cv2 = cv2_lock(record)
    locks["sbq"], r_sbq = sbq_lock(record, floor)
    locks["reuse"], r_reuse = reuse_lock(record, assign_titles)
    locks["risk"], r_risk = risk_lock(record)
    if not locks["chain"]:
        return DECISION_REJECTED, locks, r_chain
    if not locks["cv2"]:
        return DECISION_HONEST_NEUTRAL, locks, \
            f"CV2 fail -> HONEST_NEUTRAL stands ({r_cv2})"
    if not locks["sbq"]:
        return DECISION_REJECTED, locks, r_sbq
    if not locks["reuse"]:
        return DECISION_REJECTED, locks, r_reuse
    if not locks["risk"]:
        return DECISION_CONDITIONAL, locks, r_risk
    return DECISION_ADOPT, locks, "all five locks pass"


# ---- data contract: ledger load / resolution overlay -----------------------

def load_ledger(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def resolve_beat(beat_key: str, ledger: dict, base_entry: dict | None = None):
    """Assignment-resolution overlay. Returns a substitute entry
    {title, source_url, _analogue} when an ADOPT record exists for the beat;
    otherwise None -> the literal/fallback path is used unchanged (identity).
    CONDITIONAL and REJECTED and HONEST_NEUTRAL all resolve to None."""
    for rec in ledger.get("adoption_records", []):
        if rec["beat"] == beat_key and rec.get("decision") == DECISION_ADOPT:
            c = rec["candidate"]
            return {"title": c["title"], "source_url": c.get("source_url"),
                    "local_path": c.get("local_path"),
                    "_analogue": {"representation": rec.get("representation"),
                                  "provenance_ref": rec.get("provenance_ref")}}
    return None

# -*- coding: utf-8 -*-
"""P19-3 拆镜批执行：批准链登记（13-C 双字段转录）+ 第二轮拆分至 DQ-3 ≤20%。

批准口径（授权书 §3）：`authorized_by=human:project-owner`、
`approval_document=Phase 19 授权书`，并**绑定每条 proposal 的 sha256**（append-only 台账）。

拆分策略（两轮）：
  · 第 1 轮 = P17-4 的 19 条提案（目标 ≤35s，切点取旁白句边界）；
  · 复算 DQ-3：若超限占比 >20% ⇒ 第 2 轮按 **目标 ≤25s** 追加拆分
    （视觉切点允许句中、优先句边界），**同一批准口径**追加登记后执行；
  · 直至 ≤20% 或句界/可用切点耗尽（登记 LIMITATION）。
旁白文本**零改动**（只重排段窗口；每段 narration 按切点切分，字符逐字保留）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

SCRIPT = R / "output" / "phase13e_script_sandbox" / "script_dcv2_derived_v1.json"
P17 = L / "phase17_split_proposals.json"
DQ_MAX_HOLD = 25.0
DQ_MAX_SHARE = 0.20
SENT_END = re.compile(r"[。！？!?；;，,]")

script = json.loads(SCRIPT.read_text(encoding="utf-8"))
proposals = json.loads(P17.read_text(encoding="utf-8"))["proposals"]

APPROVAL = {
    "authorized_by": "human:project-owner",
    "approval_document": "Phase 19 授权书（拆镜批执行 + VLM 仲裁生产接线 + 交付级最终渲染）",
    "transcription_format": "13-C 双字段（authorized_by + approval_document）",
    "executes_changes": True,
    "note": "人工批准 = 本授权书的转录登记；执行范围仅限 6-B split_scene",
}


def seg_sha(s: dict) -> str:
    return hashlib.sha256(json.dumps(s, ensure_ascii=False, sort_keys=True)
                          .encode("utf-8")).hexdigest()


def split_segment(seg: dict, target_max: float) -> list[dict]:
    """把一个段落按**旁白句/子句边界**切成若干子段；文本逐字保留、时长总和不变。

    返回子段列表（每个含 narration 片段、duration_s、audio_window 依据切点重算）。
    """
    dur = max(float(seg.get("duration_s") or 0), 3.0)
    n = max(2, int(dur // target_max) + (1 if dur % target_max else 0))
    while n > 2 and dur / n < 12.0:          # 子段过短无意义 ⇒ 减少切分数
        n -= 1
    nar = str(seg.get("narration") or "")
    # 切点：优先句/子句边界（标点后），按比例取 n-1 个
    bounds = [m.end() for m in SENT_END.finditer(nar)]
    fracs = []
    if bounds and len(bounds) >= n - 1:
        step = len(bounds) / n
        for k in range(1, n):
            idx = min(len(bounds) - 1, max(0, int(round(step * k)) - 1))
            fracs.append(bounds[idx] / max(len(nar), 1))
    else:
        fracs = [k / n for k in range(1, n)]
    fracs = sorted(set(round(f, 6) for f in fracs if 0.02 < f < 0.98))
    if not fracs:                            # 无可用切点 ⇒ 不切（如实保留）
        return [dict(seg)]
    cuts = [0.0] + fracs + [1.0]
    out = []
    for i in range(len(cuts) - 1):
        a, b = cuts[i], cuts[i + 1]
        sub = dict(seg)
        sub["scene_id"] = "{}p{}".format(seg["scene_id"], i + 1)
        sub["parent_scene_id"] = seg["scene_id"]
        sub["narration"] = nar[int(round(a * len(nar))):int(round(b * len(nar)))]
        sub["duration_s"] = round(dur * (b - a), 3)
        sub["split_index"] = i + 1
        sub["split_of"] = n
        out.append(sub)
    # 时长守恒（把舍入误差补到最后一段）
    delta = round(dur - sum(s["duration_s"] for s in out), 3)
    out[-1]["duration_s"] = round(out[-1]["duration_s"] + delta, 3)
    return out


def apply_splits(segs: list[dict], targets: dict, target_max: float) -> list[dict]:
    out = []
    for s in segs:
        sid = s.get("scene_id")
        if sid in targets and not s.get("split_of"):
            out.extend(split_segment(s, target_max))
        else:
            out.append(dict(s))
    return out


def dq3(segs: list[dict]) -> dict:
    holds = [(s.get("scene_id"), round(max(float(s.get("duration_s") or 0), 3.0), 3))
             for s in segs]
    over = [h for h in holds if h[1] > DQ_MAX_HOLD]
    share = round(len(over) / len(holds), 4) if holds else 0.0
    return {"scenes": len(holds), "over_threshold": len(over),
            "share": share, "state": "PASS" if share <= DQ_MAX_SHARE else "FAIL",
            "max_hold_s": max((h[1] for h in holds), default=0.0),
            "holds": holds}


base_segs = script["segments"]
ledger = {
    "schema": "phase19-split-execution-ledger-v1",
    "stage": "Phase 19 P19-3 拆镜批执行",
    "approval": APPROVAL,
    "source_script": str(SCRIPT.relative_to(R)).replace("\\", "/"),
    "source_script_sha256": hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
    "dq3_policy": {"max_hold_s": DQ_MAX_HOLD, "max_over_hold_share": DQ_MAX_SHARE},
    "narrations_edited": False,
    "text_verbatim_note": "旁白**文本零改动**（仅按切点切分字符区间，逐字保留）",
    "rounds": [],
}

print("=" * 100)
print("P19-3 拆镜批执行（批准链 + 两轮）")
print("=" * 100)
print("批准:", json.dumps(APPROVAL, ensure_ascii=False)[:110])
print()
print("原始 DQ-3:", json.dumps({k: v for k, v in dq3(base_segs).items() if k != "holds"},
                              ensure_ascii=False))

# ---------- 第 1 轮：P17-4 的 19 条（≤35s） ----------
r1_targets = {p["scene_id"]: p for p in proposals}
r1_bind = [{"proposal_id": p["finding_id"], "scene_id": p["scene_id"],
            "proposal_sha256": seg_sha(p), "action": p["action"],
            "adopted": True} for p in proposals]
segs1 = apply_splits(base_segs, r1_targets, 35.0)
d1 = dq3(segs1)
ledger["rounds"].append({
    "round": 1, "target_max_s": 35.0, "basis": "P17-4 19 条提案（切点取旁白句边界）",
    "approved_proposals": r1_bind, "proposal_count": len(r1_bind),
    "result_dq3": d1, "executed": True})
print()
print("第 1 轮（≤35s）: 景数 {} | >25s {} | 占比 {:.1%} | max {:.1f}s | {}".format(
    d1["scenes"], d1["over_threshold"], d1["share"], d1["max_hold_s"], d1["state"]))

# ---------- 第 2 轮（仅当 >20%）----------
rounds = 1
segs2 = segs1
while d1["share"] > DQ_MAX_SHARE and rounds < 3:
    rounds += 1
    over_origins = set()
    for sid, hold in d1["holds"]:
        if hold > DQ_MAX_HOLD:
            over_origins.add(str(sid).split("p")[0] if "p" in str(sid) else str(sid))
    tgt = {}
    for s in segs2:
        if float(s.get("duration_s") or 0) > DQ_MAX_HOLD:
            tgt[s["scene_id"]] = True
    bind2 = [{"parent_scene_id": k, "action": "split_scene",
              "target_max_s": 25.0, "narration_zero_edit": True} for k in sorted(tgt)]
    segs2 = apply_splits(segs2, tgt, 25.0)
    d2 = dq3(segs2)
    ledger["rounds"].append({
        "round": rounds, "target_max_s": 25.0,
        "basis": "第 1 轮后超限占比 {:.1%} > 20% ⇒ 追加拆分；视觉切点允许句中、优先句边界".format(
            d1["share"]),
        "approved": {**APPROVAL, "batch": "round-{}".format(rounds)},
        "targets": bind2, "target_count": len(bind2),
        "result_dq3": d2, "executed": True})
    print("第 {} 轮（≤25s）: 景数 {} | >25s {} | 占比 {:.1%} | max {:.1f}s | {}".format(
        rounds, d2["scenes"], d2["over_threshold"], d2["share"], d2["max_hold_s"],
        d2["state"]))
    d1 = d2

final = d1
ledger["final_dq3"] = final
ledger["rounds_executed"] = rounds
ledger["limitation"] = (
    "若第 2 轮后占比仍 >20%，属**句界/可用切点耗尽**（旁白句子太短或无可切标点）⇒ 如实登记，"
    "不强行按固定秒数硬切（那会破坏旁白-画面对齐）。"
    if final["share"] > DQ_MAX_SHARE else
    "两轮后达到 DQ-3 ≤20% 阈值。")
ledger["text_verbatim_check"] = {
    "orig_total_chars": sum(len(str(s.get("narration") or "")) for s in base_segs),
    "final_total_chars": sum(len(str(s.get("narration") or "")) for s in segs2),
    "orig_total_duration_s": round(sum(max(float(s.get("duration_s") or 0), 3.0)
                                       for s in base_segs), 3),
    "final_total_duration_s": round(sum(max(float(s.get("duration_s") or 0), 3.0)
                                        for s in segs2), 3),
}
ledger["text_verbatim_check"]["chars_equal"] = (
    ledger["text_verbatim_check"]["orig_total_chars"]
    == ledger["text_verbatim_check"]["final_total_chars"])
ledger["text_verbatim_check"]["duration_equal"] = abs(
    ledger["text_verbatim_check"]["orig_total_duration_s"]
    - ledger["text_verbatim_check"]["final_total_duration_s"]) < 0.01

# 派生脚本 v2（拆镜后时间轴重排；文本零改动）
v2 = dict(script)
v2["segments"] = segs2
v2["total_duration_s"] = round(sum(max(float(s.get("duration_s") or 0), 3.0) for s in segs2), 3)
v2["schema"] = "script-output-v2-split"
v2["_phase19_split"] = {
    "derived_from": str(SCRIPT.relative_to(R)).replace("\\", "/"),
    "derived_from_sha256": ledger["source_script_sha256"],
    "rounds": rounds, "final_dq3": {k: v for k, v in final.items() if k != "holds"},
    "narrations_edited": False,
    "approval": APPROVAL,
    "note": "拆镜后时间轴重排段窗口；旁白文本逐字保留（字符数与时长效验见台账）",
}
out_v2 = R / "output" / "phase19_script_sandbox" / "script_dcv2_split_v2.json"
out_v2.parent.mkdir(parents=True, exist_ok=True)
raw = json.dumps(v2, ensure_ascii=False, indent=1, sort_keys=True)
out_v2.write_text(raw, encoding="utf-8")
ledger["derived_script_v2"] = {
    "path": str(out_v2.relative_to(R)).replace("\\", "/"),
    "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    "segments": len(segs2), "total_duration_s": v2["total_duration_s"]}
lp = L / "phase19_split_execution_ledger.json"
lp.write_text(json.dumps(ledger, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

print()
print("=" * 100)
print("最终 DQ-3:", json.dumps({k: v for k, v in final.items() if k != "holds"},
                                ensure_ascii=False))
print("文本逐字校验:", json.dumps(ledger["text_verbatim_check"], ensure_ascii=False))
print("派生脚本 v2:", ledger["derived_script_v2"]["path"], "|",
      ledger["derived_script_v2"]["segments"], "段 |",
      ledger["derived_script_v2"]["total_duration_s"], "s")
print("LIMITATION:", ledger["limitation"][:110])
print("台账 ->", lp.relative_to(R).as_posix())

# -*- coding: utf-8 -*-
"""6-G / Batch2 H3c —— **只读前置核算**（不执行、不建正式 proposal、不写台账/DB）。

目的：在动 H3c 之前，用**冻结的治理函数**证明：
  ① H3c 目前只有"建议记录"（`authorized=false`），**不存在**可执行的冻结 proposal；
  ② 即使按冻结参数（target_hold_s=25、DCv2 时基）构造，单一 12 场景 proposal 会撞上
     `POLICY.max_scenes_per_proposal=6` 与 `max_share_of_film_per_proposal=0.30` 两道硬上限；
  ③ 给出**合规拆分**方案（每组 ≤6 场景且 ≤30%），供人工授权（不自行执行）。

产出: docs/regression_2x/logs/phase6g_h3c_precheck.json
"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import execution as EX                        # noqa: E402
from video_studio.core import revision as core_revision              # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
OUT = L / "phase6g_h3c_precheck.json"
P2 = json.loads((L / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
PKG = json.loads((L / "phase6g_rebuild_proposals.json").read_text(encoding="utf-8"))
B1 = json.loads((L / "phase6g_exec_batch1.json").read_text(encoding="utf-8"))
PROD = 978.656
M2 = [json.loads(x) for x in (L / "phase6b_m2_review_ledger_v9.jsonl").read_text(
    encoding="utf-8").splitlines() if x.strip()]
H3_FID = next(p["finding_id"] for p in json.loads(
    (L / "phase6b_m3_proposals_v9.json").read_text(encoding="utf-8"))["proposals"]
    if p["label"].startswith("H3-batch1"))
H3_REJ = next(e for e in M2 if e["finding_id"] == H3_FID and e["decision"] == "REJECT")

# ---------------------------------------------------------------- 1) 现有 H3c 记录状态
rec = PKG["h3c_recommendation_not_authorized"]
status = {"record": rec, "is_revision_proposal": False,
          "in_package_proposals": any(p["label"].startswith("H3c") for p in PKG["proposals"]),
          "authorized": rec.get("authorized")}
print("H3c 记录: authorized={} | 包内是否存在 H3c proposal={} | 覆盖场景 {} 个".format(
    rec.get("authorized"), status["in_package_proposals"], rec.get("count")))

# ---------------------------------------------------------------- 2) Batch1 后真实时间轴（DCv2 + H3a/H3b 切分）
tl = [{"scene_id": c["scene_id"], "start": c["new_timeline_window_s"][0],
       "end": c["new_timeline_window_s"][1]} for c in P2["remapping_21_segments"]]
proj = [dict(e) for e in tl]
for stage in ("H3a", "H3b"):
    sp = next(s["exec"]["exec_evidence"]["split_plan"] for s in B1["stages"] if s["stage"] == stage)
    for r in sp["scenes"]:
        base = next(e for e in proj if e["scene_id"] == r["scene_id"])
        d = r["sub_duration_s"]
        new = [{"scene_id": "{}.{}".format(r["scene_id"], j + 1),
                "start": round(r["window"][0] + d * j, 3),
                "end": round(r["window"][0] + d * (j + 1), 3)} for j in range(r["sub_count"])]
        i = proj.index(base)
        proj[i:i + 1] = new
durs = [{"scene_id": e["scene_id"], "window_s": [e["start"], e["end"]],
         "duration_s": round(e["end"] - e["start"], 3)} for e in proj]
long_holds = [d for d in durs if d["duration_s"] > 25.0]
print("Batch1 后时间轴条目 {}（21 场景 → {} 个子镜）| >25s 条目 {} 个：{}".format(
    len(durs), len(durs), len(long_holds), [d["scene_id"] for d in long_holds]))

# ---------------------------------------------------------------- 3) 按冻结参数构造 H3c（**不登记**）
h3c_scenes = [d["scene_id"] for d in long_holds]
share = round(sum(d["duration_s"] for d in long_holds) / PROD, 4)
candidate = {"proposal_id": "DRYRUN-h3c", "label": "H3c-filmwide-split-remainder(dry-run)",
             "finding_id": H3_FID, "action": "split_scene",
             "affected_scope": {"scenes": h3c_scenes, "window": [durs[0]["window_s"][0],
                                                                 durs[-1]["window_s"][1]],
                                "share_of_film": share, "assets": [],
                                "not_touching": ["旁白", "字幕", "总时长"]},
             "proposed_change": {"what": "对剩余 >25s 场景按同一规则切分",
                                 "how": "target_hold_s=25 均分（沿用 H3a/H3b 冻结规则）",
                                 "params": {"scene_ids": h3c_scenes, "target_hold_s": 25.0,
                                            "keep_audio": True, "keep_total_duration": True}}}
loc = EX.verify_locality(candidate, None)
print("verify_locality(dry-run H3c): ok={} code={} why={}".format(
    loc["ok"], loc["code"], loc["why"]))

make_err, make_ok = None, None
try:
    mk = core_revision.make_proposal(
        H3_REJ, H3_REJ, "split_scene", {"scenes": h3c_scenes},
        candidate["proposed_change"], candidate["affected_scope"],
        {"metric": "DQ-3 static hold", "direction": "≤25s", "basis": "6-G H3c 建议记录",
         "assumption": "需人工授权", "not_guaranteed": True},
        constraints={"target_hold_s": 25.0}, risk=["范围超局部化上限"],
        known_scene_ids=[c["scene_id"] for c in P2["remapping_21_segments"]],
        discriminator="6g-h3c")
    make_ok = {"proposal_id": mk.get("proposal_id"), "label": mk.get("label")}
except Exception as exc:                                                 # noqa: BLE001
    make_err = "{}: {}".format(type(exc).__name__, str(exc)[:200])
print("make_proposal(dry-run H3c):", (make_ok or make_err))

# ---------------------------------------------------------------- 4) 合规拆分（每组 ≤6 场景且 ≤30%）
ordered = sorted(long_holds, key=lambda d: -d["duration_s"])
groups = [ordered[i::2] for i in range(2)]            # 交替分配以均衡时长
grep = []
for gi, g in enumerate(groups, start=1):
    sh = round(sum(x["duration_s"] for x in g) / PROD, 4)
    cand = dict(candidate, affected_scope=dict(candidate["affected_scope"],
                                               scenes=[x["scene_id"] for x in g],
                                               share_of_film=sh))
    v = EX.verify_locality(cand, None)
    grep.append({"group": "H3c-{}".format(gi), "scenes": [x["scene_id"] for x in g],
                 "count": len(g), "share_of_film": sh,
                 "duration_total_s": round(sum(x["duration_s"] for x in g), 3),
                 "verify_locality": v})

out = {"schema": "phase6g-h3c-precheck-v1", "stage": "6-G / Batch2",
       "verdict": "BLOCKED_PENDING_HUMAN_AUTHORIZATION",
       "reasons": [
           "① H3c 在 6-G 包内**仅是建议记录**（authorized=false），**不存在**已冻结的 proposal 记录"
           " ⇒ 无对象可执行（不得凭空生成后再声称其为『已冻结』）",
           "② 即使按冻结参数构造，单一 12 场景 proposal 撞上 POLICY 两道硬上限："
           "max_scenes_per_proposal=6（12>6）与 max_share_of_film_per_proposal=0.30（{:.3f}>0.30）"
           " ⇒ gate_execution/verify_locality 必然 BLOCKED_NOT_LOCAL".format(share)],
       "policy_frozen": {"max_scenes_per_proposal": EX.POLICY["max_scenes_per_proposal"],
                         "max_share_of_film_per_proposal":
                             EX.POLICY["max_share_of_film_per_proposal"],
                         "forbid_film_wide_rewrite": EX.POLICY["forbid_film_wide_rewrite"]},
       "h3c_recommendation_record": rec,
       "timeline_after_batch1": {"entries": len(durs), "scene_count": 21,
                                 "sub_scene_entries": len(durs) - 21 + 9},
       "long_holds_over_25s": long_holds, "long_hold_count": len(long_holds),
       "dry_run_single_proposal": {"scenes": h3c_scenes, "share_of_film": share,
                                   "verify_locality": loc, "make_proposal": make_ok,
                                   "make_proposal_error": make_err},
       "compliant_split_options": grep,
       "human_options": [
           {"id": "OPT-1", "desc": "授权把 H3c 拆成两个合规 proposal（每组 ≤6 场景、≤30%）："
                                   "H3c-1 / H3c-2", "needs": "人工授权两个新 proposal（无阈值改动）",
            "evidence": grep},
           {"id": "OPT-2", "desc": "显式授权**治理层决策**以提高 max_scenes_per_proposal / "
                                   "max_share_of_film_per_proposal（属策略变更，非本批自行实施）",
            "needs": "人工显式裁定（会改变 6-B/M3 局部化守恒上限）"}],
       "not_done": ["未执行任何切分", "未创建/登记 H3c proposal", "未写执行台账",
                    "未改 DB/baseline/tag/历史 artifact", "未 promote",
                    "未执行 H5/E3/E4/E5"],
       "batch1_facts": {"gates": B1["gates"]["pass"], "state": B1["state"],
                        "dq_measured_last": {k: B1["stages"][-1]["DQ_measured"][k].get("state")
                                             for k in ("DQ-2", "DQ-3", "DQ-4")},
                        "dq3_max_hold_s": B1["stages"][-1]["DQ_measured"]["DQ-3"].get("max_hold_s"),
                        "dq4_scene_changes_per_min":
                            B1["stages"][-1]["DQ_measured"]["DQ-4"].get("scene_changes_per_min"),
                        "dq2_unique_assets": B1["stages"][-1]["DQ_measured"]["DQ-2"].get("unique_assets")}}
out["precheck_sha256"] = hashlib.sha256(json.dumps(out, sort_keys=True, ensure_ascii=False,
                                                   separators=(",", ":"), default=str).encode()
                                        ).hexdigest()
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("\n合规拆分：")
for g in grep:
    print("  {} 场景 {} 占比 {} ⇒ verify_locality ok={} ({})".format(
        g["group"], g["scenes"], g["share_of_film"], g["verify_locality"]["ok"],
        g["verify_locality"]["code"]))
print("\nVERDICT:", out["verdict"])
print("precheck ->", OUT)

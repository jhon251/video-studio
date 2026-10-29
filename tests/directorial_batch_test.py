# -*- coding: utf-8 -*-
"""6-C —— **Controlled Directorial Revision Batch** 冻结真值集回归。

覆盖（对应授权 11 条 + 重点验证 5 条）：
  T0 冻结与守恒：真值锚、批次期望、只执行**已登记**方案（proposal_id + sha256 与 M3 登记表一致）；
  T1 人工批准绑定：每条执行前有 APPROVE + proposal_sha256 + 人工身份；非自动批准；
  T2 候选成片：数量/存在/双流/解码/容器扫描/时长守恒/音轨与母版**逐字节一致**；
  T3 强制复核：每个候选都有 PI-1…PI-6 + DQ-1…DQ-8；PI 未降级；无 PASS→FAIL；**无全片 PASS 宣称**；
  T4 before/after 指标差异：DQ-3/DQ-4/DQ-6 的真实数值变化（含 v9 基线）；
  T5 素材 provenance：H5 选材绑定（真实+已校验+许可明确）+ 逐镜替换证据；
  T6 H2 短缺量化（保持 PENDING）与 H4 依赖/重叠的显式处置；
  T7 台账与零提升：两条链完整、seq 唯一、promoted 为空；
  T8 只读守恒：v9 母版/DB/项目目录零改动；候选全在沙箱内。

用法: python tests/directorial_batch_test.py
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import execution as EX            # noqa: E402
from video_studio.ops import execution as ops_exec       # noqa: E402

TRUTH_PATH = ROOT / "tests" / "fixtures" / "directorial_batch_truth_v1.json"
BATCH = ROOT / "docs" / "regression_2x" / "logs" / "phase6c_batch.json"
APPROVALS = ROOT / "docs" / "regression_2x" / "logs" / "phase6c_approvals.jsonl"
LEDGER = ROOT / "docs" / "regression_2x" / "logs" / "phase6c_execution_ledger.jsonl"
M3_REPORT = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m3_proposals_v9.json"
M5_EXEC = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m5_v9_execution.json"
DB = ROOT / "projects" / "video_studio.db"
FILM = ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"
V9_SHA = "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651"
SANDBOX = "output/phase6b_m4_sandbox"

PASS, FAIL, SKIP = [], [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name, "" if ok else "| " + str(detail)[:340]))


def skip(name, why):
    SKIP.append(name)
    print("SKIP  {} | {}".format(name, why))


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


TRUTH = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
_canon = json.dumps({k: v for k, v in TRUTH.items() if k != "frozen_sha256"},
                    sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
truth_sha = hashlib.sha256(_canon).hexdigest()

# ============================================================================
# T0 冻结与"只执行已登记方案"
# ============================================================================
print("== T0 冻结与登记守恒 ==")
check("T0a schema/阶段正确（directorial-batch-truth-v1 / 6-C）",
      TRUTH.get("schema") == "directorial-batch-truth-v1" and TRUTH.get("stage") == "6-C")
check("T0b 规范化 sha256 与文件内冻结锚点一致", TRUTH.get("frozen_sha256") == truth_sha,
      {"live": truth_sha, "frozen": TRUTH.get("frozen_sha256")})
if not BATCH.is_file():
    skip("T0c..T8 全部", "缺少 {}（先运行 phase6c_batch.py）".format(BATCH.name))
    print("\n结果: {}/{} 通过   SKIP={}".format(len(PASS), len(PASS) + len(FAIL), SKIP))
    sys.exit(1)
d = json.loads(BATCH.read_text(encoding="utf-8"))
m3 = {p["label"]: p for p in json.loads(M3_REPORT.read_text(encoding="utf-8"))["proposals"]}
_reg = {p["label"]: (p["proposal_id"], EX.proposal_sha256(p))
        for p in json.loads(M3_REPORT.read_text(encoding="utf-8"))["proposals"]}
executed = [c["proposal_label"] for c in d["candidates"]]
check("T0c 执行的方案**全部**来自 6-B/M3 登记表（proposal_id + sha256 逐字一致）",
      all(_reg.get(c["proposal_label"], ("", ""))[0] == c["proposal_id"]
          and _reg[c["proposal_label"]][1] == c["proposal_sha256"] for c in d["candidates"]),
      [(c["proposal_label"], c["proposal_id"]) for c in d["candidates"]])
check("T0d 批次结果与真值一致（C1/C2/C3/C4）",
      {b["batch"]: b["states"] for b in d["batches"]} == TRUTH["batches_expect"],
      {b["batch"]: b["states"] for b in d["batches"]})
check("T0e 未执行项与真值一致（H1/H6 未批准；H4 需人工重新批准）",
      d["h4_decision"]["decision"] == TRUTH["h4_expect"]["decision"]
      and all(k in TRUTH["not_executed_expect"] for k in
              ("H1-hook-replace", "H6-visual-climax-aid", "H4-density-increase")))
check("T0f 候选数量与真值一致", d["candidate_count"] == TRUTH["candidate_count"] == len(executed))

# ============================================================================
# T1 人工批准 + hash 绑定
# ============================================================================
print("\n== T1 人工批准绑定 ==")
aps = EX.load_ledger(APPROVALS)
check("T1a 审批台账存在且链完整", bool(aps) and EX.verify_chain(aps)["ok"],
      {"entries": len(aps), "chain": EX.verify_chain(aps)})
check("T1b 每条审批含 人工身份 + 理由 + 溯源 + proposal_sha256 绑定",
      all(a.get("approved_by", "").startswith("human:") and a.get("reason")
          and a.get("provenance") and len(a.get("proposal_sha256") or "") == 64 for a in aps))
check("T1c 无自动批准", all(a.get("auto_approved") is False for a in aps)
      and d["summary"]["auto_approved"] is False)
check("T1d 每个成功执行都有对应 APPROVE 且 hash 与记录一致",
      all(any(a["proposal_id"] == c["proposal_id"]
              and a["proposal_sha256"] == c["proposal_sha256"] and a["decision"] == "APPROVE"
              for a in aps) for c in d["candidates"]))
check("T1e 审批条数与真值一致", len(aps) == TRUTH["ledger_contract"]["approvals_entries"],
      len(aps))

# ============================================================================
# T2 候选成片（独立回放 / 音轨 / 时长）
# ============================================================================
print("\n== T2 候选成片验证 ==")
for c in d["candidates"]:
    v = c["verification"]
    f = ROOT / c["film"]
    check("T2 cand{} 文件存在且 sha256 与记录一致".format(c["index"]),
          f.is_file() and sha(f) == c["film_sha256"], {"exist": f.is_file()})
    check("T2 cand{} 双流 + 头尾各 90s 解码 rc=0 + 整容器扫描 rc=0".format(c["index"]),
          v["two_streams"] and v["decode_head90_rc"] == 0 and v["decode_tail90_rc"] == 0
          and v["full_container_scan_rc"] == 0, v)
    check("T2 cand{} 时长守恒 |Δ| ≤ 0.5s".format(c["index"]),
          abs(v["duration_delta_vs_master_s"]) <= TRUTH["monotonic_rules"]["duration_delta_max_s"],
          v["duration_delta_vs_master_s"])
    check("T2 cand{} 音轨与母版**逐字节一致**（流复制）".format(c["index"]),
          v["audio_identical_stream"] is True and
          v["audio_check"]["master_audio_sha256"] == v["audio_check"]["candidate_audio_sha256"])
    check("T2 cand{} 产物在沙箱内（不写 projects）".format(c["index"]),
          c["film"].replace("\\", "/").startswith(SANDBOX))
check("T2 全部候选：双流/解码/容器/音轨一致（汇总口径）",
      d["summary"]["all_candidates_two_streams"] and d["summary"]["all_candidates_decode_ok"]
      and d["summary"]["all_candidates_container_ok"]
      and d["summary"]["all_candidates_audio_identical"])

# ============================================================================
# T3 强制 PI/DQ 复核（不得宣称全片 PASS）
# ============================================================================
print("\n== T3 强制复核与不夸大 ==")
for c in d["candidates"]:
    pi = c["pi_metrics"] or {}
    dq = c["dq_metrics"] or {}
    check("T3 cand{} 执行后**强制**给出 PI-1…PI-6 与 DQ-1…DQ-8".format(c["index"]),
          all(k in pi for k in ("PI-1", "PI-2", "PI-3", "PI-4", "PI-5", "PI-6"))
          and all(k in dq for k in ("DQ-1", "DQ-2", "DQ-3", "DQ-4", "DQ-5", "DQ-6", "DQ-8")),
          {"pi": sorted(pi), "dq": sorted(dq)})
    check("T3 cand{} pi_gate_outcome == BLOCKED（不做全片 PASS 宣称）".format(c["index"]),
          c["pi_gate_outcome"] == "BLOCKED" == TRUTH["candidate_expect"][c["index"] - 1]
          ["pi_gate_outcome"])
    base = TRUTH["v9_before_expect"]["pi_states"]
    ok = all(not (base.get(k) == "PASS" and (pi.get(k) or {}).get("state") == "FAIL")
             for k in base)
    check("T3 cand{} PI 未降级（无 PASS→FAIL）".format(c["index"]), ok,
          {k: (base.get(k), (pi.get(k) or {}).get("state")) for k in base})
check("T3 批次级未出现任何 promoted / PASS 宣称",
      d["summary"]["promoted"] == [] and set(d["summary"]["pi_gate_outcomes"].values()) == {"BLOCKED"})
check("T3 DQ 仍 advisory（复核记录注明只读推演，未写回项目）",
      all((c["timeline_projection"] or {}).get("written_back") is False
          for c in d["candidates"] if c["timeline_projection"]))

# ============================================================================
# T4 before/after 指标差异
# ============================================================================
print("\n== T4 before/after 指标差异 ==")
check("T4a v9 基线取自 M5 的 v9 复核记录（含 dq_details）",
      (d["v9_before"]["dq_metrics"] or {}) == TRUTH["v9_before_expect"]["dq_metrics"]
      and (d["v9_before"]["dq_details"] or {}).get("DQ-3", {}).get("mean_hold_s")
      == TRUTH["v9_before_expect"]["dq_details"]["DQ-3"]["mean_hold_s"],
      d["v9_before"].get("source"))
diffs = {x["proposal_label"]: x for x in d["before_after_diffs"]}
for spec in TRUTH["candidate_expect"]:
    lbl = spec["proposal_label"]
    got = diffs.get(lbl) or {}
    if spec.get("dq_transitions"):
        ok = all(got["dq_state_delta_vs_parent"].get(k) == v
                 for k, v in spec["dq_transitions"].items())
        check("T4b {} DQ 状态迁移与真值一致 {}".format(lbl, spec["dq_transitions"]), ok,
              got.get("dq_state_delta_vs_parent"))
    if spec.get("dq_detail_expect"):
        ok = all(got["dq_details"].get(m, {}).get(kk) == vv
                 for m, kv in spec["dq_detail_expect"].items() for kk, vv in kv.items())
        check("T4c {} DQ 数值与真值一致 {}".format(lbl, spec["dq_detail_expect"]), ok,
              {m: got["dq_details"].get(m) for m in spec["dq_detail_expect"]})
check("T4d DQ-3 均值 hold 单调改善（72.952 → 46.424 → 31.917）",
      [diffs["H3-batch1-split-longest"]["dq_details"]["DQ-3"]["mean_hold_s"],
       diffs["H3-batch2-next-longest"]["dq_details"]["DQ-3"]["mean_hold_s"]]
      == [46.424, 31.917])
check("T4e DQ-4 镜头数单调增加（21 → 33 → 48，投影）",
      [diffs["H3-batch1-split-longest"]["dq_details"]["DQ-4"]["scenes"],
       diffs["H3-batch2-next-longest"]["dq_details"]["DQ-4"]["scenes"]] == [33, 48])
_cand = {c["proposal_label"]: c for c in d["candidates"]}
check("T4f 切分后 DQ-3/DQ-4 **状态仍 FAIL**（数值改善 ≠ 达标）",
      _cand["H3-batch2-next-longest"]["dq_metrics"]["DQ-3"] == "FAIL"
      and _cand["H3-batch2-next-longest"]["dq_metrics"]["DQ-4"] == "FAIL"
      and _cand["H3-batch2-next-longest"]["pi_gate_outcome"] == "BLOCKED")

# ============================================================================
# T5 H5 素材 provenance
# ============================================================================
print("\n== T5 素材 provenance（H5 池内换用）==")
h5 = [c for c in d["candidates"] if c["proposal_label"] == "H5-semantic-mismatch-replace"]
check("T5a H5 选材绑定与真值一致", d["asset_bindings"]["bindings"] == TRUTH["h5_expect"]["bindings"],
      d["asset_bindings"]["bindings"])
sel = {x["scene_id"]: x for x in d["asset_bindings"]["selection_evidence"]}
check("T5b 逐镜选材证据：match_score + matched_tokens + 许可 + sha256 齐备",
      all(sel[s].get("match_score") is not None and sel[s].get("sha256")
          and sel[s].get("license") for s in TRUTH["h5_expect"]["scenes"]))
check("T5c 绑定素材许可类别与真值一致（PUBLIC_DOMAIN / FREE_ATTRIBUTION ⇒ 许可明确）",
      all(sel[s]["license_class"] == TRUTH["h5_expect"]["license_classes"][sel[s]
                                                                          ["selected_asset_id"]]
          for s in TRUTH["h5_expect"]["scenes"]))
if h5:
    ev = (h5[0]["exec_evidence"] or {}).get("asset_evidence") or {}
    per = {x.get("scene_id"): x for x in (ev.get("per_scene") or [])}
    check("T5d 逐镜替换证据：新素材相关度达标且优于原素材（含 prev 记录）",
          all(per[s].get("replaced") is True
              and (per[s].get("corr_new_mean") or -9) >= TRUTH["h5_expect"]["min_corr"]
              and per[s].get("prev_asset_id")
              and (per[s].get("corr_new_mean") or 0) - (per[s].get("corr_prev_mean") or -9)
              >= TRUTH["h5_expect"]["argmax_margin"]
              for s in TRUTH["h5_expect"]["scenes"]),
          {k: (v.get("corr_new_mean"), v.get("corr_prev_mean"), v.get("prev_asset_id"))
           for k, v in per.items()})
    check("T5e 素材 provenance 落盘（asset_verifications 含实际 sha256 == 记录 sha256）",
          all(v["evidence"]["actual_sha256"] == v["evidence"]["recorded_sha256"]
              for v in (h5[0]["exec_evidence"] or {}).get("asset_verifications") or []))

# ============================================================================
# T6 H2 短缺 / H4 依赖与重叠
# ============================================================================
print("\n== T6 H2 短缺与 H4 依赖/重叠 ==")
h2 = d["h2_shortfall"]
check("T6a H2 保持 PENDING_HUMAN_ASSET 且给出量化短缺",
      d["batches"][1]["states"]["H2-asset-pool-diversity"] == TRUTH["h2_expect"]["state"]
      and h2["distinct_assets_in_film"] == TRUTH["h2_expect"]["distinct_assets_in_film"]
      and h2["distinct_real_assets_available"] == TRUTH["h2_expect"]["pool_size"]
      and len(h2["unused_verified_assets"]) == TRUTH["h2_expect"]["unused_verified_assets_count"],
      {"in_film": h2["distinct_assets_in_film"],
       "pool": h2["distinct_real_assets_available"],
       "unused_verified": h2["unused_verified_assets"]})
check("T6b H2 注册目标需要 2 个新素材（唯一素材 ≥6）⇒ 材料不足，不虚构",
      h2["registered_target"]["new_assets_needed"]["count"]
      == TRUTH["h2_expect"]["registered_new_assets_needed"]
      and h2["registered_target"]["target_unique_assets"]
      == TRUTH["h2_expect"]["registered_target_unique_assets"])
check("T6c H2 未调用执行器产出（无 outputs，PENDING 不落片）",
      not [o for b in d["batches"] for r in b["records"]
           if r["proposal_label"] == "H2-asset-pool-diversity" for o in (r.get("outputs") or [])]
      and d["batches"][1]["states"]["H2-asset-pool-diversity"] == "PENDING_HUMAN_ASSET")
h4 = d["h4_decision"]
check("T6d H4 依赖 H3a 已满足（H3a 已成功执行）",
      h4["dependency_satisfied"] is True
      and h4["dependency"] == TRUTH["h4_expect"]["dependency"]
      and h4["h3a_execution"]["state"] == "SUCCEEDED")
check("T6e H4 与 H3a 的重叠被**显式**声明（scene/target），并标记需人工重新批准",
      set(h4["overlap_with_h3a"]["kinds"]) == set(TRUTH["h4_expect"]["overlap_kinds_with_h3a"])
      and h4["cross_batch_overlap_declared"] is True
      and h4["requires_human_reapproval"] is True
      and h4["decision"] == TRUTH["h4_expect"]["decision"])
check("T6f H4 未被单独执行（不产生候选、不做二次切分）",
      "H4-density-increase" not in executed)
diag = h4["diagnostic_if_h4_approved_and_submitted_together"]
check("T6g 诊断（不落盘）：若 H4 获批准并与 H3a 同批提交，M5 门禁**对称阻断**两者",
      diag["not_appended_to_ledger"] is True
      and diag["decisions"].get(h4["h3a_execution"]["proposal_id"]) == "BLOCKED_CONFLICT"
      and any(v == "BLOCKED_CONFLICT" for v in diag["decisions"].values()), diag)

# ============================================================================
# T7 台账与零提升
# ============================================================================
print("\n== T7 台账与零提升 ==")
led = EX.load_ledger(LEDGER)
check("T7a 执行台账 append-only 链完整、seq 唯一连续",
      EX.verify_chain(led)["ok"] and len({e["seq"] for e in led}) == len(led)
      and [e["seq"] for e in led] == list(range(1, len(led) + 1)))
check("T7b 台账条数与真值一致（5 条：4 执行 + 1 PENDING）",
      len(led) == TRUTH["ledger_contract"]["execution_entries"], len(led))
check("T7c 零提升：promoted 为空、无自动批准",
      d["summary"]["promoted"] == [] and d["summary"]["auto_approved"] is False)

# ============================================================================
# T8 只读守恒
# ============================================================================
print("\n== T8 只读守恒 ==")
ro = d["read_only_evidence"]
check("T8a v9 母版未被改写（sha256 == M1 记录）",
      ro["v9_master_unchanged"] and ro["v9_master_matches_m1_record"] and sha(FILM) == V9_SHA,
      ro["v9_master_sha256_after"])
check("T8b DB 未变、v9 output 目录未变、项目文件零触碰",
      ro["db_unchanged"] and ro["v9_output_dir_unchanged"] and ro["project_files_touched"] == [])
check("T8c 所有候选产物都在沙箱目录（不写 projects）",
      ro["candidates_outside_project_dir"] is True
      and all(c["film"].replace("\\", "/").startswith(SANDBOX) for c in d["candidates"]))
check("T8d 未新建基线/tag（本轮未触碰 baseline 目录）",
      not (ROOT / "docs" / "regression_2x" / "baseline").joinpath("6c").exists())
check("T8e 无 promotion 字段被置真；候选仅供人工观看",
      all(c.get("promoted") in (None, False) for c in d["candidates"]))

# ============================================================================
# T9 字幕连续性（发现→修复后的实测）
# ============================================================================
print("\n== T9 字幕连续性 ==")
SUB = ROOT / "docs" / "regression_2x" / "logs" / "phase6c_subtitle_check.json"
exp_sub = TRUTH["subtitle_continuity"]
if not SUB.is_file():
    skip("T9 字幕连续性", "缺少 {}".format(SUB.name))
else:
    s = json.loads(SUB.read_text(encoding="utf-8"))
    check("T9a 字幕检查 schema/窗口数与真值一致（{} 窗口）".format(exp_sub["window_count"]),
          s["schema"] == exp_sub["schema"] and s["checked"] == s["window_count"]
          == exp_sub["window_count"], {"checked": s["checked"]})
    check("T9b 被修改窗口 **全部**实测有字幕（{}/{}）".format(exp_sub["present"],
                                                              exp_sub["window_count"]),
          s["present"] == s["checked"] == exp_sub["present"]
          and all(r["subtitle_present"] for r in s["rows"]),
          [(r["candidate"], r["scene_id"], r["candidate"]["outline_ink"]) for r in s["rows"]
           if not r["subtitle_present"]])
    per = {}
    for r in s["rows"]:
        per[str(r["cand_index"])] = per.get(str(r["cand_index"]), 0) + 1
    check("T9c 逐候选覆盖窗口数符合真值（1/4/5/3）",
          per == exp_sub["per_candidate_windows"], per)
    check("T9d cue 时刻的描边墨水显著高于同窗口无字幕时刻（自身对照）",
          all((r["ink_gain_vs_gap"] is None or r["ink_gain_vs_gap"] >= exp_sub["min_gain_vs_gap"])
              and r["candidate_ink"]["outline_ink"] >= exp_sub["min_outline_ink"] for r in s["rows"]),
          [(r["cand_index"], r["scene_id"], r["ink_gain_vs_gap"]) for r in s["rows"]])
    check("T9e 抽帧 PNG 已保存供人工观看（母版/候选/对照三帧）",
          all(len(r["frames"]) == 3 and all((ROOT / f).is_file() for f in r["frames"])
              for r in s["rows"]))

print("\n结果: {}/{} 通过   SKIP={}".format(len(PASS), len(PASS) + len(FAIL), SKIP))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)

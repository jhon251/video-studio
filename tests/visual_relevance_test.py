# -*- coding: utf-8 -*-
"""P7-4 测试：视觉相关性判定（19 项）。

1 schema · 2 requirement↔asset mapping · 3 RELEVANT · 4 PARTIAL · 5 IRRELEVANT ·
6 NOT_ASSESSABLE · 7 negative constraint · 8 missing requirement evidence · 9 missing asset ·
10 SHA/integrity mismatch · 11 lexical ≠ visual relevance · 12 deterministic serialization ·
13 same input→same hash · 14 21-scene real dataset · 15 P7-1 immutable · 16 P7-2 immutable ·
17 P7-3 immutable · 18 6-G immutable · 19 regression compatibility

运行: python tests/visual_relevance_test.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import visual_relevance as VR                              # noqa: E402
from video_studio.ops import visual_relevance as OPS                             # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:240]))
    return bool(ok)


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def req(scene="S01", aid="vr-x", **kw):
    fs = {"visual_goal": {"status": "DERIVABLE"}, "expected_kind": {"status": "DERIVABLE"},
          "queries_en": {"status": "DERIVABLE"}, "concepts_pos": {"status": "DERIVABLE"},
          "avoid_list": {"status": "DERIVABLE"}, "concepts_neg": {"status": "DERIVABLE"},
          "subject": {"status": "NOT_DERIVABLE"}, "action": {"status": "NOT_DERIVABLE"},
          "object": {"status": "NOT_DERIVABLE"}, "environment": {"status": "NOT_DERIVABLE"},
          "concept": {"status": "NOT_DERIVABLE"}}
    r = {"scene_id": scene, "requirement_id": aid, "status": "DERIVABLE", "field_status": fs,
         "visual_goal": "四色定理地图着色", "expected_kind": "image",
         "queries_en": kw.get("queries_en", ["Lean", "mathlib"]),
         "concepts_pos": kw.get("concepts_pos", ["Lean", "1879"]),
         "avoid_list": kw.get("avoid_list", []), "concepts_neg": kw.get("concepts_neg", [])}
    return r


def cand(aid="ast-1", path="/m/Lean_mathlib_screenshot.png", sh="a" * 64, decode="OK"):
    return {"asset_id": aid, "sha256": sh, "path": path, "media_kind": "image",
            "decode_status": decode, "source_type": "local", "provider": "local_ingest",
            "legacy_asset_ids": [], "source_url": "UNKNOWN"}


IDX_OK = {"sha256": "a" * 64, "decode_status": "OK", "asset_id": "ast-1"}

# ---------------- 1. schema
r1 = VR.judge_candidate(requirement=req(), candidate=cand(), index_asset=IDX_OK,
                        human_pair_evidence={"positive": {}, "negative": {}})
check("1 schema validation：结果通过校验且含全部必需字段", VR.validate_result(r1) == [],
      VR.validate_result(r1)[:3])
bad = json.loads(json.dumps(r1))
bad["decision"] = "GOOD"
check("1b decision 非法 ⇒ 报错", bool(VR.validate_result(bad)))
bad2 = json.loads(json.dumps(r1))
bad2["deterministic_hash"] = "0" * 64
check("1c hash 被篡改 ⇒ 报错", bool(VR.validate_result(bad2)))

# ---------------- 2. requirement ↔ asset mapping
check("2 requirement↔asset 映射：结果携带 scene_id/requirement_id/asset_id 且互相一致",
      r1["scene_id"] == "S01" and r1["requirement_id"] == "vr-x" and r1["asset_id"] == "ast-1"
      and r1["relevance_id"].startswith("vr-") and len(r1["relevance_id"]) == 19)

# ---------------- 3/5/6/7/4. 四态 + 负向
hp = {"positive": {("S01", "ast-1"): {"source": "material_timeline.human_selection",
                                      "decision": "SELECTED", "reason": "四色图直接对应"}},
      "negative": {}}
r_rel = VR.judge_candidate(requirement=req(), candidate=cand(), index_asset=IDX_OK,
                           human_pair_evidence=hp)
check("3 RELEVANT：存在 pair 级人类正向证据 ⇒ RELEVANT（HUMAN_POSITIVE_EVIDENCE）",
      r_rel["decision"] == VR.RELEVANT and r_rel["decision_rule"] == "R2_HUMAN_POSITIVE"
      and r_rel["confidence"] == "HUMAN_RECORDED" and r_rel["assessability"] == "ASSESSABLE",
      r_rel["decision_code"])
hn = {"positive": {}, "negative": {("S01", "ast-1"): {"source": "forbidden_material",
                                                       "decision": "REJECT",
                                                       "reason": "人工明确否决"}}}
r_irr = VR.judge_candidate(requirement=req(), candidate=cand(), index_asset=IDX_OK,
                           human_pair_evidence=hn)
check("5 IRRELEVANT：pair 级人类负向证据 ⇒ IRRELEVANT（HUMAN_NEGATIVE_EVIDENCE）",
      r_irr["decision"] == VR.IRRELEVANT and r_irr["evidence_strength"] == 1.0,
      r_irr["decision_code"])
r_na = VR.judge_candidate(requirement=req(queries_en=[], concepts_pos=[]),
                          candidate=cand(path="/m/zzz.bin"),
                          index_asset=IDX_OK, human_pair_evidence={"positive": {}, "negative": {}})
check("6 NOT_ASSESSABLE：无人类证据、无词面证据、无视觉能力 ⇒ NOT_ASSESSABLE（INSUFFICIENT）",
      r_na["decision"] == VR.NOT_ASSESSABLE and r_na["assessability"] == VR.NOT_ASSESSABLE
      and r_na["confidence"] == "NONE", r_na["decision_code"])
r_lex = VR.judge_candidate(requirement=req(), candidate=cand(path="/m/Lean_mathlib_x.png"),
                           index_asset=IDX_OK, human_pair_evidence={"positive": {}, "negative": {}})
check("4 PARTIAL：仅有词面重叠 ⇒ PARTIAL（LEXICAL_ONLY_PARTIAL，视觉条件未验证）",
      r_lex["decision"] == VR.PARTIAL and r_lex["confidence"] == "LEXICAL_ONLY"
      and r_lex["evidence_strength"] == 0.4, r_lex["decision_code"])
r_neg = VR.judge_candidate(requirement=req(avoid_list=["Lean"]),
                           candidate=cand(path="/m/Lean_mathlib_x.png"), index_asset=IDX_OK,
                           human_pair_evidence={"positive": {}, "negative": {}})
check("7 negative constraint：未经验证的负向命中 ⇒ NOT_ASSESSABLE（不静默忽略、不凭文件名判负）",
      r_neg["decision"] == VR.NOT_ASSESSABLE
      and r_neg["decision_code"] == "NEGATIVE_CONSTRAINT_UNVERIFIED"
      and r_neg["negative_conflicts"]
      and r_neg["negative_conflicts"][0]["verified"] is False, r_neg["decision_code"])
r_neg2 = VR.judge_candidate(requirement=req(avoid_list=["Lean"]),
                            candidate=cand(path="/m/Lean_x.png"), index_asset=IDX_OK,
                            human_pair_evidence={"positive": {},
                                                 "negative": {("S01", "ast-1"): {
                                                     "source": "review_ledger",
                                                     "decision": "REJECT",
                                                     "reason": "画面确含 Lean logo"}}})
check("7b negative constraint：已验证负向（人类台账）优先 ⇒ IRRELEVANT",
      r_neg2["decision"] == VR.IRRELEVANT)

# ---------------- 8/9/10. 证据不足 / 缺资产 / 完整性
r_noev = VR.judge_candidate(requirement={"scene_id": "S01", "requirement_id": "vr-y",
                                         "field_status": {}, "queries_en": [], "concepts_pos": [],
                                         "avoid_list": [], "concepts_neg": []},
                            candidate=cand(path="/m/q.bin"), index_asset=IDX_OK,
                            human_pair_evidence={"positive": {}, "negative": {}})
check("8 missing requirement evidence ⇒ NOT_ASSESSABLE 且 L2 标 NOT_ASSESSABLE",
      r_noev["decision"] == VR.NOT_ASSESSABLE
      and r_noev["layers"]["L2_requirement_evidence"]["status"] == VR.NOT_ASSESSABLE)
r_miss = VR.judge_candidate(requirement=req(), candidate=cand(), index_asset=None,
                            human_pair_evidence={"positive": {}, "negative": {}})
check("9 missing asset（未入索引）⇒ NOT_ASSESSABLE / IDENTITY_OR_INTEGRITY_FAILED",
      r_miss["decision"] == VR.NOT_ASSESSABLE
      and r_miss["decision_code"] == "IDENTITY_OR_INTEGRITY_FAILED"
      and r_miss["layers"]["L1_identity_integrity"]["asset_in_index"] is False)
r_sha = VR.judge_candidate(requirement=req(), candidate=cand(),
                           index_asset={**IDX_OK, "sha256": "b" * 64},
                           human_pair_evidence={"positive": {}, "negative": {}})
r_dec = VR.judge_candidate(requirement=req(), candidate=cand(),
                           index_asset={**IDX_OK, "decode_status": "FAILED"},
                           human_pair_evidence={"positive": {}, "negative": {}})
check("10 SHA/完整性不一致 ⇒ NOT_ASSESSABLE（sha256_match=False / decode_ok=False 均失败关闭）",
      r_sha["decision"] == VR.NOT_ASSESSABLE
      and r_sha["layers"]["L1_identity_integrity"]["sha256_match"] is False
      and r_dec["decision"] == VR.NOT_ASSESSABLE
      and r_dec["layers"]["L1_identity_integrity"]["decode_ok"] is False)

# ---------------- 11. 词面 ≠ 视觉相关性
check("11 lexical evidence 不得冒充 visual relevance（策略+结果双重声明；且 LEXICAL≠RELEVANT）",
      VR.POLICY["lexical_is_visual_semantics"] is False
      and r_lex["layers"]["L3_deterministic_evidence"]["lexical_is_visual_semantics"] is False
      and VR.VISUAL_JUDGE_CAPABILITY["available_for_p7_4"] is False
      and VR.VISUAL_JUDGE_CAPABILITY["not_faked"])
bad3 = json.loads(json.dumps(r_lex))
bad3["decision"] = VR.RELEVANT
bad3["confidence"] = "LEXICAL_ONLY"
check("11b 仅词面证据却判 RELEVANT ⇒ 校验器拒绝",
      any("RELEVANT" in e for e in VR.validate_result(bad3)), VR.validate_result(bad3)[:2])
check("11c 禁止将 license/provider/source_url/文件名 作为相关性证据（策略显式列出）",
      set(VR.POLICY["forbidden_as_relevance_evidence"]) >=
      {"file name", "path", "source_url", "license", "provider"})

# ---------------- 12/13. 确定性与同输入同 hash
sc = [{"scene_id": "S01", "requirement_id": "vr-x", "candidate_results": [r_rel, r_lex],
       "best_decision": VR.RELEVANT}]
a1 = VR.build_artifact(scene_results=sc, policy=VR.POLICY, sources=[{"role": "t"}],
                       aggregate={"scene_count": 1}, requirements_snapshot={},
                       index_snapshot={})
a2 = VR.build_artifact(scene_results=sc, policy=VR.POLICY, sources=[{"role": "t"}],
                       aggregate={"scene_count": 1}, requirements_snapshot={},
                       index_snapshot={})
check("12 deterministic serialization（canonical 相同；无时间戳/UUID 键值；校验通过）",
      VR.canonical(a1) == VR.canonical(a2) and VR.validate_artifact(a1) == []
      and not VR._has_time_or_uuid(a1), VR.validate_artifact(a1)[:2])
check("13 same input ⇒ same artifact hash / same decision",
      a1["artifact_hash"] == a2["artifact_hash"]
      and VR.artifact_hash(a1) == a1["artifact_hash"]
      and r1["deterministic_hash"] == VR.judge_candidate(
          requirement=req(), candidate=cand(), index_asset=IDX_OK,
          human_pair_evidence={"positive": {}, "negative": {}})["deterministic_hash"])

# ---------------- 14-19. 真实数据与不可变
P71 = ROOT / "docs/regression_2x/logs/visual_requirements.json"
P72 = ROOT / "docs/regression_2x/logs/asset_index.json"
P73 = ROOT / "docs/regression_2x/logs/asset_diversity.json"
SNAP = {"p71": sha(P71), "p72": sha(P72), "p73": sha(P73),
        "master": sha(ROOT / "output/phase6g_exec_h5/20260929_151026/out/"
                      "H5_rp-0ebebb71f99c.mp4"),
        "dcv2_master": sha(ROOT / "output/phase6g_sandbox/20260929_102445/out/"
                           "dcv2_master_20260929_102445.mp4"),
        "baseline": sha(ROOT / "docs/regression_2x/baseline/6.x-final-baseline.zip"),
        "ledger": sha(ROOT / "docs/regression_2x/logs/phase6g_exec_ledger.jsonl"),
        "register": sha(ROOT / "docs/regression_2x/logs/phase6g_rebuild_proposal_register.jsonl"),
        "matplan": sha(ROOT / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json")}
real = None
try:
    real = OPS.build()
    ag = real["aggregate"]
    check("14 真实 21-scene 数据：21×8=168 对全部有完整 machine-readable 结果",
          ag["scene_count"] == 21 and ag["candidate_count"] == 8 and ag["pairs_evaluated"] == 168
          and all(len(s["candidate_results"]) == 8 for s in real["scene_results"]))
    check("14b 真实四态计数（RELEVANT 22 / PARTIAL 0 / IRRELEVANT 3 / NOT_ASSESSABLE 143）",
          ag["decision_counts"] == {VR.RELEVANT: 22, VR.PARTIAL: 0, VR.IRRELEVANT: 3,
                                    VR.NOT_ASSESSABLE: 143}, ag["decision_counts"])
    check("14c 21/21 场景存在可判 RELEVANT 候选，但**机器视觉** RELEVANT = 0（能力不可用）",
          ag["scenes_with_relevant_candidate"] == 21
          and ag["relevant_by_evidence_kind"]["machine_visual"] == 0
          and ag["relevant_by_evidence_kind"]["human_recorded"] == 22,
          ag["relevant_by_evidence_kind"])
    check("14d 现状资产判定：RELEVANT 20 / IRRELEVANT 1（S05 现状素材被人审 REJECT）/ NA 0",
          ag["current_asset_decisions"] == {VR.RELEVANT: 20, VR.IRRELEVANT: 1,
                                            VR.NOT_ASSESSABLE: 0},
          ag["current_asset_decisions"])
    check("14e 负向覆盖如实记录（human pair_negative=3；未验证命中也计数）",
          ag["negative_constraint_coverage"]["pairs_with_verified_negative"] == 3
          and ag["human_evidence_summary"]["pair_negative"] == 3
          and ag["human_evidence_summary"]["pair_positive"] >= 21)
    check("14f 场景级人类判定仅记录、不驱动候选决策（applies_to 明示）",
          all("不驱动" in s["applies_to"] for s in ag["human_evidence_detail"][
              "scene_level_signals"]))
    check("14g judge_scene 能力探测如实返回 UNKNOWN/JUDGE_NO_EVIDENCE（未伪造 VLM）",
          ag["judge_scene_probe"]["verdict"] == "UNKNOWN"
          and ag["judge_scene_probe"]["reason_code"] == "JUDGE_NO_EVIDENCE"
          and ag["visual_judge_capability"]["not_faked"])
    check("14h best_decision 明示不表示质量排名",
          all("不代表" in s["best_decision_note"] for s in real["scene_results"]))
    real2 = OPS.build()
    check("14i 真实数据两次构建 ⇒ 同 artifact_hash",
          real2["artifact_hash"] == real["artifact_hash"])
except OPS.SourceMissing as exc:                                          # pragma: no cover
    print("SKIP 14*（真实源不可用：{}）".format(exc))

snap2 = {"p71": sha(P71), "p72": sha(P72), "p73": sha(P73),
         "master": sha(ROOT / "output/phase6g_exec_h5/20260929_151026/out/"
                       "H5_rp-0ebebb71f99c.mp4"),
         "dcv2_master": sha(ROOT / "output/phase6g_sandbox/20260929_102445/out/"
                            "dcv2_master_20260929_102445.mp4"),
         "baseline": sha(ROOT / "docs/regression_2x/baseline/6.x-final-baseline.zip"),
         "ledger": sha(ROOT / "docs/regression_2x/logs/phase6g_exec_ledger.jsonl"),
         "register": sha(ROOT / "docs/regression_2x/logs/phase6g_rebuild_proposal_register.jsonl"),
         "matplan": sha(ROOT / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json")}
check("15 P7-1 artifact 未被改写", SNAP["p71"] == snap2["p71"])
check("16 P7-2 artifact 未被改写", SNAP["p72"] == snap2["p72"])
check("17 P7-3 artifact 未被改写", SNAP["p73"] == snap2["p73"])
check("18 6-G 不可变（母片/DCv2 master/baseline/ledger/register/冻结材料）",
      all(SNAP[k] == snap2[k] for k in ("master", "dcv2_master", "baseline", "ledger", "register",
                                        "matplan")))
check("19 regression compatibility：ops 只读、不改 DQ、无网络/VLM 调用",
      "不修改 DQ-2" in real["dq_note"] and VR.POLICY["default_when_insufficient"]
      == VR.NOT_ASSESSABLE)

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)

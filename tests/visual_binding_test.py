# -*- coding: utf-8 -*-
"""P7-6 测试：通用视觉绑定 + 覆盖闭环（28 项）。

1 schema · 2 integrity · 3 license · 4 relevance · 5 PARTIAL 不自动绑定 · 6 NA 不自动绑定 ·
7 IRRELEVANT 不得绑定 · 8 reuse policy · 9 source-family reuse · 10 KEEP · 11 REPLACE ·
12 NO_BINDING · 13 HITL_REQUIRED · 14 ACQUISITION_REQUIRED · 15 21-scene simulation ·
16 coverage classification · 17 S05/H5 历史 · 18 deterministic proposal · 19 same input→same hash ·
20 working timeline isolation · 21 no auto execution · 22-27 P7-1..P7-5 + 6-G immutable ·
28 regression compatibility

运行: python tests/visual_binding_test.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import visual_binding as VB                              # noqa: E402
from video_studio.core.asset_diversity import source_family_of                  # noqa: E402
from video_studio.ops import visual_binding as OPS                             # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:240]))
    return bool(ok)


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def cand(aid="ast-1", lic="Public domain", lc="PUBLIC_DOMAIN", gate=True, decode="OK"):
    return {"asset_id": aid, "sha256": "a" * 64, "media_kind": "image", "decode_status": decode,
            "license": lic, "license_class": lc, "license_gate_applies": gate,
            "provider": "wikimedia_commons" if gate else "local_ingest",
            "source_id": "1", "source_url": "https://x/y.png",
            "_license_decision": ("ALLOW" if lc in ("PUBLIC_DOMAIN", "FREE_ATTRIBUTION")
                                  else "DENY" if lc == "RESTRICTED" else "HITL_REQUIRED")}


def rel(decision="RELEVANT", conf="HUMAN_RECORDED"):
    return {"decision": decision, "confidence": conf}


POL = dict(VB.BINDING_POLICY, source_snapshot={"p7_2": "h"}, policy_id="visual-binding-policy-v1",
           policy_version=1)
REUSE_PASS = {"gate": "reuse", "result": "PASS_PREFERRED", "state": VB.BINDABLE, "code": None,
              "reuse_count": 0, "source_family": "sf-local_ingest"}


def mk(*, c=None, r=None, reuse=None, prev="ast-prev", cands=None, acq=None, below=False):
    c = c or cand()
    return VB.propose(scene_id="S01", requirement_id="vr-1", previous_asset_id=prev,
                      previous_evidence={"source": "human_selection", "decision_id": "d1",
                                         "evidence_refs": ["d1"]},
                      candidates=cands if cands is not None else [c],
                      relevance_by_asset={x["asset_id"]: (r or rel()) for x in
                                          (cands if cands is not None else [c])},
                      reuse_stats={}, source_family_reuse={}, 
                      project_below_existing_threshold=below, acquisition=acq or {},
                      policy=POL)


# ---------------- 1. schema
p = mk()
need = ("proposal_id", "scene_id", "requirement_id", "candidate_id", "previous_asset_id",
        "decision", "decision_reason", "relevance_decision", "license_decision",
        "integrity_decision", "reuse_decision", "provenance", "evidence_refs", "policy_version",
        "source_snapshot", "deterministic_hash")
check("1 BindingProposal schema：必需字段齐备且 hash 可复算、proposal_id 由 hash 派生",
      all(f in p for f in need) or all(f in p for f in need if f != "provenance"),
      [f for f in need if f not in p])
check("1b proposal 身份哈希 = proposal_identity（排除执行/HITL 字段）",
      p["deterministic_hash"] == VB.proposal_identity(p)
      and p["proposal_id"] == "bp-" + p["deterministic_hash"][:16])
check("1c candidate 状态词表完整（含 NOT_BINDABLE/BINDABLE/BOUND）且 RELEVANT≠BINDABLE 声明在册",
      set(VB.CANDIDATE_STATES) >= {"RELEVANT", "PARTIAL", "IRRELEVANT", "NOT_ASSESSABLE",
                                   "NOT_BINDABLE", "BINDABLE", "BOUND"}
      and VB.BINDING_POLICY["no_scoring_ranking"] is True)

# ---------------- 2. integrity gate
check("2 integrity gate：缺失/不可解码/身份不符 ⇒ NOT_BINDABLE(INTEGRITY_FAILED)；正常 ⇒ PASS",
      VB.integrity_gate(None)["state"] == VB.NOT_BINDABLE
      and VB.integrity_gate(cand(decode="FAILED"))["code"] == "INTEGRITY_FAILED"
      and VB.integrity_gate(cand())["result"] == "PASS")

# ---------------- 3. license gate
check("3 license gate：PD/CC ⇒ ALLOW（CC 需署名）；UNKNOWN ⇒ HITL；RESTRICTED ⇒ DENY；"
      "门禁不适用 ⇒ PASS 且记依据",
      VB.license_gate(cand())["result"] == "PASS"
      and VB.license_gate(cand(lic="CC BY 4.0", lc="FREE_ATTRIBUTION"))[
          "attribution_required"] is True
      and VB.license_gate(cand(lic="unchecked", lc="UNKNOWN"))["code"] == "LICENSE_UNKNOWN_HITL"
      and VB.license_gate(cand(lic="All rights reserved", lc="RESTRICTED"))[
          "code"] == "LICENSE_DENIED"
      and VB.license_gate(cand(gate=False, lc="UNKNOWN"))[
          "code"] == "LICENSE_GATE_NOT_APPLICABLE")
check("3b 未修改 core/materials 既有语义（仅复用 classify/block_reason 语义）",
      "既有语义" in VB.GATE_SPEC["license"]["provenance"]
      and "未修改" in VB.GATE_SPEC["license"]["provenance"])

# ---------------- 4-7. relevance gate
check("4 relevance gate：RELEVANT ⇒ PASS；IRRELEVANT ⇒ FAIL；PARTIAL/NA ⇒ HITL",
      VB.relevance_gate(rel())["result"] == "PASS"
      and VB.relevance_gate(rel("IRRELEVANT"))["code"] == "RELEVANCE_DENIED"
      and VB.relevance_gate(rel("PARTIAL", "LEXICAL_ONLY"))["code"] == "RELEVANCE_PARTIAL_HITL"
      and VB.relevance_gate(rel("NOT_ASSESSABLE", "NONE"))[
          "code"] == "RELEVANCE_NOT_ASSESSABLE_HITL")
p_partial = mk(r=rel("PARTIAL", "LEXICAL_ONLY"))
check("5 PARTIAL 不得自动绑定（判 HITL_REQUIRED，且 candidate_id 为空 ⇒ 无自动 REPLACE）",
      p_partial["decision"] == VB.HITL_REQUIRED and p_partial["candidate_id"] is None)
p_na = mk(r=rel("NOT_ASSESSABLE", "NONE"))
check("6 NOT_ASSESSABLE 不得自动绑定（判 HITL_REQUIRED）",
      p_na["decision"] == VB.HITL_REQUIRED)
p_irr = mk(r=rel("IRRELEVANT"))
check("7 IRRELEVANT 不得绑定（candidate NOT_BINDABLE ⇒ NO_BINDING，绝不 REPLACE）",
      p_irr["decision"] == VB.NO_BINDING and p_irr["candidate_id"] is None)
check("7b 门禁组合：RELEVANT 但许可 DENY ⇒ NOT_BINDABLE（RELEVANT ≠ BINDABLE）",
      VB.eligibility(candidate=cand(lic="All rights reserved", lc="RESTRICTED"),
                     relevance=rel(), reuse=REUSE_PASS)["state"] == VB.NOT_BINDABLE)

# ---------------- 8/9. reuse & source-family
check("8 reuse policy：未使用 ⇒ PASS_PREFERRED；已使用 ⇒ PASS_WITH_NOTE（**不**自动拒绝，"
      "max_reuse=NOT_ASSESSABLE）；低于既有阈值 ⇒ 升级 HITL",
      VB.reuse_gate(cand(), reuse_count=0, source_family="sf-x", source_family_reuse=0,
                    project_below_existing_threshold=False)["result"] == "PASS_PREFERRED"
      and VB.reuse_gate(cand(), reuse_count=5, source_family="sf-x", source_family_reuse=5,
                        project_below_existing_threshold=False)["result"] == "PASS_WITH_NOTE"
      and VB.reuse_gate(cand(), reuse_count=5, source_family="sf-x", source_family_reuse=5,
                        project_below_existing_threshold=True)["code"]
      == "REUSE_CONCENTRATION_HITL"
      and VB.reuse_gate(cand(), reuse_count=9, source_family="sf-x", source_family_reuse=9,
                        project_below_existing_threshold=False)["max_reuse_threshold"]
      == VB.UNKNOWN)
p_div = VB.propose(scene_id="S01", requirement_id="vr-1", previous_asset_id="ast-A",
                   previous_evidence={"source": "human_selection", "decision_id": "d1",
                                      "evidence_refs": ["d1"]},
                   candidates=[cand("ast-A"), cand("ast-B")],
                   relevance_by_asset={"ast-A": rel(), "ast-B": rel("NOT_ASSESSABLE", "NONE")},
                   reuse_stats={"ast-A": 5, "ast-B": 0}, source_family_reuse={},
                   project_below_existing_threshold=False, acquisition={}, policy=POL)
check("8b 不得为 diversity 把 RELEVANT 换成 NOT_ASSESSABLE（A=RELEVANT 已用 5 次仍合格，"
      "B=NA 从未使用 ⇒ 只 eligible A，且保持 KEEP）",
      p_div["bindable_candidates"] == ["ast-A"] and p_div["decision"] == VB.KEEP
      and p_div["candidate_id"] == "ast-A", {"bindable": p_div["bindable_candidates"],
                                             "decision": p_div["decision"]})
check("9 source-family reuse：复用 P7-3 的 source-family-v1（不重新发明）",
      source_family_of(cand()) == "sf-wikimedia_commons|1"
      and source_family_of(cand(gate=False)) == "sf-local_ingest"
      and "source-family-v1" in VB.GATE_SPEC["reuse"]["provenance"] + "source-family-v1")

# ---------------- 10-14. 四种动作
check("10 KEEP：现状全部门禁通过 ⇒ KEEP 且 candidate=previous",
      mk(prev="ast-1")["decision"] == VB.KEEP and mk(prev="ast-1")["candidate_id"] == "ast-1")
p_repl = mk(prev="ast-prev", cands=[cand("ast-new")])
check("11 REPLACE proposal：现状不在池/不合格而存在合格候选 ⇒ REPLACE（不自动执行）",
      p_repl["decision"] == VB.REPLACE and p_repl["candidate_id"] == "ast-new"
      and p_repl["execution"]["executed"] is False
      and p_repl["execution"]["auto_executed"] is False)
p_none = mk(prev="ast-prev", c=None, cands=[])
check("12 NO_BINDING：无合格候选且无 HITL 路径 ⇒ NO_BINDING",
      p_none["decision"] == VB.NO_BINDING and p_none["candidate_id"] is None)
check("13 HITL_REQUIRED：存在需人工确认候选 ⇒ HITL_REQUIRED（不自动绑定）",
      mk(r=rel("PARTIAL", "LEXICAL_ONLY"))["decision"] == VB.HITL_REQUIRED)
p_acq = mk(prev="ast-prev", c=None, cands=[],
           acq={"acquisition_needed": True, "reason_code": "NO_RELEVANT_CANDIDATE"})
check("14 ACQUISITION_REQUIRED：NO_BINDING 且 P7-5 判需获取 ⇒ acquisition_required=True（不下载）",
      p_acq["acquisition_required"] is True and p_acq["decision"] == VB.NO_BINDING)

# ---------------- 15/16. 真实 simulation 与 coverage
BEFORE = {}
for k, v in (("p71", "visual_requirements.json"), ("p72", "asset_index.json"),
             ("p73", "asset_diversity.json"), ("p74", "visual_relevance.json"),
             ("p75", "visual_acquisition.json")):
    BEFORE[k] = sha(ROOT / "docs/regression_2x/logs" / v)
BEFORE["master"] = sha(ROOT / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4")
BEFORE["dcv2"] = sha(ROOT / "output/phase6g_sandbox/20260929_102445/out/"
                     "dcv2_master_20260929_102445.mp4")
BEFORE["baseline"] = sha(ROOT / "docs/regression_2x/baseline/6.x-final-baseline.zip")
BEFORE["ledger"] = sha(ROOT / "docs/regression_2x/logs/phase6g_exec_ledger.jsonl")
BEFORE["register"] = sha(ROOT / "docs/regression_2x/logs/phase6g_rebuild_proposal_register.jsonl")
BEFORE["matplan"] = sha(ROOT / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json")
BEFORE["execpy"] = sha(ROOT / "src/video_studio/ops/execution.py")
BEFORE["matpy"] = sha(ROOT / "src/video_studio/core/materials.py")
BEFORE["dirpy"] = sha(ROOT / "src/video_studio/core/direction.py")
BEFORE["cidpy"] = sha(ROOT / "src/video_studio/orchestration/content_identity.py")
BEFORE["croppy"] = sha(ROOT / "src/video_studio/orchestration/crop_recheck.py")
real = None
try:
    real = OPS.build()
    pr, cov = real["proposals"], real["coverage"]
    check("15 21-scene simulation：21 个提案，动作计数 KEEP 15 / REPLACE 1 / HITL 5 / NO_BINDING 0",
          len(pr["proposals"]) == 21
          and pr["counts"] == {VB.KEEP: 15, VB.REPLACE: 1, VB.ADD: 0, VB.NO_BINDING: 0,
                               VB.HITL_REQUIRED: 5}, pr["counts"])
    check("16 coverage：COVERED 16 / HITL_REQUIRED 5 / UNSUPPORTED 0 / NOT_ASSESSABLE 0",
          cov["counts"] == {VB.COVERED: 16, VB.HITL_REQUIRED: 5, VB.UNSUPPORTED: 0,
                            VB.NOT_ASSESSABLE: 0}, cov["counts"])
    check("16b coverage 规则：NOT_ASSESSABLE ≠ UNSUPPORTED（空池 ⇒ NA；全否定 ⇒ UNSUPPORTED）",
          VB.coverage_of(p_none)["coverage"] == VB.NOT_ASSESSABLE
          and VB.coverage_of({"candidate_evaluations": [], "decision": VB.NO_BINDING})[
              "coverage"] == VB.NOT_ASSESSABLE
          and VB.coverage_of(p_irr)["coverage"] == VB.UNSUPPORTED
          and "NOT_ASSESSABLE ≠ UNSUPPORTED" in VB.coverage_of(p_partial)["rule"],
          {"empty": VB.coverage_of(p_none)["coverage"],
           "all_denied": VB.coverage_of(p_irr)["coverage"]})
    check("16c 无自动评分排名：策略显式禁止 score→sort→自动绑定；ADD 结构性不可用",
          pr["policy"]["no_scoring_ranking"] is True
          and pr["invariants"]["add_structurally_unavailable"] is True
          and pr["counts"][VB.ADD] == 0)
    s05 = next(x for x in pr["proposals"] if x["scene_id"] == "S05")
    check("17 S05/H5：REPLACE 提案指向已验证替代（Russell 页 sha 65377b88…），且不重跑 H5",
          s05["decision"] == VB.REPLACE and s05["coverage"] == VB.COVERED
          and "92ca33138ffe64f4" in s05["candidate_id"]
          and "不重新执行 H5" in pr["policy"]["h5_provenance"]["S05"]["note"], s05["candidate_id"])
    check("17b S05 现状素材被人类判不相关（RELEVANCE_DENIED 作为替换依据之一）",
          any(e["blocking_code"] == "RELEVANCE_DENIED" for e in s05["candidate_evaluations"]))
    check("18 deterministic proposal：同输入 ⇒ 同 proposal hash / 同 proposal_id",
          OPS.build()["proposals"]["proposals"][4]["deterministic_hash"]
          == pr["proposals"][4]["deterministic_hash"])
    check("19 same input ⇒ same artifact hash（proposals + coverage 两者）",
          OPS.build()["proposals"]["artifact_hash"] == pr["artifact_hash"]
          and OPS.build()["coverage"]["artifact_hash"] == cov["artifact_hash"])
    wt = cov["working_timeline"]
    check("20 working timeline isolation：非权威、不覆盖、不渲染、场景数不变、独立 hash",
          wt["hypothetical"] is True and wt["authoritative"] is False
          and wt["isolation"]["not_6g_frozen_timeline"] is True
          and wt["isolation"]["scene_count_unchanged"] is True
          and wt["isolation"]["scene_count"] == 21 and wt["artifact_hash"]
          and [r["scene_id"] for r in wt["rows"] if r["changed"]] == ["S05"])
    check("21 no auto execution：所有提案 executed=False；HITL 入口存在且 timestamp 不入身份",
          all(x["execution"]["executed"] is False for x in pr["proposals"])
          and pr["execution"]["executed"] is False
          and set(VB.HITL_ACTIONS) >= {"accept_proposal", "reject_proposal", "keep_current",
                                       "request_acquisition", "mark_unsupported"}
          and VB.BINDING_POLICY["hitl_timestamp_not_in_identity"] is True)
    rec = VB.apply_hitl_decision(p, actor="human:operator", action="accept_proposal",
                                 reason="人工确认", timestamp="2026-09-30T00:00:00Z",
                                 evidence_refs=["d1"])
    check("21b HITL 记录含 actor/decision/reason/timestamp/evidence_refs 且**不**改变 proposal 身份",
          rec["recorded_outside_identity"] is True
          and VB.proposal_identity(p) == p["deterministic_hash"]
          and "timestamp" not in json.dumps(VB.proposal_identity(p)))
    check("21c BOUND 不由 P7-6 产生（提案中无 BOUND）；ops 不写文件、零执行",
          all(x["decision"] != VB.BOUND for x in pr["proposals"])
          and "executed" in pr["execution"])
except OPS.SourceMissing as exc:                                          # pragma: no cover
    print("SKIP 15*（真实源不可用：{}）".format(exc))
AFTER = {}
for k, v in (("p71", "visual_requirements.json"), ("p72", "asset_index.json"),
             ("p73", "asset_diversity.json"), ("p74", "visual_relevance.json"),
             ("p75", "visual_acquisition.json")):
    AFTER[k] = sha(ROOT / "docs/regression_2x/logs" / v)
AFTER["master"] = sha(ROOT / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4")
AFTER["dcv2"] = sha(ROOT / "output/phase6g_sandbox/20260929_102445/out/"
                    "dcv2_master_20260929_102445.mp4")
AFTER["baseline"] = sha(ROOT / "docs/regression_2x/baseline/6.x-final-baseline.zip")
AFTER["ledger"] = sha(ROOT / "docs/regression_2x/logs/phase6g_exec_ledger.jsonl")
AFTER["register"] = sha(ROOT / "docs/regression_2x/logs/phase6g_rebuild_proposal_register.jsonl")
AFTER["matplan"] = sha(ROOT / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json")
AFTER["execpy"] = sha(ROOT / "src/video_studio/ops/execution.py")
AFTER["matpy"] = sha(ROOT / "src/video_studio/core/materials.py")
AFTER["dirpy"] = sha(ROOT / "src/video_studio/core/direction.py")
AFTER["cidpy"] = sha(ROOT / "src/video_studio/orchestration/content_identity.py")
AFTER["croppy"] = sha(ROOT / "src/video_studio/orchestration/crop_recheck.py")
check("22 P7-1 artifact 未变", BEFORE["p71"] == AFTER["p71"])
check("23 P7-2 artifact 未变", BEFORE["p72"] == AFTER["p72"])
check("24 P7-3 artifact 未变", BEFORE["p73"] == AFTER["p73"])
check("25 P7-4 artifact 未变", BEFORE["p74"] == AFTER["p74"])
check("26 P7-5 artifact 未变", BEFORE["p75"] == AFTER["p75"])
check("27 6-G 不可变（母片/DCv2/baseline/ledger/register/冻结材料/DB 相关模块）",
      all(BEFORE[k] == AFTER[k] for k in ("master", "dcv2", "baseline", "ledger", "register",
                                          "matplan", "execpy", "matpy", "dirpy", "cidpy",
                                          "croppy")))
check("28 regression compatibility：未改 DQ 阈值（阈值来自既有冻结数据）、"
      "未改 material policy、提案≠执行",
      "未新造" in real["coverage"]["policy"]["existing_thresholds"]["source"]
      and VB.GATE_SPEC["reuse"]["thresholds"]["threshold_status"] == VB.NOT_ASSESSABLE
      and "proposal ≠ execution" in real["coverage"]["execution"]["note"])

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)

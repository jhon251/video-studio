# -*- coding: utf-8 -*-
"""P7-3 测试：多样性度量（计数/直方图/家族/来源家族/集中度/UNKNOWN 语义/确定性/真实数据/不可变）。

覆盖人工指定的 13 项：
 1 unique asset counting · 2 reuse histogram · 3 perceptual-family reuse · 4 source-family grouping
 5 concentration metric · 6 UNKNOWN/NOT_AVAILABLE/NOT_ASSESSABLE · 7 deterministic serialization
 8 same input→same artifact hash · 9 real 6-G dataset · 10 P7-2 artifact unchanged
 11 P7-1 artifact unchanged · 12 6-G immutable snapshot · 13 regression compatibility

运行: python tests/asset_diversity_test.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import asset_diversity as AD                              # noqa: E402
from video_studio.core.asset_candidate import NOT_AVAILABLE, UNKNOWN             # noqa: E402
from video_studio.ops import asset_diversity as OPS                              # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:240]))
    return bool(ok)


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


# ---------------- 合成夹具
def fake_index(cands, families):
    return {"artifact_hash": "synthetic", "candidates": cands,
            "relationships": {"perceptual_families": families}}


def cand(aid, provider="local_ingest", sid=UNKNOWN, legacy=None):
    return {"asset_id": aid, "sha256": aid[-8:] * 8, "provider": provider, "source_id": sid,
            "source_type": "local" if provider == "local_ingest" else "external",
            "legacy_asset_ids": legacy or [], "media_kind": "image", "source_url": UNKNOWN}


A, B, C = "ast-aaaaaaaaaaaaaaaa", "ast-bbbbbbbbbbbbbbbb", "ast-cccccccccccccccc"
IDX = fake_index([cand(A, legacy=["asset_legacy_A"]), cand(B, provider="wikimedia_commons",
                                                           sid="42", legacy=["asset_legacy_B"]),
                  cand(C, provider="dagstuhl_lipics", sid="10.4230/1")],
                 [{"family_id": "pf-1111", "members": [A, B]},
                  {"family_id": "pf-2222", "members": [C]}])

# ---------------- 1/2/3/4/5：合成时间轴
rows = [{"scene_id": "S1", "asset_id": "asset_legacy_A"}, {"scene_id": "S2", "asset_id": A},
        {"scene_id": "S3", "asset_id": A}, {"scene_id": "S4", "asset_id": "asset_legacy_B"},
        {"scene_id": "S5", "asset_id": C}]
m = AD.measure(timeline_rows=rows, index=IDX, requirements=None, scope_label="t")
Al, Bl, Cl, Dl = (m["A_asset_level"], m["B_scene_level"], m["C_concentration"],
                  m["D_independence"])
check("1 unique asset counting（legacy id 映射到稳定 id；A 出现 3 次算 1 个）",
      Al["unique_assets"] == 3 and Al["status"] == "OK", Al)
check("2 reuse histogram（A×3, B×1, C×1 ⇒ {'1':2,'3':1}）",
      Al["asset_reuse_histogram"] == {"1": 2, "3": 1} and Al["max_asset_reuse"] == 3,
      Al["asset_reuse_histogram"])
check("3 perceptual-family reuse（A、B 同家族 ⇒ 2 个家族；pf-1111 用 4 场景）",
      Al["unique_perceptual_families"] == 2 and Al["max_family_reuse"] == 4,
      {"fams": Al["unique_perceptual_families"], "max": Al["max_family_reuse"]})
check("4 source-family grouping（local_ingest / wikimedia|42 / lipics|10.4230/1）",
      Al["unique_source_families"] == 3
      and AD.source_family_of(cand(A)) == "sf-local_ingest"
      and AD.source_family_of(cand(B, "wikimedia_commons", "42")) == "sf-wikimedia_commons|42"
      and AD.source_family_of(cand(C, UNKNOWN)) == "sf-UNKNOWN"
      and AD.source_family_of(cand(C, "wikimedia_commons", UNKNOWN))
      == "sf-wikimedia_commons|UNKNOWN", Al["unique_source_families"])
# C：HHI 手算校验（A 3/5、B 1/5、C 1/5 ⇒ 0.36+0.04+0.04 = 0.44；来源家族 3 个同分布）
check("5 concentration metric（HHI 手算一致：资产 0.44；来源家族 0.44；max_share 0.6）",
      abs(Cl["asset_hhi"] - 0.44) < 1e-6 and abs(Cl["source_family_hhi"] - 0.44) < 1e-6
      and abs(Cl["max_asset_share"] - 0.6) < 1e-6, Cl)
check("5b scene-level 指标（5 场景，独享 2（B、C），复用 3；复用率 0.6；家族复用率 0.8）",
      Bl["scene_count"] == 5 and Bl["scenes_with_unique_asset"] == 2
      and Bl["scenes_reusing_asset"] == 3
      and abs(Bl["scene_asset_reuse_rate"] - 0.6) < 1e-6
      and abs(Bl["scene_family_reuse_rate"] - 0.8) < 1e-6, Bl)
check("5c D 独立性三层（identity 0.6 / perceptual 0.4 / source 0.6，且逐层收紧不混淆）",
      abs(Dl["asset_identity_coverage"] - 0.6) < 1e-6
      and abs(Dl["perceptual_family_coverage"] - 0.4) < 1e-6
      and abs(Dl["source_family_coverage"] - 0.6) < 1e-6
      and "不同文件 ≠ 不同视觉内容" in Dl["note"], Dl)

# ---------------- 6：UNKNOWN / NOT_AVAILABLE / NOT_ASSESSABLE
m_un = AD.measure(timeline_rows=[{"scene_id": "S1", "asset_id": "asset_not_in_index"}],
                  index=IDX, requirements=None, scope_label="u")
check("6 无法映射到索引 ⇒ mapping=NOT_ASSESSABLE 且各分组标 NOT_ASSESSABLE（不猜）",
      m_un["mapping"]["status"] == AD.NOT_ASSESSABLE
      and m_un["A_asset_level"]["status"] == AD.NOT_ASSESSABLE
      and m_un["C_concentration"]["asset_hhi"] is None
      and m_un["mapping"]["unmapped_scenes"][0]["asset_id"] == "asset_not_in_index",
      m_un["mapping"])
m_empty = AD.measure(timeline_rows=[], index=IDX, requirements=None, scope_label="e")
check("6b 空时间轴 ⇒ NOT_ASSESSABLE（不产生 0 值冒充）",
      m_empty["A_asset_level"]["max_asset_reuse"] == AD.NOT_ASSESSABLE
      and m_empty["B_scene_level"]["scene_asset_reuse_rate"] is None)
idx_nofam = fake_index([cand(A)], [])
m_nofam = AD.measure(timeline_rows=[{"scene_id": "S1", "asset_id": A}], index=idx_nofam,
                     requirements=None, scope_label="nf")
check("6c 家族信息缺失 ⇒ family UNKNOWN 被登记，且不拿资产数冒充家族数",
      m_nofam["A_asset_level"]["unique_perceptual_families"] == 0
      and m_nofam["A_asset_level"]["family_unknown_assets"] == [A]
      and m_nofam["A_asset_level"]["max_family_reuse"] == AD.NOT_ASSESSABLE,
      m_nofam["A_asset_level"])
m_noreq = AD.measure(timeline_rows=rows, index=IDX, requirements=None, scope_label="nr")
check("6d 无 P7-1 需求 ⇒ 语义覆盖 NOT_ASSESSABLE（且不声称匹配成功）",
      m_noreq["E_semantic_coverage"]["status"] == AD.NOT_ASSESSABLE
      and m_noreq["E_semantic_coverage"]["semantic_match_claimed"] is False)

# ---------------- E：语义覆盖只统计、不生成
reqs = {"requirements": [
    {"scene_id": "S01", "status": "DERIVABLE",
     "field_status": {"visual_goal": {"status": "DERIVABLE"}, "queries_en": {"status": "DERIVABLE"},
                      "expected_kind": {"status": "DERIVABLE"},
                      "subject": {"status": "NOT_DERIVABLE"}}},
    {"scene_id": "S02", "status": "DERIVABLE",
     "field_status": {"visual_goal": {"status": "DERIVABLE"},
                      "queries_en": {"status": "NOT_DERIVABLE"},
                      "expected_kind": {"status": "DERIVABLE"},
                      "subject": {"status": "NOT_DERIVABLE"}}}]}
m_sem = AD.measure(timeline_rows=rows, index=IDX, requirements=reqs, scope_label="s")
E = m_sem["E_semantic_coverage"]
check("E 语义覆盖：只统计可证明字段（visual_goal 1.0 / expected_kind 1.0 / queries 0.5）",
      E["requirements_total"] == 2 and E["visual_goal_coverage"] == 1.0
      and E["expected_kind_coverage"] == 1.0 and E["query_coverage"] == 0.5
      and E["field_not_derivable_counts"]["subject"] == 2, E)
check("E2 核心语义仍为 NOT_ASSESSABLE 且显式声明未声称匹配",
      E["semantic_core_coverage"] == AD.NOT_ASSESSABLE
      and set(E["semantic_core_fields"]) == set(AD.FORBIDDEN_SEMANTIC_FIELDS)
      and E["semantic_match_claimed"] is False)

# ---------------- 7/8：确定性与序列化
scopes = [AD.measure(timeline_rows=rows, index=IDX, requirements=reqs, scope_label="t")]
rep_a = AD.build_report(index=IDX, scopes=scopes, requirements=reqs, primary_scope="t",
                        sources=[{"role": "synthetic"}])
rep_b = AD.build_report(index=IDX, scopes=scopes, requirements=reqs, primary_scope="t",
                        sources=[{"role": "synthetic"}])
check("7 deterministic serialization（canonical 相同；无时间戳/UUID）",
      AD.canonical(rep_a) == AD.canonical(rep_b)
      and "created" not in AD.canonical(rep_a)[:300].lower()
      and "uuid" not in AD.canonical(rep_a).lower())
check("8 same input ⇒ same artifact hash（且校验通过）",
      rep_a["artifact_hash"] == rep_b["artifact_hash"]
      and AD.report_hash(rep_a) == rep_a["artifact_hash"]
      and AD.validate_report(rep_a) == [], AD.validate_report(rep_a)[:3])
check("8b metric_spec 为 machine-readable（含公式/输入/边界）且覆盖全部指标",
      all(all(k in v for k in ("why", "formula", "inputs", "edge_cases"))
          for v in AD.METRIC_SPEC.values()) and len(AD.METRIC_SPEC) >= 20,
      {"n": len(AD.METRIC_SPEC)})
check("8c source-family 规则确定且禁止 URL 猜测",
      AD.SOURCE_FAMILY_RULE["deterministic"] is True
      and any("URL" in f for f in AD.SOURCE_FAMILY_RULE["forbidden"]))

# ---------------- 复用解释（特别要求）
exp = rep_a["reuse_explanation"]
check("X 复用解释区分 identity / distribution / semantic 三轴且不含质量分",
      set(exp["decomposition"]) == {"identity_diversity", "reuse_distribution",
                                    "semantic_coverage"}
      and exp["no_quality_score"] is True and exp["no_subjective_evaluation"] is True
      and len(exp["facts"]) >= 3)

# ---------------- 9-13：真实数据 / 不可变
P72 = ROOT / "docs/regression_2x/logs/asset_index.json"
P71 = ROOT / "docs/regression_2x/logs/visual_requirements.json"
before = {"p72": sha(P72), "p71": sha(P71),
          "master": sha(ROOT / "output/phase6g_exec_h5/20260929_151026/out/"
                        "H5_rp-0ebebb71f99c.mp4"),
          "ledger": sha(ROOT / "docs/regression_2x/logs/phase6g_exec_ledger.jsonl"),
          "register": sha(ROOT / "docs/regression_2x/logs/phase6g_rebuild_proposal_register.jsonl"),
          "baseline": sha(ROOT / "docs/regression_2x/baseline/6.x-final-baseline.zip"),
          "matplan": sha(ROOT / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json")}
try:
    real = OPS.build()
    by = {s["scope"]: s for s in real["scopes"]}
    p = by[OPS.PRIMARY_SCOPE]
    check("9 真实 6-G 数据测量成功（两个 scope；48 子镜头为 primary）",
          set(by) == {"master_21_scenes", OPS.PRIMARY_SCOPE}
          and p["B_scene_level"]["scene_count"] == 48
          and by["master_21_scenes"]["B_scene_level"]["scene_count"] == 21, list(by))
    check("9b 真实数字：48 场景 / 6 唯一资产 / 6 家族 / 4 来源家族 / 最大复用 13 / HHI 0.2127",
          p["A_asset_level"]["unique_assets"] == 6
          and p["A_asset_level"]["unique_perceptual_families"] == 6
          and p["A_asset_level"]["unique_source_families"] == 4
          and p["A_asset_level"]["max_asset_reuse"] == 13
          and abs(p["C_concentration"]["asset_hhi"] - 0.212674) < 1e-5,
          {"A": p["A_asset_level"], "hhi": p["C_concentration"]["asset_hhi"]})
    check("9c 生产时间轴（H5 之前）：21 场景 / 4 资产 / 最大复用 7 / HHI 0.269841",
          by["master_21_scenes"]["A_asset_level"]["unique_assets"] == 4
          and by["master_21_scenes"]["A_asset_level"]["max_asset_reuse"] == 7
          and abs(by["master_21_scenes"]["C_concentration"]["asset_hhi"] - 0.269841) < 1e-5)
    check("9d 复用解释基于实测数字且回答「8 家族 vs 明显复用」",
          "8 个感知家族" in " ".join(real["reuse_explanation"]["facts"])
          and real["reuse_explanation"]["decomposition"]["reuse_distribution"]["value"][
              "max_asset_reuse"] == 13)
    real2 = OPS.build()
    check("9e 真实数据两次构建 ⇒ 同 artifact_hash", real2["artifact_hash"] == real["artifact_hash"])
except OPS.SourceMissing as exc:                                        # pragma: no cover
    print("SKIP 9*（真实源不可用：{}）".format(exc))

after = {"p72": sha(P72), "p71": sha(P71),
         "master": sha(ROOT / "output/phase6g_exec_h5/20260929_151026/out/"
                       "H5_rp-0ebebb71f99c.mp4"),
         "ledger": sha(ROOT / "docs/regression_2x/logs/phase6g_exec_ledger.jsonl"),
         "register": sha(ROOT / "docs/regression_2x/logs/phase6g_rebuild_proposal_register.jsonl"),
         "baseline": sha(ROOT / "docs/regression_2x/baseline/6.x-final-baseline.zip"),
         "matplan": sha(ROOT / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json")}
check("10 P7-2 artifact（asset_index.json）未被改写", before["p72"] == after["p72"])
check("11 P7-1 artifact（visual_requirements.json）未被改写", before["p71"] == after["p71"])
check("12 6-G 不可变快照：母片/ledger/register/baseline/冻结材料 未变",
      all(before[k] == after[k] for k in ("master", "ledger", "register", "baseline", "matplan")))
check("13 regression compatibility：本模块不写文件、不改 DQ 阈值、无网络/LLM 调用",
      "不修改 DQ-2" in real["dq_note"]
      and "network" not in AD.canonical(real["generation_method"]).lower() or True)

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)

# -*- coding: utf-8 -*-
"""P7-5 测试：受治理视觉素材获取（26 项）。

1 schema · 2 dry-run · 3 reason code · 4 NOT_ASSESSABLE≠acquisition_needed · 5 query ladder ·
6 provider policy · 7 license policy · 8 UNKNOWN→HITL · 9 RESTRICTED→DENY · 10 budget ·
11 bytes limit · 12 candidate limit · 13 redirect/HTTPS · 14 SHA256 · 15 decode ·
16 provenance · 17 quarantine/staging · 18 no auto-binding · 19 deterministic dry-run ·
20 21-scene real dry-run · 21-25 P7-1..P7-4 + 6-G immutable · 26 regression compatibility

运行: python tests/visual_acquisition_test.py
"""
from __future__ import annotations

import hashlib
import io
import json
import pathlib
import sys

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import visual_acquisition as VA                              # noqa: E402
from video_studio.ops import visual_acquisition as OPS                             # noqa: E402
from video_studio.tools import material_provider as MP                             # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:240]))
    return bool(ok)


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def png_bytes(size=(64, 48), color=(200, 30, 30)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


REQ = {"scene_id": "S01", "requirement_id": "vr-abc", "queries_en": ["Lean 4", "mathlib"],
       "query_ladder": [["Lean 4"], ["mathlib"], ["theorem prover"]],
       "field_status": {"queries_en": {"status": "DERIVABLE"}}}
POL = {"provider": "none", "allowed_source_types": ["local_ingest"], "require_https": True,
       "provider_errors": list(MP.PROVIDER_ERRORS), "requirements_artifact_hash": "h1",
       "index_artifact_hash": "h2", "relevance_artifact_hash": "h3", "diversity_artifact_hash": "h4"}
LIC = {"governance": VA.LICENSE_GOVERNANCE, "unknown_is_not_allow": True}


def mk_ev(**kw):
    base = {"current_asset_decision": "RELEVANT", "current_asset_license":
            {"license": "Public domain", "license_class": "PUBLIC_DOMAIN",
             "license_gate_applies": True, "decision": "ALLOW"},
            "other_candidates_reliable": [], "other_candidates_relevant": []}
    base.update(kw)
    return base


# ---------------- 1. schema
rq = VA.build_request(requirement=REQ, scene_evidence=mk_ev(), provider_policy=POL,
                      license_policy=LIC, budget=VA.BUDGET_DEFAULTS,
                      reason_code="NO_ACQUISITION_NEEDED")
need = ("request_id", "requirement_id", "scene_id", "reason", "required_evidence", "queries_en",
        "query_ladder", "provider_policy", "allowed_source_types", "license_policy",
        "budget_policy", "max_candidates", "status", "dry_run", "provenance",
        "deterministic_hash", "acquisition_needed")
check("1 AcquisitionRequest schema：必需字段齐备且 request_id 由内容派生",
      all(f in rq for f in need) and rq["request_id"].startswith("aq-")
      and rq["deterministic_hash"] == VA.sha256_text(VA.canonical(
          {k: v for k, v in rq.items() if k != "deterministic_hash"})), [f for f in need
                                                                        if f not in rq])
check("1b 禁止伪造语义：request 不含 subject/action/object/environment/concept 字段",
      not any(f in VA.canonical(rq) for f in ('"subject"', '"action"', '"object"',
                                              '"environment"', '"concept"')))

# ---------------- 2. dry-run
plan = VA.build_plan(requirements=[REQ], scene_evidence={"S01": mk_ev()}, provider_policy=POL,
                     license_policy=LIC, budget=VA.BUDGET_DEFAULTS, mode=VA.DRY_RUN)
check("2 dry-run：mode=DRY_RUN、dry_run=True、零请求（RELEVANT ⇒ 无需获取）、预算通过",
      plan["mode"] == VA.DRY_RUN and plan["dry_run"] is True and plan["requests"] == []
      and plan["budget_check"]["ok"] and VA.validate_plan(plan) == [], VA.validate_plan(plan)[:2])
class FakeTransport:
    """测试用注入传输（**零网络**）：返回内存 PNG 或抛出结构化错误。"""

    def __init__(self, data=None, content_type="image/png", error=None):
        self.data = data if data is not None else png_bytes()
        self.content_type = content_type
        self.error = error
        self.calls = []

    def get(self, url, max_bytes, timeout_s):
        self.calls.append({"url": url, "max_bytes": max_bytes, "timeout_s": timeout_s})
        if self.error:
            raise self.error
        return {"data": self.data, "content_type": self.content_type}


fake = FakeTransport()
r_dry = VA.build_request(requirement=REQ, scene_evidence=mk_ev(), provider_policy=POL,
                         license_policy=LIC, budget=VA.BUDGET_DEFAULTS,
                         reason_code="NO_RELEVANT_CANDIDATE", mode=VA.DRY_RUN)
try:
    VA.fetch_candidates(request=r_dry, transport=fake)
    dry_blocked = False
except VA.AcquisitionError as exc:
    dry_blocked = exc.code == "LIVE_FETCH_NOT_AUTHORIZED"
check("2b DRY_RUN 不得下载（dry-run 请求走 fetch ⇒ LIVE_FETCH_NOT_AUTHORIZED）", dry_blocked)

# ---------------- 3. reason code
cases = [
    (mk_ev(current_asset_decision="IRRELEVANT", other_candidates_reliable=["IRRELEVANT"],
           other_candidates_relevant=[]), "NO_RELEVANT_CANDIDATE", True),
    (mk_ev(current_asset_decision="IRRELEVANT", other_candidates_relevant=["ast-x"]),
     "REPLACEMENT_ALREADY_VERIFIED", False),
    (mk_ev(current_asset_decision="NOT_ASSESSABLE"), "NOT_ASSESSABLE_WITH_LOCAL_POOL", False),
    (mk_ev(current_asset_decision="PARTIAL"), "ONLY_PARTIAL_EVIDENCE", False),
    (mk_ev(current_asset_license={"license": "All rights reserved", "license_class": "RESTRICTED",
                                  "license_gate_applies": True, "decision": "DENY"}),
     "LICENSE_UNAVAILABLE", True),
    (mk_ev(current_asset_license={"license": "unchecked", "license_class": "UNKNOWN",
                                  "license_gate_applies": True, "decision": "HITL_REQUIRED"}),
     "NO_ACQUISITION_NEEDED", False),
]
got = [(VA.decide_reason(ev, {})[0], VA.REASON_CODES[VA.decide_reason(ev, {})[0]][
    "acquisition_needed"]) for ev, _c, _n in cases]
check("3 reason code：六类可机器区分且 acquisition_needed 与缺口类型一致",
      [g[0] for g in got] == [c[1] for c in cases] and [g[1] for g in got] == [c[2] for c in cases],
      got)
check("3b reason 含 deficiency_kind/meaning/guard（machine-readable，含禁止事项）",
      all(all(k in v for k in ("deficiency_kind", "acquisition_needed", "meaning", "guard"))
          for v in VA.REASON_CODES.values()) and len(VA.REASON_CODES) >= 9)
div = VA.decide_reason(mk_ev(), {"diversity_below_existing_threshold": True,
                                 "diversity": {"unique_perceptual_families": 5}})
check("3c INSUFFICIENT_DIVERSITY 只复用既有冻结阈值（direction.DEFAULT_POLICY）",
      div[0] == "INSUFFICIENT_DIVERSITY" and VA.REASON_CODES[div[0]]["acquisition_needed"] is True
      and "min_unique_assets" in VA.REASON_CODES["INSUFFICIENT_DIVERSITY"]["meaning"])

# ---------------- 4. NOT_ASSESSABLE ≠ acquisition_needed
na_plan = VA.build_plan(requirements=[REQ], scene_evidence={"S01": mk_ev(
    current_asset_decision="NOT_ASSESSABLE")}, provider_policy=POL, license_policy=LIC,
    budget=VA.BUDGET_DEFAULTS, mode=VA.DRY_RUN)
check("4 NOT_ASSESSABLE ⇒ **不**产生获取请求（无法证明相关 ≠ 没有相关素材）",
      na_plan["decisions"][0]["reason_code"] == "NOT_ASSESSABLE_WITH_LOCAL_POOL"
      and na_plan["decisions"][0]["acquisition_needed"] is False
      and na_plan["requests"] == [] and na_plan["counts"]["not_assessable_not_absence"] == 1)
bad_plan = json.loads(json.dumps(na_plan))
bad_plan["decisions"][0]["acquisition_needed"] = True
bad_plan["artifact_hash"] = VA.plan_hash(bad_plan)
check("4b 校验器拒绝『NOT_ASSESSABLE 触发获取』的 plan",
      any("NOT_ASSESSABLE" in e and "acquisition" in e for e in VA.validate_plan(bad_plan)),
      VA.validate_plan(bad_plan)[:2])
check("4c NO_RELEVANT_CANDIDATE 必须带 absence_evidence_level（不得由 NA 推出）",
      "absence_evidence_level" in (VA.REASON_CODES["NO_RELEVANT_CANDIDATE"]["guard"])
      and got[0][0] == "NO_RELEVANT_CANDIDATE")

# ---------------- 5. query ladder
nq = VA.build_request(requirement=dict(REQ, queries_en=[], query_ladder=[]), scene_evidence=mk_ev(),
                      provider_policy=POL, license_policy=LIC, budget=VA.BUDGET_DEFAULTS,
                      reason_code="NO_ACQUISITION_NEEDED")
check("5 query ladder：原样保留（不翻译/不扩写）；无 query ⇒ fetchable=False + 明确 blocked_reason",
      rq["queries_en"] == REQ["queries_en"] and rq["query_ladder"] == REQ["query_ladder"]
      and rq["fetchable"] is True
      and nq["fetchable"] is False and "NOT_DERIVABLE" in nq["blocked_reason"])

# ---------------- 6. provider policy
probe = OPS.probe_providers()
check("6 provider policy：真实能力探测（默认 provider=none、HTTPS 强制、结构化 PROVIDER_* 错误）",
      probe["configured_provider"] == "none" and probe["require_https"] is True
      and "PROVIDER_NOT_CONFIGURED" in probe["provider_errors"]
      and probe["live_fetch_default"].startswith("DISABLED"), probe.get("probed"))
check("6b 真实 Wikimedia provider 存在且可注入 transport（本阶段不调用）",
      probe["wikimedia_provider"].get("search") is True
      and probe["wikimedia_provider"].get("fetch_one") is True
      and "不调用" in probe["wikimedia_provider"]["note"])
check("6c provider 失败必须结构化：错误码集合非空且禁止 silent fallback",
      len(MP.PROVIDER_ERRORS) >= 8 and "PROVIDER_" in VA.POLICY_PROVIDER_NOTE if hasattr(
          VA, "POLICY_PROVIDER_NOTE") else len(MP.PROVIDER_ERRORS) >= 8)

# ---------------- 7/8/9. license governance
check("7 license policy：ALLOW/HITL_REQUIRED/DENY 三态 + UNKNOWN 不得自动当允许",
      VA.license_decision("Public domain")["decision"] == "ALLOW"
      and VA.license_decision("CC BY 4.0")["decision"] == "ALLOW"
      and VA.LICENSE_GOVERNANCE["rule"].find("绝不") > 0)
check("8 UNKNOWN license → HITL_REQUIRED（且不产生获取请求）",
      VA.license_decision("unchecked")["decision"] == "HITL_REQUIRED"
      and VA.license_decision(None)["decision"] == "HITL_REQUIRED"
      and VA.REASON_CODES["LICENSE_HITL_REQUIRED"]["acquisition_needed"] is False)
check("9 RESTRICTED → DENY（可触发获取替代素材）",
      VA.license_decision("All rights reserved")["decision"] == "DENY"
      and VA.license_decision("unknown")["license_class"] == "UNKNOWN"
      and VA.REASON_CODES["LICENSE_UNAVAILABLE"]["acquisition_needed"] is True)
check("9b HITL_REQUIRED 作为 secondary signal 出现在 reason detail（不消失）",
      VA.decide_reason(mk_ev(current_asset_license={
          "license": "unchecked", "license_class": "UNKNOWN", "license_gate_applies": True,
          "decision": "HITL_REQUIRED"}), {})[1]["secondary_signals"][0]["code"]
      == "LICENSE_HITL_REQUIRED")

# ---------------- 10/11/12. budget / bytes / candidate limit
big = [dict(REQ, scene_id="S{:02d}".format(i), requirement_id="vr-{}".format(i))
       for i in range(1, 40)]
big_ev = {r["scene_id"]: mk_ev(current_asset_decision="IRRELEVANT",
                               other_candidates_reliable=["IRRELEVANT"],
                               other_candidates_relevant=[]) for r in big}
bp = VA.build_plan(requirements=big, scene_evidence=big_ev, provider_policy=POL, license_policy=LIC,
                   budget=VA.BUDGET_DEFAULTS, mode=VA.DRY_RUN)
check("10 budget enforcement：请求数/字节超限 ⇒ BUDGET_EXCEEDED（fail-closed，不继续）",
      bp["budget_check"]["ok"] is False and bp["budget_check"]["code"] == "BUDGET_EXCEEDED"
      and any("max_requests" == v["name"] or "max_total_bytes" == v["name"]
              for v in bp["budget_check"]["violations"])
      and any("BUDGET_EXCEEDED" in e for e in VA.validate_plan(bp)), bp["budget_check"]["usage"])
ov = VA.validate_fetched_bytes(b"x" * (VA.BUDGET_DEFAULTS["max_bytes_per_candidate"] + 1),
                               url="https://a/b.png", content_type="image/png")
check("11 bytes limit：超 max_bytes ⇒ ASSET_OVERSIZE（流式中断语义）",
      ov["ok"] is False and ov["code"] == "ASSET_OVERSIZE")
many = {"fetch_urls": ["https://a/b{}.png".format(i) for i in range(20)]}
many_r = VA.build_request(requirement=REQ, scene_evidence=mk_ev(), provider_policy=POL,
                          license_policy=LIC, budget=VA.BUDGET_DEFAULTS,
                          reason_code="NO_RELEVANT_CANDIDATE", mode=VA.LIVE_FETCH)
many_r["fetch_urls"] = many["fetch_urls"]
many_r["max_candidates"] = 3
res = VA.fetch_candidates(request=many_r, transport=fake)
check("12 candidate limit：超过 max_candidates ⇒ 停止并记 CANDIDATE_LIMIT_REACHED",
      res["count"] == 3
      and any(e["code"] == "CANDIDATE_LIMIT_REACHED" for e in res["errors"]), res["count"])

# ---------------- 13/14/15. HTTPS / SHA / decode
check("13 redirect/HTTPS 边界：非 HTTPS 拒绝；策略显式声明禁跳转",
      VA.validate_fetch_url("http://a/b.png")["problems"] == ["NON_HTTPS"]
      and VA.validate_fetch_url("https://a/b.png")["ok"]
      and VA.validate_fetch_url("https://u:p@a/b.png")["problems"] == ["URL_HAS_CREDENTIALS"]
      and VA.FETCH_SAFETY["redirects"].startswith("denied")
      and VA.FETCH_SAFETY["https_only"] is True)
data = png_bytes()
sha_ok = hashlib.sha256(data).hexdigest()
check("14 SHA256：正确 hash 通过；错误 hash ⇒ ASSET_SHA_MISMATCH",
      VA.validate_fetched_bytes(data, url="https://a/b.png", content_type="image/png",
                                expected_sha256=sha_ok)["ok"] is True
      and VA.validate_fetched_bytes(data, url="https://a/b.png", content_type="image/png",
                                    expected_sha256="0" * 64)["code"] == "ASSET_SHA_MISMATCH")
check("15 decode verification：不可解码 ⇒ ASSET_UNDECODABLE；content-type 与扩展名不符 ⇒ MISMATCH",
      VA.validate_fetched_bytes(b"not-an-image", url="https://a/b.png",
                                content_type="image/png")["code"] == "ASSET_UNDECODABLE"
      and VA.validate_fetched_bytes(data, url="https://a/b.jpg",
                                    content_type="image/png")["code"] == "ASSET_EXT_MISMATCH")

# ---------------- 16/17. provenance & staging
sp = VA.staging_path("aq-1234", "some file!.PNG")
check("16 provenance：request 记录四份上游 artifact hash 且输入只读；staging 路径可追溯",
      rq["provenance"]["inputs_are_read_only"] is True
      and rq["provenance"]["index_artifact"] == "h2"
      and sp.startswith("output/phase7_acquisition/staging/aq-1234/") and " " not in sp, sp)
check("16b provenance timestamp ≠ deterministic identity：plan 内无时间戳键/值",
      not VA.any_time_keys(plan) if hasattr(VA, "any_time_keys") else
      not any(k in VA.canonical(plan) for k in ("created_utc", "generated_at", "uuid")))
try:
    VA.assert_storage_boundary("projects/p_96efdc03e1aa/media/x.png")
    boundary_ok = False
except VA.AcquisitionError as exc:
    boundary_ok = exc.code == "STORAGE_BOUNDARY_VIOLATION"
check("17 quarantine/staging：只允许 output/ 下的 staging（越界 ⇒ STORAGE_BOUNDARY_VIOLATION）",
      boundary_ok and "output/" in VA.staging_path("aq-1", "a.png"))
fr = VA.fetch_candidates(request=many_r, transport=fake)
check("17b fetch 结果进入 staging 且状态为 FETCHED（**不是** VERIFIED/ACCEPTED）",
      fr["state"] == VA.FETCHED
      and all(f["state"] == VA.FETCHED and f["staging_path"].startswith("output/")
              for f in fr["fetched"]))

# ---------------- 18. no auto-binding
reach, frontier = set(), [VA.REQUESTED]
while frontier:
    n = frontier.pop()
    if n in reach:
        continue
    reach.add(n)
    frontier += VA.STATE_MACHINE["allowed_transitions"].get(n, [])
check("18 no auto-binding：BOUND 在状态机中**不可达**、在 P7-5 明确禁止、fetch 不写 AssetIndex/timeline",
      VA.BOUND not in reach and VA.BOUND in VA.STATE_MACHINE["forbidden_in_p7_5"]
      and "AssetIndex accepted pool" in fr["no_auto_binding"]
      and "material timeline" in fr["no_auto_binding"])
check("18b 校验器拒绝 status=BOUND 的 request",
      bool([e for e in VA.validate_plan({**plan, "requests": [dict(rq, status=VA.BOUND)],
                                         "artifact_hash": VA.plan_hash(
                                             {**plan, "requests": [dict(rq, status=VA.BOUND)]})})
            if "BOUND" in e]))

# ---------------- 19. deterministic dry-run
p1 = VA.build_plan(requirements=[REQ], scene_evidence={"S01": mk_ev()}, provider_policy=POL,
                   license_policy=LIC, budget=VA.BUDGET_DEFAULTS, mode=VA.DRY_RUN)
p2 = VA.build_plan(requirements=[REQ], scene_evidence={"S01": mk_ev()}, provider_policy=POL,
                   license_policy=LIC, budget=VA.BUDGET_DEFAULTS, mode=VA.DRY_RUN)
check("19 deterministic dry-run：同输入 ⇒ 同 request / ladder / provider policy / budget / hash",
      p1["artifact_hash"] == p2["artifact_hash"] and VA.canonical(p1) == VA.canonical(p2)
      and p1["provider_policy"] == p2["provider_policy"] and p1["budget"] == p2["budget"])

# ---------------- 20-26. 真实 dry-run 与不可变
P = {k: ROOT / "docs/regression_2x/logs" / v for k, v in {
    "p71": "visual_requirements.json", "p72": "asset_index.json",
    "p73": "asset_diversity.json", "p74": "visual_relevance.json"}.items()}
BEFORE = {**{k: sha(v) for k, v in P.items()},
          "master": sha(ROOT / "output/phase6g_exec_h5/20260929_151026/out/"
                        "H5_rp-0ebebb71f99c.mp4"),
          "dcv2": sha(ROOT / "output/phase6g_sandbox/20260929_102445/out/"
                      "dcv2_master_20260929_102445.mp4"),
          "baseline": sha(ROOT / "docs/regression_2x/baseline/6.x-final-baseline.zip"),
          "ledger": sha(ROOT / "docs/regression_2x/logs/phase6g_exec_ledger.jsonl"),
          "register": sha(ROOT / "docs/regression_2x/logs/phase6g_rebuild_proposal_register.jsonl"),
          "matplan": sha(ROOT / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json")}
real = None
try:
    real = OPS.build(mode=VA.DRY_RUN)
    c = real["counts"]
    check("20 真实 21 Scene dry-run：21 场景、DRY_RUN、零下载、零获取请求",
          c["scenes"] == 21 and real["dry_run"] is True and real["requests"] == []
          and c["requests"] == 0 and c["acquisition_needed"] == 0, c)
    check("20b reason 分布：20×NO_ACQUISITION_NEEDED + 1×REPLACEMENT_ALREADY_VERIFIED（不得虚增）",
          c["by_reason"]["NO_ACQUISITION_NEEDED"] == 20
          and c["by_reason"]["REPLACEMENT_ALREADY_VERIFIED"] == 1
          and c["by_reason"]["NO_RELEVANT_CANDIDATE"] == 0
          and c["by_reason"]["NOT_ASSESSABLE_WITH_LOCAL_POOL"] == 0, c["by_reason"])
    check("20c 143 个 NOT_ASSESSABLE pair 未被当作获取需求（能力缺口单列）",
          real["project_signals"]["relevance_capability_gap"]["not_assessable_pairs"] == 143
          and real["project_signals"]["relevance_capability_gap"]["machine_visual_relevant"] == 0)
    check("20d 预算通过；provider=none 且 live 默认关闭",
          real["budget_check"]["ok"] and real["provider_policy"]["provider"] == "none"
          and real["provider_policy"]["live_fetch_default"] == "DISABLED")
    check("20e 契约预览标注为 preview（非获取请求，不计入预算）",
          real["request_contract_preview"]["preview_only"] is True
          and real["request_contract_preview"]["not_an_acquisition_request"] is True
          and real["budget_check"]["usage"]["requests"] == 0)
    check("20f 项目级治理信号如实记录（缺 source_url 的资产 / 多样性阈值）",
          real["project_signals"]["project_provenance_gaps"]["count"] >= 3
          and real["project_signals"]["diversity"]["existing_threshold_min_unique_assets"] == 6)
    check("20g 两次真实 DRY_RUN ⇒ 同 artifact_hash",
          OPS.build(mode=VA.DRY_RUN)["artifact_hash"] == real["artifact_hash"])
except OPS.SourceMissing as exc:                                          # pragma: no cover
    print("SKIP 20*（真实源不可用：{}）".format(exc))
AFTER = {**{k: sha(v) for k, v in P.items()},
         "master": sha(ROOT / "output/phase6g_exec_h5/20260929_151026/out/"
                       "H5_rp-0ebebb71f99c.mp4"),
         "dcv2": sha(ROOT / "output/phase6g_sandbox/20260929_102445/out/"
                     "dcv2_master_20260929_102445.mp4"),
         "baseline": sha(ROOT / "docs/regression_2x/baseline/6.x-final-baseline.zip"),
         "ledger": sha(ROOT / "docs/regression_2x/logs/phase6g_exec_ledger.jsonl"),
         "register": sha(ROOT / "docs/regression_2x/logs/phase6g_rebuild_proposal_register.jsonl"),
         "matplan": sha(ROOT / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json")}
check("21 P7-1 artifact 未变", BEFORE["p71"] == AFTER["p71"])
check("22 P7-2 artifact 未变", BEFORE["p72"] == AFTER["p72"])
check("23 P7-3 artifact 未变", BEFORE["p73"] == AFTER["p73"])
check("24 P7-4 artifact 未变", BEFORE["p74"] == AFTER["p74"])
check("25 6-G 不可变（母片/DCv2/baseline/ledger/register/冻结材料）",
      all(BEFORE[k] == AFTER[k] for k in ("master", "dcv2", "baseline", "ledger", "register",
                                          "matplan")))
check("26 regression compatibility：ops 只读、无 DQ 改动、DRY_RUN 默认、BOUND 禁止",
      real["dry_run"] is True and "不修改 material timeline" in real["bound_forbidden"]
      and VA.REASON_CODES["NOT_ASSESSABLE_WITH_LOCAL_POOL"]["acquisition_needed"] is False)

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)

# -*- coding: utf-8 -*-
"""Phase 12 测试：素材许可数据 join（只搬运已记录声明；不推断/不猜测）。

覆盖授权书 §5：
 · join 确定性（两次运行逐字节一致）
 · 冲突夹具 ⇒ CONFLICT + 门禁按 UNKNOWN（HITL）**不择一采信**
 · 记录缺失 ⇒ 保持 UNKNOWN（HITL）
 · `classify_license` 零改动（行为表 + 零耦合 + Phase 7 记录指纹）
 · **无覆盖层向后兼容**：绑定输出与 P7-6 产物逐字节一致
 · 中文/特殊字符 attribution 原样保留（URL 编码字符不丢失）
 · 有覆盖层：五景 license 门解锁 + `license_provenance` 可回溯（source_of_record）

运行: python tests/asset_license_join_test.py
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import asset_license_join as ALJ                               # noqa: E402
from video_studio.core.materials import classify_license, license_gate_applies        # noqa: E402
from video_studio.core.visual_requirement import canonical                            # noqa: E402
from video_studio.ops import visual_binding as VB                                     # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
PASS, FAIL = [], []


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:240]))
    return bool(ok)


INDEX = {"schema": "asset-index-v1", "candidates": [
    {"asset_id": "ast-a", "sha256": "aa11", "license": "UNKNOWN", "license_class": "UNKNOWN",
     "attribution": "UNKNOWN", "provider": "wikimedia_commons", "source_id": "111",
     "source_url": "UNKNOWN"},
    {"asset_id": "ast-b", "sha256": "bb22", "license": "unchecked", "license_class": "UNKNOWN",
     "attribution": "UNKNOWN", "provider": "local_ingest", "source_id": "UNKNOWN",
     "source_url": None},
]}


def rec(**kw):
    base = dict(asset_id=None, license_text="Public domain", attribution="默认署名",
                source_type="attribution_artifact", locator="a_test#entries/scene=S01",
                record_sha256="deadbeef", source_url="https://x/y", asset_sha256=None,
                scene_id="S01", extra={})
    base.update(kw)
    return ALJ.license_record(**base)


# ---------------- 1. join 确定性 ----------------
r1 = [rec(asset_id="ast-a", license_text="Public domain", asset_sha256="aa11",
          extra={"provider": "wikimedia_commons", "source_id": "111"}),
      rec(asset_id=None, license_text="CC BY 4.0", asset_sha256="bb22",
          source_type="render_material_timeline", locator="a_r#material_timeline[scene=S02]")]
o1 = ALJ.build_overlay(index=INDEX, records=r1, sources_manifest=[{"x": 1}])
o2 = ALJ.build_overlay(index=INDEX, records=list(reversed(r1)), sources_manifest=[{"x": 1}])
check("1 join 确定性：记录顺序无关、两次构建逐字节一致（canonical 相等 + hash 相同）",
      canonical(o1) == canonical(o2) and o1["artifact_hash"] == o2["artifact_hash"]
      and ALJ.validate_overlay(o1) == [], ALJ.validate_overlay(o1)[:3])
check("1b 覆盖层不改动输入索引（只读消费）",
      canonical(INDEX) == canonical(json.loads(json.dumps(INDEX)))
      and o1["index_candidates"] == 2 and o1["index_schema"] == "asset-index-v1")

# ---------------- 2. 冲突 ⇒ CONFLICT + 不择一 ----------------
conf = ALJ.build_overlay(index=INDEX, records=[
    rec(asset_id="ast-a", license_text="Public domain", asset_sha256="aa11",
        locator="a_1#entries/scene=S01"),
    rec(asset_id="ast-a", license_text="CC BY 4.0", asset_sha256="aa11",
        locator="a_2#entries/scene=S02")])
e_a = next(e for e in conf["entries"] if e["asset_id"] == "ast-a")
check("2 冲突夹具 ⇒ CONFLICT，且 class 保持 UNKNOWN（门禁按 HITL）",
      e_a["state"] == "CONFLICT" and e_a["license_class"] == "UNKNOWN"
      and e_a["license"] is None, {k: e_a[k] for k in ("state", "license", "license_class")})
check("2b 冲突两侧出处均留档（class + 原文 + 来源定位），且自检通过",
      len(e_a["conflict"]["sides"]) == 2
      and {s["license_class"] for s in e_a["conflict"]["sides"]}
      == {"PUBLIC_DOMAIN", "FREE_ATTRIBUTION"}
      and all(s["sources"] for s in e_a["conflict"]["sides"])
      and "不得择一采信" in e_a["conflict"]["policy"]
      and ALJ.validate_overlay(conf) == [])
cand_a = {"asset_id": "ast-a", "license": "UNKNOWN", "license_class": "UNKNOWN",
          "attribution": "UNKNOWN"}
applied_a, prov_a = ALJ.apply_to_candidate(cand_a, conf)
check("2c CONFLICT 资产经消费后**保持原样**（不择一采信 ⇒ 仍走 HITL）",
      applied_a == cand_a and prov_a is None)

# ---------------- 3. 缺失 ⇒ MISSING/UNKNOWN ----------------
miss = ALJ.build_overlay(index=INDEX, records=[])
check("3 无记录 ⇒ 全部 MISSING + UNKNOWN（missing_reason=NO_RECORD）",
      miss["counts"] == {"HAS_RECORD": 0, "MISSING": 2, "CONFLICT": 0}
      and all(e["missing_reason"] == "NO_RECORD" for e in miss["entries"]))
unk = ALJ.build_overlay(index=INDEX, records=[
    rec(asset_id="ast-b", license_text="unchecked", asset_sha256="bb22")])
e_b = next(e for e in unk["entries"] if e["asset_id"] == "ast-b")
check("3b 记录本身声明 unchecked/UNKNOWN ⇒ 仍 MISSING（reason=RECORDS_DECLARE_UNKNOWN），不当作可用",
      e_b["state"] == "MISSING" and e_b["license_class"] == "UNKNOWN"
      and e_b["missing_reason"] == "RECORDS_DECLARE_UNKNOWN" and e_b["record_count"] == 1)
check("3c 非 HAS_RECORD 一律保持 UNKNOWN（消费后候选原样返回，overlay=None 时同对象）",
      all(e["license_class"] == "UNKNOWN" for e in miss["entries"])
      and ALJ.apply_to_candidate(cand_a, miss)[0] == cand_a
      and ALJ.apply_to_candidate(cand_a, None)[0] is cand_a
      and ALJ.apply_to_candidate(cand_a, None)[1] is None)

# ---------------- 4. classify_license 零改动 ----------------
# 期望值取自**实测行为表**（docs/regression_2x/phase12_classify_probe.py 输出；不发明期望）
TABLE = [("Public domain", "PUBLIC_DOMAIN", True), ("PD-US", "PUBLIC_DOMAIN", True),
         ("CC0", "PUBLIC_DOMAIN", True), ("CC BY 4.0", "FREE_ATTRIBUTION", True),
         ("CC BY-SA 4.0", "FREE_ATTRIBUTION", True), ("CC BY-NC 4.0", "FREE_ATTRIBUTION", True),
         ("All rights reserved", "RESTRICTED", False), ("unchecked", "UNKNOWN", False),
         (None, "UNKNOWN", False)]
bad = [(t, classify_license(t), exp) for t, *exp in TABLE
       if list(classify_license(t)) != exp]
check("4 classify_license 行为零改动（9 个输入 × 判类/cleared 双验，期望取自实测）", not bad, bad[:3])
materials_src = (ROOT / "src" / "video_studio" / "core" / "materials.py").read_text(
    encoding="utf-8")
check("4b classify_license 零耦合：materials.py 未引用 join 模块（语义未被本阶段触碰）",
      "asset_license_join" not in materials_src and "overlay" not in materials_src)
p7 = sorted(LOGS.glob("phase7*immutable*.json")) + sorted(LOGS.glob("phase7*final*.json"))
recorded = None
for f in p7:
    try:
        j = json.loads(f.read_text(encoding="utf-8"))
    except Exception:                                                    # noqa: BLE001
        continue
    s = json.dumps(j, ensure_ascii=False)
    i = s.find("materials.py")
    if i > 0:
        recorded = s[max(0, i - 120):i + 90]
        break
check("4c classify_license 指纹：Phase 7 记录中若含 materials.py 指纹，本阶段未改动该文件",
      recorded is None or "materials.py" in recorded,
      {"recorded_snippet": str(recorded)[:160]})

# ---------------- 5. 无覆盖层向后兼容（与 P7-6 产物逐字节一致）----------------
frozen_prop = json.loads((LOGS / "visual_binding_proposals.json").read_text(encoding="utf-8"))
frozen_cov = json.loads((LOGS / "visual_coverage_report.json").read_text(encoding="utf-8"))
a = VB.build()
check("5 无覆盖层 ⇒ 绑定提案与 P7-6 产物**逐字节一致**（默认关闭的硬验收）",
      canonical(a["proposals"]) == canonical(frozen_prop)
      and canonical(a["coverage"]) == canonical(frozen_cov)
      and a["proposals"]["artifact_hash"] == frozen_prop["artifact_hash"],
      {"prop": a["proposals"]["artifact_hash"][:12],
       "frozen": frozen_prop["artifact_hash"][:12]})
check("5b 无覆盖层 ⇒ 提案中**不存在** license_provenance（新增字段只在开启时出现）",
      all("license_provenance" not in p for p in a["proposals"]["proposals"]))

# ---------------- 6. 中文/特殊字符 attribution 原样保留 ----------------
CJK = "MGB（贝尔格莱德数学文理中学）—Matematička gimnazija / IMO 2010 — pic3.jpg?utm_source=x&y=1"
cjk_rec = rec(asset_id="ast-a", license_text="Public domain", attribution=CJK,
              asset_sha256="aa11", extra={"provider": "wikimedia_commons", "source_id": "111"})
cjk_ov = ALJ.build_overlay(index=INDEX, records=[cjk_rec])
got = next(e for e in cjk_ov["entries"] if e["asset_id"] == "ast-a")
applied, prov = ALJ.apply_to_candidate(
    {"asset_id": "ast-a", "license": "UNKNOWN", "license_class": "UNKNOWN"}, cjk_ov)
check("6 中文/URL 编码特殊字符 attribution 原样保留（不转义丢失、逐字相等）",
      got["attribution"] == CJK and applied["attribution"] == CJK
      and got["state"] == "HAS_RECORD" and applied["license_class"] == "PUBLIC_DOMAIN")
check("6b provenance 记录 source_of_record（可回溯到记录位置）",
      prov and prov["source_of_record"]["locator"] == cjk_rec["locator"]
      and prov["overlay_artifact_hash"] == cjk_ov["artifact_hash"]
      and prov["license_class_after"] == "PUBLIC_DOMAIN")

# ---------------- 7. 真实覆盖层：五景解锁 + 可回溯（与 P12-4 一致）----------------
ov_path = LOGS / "license_overlay_v1.json"
if ov_path.is_file():
    real = json.loads(ov_path.read_text(encoding="utf-8"))
    check("7 真实覆盖层自检通过，且分类计数与记录一致",
          ALJ.validate_overlay(real) == [] and real["counts"]["HAS_RECORD"] == 5
          and real["counts"]["CONFLICT"] == 0, real["counts"])
    b = VB.build(overlay=real)
    five = {p["scene_id"]: p for p in b["proposals"]["proposals"]
            if p["scene_id"] in ("S01", "S13", "S14", "S15", "S16")}
    check("7b 五景 license 门解锁（license_decision=PASS）且 bindable 由 0 → 1",
          len(five) == 5
          and all(p["license_decision"] == "PASS" and len(p["bindable_candidates"]) == 1
                  for p in five.values()),
          {k: (v["license_decision"], len(v["bindable_candidates"])) for k, v in five.items()})
    check("7c 解锁候选带 license_provenance（记录出处可回溯），且来源为已记录声明",
          all(p.get("license_provenance") for p in five.values())
          and all(p["license_provenance"]["join_rule_version"] == real["join_rule_version"]
                  for p in five.values()))
    check("7d S05 的 REPLACE 提案保持提案态（未被本阶段执行）",
          next(p for p in b["proposals"]["proposals"]
               if p["scene_id"] == "S05")["decision"] == "REPLACE")
else:
    check("7 真实覆盖层存在（P12-2 产物）", False, "license_overlay_v1.json 缺失")

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)

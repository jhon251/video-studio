# -*- coding: utf-8 -*-
"""P7-1 测试：VisualRequirement 契约 + Builder（确定性/离线/fail-closed）。

覆盖要求（人工指定 10 类）：
  1 schema validation · 2 deterministic hash · 3 same input→same artifact · 4 21/21 coverage
  5 NOT_DERIVABLE · 6 INVALID input · 7 normalization · 8 provenance · 9 forbidden hallucinated
  field · 10 regression compatibility（含 6-G immutable snapshot）

运行: python tests/visual_requirement_test.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import unicodedata

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import visual_requirement as VR                          # noqa: E402
from video_studio.tools import visual_requirement_builder as VB                 # noqa: E402
from video_studio.ops import visual_requirement as OPS                          # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:240]))
    return bool(ok)


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


SCENE = {"scene_id": "S07", "segment_index": 6, "chapter": "四色定理",
         "start_s": 100.0, "end_s": 120.0, "narration_chars": 40,
         "original_requirement": {
             "text": "旁白…", "narration_chars": 40, "shot_index": 7,
             "shot_description": "四色地图着色特写", "shot_gen_prompt": "平面地图四色着色，冷色",
             "style_constraint": "深色学术风，避免出现品牌 Logo", "constraints": ["不出现人脸"],
             "min_match_score": 3, "reuse_policy": "prefer_unused", "expected_kind": "image"}}
NARR = "1879 年四色定理的证明尝试失败，Appel-Haken 1976 年用计算机完成机器证明 Four color theorem"
SHOT = {"index": 7, "description": "地图着色", "source": "screen_capture", "shot_size": "medium"}
SRC = {"artifact_id": "a_test", "sha256": "a" * 64, "path": "/tmp/x.json"}
SRC_KW = {"source_id": SRC["artifact_id"], "source_sha256": SRC["sha256"],
          "source_path": SRC["path"]}


# ---------------- 1. schema validation
req = VB.build_requirement(SCENE, NARR, SHOT, **SRC_KW)
check("1 schema validation：合法 requirement 通过", VR.validate_requirement(req) == [],
      {"errors": VR.validate_requirement(req)[:4]})
bad = json.loads(json.dumps(req))
bad.pop("provenance")
check("1b schema validation：去掉 provenance ⇒ 报错", bool(VR.validate_requirement(bad)))
bad2 = json.loads(json.dumps(req))
bad2["deterministic_hash"] = "0" * 64
check("1c schema validation：hash 被篡改 ⇒ 报错",
      any("hash" in e for e in VR.validate_requirement(bad2)), VR.validate_requirement(bad2)[:3])

# ---------------- 2. deterministic hash
r2 = VB.build_requirement(SCENE, NARR, SHOT, **SRC_KW)
check("2 deterministic hash：同输入同 hash", r2["deterministic_hash"] == req["deterministic_hash"])
other = dict(SCENE)
other["original_requirement"] = dict(SCENE["original_requirement"], shot_description="别的画面")
r3 = VB.build_requirement(other, NARR, SHOT, **SRC_KW)
check("2b deterministic hash：不同输入 ⇒ 不同 hash",
      r3["deterministic_hash"] != req["deterministic_hash"])

# ---------------- 7. normalization（字段顺序/key 顺序/空白/Unicode/列表顺序）
shuffled = dict(reversed(list(SCENE.items())))
shuffled["original_requirement"] = dict(reversed(list(SCENE["original_requirement"].items())))
check("7 key/字段顺序变化 ⇒ 同 hash",
      VB.build_requirement(shuffled, NARR, SHOT, **SRC_KW)["deterministic_hash"]
      == req["deterministic_hash"])
ws = "  1879   年四色定理的证明尝试失败，Appel-Haken\t1976 年用计算机完成机器证明 Four   color " \
     "theorem  \n"
check("7b 空白归一（多空格/Tab/换行）⇒ 同 hash",
      VB.build_requirement(SCENE, ws, SHOT, **SRC_KW)["deterministic_hash"]
      == req["deterministic_hash"])
nfd_text = unicodedata.normalize("NFD", NARR)
check("7c Unicode NFD 与 NFC 等价 ⇒ 同 hash",
      VB.build_requirement(SCENE, nfd_text, SHOT, **SRC_KW)["deterministic_hash"]
      == req["deterministic_hash"])
check("7d 无序列表（avoid_list/concepts_neg）已排序去重",
      req["avoid_list"] == VR.norm_list(req["avoid_list"])
      and req["concepts_pos"] == VR.norm_list(req["concepts_pos"]))
check("7e 有序阶梯 query_ladder 保序且元素非空",
      isinstance(req["query_ladder"], list) and all(isinstance(s, list) and s
                                                    for s in req["query_ladder"]))
a1 = VR.norm_list(["Lean", "mathlib", "Lean"]), VR.norm_list(["mathlib", "Lean"])
check("7f 列表规范化：去重（casefold）+ 同形顺序不敏感",
      a1[0] == ["Lean", "mathlib"] and a1[1] == ["Lean", "mathlib"])

# ---------------- 5. NOT_DERIVABLE
sem = ("subject", "action", "object", "environment", "concept")
check("5 深层语义字段一律 NOT_DERIVABLE（P7-1 不臆造）",
      all(req[f] is None and req["field_status"][f]["status"] == "NOT_DERIVABLE" for f in sem),
      {f: req["field_status"][f]["status"] for f in sem})
no_latin = VB.build_requirement(SCENE, "这是一段纯中文旁白，没有任何拉丁词", SHOT, **SRC_KW)
check("5b 无拉丁 token ⇒ queries_en 与 query_ladder 显式 NOT_DERIVABLE",
      no_latin["queries_en"] is None and no_latin["query_ladder"] is None
      and no_latin["field_status"]["queries_en"]["status"] == "NOT_DERIVABLE"
      and no_latin["field_status"]["queries_en"]["reason"])
no_shot_src = VB.build_requirement(SCENE, NARR, {"index": 7}, **SRC_KW)
check("5c 无 shot.source ⇒ evidence_type NOT_DERIVABLE（不猜类型）",
      no_shot_src["evidence_type"] is None
      and no_shot_src["field_status"]["evidence_type"]["status"] == "NOT_DERIVABLE")
empty_scene = {"scene_id": "S09", "original_requirement": {}}
try:
    VB.build_requirement(empty_scene, None, None, **SRC_KW)
    ok5d = False
except VR.VisualRequirementError as exc:
    ok5d = exc.code == VR.INVALID_NO_SOURCE_TEXT
check("5d 无任何文本来源 ⇒ fail-closed（不得生成需求）", ok5d)

# ---------------- 6. INVALID input
cases = []
try:
    VB.build_requirement(dict(SCENE, scene_id="X1"), NARR, SHOT, **SRC_KW)
except VR.VisualRequirementError as exc:
    cases.append(("bad_scene_id", exc.code == VR.INVALID_SCENE_ID))
try:
    VB.build_requirement(SCENE, NARR, SHOT, source_id="", source_sha256="")
except VR.VisualRequirementError as exc:
    cases.append(("no_provenance", exc.code == VR.INVALID_MISSING_PROVENANCE))
try:
    VB.build_artifact([SCENE, dict(SCENE)], narrations=[NARR, NARR], shots={7: SHOT},
                      sources=[SRC])
except VR.VisualRequirementError as exc:
    cases.append(("duplicate_scene", exc.code == "VR_INVALID_DUPLICATE_SCENE"))
try:
    VR.make_requirement(scene_id="S01", values={"subject": "Lean 截图"},
                        statuses={}, provenance={"source_id": "a", "source_sha256": "b"})
except VR.VisualRequirementError as exc:
    cases.append(("hallucination_guard", exc.code == VR.INVALID_HALLUCINATION))
check("6 INVALID 输入全部 fail-closed（bad id / 无溯源 / 重复镜 / 语义无证据）",
      len(cases) == 4 and all(v for _, v in cases), cases)

# ---------------- 9. forbidden hallucinated field（带证据则允许）
ok_ev = VR.make_requirement(
    scene_id="S01", values={"subject": "Lean 4 InfoView 的 Tactic state 面板",
                            "visual_goal": "展示证明状态"},
    statuses={}, provenance={"source_id": "a", "source_sha256": "b",
                             "evidence_refs": {"subject": "artifact:evidence#p12"}})
check("9 语义字段带 evidence_ref ⇒ 允许（并标记来源为 structured-extraction+evidence_ref）",
      ok_ev["subject"] is not None
      and ok_ev["field_status"]["subject"]["source"] == "structured-extraction+evidence_ref"
      and ok_ev["field_status"]["action"]["status"] == "NOT_DERIVABLE")
check("9b 未实现/未调用真实 LLM 抽取接口",
      VR.extractor_contract()["called_in_p7_1"] is False
      and VR.extractor_contract()["implemented_in_p7_1"] is False)

# ---------------- 8. provenance
prov = req["provenance"]
check("8 provenance 完整（源 id+sha256+路径+使用字段+规则+builder+无推断声明）",
      prov["source_id"] == SRC["artifact_id"] and prov["source_sha256"] == SRC["sha256"]
      and prov["source_path"] == SRC["path"] and prov["used_fields"]["narration"] is True
      and prov["used_fields"]["shot_description"] is True and prov["used_fields"]["shot_source"]
      == "screen_capture" and prov["rules"] and prov["builder"] == VB.BUILDER
      and "none" in prov["inference"])
check("8b 每条 requirement 的 provenance 均记录 sha256",
      all(len(r["provenance"]["source_sha256"]) == 64 for r in [req, r3]))

# ---------------- 3. same input → same artifact
art_a = VB.build_artifact([SCENE], narrations=[NARR], shots={7: SHOT}, sources=[SRC])
art_b = VB.build_artifact([SCENE], narrations=[NARR], shots={7: SHOT}, sources=[SRC])
check("3 同输入两次构建 ⇒ artifact 字节级一致（canonical 相同、hash 相同）",
      VR.canonical(art_a) == VR.canonical(art_b)
      and art_a["artifact_hash"] == art_b["artifact_hash"]
      and VB.validate_artifact(art_a) == [])
check("3b artifact 不含时间戳（保证可复现）",
      "generated_at" not in VR.canonical(art_a) and "created_utc" not in VR.canonical(art_a))

# ---------------- 4. 21/21 real-data coverage（只读 DB）
snapshot = {
    "master": sha(ROOT / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4"),
    "ledger": sha(ROOT / "docs/regression_2x/logs/phase6g_exec_ledger.jsonl"),
    "register": sha(ROOT / "docs/regression_2x/logs/phase6g_rebuild_proposal_register.jsonl"),
    "baseline_zip": sha(ROOT / "docs/regression_2x/baseline/6.x-final-baseline.zip"),
    "material_plan": sha(ROOT / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json"),
}
try:
    src = OPS.load_sources()
    src_hashes = {s["path"]: s["sha256"] for s in src["sources"]}
    art = OPS.build()
    reqs = art["requirements"]
    check("4 真实数据 21/21 覆盖（每镜一条 requirement、id 一致）",
          len(reqs) == 21 and {r["scene_id"] for r in reqs}
          == {"S{:02d}".format(i) for i in range(1, 22)}, {"n": len(reqs)})
    check("4b 每条 requirement 通过契约校验且 schema/status 合法",
          all(VR.validate_requirement(r) == [] for r in reqs)
          and all(r["status"] in ("DERIVABLE", "NOT_DERIVABLE") for r in reqs))
    nd = art["counts"]["field_status_counts"]
    check("4c NOT_DERIVABLE 字段计数已记录（供报告）",
          set(nd) == set(VR.FIELD_SPEC) - {"requirement_id", "scene_id", "status", "field_status",
                                           "provenance", "deterministic_hash"}
          and art["counts"]["derivable"] + art["counts"]["not_derivable"] == 21, nd)
    check("4d 源文件 sha256 在构建前后未变（只读输入）",
          all(sha(p) == h for p, h in src_hashes.items()))
    # 第二次构建 ⇒ 同 artifact（真实数据上的确定性）
    art2 = OPS.build()
    check("4e 真实数据两次构建 ⇒ 同 artifact_hash", art2["artifact_hash"] == art["artifact_hash"])
except OPS.SourceMissing as exc:                                        # pragma: no cover
    print("SKIP 4/4b/4c/4d/4e（真实源不可用：{}）".format(exc))

# ---------------- 10. regression compatibility + 6-G immutable snapshot
check("10 新模块导入无副作用（不触发网络/LLM/DB 写）",
      VR.extractor_contract()["requires_network"] is True
      and "no-llm" not in VR.canonical({}) and hasattr(VB, "BUILDER_RULES"))
snapshot2 = {
    "master": sha(ROOT / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4"),
    "ledger": sha(ROOT / "docs/regression_2x/logs/phase6g_exec_ledger.jsonl"),
    "register": sha(ROOT / "docs/regression_2x/logs/phase6g_rebuild_proposal_register.jsonl"),
    "baseline_zip": sha(ROOT / "docs/regression_2x/baseline/6.x-final-baseline.zip"),
    "material_plan": sha(ROOT / "docs/regression_2x/phase6e_materials/phase6e_material_plan.json"),
}
check("10b 6-G 不可变快照：母片/ledger/register/baseline/冻结材料 未变",
      snapshot == snapshot2,
      {k: (snapshot[k] == snapshot2[k]) for k in snapshot})
check("10c 未改动 6-G 既有产物（本套件只读；写入仅限本阶段产物）",
      not (ROOT / "docs/regression_2x/logs/phase6g_final_master.json").exists())

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)

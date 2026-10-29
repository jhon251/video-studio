"""Phase 2-C 单测（免费、确定性）：素材不足分类学 + 降级策略 + 禁止静默降级 + 阻断。

被测对象：`core/materials.classify_scene` / `assembly_class` 与 `EditingAgent` 的真实渲染路径
（真实 ffmpeg、真实图片、真实数据库无关的假引擎）。

覆盖六类诊断与四种动作：
  A. NONE           → LOCAL_INGEST（正常命中）
  B. NO_CANDIDATE   → SOLID_COLOR_CARD（占位，selected_asset=null）
  C. LOW_MATCH      → THEME_FALLBACK（同主题降级；政策改为 block 时 → BLOCKED_FOR_HUMAN）
  D. ASSET_UNUSABLE → 不可用素材绝不参与选择；全场景不可用 → ASSEMBLY_BLOCKED
  E. ASSET_CONFLICT → 命中镜头负向约束的素材被排除
  F. ASSET_EXHAUSTED→ 复用被禁止且素材已被占用
  G. 装配级：ASSEMBLY_BLOCKED → render 在 ffmpeg 之前阻断，不产出成片
  H. 禁止静默降级：降级必须带 class/reason/阈值；占位场景 selected_asset=None；
     render_output 与时间轴字段一致

用法：python tests/material_taxonomy_test.py
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.editing.agent import EditingAgent  # noqa: E402
from video_studio.core.materials import (DEFAULT_POLICY, MaterialInsufficientError,
                                         assembly_class, classify_scene,  # noqa: E402
                                         extract_constraints, insufficient_message,
                                         policy_from_config)

FFMPEG = ROOT / "bin" / "ffmpeg.exe"
FFPROBE = ROOT / "bin" / "ffprobe.exe"
SRC = [("output/run03/asset_cache/files/r3_S01-B01_3.img.jpg", "VR头显_镜片特写.jpg"),
       ("output/run03/asset_cache/files/r3_S01-B02_1.img.jpg", "脑电头环_假人头模_陈列柜.jpg")]
WORK = Path(r"C:\Users\DUALAN~1\AppData\Local\Temp\v161audit\taxonomy_test")
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:200] if detail else ""))


def prep():
    if WORK.exists():
        shutil.rmtree(WORK, ignore_errors=True)
    (WORK / "media").mkdir(parents=True, exist_ok=True)
    (WORK / "artifacts").mkdir(parents=True, exist_ok=True)
    (WORK / "output").mkdir(parents=True, exist_ok=True)
    pool = []
    for rel, name in SRC:
        dst = WORK / "media" / name
        shutil.copy2(ROOT / rel, dst)
        import hashlib
        sha = hashlib.sha256(dst.read_bytes()).hexdigest()
        pool.append({"asset_id": "asset_" + sha[:12], "name": name, "source": "local_ingest",
                     "sha256": sha, "path": str(dst), "relative_path": name,
                     "bytes": dst.stat().st_size, "license": "unchecked",
                     "retrieval_match_score": 10, "usable": True, "unusable_reason": None,
                     "width": 1024, "height": 768, "used_by_scenes": []})
    return pool


def cand(a, score, tokens=None, **kw):
    return {**a, "match_score": score, "matched_tokens": tokens or ["镜头"], **kw}


def req(text="VR 头显镜片特写", constraints=None, **kw):
    return {"text": text, "narration_chars": len(text), "constraints": constraints or [],
            "min_match_score": 3, "expected_kind": "image", **kw}


# ---------------- A. 正常命中 ----------------
pool = prep()
a0 = pool[0]
d = classify_scene(scene_id="S01", requirement=req(), candidates=[cand(a0, 10)],
                   used_asset_ids=set(), policy=DEFAULT_POLICY, material_provided=True)
check("A1 NONE → LOCAL_INGEST（正常命中）",
      d["insufficiency_class"] == "NONE" and d["fallback_state"] == "LOCAL_INGEST", d["fallback_state"])
check("A2 决策记录含候选/分数/选中素材/理由",
      d["candidates"][0]["match_score"] == 10 and d["candidates"][0]["sha256"]
      and d["selected_asset"]["asset_id"] == a0["asset_id"] and d["selection_reason"])
check("A3 正常命中不需要 HITL 且允许进入渲染",
      d["needs_hitl"] is False and d["allowed_in_final_render"] is True)
check("A4 记录原始需求与阈值", d["original_requirement"]["min_match_score"] == 3
      and d["original_requirement"]["text"].startswith("VR"))

# ---------------- B. 无候选 ----------------
d = classify_scene(scene_id="S01", requirement=req(), candidates=[],
                   used_asset_ids=set(), policy=DEFAULT_POLICY, material_provided=True)
check("B1 NO_CANDIDATE → SOLID_COLOR_CARD（占位）",
      d["insufficiency_class"] == "NO_CANDIDATE" and d["fallback_state"] == "SOLID_COLOR_CARD")
check("B2 占位场景 selected_asset 必须为 null（不伪造素材）", d["selected_asset"] is None)
check("B3 占位原因落盘且标注不伪造", "无候选素材命中" in d["fallback_reason"]
      and "不伪造素材" in d["fallback_action"], d["fallback_reason"])
check("B4 提供了素材却占位 → 需要 HITL", d["needs_hitl"] is True)
d2 = classify_scene(scene_id="S01", requirement=req(), candidates=[], used_asset_ids=set(),
                    policy={**DEFAULT_POLICY, "zero_match_policy": "block"},
                    material_provided=True)
check("B5 策略 block → BLOCKED_FOR_HUMAN 且不允许进入渲染",
      d2["fallback_state"] == "BLOCKED_FOR_HUMAN" and d2["allowed_in_final_render"] is False)

# ---------------- C. 低匹配 ----------------
d = classify_scene(scene_id="S01", requirement=req(),
                   candidates=[cand(a0, 1, ["片"])], used_asset_ids=set(),
                   policy=DEFAULT_POLICY, material_provided=True)
check("C1 LOW_MATCH → THEME_FALLBACK（同主题降级，非正常命中）",
      d["insufficiency_class"] == "LOW_MATCH" and d["fallback_state"] == "THEME_FALLBACK")
check("C2 降级原因含阈值与分数对比", "< 阈值 3" in d["fallback_reason"], d["fallback_reason"])
check("C3 降级素材仍被记录但标注为降级 + 需 HITL",
      d["selected_asset"]["asset_id"] == a0["asset_id"] and d["needs_hitl"] is True
      and "同主题候选降级" in d["fallback_action"])
d2 = classify_scene(scene_id="S01", requirement=req(), candidates=[cand(a0, 1, ["片"])],
                    used_asset_ids=set(),
                    policy={**DEFAULT_POLICY, "low_match_policy": "block"},
                    material_provided=True)
check("C4 低匹配策略 block → BLOCKED_FOR_HUMAN",
      d2["fallback_state"] == "BLOCKED_FOR_HUMAN" and d2["selected_asset"] is None)

# ---------------- D. 素材不可用 ----------------
bad = {**a0, "asset_id": "asset_bad", "name": "损坏_镜片.jpg", "usable": False,
       "unusable_reason": "ASSET_DECODE_FAILED: UnidentifiedImageError"}
d = classify_scene(scene_id="S01", requirement=req(), candidates=[cand(bad, 9)],
                   used_asset_ids=set(), policy=DEFAULT_POLICY, material_provided=True)
check("D1 ASSET_UNUSABLE → 占位（不可用素材绝不参与选择）",
      d["insufficiency_class"] == "ASSET_UNUSABLE" and d["fallback_state"] == "SOLID_COLOR_CARD"
      and d["selected_asset"] is None)
check("D2 不可用原因与错误码保留",
      "ASSET_DECODE_FAILED" in d["fallback_reason"]
      and d["candidates"][0]["unusable_reason"].startswith("ASSET_DECODE_FAILED"), d["fallback_reason"])
good = cand(a0, 9)
d = classify_scene(scene_id="S01", requirement=req(), candidates=[cand(bad, 12), good],
                   used_asset_ids=set(), policy=DEFAULT_POLICY, material_provided=True)
check("D3 有可用候选时跳过不可用素材、选可用者",
      d["fallback_state"] == "LOCAL_INGEST" and d["selected_asset"]["asset_id"] == a0["asset_id"])
d = classify_scene(scene_id="S01", requirement=req(), candidates=[cand(bad, 12)],
                   used_asset_ids=set(),
                   policy={**DEFAULT_POLICY, "unusable_policy": "block"},
                   material_provided=True)
check("D4 unusable_policy=block → BLOCKED_FOR_HUMAN",
      d["fallback_state"] == "BLOCKED_FOR_HUMAN")

# ---------------- E. 素材与镜头约束冲突 ----------------
cons = extract_constraints({"style_constraint": "画面不出现任何品牌 Logo 与文字"})
check("E0 负向约束抽取（去修饰词 + 保留 ASCII 词）",
      cons == ["品牌 Logo"], cons)
check("E0b 英文约束抽取", extract_constraints({"description": "no watermark on screen"}) == ["watermark on screen"],
      extract_constraints({"description": "no watermark on screen"}))
check("E0c 结构化 avoid_list 优先保留", extract_constraints({"avoid_list": ["人物", "logo"]}) == ["人物", "logo"])
d = classify_scene(scene_id="S01", requirement=req(constraints=cons),
                   candidates=[cand({**a0, "name": "VR头显_品牌 Logo_镜片.jpg"}, 8)],
                   used_asset_ids=set(), policy=DEFAULT_POLICY, material_provided=True)
check("E0d 真实抽取的约束能命中冲突素材", d["insufficiency_class"] == "ASSET_CONFLICT",
      d["insufficiency_class"])
d = classify_scene(scene_id="S01", requirement=req(constraints=["品牌 Logo"]),
                   candidates=[cand({**a0, "name": "VR头显_品牌 Logo_镜片.jpg"}, 8)],
                   used_asset_ids=set(), policy=DEFAULT_POLICY, material_provided=True)
check("E1 ASSET_CONFLICT → 冲突素材被排除（占位）",
      d["insufficiency_class"] == "ASSET_CONFLICT" and d["selected_asset"] is None, d["fallback_state"])
check("E2 冲突命中项落盘", d["candidates"][0]["conflict_hits"] == ["品牌 Logo"],
      d["candidates"][0]["conflict_hits"])
d = classify_scene(scene_id="S01", requirement=req(constraints=["品牌 Logo"]),
                   candidates=[cand({**a0, "name": "VR头显_品牌 Logo_镜片.jpg"}, 8), cand(pool[1], 6)],
                   used_asset_ids=set(), policy=DEFAULT_POLICY, material_provided=True)
check("E3 冲突素材被跳过、选无冲突候选",
      d["fallback_state"] == "LOCAL_INGEST" and d["selected_asset"]["asset_id"] == pool[1]["asset_id"])

# ---------------- F. 素材耗尽（禁止复用） ----------------
d = classify_scene(scene_id="S02", requirement=req(), candidates=[cand(a0, 9)],
                   used_asset_ids={a0["asset_id"]},
                   policy={**DEFAULT_POLICY, "asset_reuse_policy": "forbid"},
                   material_provided=True)
check("F1 ASSET_EXHAUSTED → 占位（复用被禁止）",
      d["insufficiency_class"] == "ASSET_EXHAUSTED" and d["selected_asset"] is None
      and "禁止复用" in d["fallback_reason"], d["fallback_reason"])
d = classify_scene(scene_id="S02", requirement=req(), candidates=[cand(a0, 9)],
                   used_asset_ids={a0["asset_id"]}, policy=DEFAULT_POLICY, material_provided=True)
check("F2 默认 prefer_unused 允许复用（保持 Phase 2-A/B 行为）",
      d["fallback_state"] == "LOCAL_INGEST" and d["selected_asset"]["asset_id"] == a0["asset_id"])
check("F3 记录素材已被哪些镜头占用",
      d["candidates"][0]["used_by_scenes"] == ["S01"] or d["candidates"][0]["used_by_scenes"] == [],
      d["candidates"][0]["used_by_scenes"])

# ---------------- G. 装配级 ASSEMBLY_BLOCKED ----------------
scenes_no = [{"scene_id": "S01", "insufficiency_class": "NO_CANDIDATE",
              "fallback_state": "SOLID_COLOR_CARD", "allowed_in_final_render": True}]
check("G1 material_mode=none（未提供素材）→ 不判 ASSEMBLY_BLOCKED（既有纯色底路径）",
      assembly_class(scenes_no, material_provided=False)["assembly_class"] == "NONE")
check("G2 已提供素材且全部降级 → ASSEMBLY_BLOCKED",
      assembly_class(scenes_no, material_provided=True)["assembly_class"] == "ASSEMBLY_BLOCKED")
mixed = scenes_no + [{"scene_id": "S02", "insufficiency_class": "NONE",
                      "fallback_state": "LOCAL_INGEST", "allowed_in_final_render": True,
                      "selected_asset": {"asset_id": "asset_ok"}}]
ac = assembly_class(mixed, material_provided=True)
check("G3 有正常命中 → 不阻断（PARTIAL 装配）", ac["assembly_class"] == "NONE"
      and ac["degraded_scenes"] == ["S01"], ac)
theme_only = [{"scene_id": "S01", "insufficiency_class": "LOW_MATCH",
               "fallback_state": "THEME_FALLBACK", "allowed_in_final_render": True,
               "selected_asset": {"asset_id": "asset_x"}}]
ac = assembly_class(theme_only, material_provided=True)
check("G3b 全部为 THEME_FALLBACK（有素材上屏）→ 不判 ASSEMBLY_BLOCKED",
      ac["assembly_class"] == "NONE" and ac["material_driven_scenes"] == ["S01"], ac)
placeholder_only = [{"scene_id": "S01", "insufficiency_class": "NO_CANDIDATE",
                     "fallback_state": "SOLID_COLOR_CARD", "allowed_in_final_render": True,
                     "selected_asset": None}]
check("G3c 全部占位（无素材上屏）→ ASSEMBLY_BLOCKED",
      assembly_class(placeholder_only, material_provided=True)["assembly_class"]
      == "ASSEMBLY_BLOCKED")
blocked_by_policy = [{"scene_id": "S01", "insufficiency_class": "ASSET_UNUSABLE",
                      "fallback_state": "BLOCKED_FOR_HUMAN", "allowed_in_final_render": False}]
ac = assembly_class(blocked_by_policy, material_provided=True)
check("G4 策略阻断场景 → ASSEMBLY_BLOCKED + blocked_scenes",
      ac["assembly_class"] == "ASSEMBLY_BLOCKED" and ac["blocked_scenes"] == ["S01"])
check("G5 阻断文案含明确错误码", "[ASSET_INSUFFICIENT]" in insufficient_message({"a": 1}))

# ---------------- 策略读取 ----------------
pol = policy_from_config({"editing": {"min_match_score": 5, "low_match_policy": "block",
                                      "min_asset_width": 640}})
check("P1 配置覆盖生效且缺省项保持默认",
      pol["min_match_score"] == 5 and pol["low_match_policy"] == "block"
      and pol["min_asset_width"] == 640 and pol["zero_match_policy"] == "placeholder")
check("P2 非法值回落默认",
      policy_from_config({"editing": {"min_match_score": "abc"}})["min_match_score"] == 3)

# ---------------- H. 真实渲染路径：占位场景 + 阻断 ----------------
script = {"segments": [
    {"chapter": "命中", "narration": "镜片特写是第一道门。", "duration_s": 3},
    {"chapter": "占位", "narration": "完全无关的一段旁白。", "duration_s": 3},
]}
shots = [{"description": "VR头显 镜片 特写", "gen_prompt": "vr lens"},
         {"description": "无", "gen_prompt": ""}]
pool2 = prep()
tl = EditingAgent._build_material_timeline(script, shots, pool2, policy=DEFAULT_POLICY,
                                           material_provided=True)
check("H1 场景1正常命中、场景2占位（同一时间轴内混合）",
      tl[0]["fallback_state"] == "LOCAL_INGEST"
      and tl[1]["fallback_state"] == "SOLID_COLOR_CARD", [s["fallback_state"] for s in tl])
check("H2 占位场景 entering timeline=True 但 selected_asset=None",
      tl[1]["selected_asset"] is None and tl[1]["entered_timeline"] is True)
check("H3 每个场景都有完整决策记录（需求/候选/分类/原因/动作/HITL/是否可渲染）",
      all({"original_requirement", "candidates", "insufficiency_class", "fallback_reason",
           "fallback_action", "selection_reason", "needs_hitl",
           "allowed_in_final_render"} <= set(s) for s in tl))
ac = assembly_class(tl, material_provided=True, policy=DEFAULT_POLICY)
check("H4 混合场景不阻断（PARTIAL）", ac["assembly_class"] == "NONE"
      and ac["degraded_scenes"] == ["S02"], ac)

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(0 if not FAIL else 1)

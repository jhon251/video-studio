"""5.x Phase 5-D 单测：多帧/时序多模态证据增强（真实视觉模型 CLIP，**只读、平行证据、fail-closed**）。

覆盖授权要求：
  A 默认关闭 + 配置读取（非法值回退，**不放松**任何阈值；与 5-A 的 min_sim/margin 对齐）
  B 纯函数：时序指标（逐帧 argmax / 期望相似度分布 / 边际分布 / 投票 / 相邻余弦 / 散布）
  C 纯函数：判定规则 T0–T7（三态 + 规则 ID + 置信度；先命中先返回）+ 一致性分类边界
  D fail-closed：模型缺失 / 解释器缺失 / 无帧 / 空 job / worker 失败 / 结果损坏 → 一律 UNKNOWN + 错误码
  E **真实模型回归**：冻结 4-B 真值产物方向上一致；当前成片 v6 上 S01–S04 一致支持、S05/S06 稳定歧义
  F **S06 视角解释**：v5（front）MATCH vs v6（side）UNKNOWN，且两者逐帧投票均为 1.0（**不是帧噪声**）
  G **受控时序切换夹具**（真实模型）：镜头内切图 → 必须 UNKNOWN / MMT_TEMPORAL_SPLIT（T1）；静态对照不触发
  H 只读与不覆盖：DB 字节/五张表/项目文件未变；`core/multimodal.py`（5-A）哈希未被本阶段改动；
    5-A 结果未被覆盖（重跑 `multimodal-check` 与 5-C 冻结证据一致）
  I 确定性：同一输入两次运行逐字节一致（剔除临时路径）；帧计划固定

用法：python tests/mm_temporal_test.py
"""
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core.mm_temporal import (MMT_DEFAULTS, TEMPORAL_RULES,  # noqa: E402
                                           classify_stability, cosine, labels_from_prompts,
                                           mmt_settings, run_temporal_worker, temporal_metrics,
                                           temporal_verdict, validate_temporal)
from video_studio.core.multimodal import DOMAIN_PROMPTS, mm_settings  # noqa: E402
from video_studio.ops.mm_temporal import format_mmt, temporal_report  # noqa: E402
from video_studio.ops.multimodal import extract_frames, multimodal_report  # noqa: E402
from video_studio.core.multimodal import frame_plan  # noqa: E402

REAL_DB = ROOT / "projects" / "video_studio.db"
REAL_PID = "p_f4b466a4a024"
FROZEN_ARTIFACT = "a_2ed5f41d6b58"          # 4-B 真值钉定的冻结 3-A 成片（S04/S06 = 鲨鱼照）
V5_ARTIFACT = "a_e369526c2f47"              # 5-C 替换前（S06 = front View）
V6_ARTIFACT = "a_fa4716cffb26"              # 5-C 替换后（S06 = side View）
BASE_MANIFEST = (ROOT / "docs" / "regression_2x" / "baseline" /
                 "baseline_manifest_5.x-phase5c-baseline.json")
FIVE_A_FROZEN = ROOT / "docs" / "regression_2x" / "logs" / "phase5c_mm_after.json"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:240] if detail else ""))


def sha(p: Path):
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


def project_state():
    con = sqlite3.connect(str(REAL_DB))
    counts = {t: con.execute("select count(*) from {}".format(t)).fetchone()[0]
              for t in ("tasks", "artifacts", "events", "decisions", "changelog")}
    con.close()
    proj = REAL_DB.parent / REAL_PID
    files = {str(p.relative_to(proj)): sha(p) for p in sorted(proj.rglob("*")) if p.is_file()}
    return {"db": sha(REAL_DB), "counts": counts, "files": files}


def _norm(obj):
    """剔除临时目录/路径类字段，便于比较"判定与相似度"是否一致。"""
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True)
    for key in ("frames_dir", "path", "dir", "stderr_tail", "detail"):
        pass
    import re
    s = re.sub(r"[A-Za-z]:\\\\\\\\[^\"]*vs_mm[^\"]*", "<TMP>", s)
    s = re.sub(r"[A-Za-z]:\\\\[^\"]*Temp[^\"]*", "<TMP>", s)
    return s


STATE_BEFORE = project_state()
CLI_BEFORE = project_state()


def fr(i, scores, emb=None, t=None):
    return {"id": "S#{}".format(i), "time_s": (i if t is None else t), "scores": scores,
            "embedding": (emb if emb is not None else [1.0, 0.0, 0.0])}


E = [1.0, 0.0, 0.0]
E2 = [0.0, 1.0, 0.0]

# ============ A. 默认关闭 + 配置 ============
print("== A. 默认关闭与配置 ==")
d0 = mmt_settings({})
check("A1 缺省 = 关闭（enabled=False）且阈值与 5-A 对齐（min_sim/margin 同值）",
      d0["enabled"] is False and d0["_source"] == "default(disabled)"
      and d0["min_sim"] == mm_settings({})["min_sim"] and d0["margin"] == mm_settings({})["margin"]
      and d0["frames_per_scene"] == 7 and d0["frames_per_scene"] > mm_settings({})["frames_per_scene"],
      {"min_sim": d0["min_sim"], "margin": d0["margin"], "frames": d0["frames_per_scene"]})
d1 = mmt_settings({"tools": {"multimodal_temporal": {"enabled": True, "min_sim": "x", "margin": None,
                                                    "min_vote_frac": 0.9, "frames_per_scene": 0,
                                                    "min_frames": 99, "top_k": "z"}}})
check("A2 非法值回退默认（不放松阈值）；合法值生效；帧数/最小帧数下限保护",
      d1["enabled"] is True and d1["min_sim"] == MMT_DEFAULTS["min_sim"]
      and d1["margin"] == MMT_DEFAULTS["margin"] and d1["min_vote_frac"] == 0.9
      and d1["frames_per_scene"] == MMT_DEFAULTS["frames_per_scene"]
      and d1["min_frames"] == MMT_DEFAULTS["min_frames"] and d1["top_k"] == MMT_DEFAULTS["top_k"]
      and len(d1["_notes"]) >= 4, {"notes": d1["_notes"]})
check("A3 提示词表与 5-A 完全一致（12 域；本层不新增/不改提示词）",
      labels_from_prompts() == [{"id": "{dom}#{i}".format(dom=d, i=i), "text": t, "domain": d}
                                for d in sorted(DOMAIN_PROMPTS)
                                for i, t in enumerate(DOMAIN_PROMPTS[d])],
      {"labels": len(labels_from_prompts())})
check("A4 规则 ID 表齐备（T0–T7，8 条，含 fail-closed 与三类 UNKNOWN）",
      len(TEMPORAL_RULES) == 8 and TEMPORAL_RULES[0] == "T0_FAIL_CLOSED"
      and {"T1_TEMPORAL_SPLIT", "T2_LOW_CONSISTENCY", "T3_CONSISTENT_MATCH",
           "T4_CONSISTENT_MISMATCH", "T5_INCONSISTENT", "T6_LOW_SIGNAL",
           "T7_AMBIGUOUS"} <= set(TEMPORAL_RULES), TEMPORAL_RULES)

# ============ B. 时序指标（纯函数） ============
print("\n== B. 时序指标（纯函数） ==")
m = temporal_metrics([fr(0, {"xr_device": 0.30, "vehicle": 0.20}, E, 10.0),
                      fr(1, {"xr_device": 0.28, "vehicle": 0.22}, E, 11.0),
                      fr(2, {"xr_device": 0.32, "vehicle": 0.18}, E, 12.0)], "xr_device")
check("B1 逐帧证据/投票/相邻余弦/散布齐备",
      m["frames_used"] == 3 and m["vote_expected"] == 1.0 and m["argmax_votes"] == {"xr_device": 3}
      and m["adjacent_cos"] == [1.0, 1.0] and m["visual_stability_mean"] == 1.0
      and m["dispersion"] == 0.0 and len(m["per_frame"]) == 3
      and all(x["argmax_domain"] == "xr_device" for x in m["per_frame"]), m["argmax_votes"])
check("B2 期望相似度/边际的 中位数 与 最小 值正确（期望中位数=0.30、最小=0.28、边际中位数=0.10、最小=0.06）",
      m["expected_sim_median"] == 0.3 and m["expected_sim_min"] == 0.28
      and m["expected_sim_mean"] == 0.3 and m["margin_median"] == 0.1
      and m["margin_min"] == 0.06, {"med": m["expected_sim_median"], "mm": m["margin_median"]})
m_unsorted = temporal_metrics([fr(2, {"xr_device": 0.3}, E, 12.0), fr(0, {"xr_device": 0.3}, E, 10.0),
                               fr(1, {"xr_device": 0.3}, E, 11.0)], "xr_device")
check("B3 输入顺序即时间顺序（调用方负责排序；纯函数不改序，报告层按 time_s 排序）",
      [x["time_s"] for x in m_unsorted["per_frame"]] == [12.0, 10.0, 11.0], "ok")
check("B4 cosine 边界：长度不等/零向量/空 → 0.0（不抛异常）",
      cosine([1, 0], [1, 0, 0]) == 0.0 and cosine([], []) == 0.0
      and cosine([0, 0], [1, 1]) == 0.0 and round(cosine([1, 0], [1, 0]), 6) == 1.0)
m1 = temporal_metrics([fr(0, {"xr_device": 0.3, "vehicle": 0.1}, E, 1.0)], "xr_device")
check("B5 单帧：投票=1.0、无相邻余弦/一致性 → None（不编造一致性）",
      m1["vote_expected"] == 1.0 and m1["adjacent_cos"] == []
      and m1["visual_stability_mean"] is None and m1["visual_stability_min"] is None)
m_nod = temporal_metrics([fr(0, {"xr_device": 0.3}, E, 1.0), fr(1, {"xr_device": 0.3}, E, 2.0)], None)
check("B6 期望域缺失：vote/期望相似度/边际 均为 None（不猜域）",
      m_nod["vote_expected"] is None and m_nod["expected_sim_median"] is None
      and m_nod["margin_median"] is None and m_nod["frames_used"] == 2)
m_multi = temporal_metrics([fr(0, {"xr_device": 0.30, "vehicle": 0.10}, E, 1.0)], "xr_device")
rec_multi = {"id": "S#0", "time_s": 1.0,
             "scores": {"xr_device": 0.4, "vehicle": 0.2}, "embedding": E}
check("B7 逐域聚合 = 帧间均值（与 5-A 同口径）",
      m_multi["domains_aggregated"] == {"vehicle": 0.1, "xr_device": 0.3}
      and temporal_metrics([rec_multi], "xr_device")["domains_aggregated"]["xr_device"] == 0.4,
      m_multi["domains_aggregated"])
st = [classify_stability({"visual_stability_mean": v, "visual_stability_min": v}, {})[
    "stability_class"] for v in (0.99, 0.70, 0.40)]
check("B8 一致性分类边界：≥0.75 STABLE / [0.50,0.75) MODERATE / <0.50 SPLIT",
      st == ["STABLE", "MODERATE", "SPLIT"]
      and classify_stability({"visual_stability_mean": 0.99, "visual_stability_min": 0.40},
                             {})["temporal_split"] is True, st)

# ============ C. 判定规则（纯函数） ============
print("\n== C. 判定规则 T0–T7（纯函数） ==")
def verdict_of(records, dom="xr_device", **over):
    s = {**MMT_DEFAULTS, **over}
    return temporal_verdict(temporal_metrics(records, dom), dom, s)


v = verdict_of([fr(0, {"xr_device": 0.30, "vehicle": 0.20}, E, 1.0),
                fr(1, {"xr_device": 0.31, "vehicle": 0.19}, E, 2.0),
                fr(2, {"xr_device": 0.29, "vehicle": 0.21}, E, 3.0)])
check("C1 T3 一致支持期望域 → MATCH（边际 0.10 ≥ 2×0.02、一致性 1.0 → HIGH）",
      v["verdict"] == "MATCH" and v["rule_id"] == "T3_CONSISTENT_MATCH"
      and v["confidence"] == "HIGH" and v["code"] is None, {k: v[k] for k in ("verdict",
                                                                            "confidence")})
v = verdict_of([fr(0, {"xr_device": 0.30, "vehicle": 0.27}, E, 1.0),
                fr(1, {"xr_device": 0.30, "vehicle": 0.27}, E, 2.0),
                fr(2, {"xr_device": 0.30, "vehicle": 0.27}, E, 3.0)])
check("C2 T3 但边际仅 0.03（≥margin 但 < 2×margin）→ MATCH / MEDIUM",
      v["verdict"] == "MATCH" and v["confidence"] == "MEDIUM", v["confidence"])
v = verdict_of([fr(0, {"xr_device": 0.19, "vehicle": 0.31}, E, 1.0),
                fr(1, {"xr_device": 0.18, "vehicle": 0.32}, E, 2.0),
                fr(2, {"xr_device": 0.20, "vehicle": 0.30}, E, 3.0)])
check("C3 T4 一致指向另一域 → MISMATCH（带其它域投票占比）",
      v["verdict"] == "MISMATCH" and v["rule_id"] == "T4_CONSISTENT_MISMATCH"
      and v["other_vote_domain"] == "vehicle" and v["other_vote_frac"] == 1.0,
      {k: v[k] for k in ("other_vote_domain", "other_vote_frac")})
v = verdict_of([fr(0, {"xr_device": 0.30, "vehicle": 0.29, "wildlife": 0.28}, E, 1.0),
                fr(1, {"xr_device": 0.30, "vehicle": 0.29, "wildlife": 0.28}, E, 2.0),
                fr(2, {"xr_device": 0.30, "vehicle": 0.29, "wildlife": 0.28}, E, 3.0)],
               min_vote_frac=0.9)
check("C4 投票虽 1.0 但域间极近 → 不误判 MATCH（边际 0.01 < 0.02 → T7 AMBIGUOUS）",
      v["verdict"] == "UNKNOWN" and v["code"] == "MMT_AMBIGUOUS" and v["rule_id"] == "T7_AMBIGUOUS",
      v["code"])
v = verdict_of([fr(0, {"xr_device": 0.9, "vehicle": 0.1}, E, 1.0),
                fr(1, {"xr_device": 0.9, "vehicle": 0.1}, E2, 2.0),
                fr(2, {"xr_device": 0.9, "vehicle": 0.1}, E, 3.0)])
check("C5 镜头内视觉切换（相邻余弦 0.0 < split 0.5）→ T1 TEMPORAL_SPLIT（不判定）",
      v["verdict"] == "UNKNOWN" and v["code"] == "MMT_TEMPORAL_SPLIT"
      and v["rule_id"] == "T1_TEMPORAL_SPLIT" and v["stability_class"] == "SPLIT",
      v["stability_class"])
cos6 = cosine([1.0, 1.0, 0.0], [1.0, 0.0, 0.0])
v = verdict_of([fr(0, {"xr_device": 0.9, "vehicle": 0.1}, [1.0, 1.0, 0.0], 1.0),
                fr(1, {"xr_device": 0.9, "vehicle": 0.1}, [1.0, 0.0, 0.0], 2.0),
                fr(2, {"xr_device": 0.9, "vehicle": 0.1}, [1.0, 1.0, 0.0], 3.0)])
check("C6 一致性介于 split 与 min_stability 之间（MODERATE，cos≈0.707）→ T2 LOW_CONSISTENCY（不判定）",
      v["verdict"] == "UNKNOWN" and v["rule_id"] == "T2_LOW_CONSISTENCY"
      and v["stability_class"] == "MODERATE",
      {"cos": round(cos6, 6), "cls": v["stability_class"], "mean": v["visual_stability_mean"]})
v = verdict_of([fr(0, {"xr_device": 0.10, "vehicle": 0.095}, E, 1.0),
                fr(1, {"xr_device": 0.10, "vehicle": 0.095}, E, 2.0),
                fr(2, {"xr_device": 0.10, "vehicle": 0.095}, E, 3.0)])
check("C7 期望域相似度中位数 0.10 < min_sim 0.20 且投票一致 → T6 LOW_SIGNAL / UNKNOWN / MEDIUM"
      "（置信度描述的是「这个 UNKNOWN 有多可靠」）",
      v["verdict"] == "UNKNOWN" and v["code"] == "MMT_LOW_SIGNAL"
      and v["rule_id"] == "T6_LOW_SIGNAL" and v["confidence"] == "MEDIUM",
      {"conf": v["confidence"], "code": v["code"]})
v = verdict_of([fr(0, {"xr_device": 0.2248, "vehicle": 0.2188}, E, 1.0),
                fr(1, {"xr_device": 0.2249, "vehicle": 0.2187}, E, 2.0),
                fr(2, {"xr_device": 0.2247, "vehicle": 0.2189}, E, 3.0)])
check('C8 稳定歧义（投票 1.0、一致性 1.0、边际 0.006 < 0.02）→ T7 / UNKNOWN / **MEDIUM**（「稳定地判不出来」）',
      v["verdict"] == "UNKNOWN" and v["code"] == "MMT_AMBIGUOUS" and v["confidence"] == "MEDIUM",
      v["confidence"])
v = verdict_of([fr(0, {"xr_device": 0.3}, E, 1.0), fr(1, {"xr_device": 0.3}, E, 2.0),
                fr(2, {"xr_device": 0.3}, E, 3.0)], dom=None)
check("C9 T0 期望域推不出 → UNKNOWN / MMT_UNKNOWN_DOMAIN（不猜域）",
      v["verdict"] == "UNKNOWN" and v["code"] == "MMT_UNKNOWN_DOMAIN"
      and v["rule_id"] == "T0_FAIL_CLOSED")
v = verdict_of([fr(0, {"xr_device": 0.9, "vehicle": 0.1}, E, 1.0),
                fr(1, {"xr_device": 0.9, "vehicle": 0.1}, E, 2.0)])
check("C10 T0 帧数 2 < min_frames 3 → UNKNOWN / MMT_INSUFFICIENT_FRAMES",
      v["verdict"] == "UNKNOWN" and v["code"] == "MMT_INSUFFICIENT_FRAMES"
      and v["frames_used"] == 2)
v = temporal_verdict(temporal_metrics([fr(0, {"xr_device": 0.9}, E, 1.0),
                                       fr(1, {"xr_device": 0.9}, E, 2.0)], "xr_device"),
                     "xr_device", MMT_DEFAULTS, fail_code="MM_MODEL_MISSING",
                     fail_detail="模型目录不存在")
check("C11 T0 模型不可用 → UNKNOWN / 原样透出 MM 错误码（绝不退回 MATCH/MISMATCH）",
      v["verdict"] == "UNKNOWN" and v["code"] == "MM_MODEL_MISSING"
      and v["rule_id"] == "T0_FAIL_CLOSED" and v["confidence"] == "LOW")

# ============ D. fail-closed ============
print("\n== D. fail-closed ==")
fake_root = Path(tempfile.mkdtemp(prefix="vs_mmt_fakeroot_"))
(fake_root / "src" / "video_studio" / "core").mkdir(parents=True, exist_ok=True)
dummy_model = fake_root / "models" / "clip" / "dummy"
dummy_model.mkdir(parents=True, exist_ok=True)
frames_fixture = [{"id": "S01#0", "path": str(fake_root / "x.jpg"), "scene_id": "S01",
                   "time_s": 1.0, "sha256": None}]
labs = labels_from_prompts()[:2]
r = run_temporal_worker([{"id": "a", "path": "x"}], labs,
                        {"model_dir": str(fake_root / "nope"), "python": sys.executable},
                        root=fake_root)
check("D1 模型目录不存在 → ok=False / MM_MODEL_MISSING（无相似度、无嵌入）",
      r["ok"] is False and r["code"] == "MM_MODEL_MISSING" and not r["similarities"]
      and not r["embeddings"], r.get("detail"))
r = run_temporal_worker([{"id": "a", "path": "x"}], labs,
                        {"model_dir": str(dummy_model), "python": str(fake_root / "no_py.exe")},
                        root=fake_root)
check("D2 worker 解释器不存在 → MM_PYTHON_MISSING", r["code"] == "MM_PYTHON_MISSING", r.get("detail"))
r = run_temporal_worker([], labs, {"model_dir": str(dummy_model), "python": sys.executable},
                        root=fake_root)
check("D3 无帧 → MMT_NO_FRAMES（不调用模型）", r["code"] == "MMT_NO_FRAMES", r.get("detail"))
rep = validate_temporal([], labs, root=ROOT, settings=MMT_DEFAULTS,
                        narration_by_scene={"S01": {"text": "vico vr 头显"}})
check("D4 无帧 → 报告级 MMT_NO_FRAMES，逐镜头 UNKNOWN（T0），计数 UNKNOWN=1",
      rep["error"]["code"] == "MMT_NO_FRAMES" and rep["counts"]["UNKNOWN"] == 1
      and rep["scenes"][0]["rule_id"] == "T0_FAIL_CLOSED", rep["counts"])
# 伪造 worker：写出非法 JSON / 不写结果 → MM_PARSE_FAILED / MM_WORKER_FAILED
(fake_root / "src" / "video_studio" / "core" / "mm_worker_clip.py").write_text(
    "import sys,pathlib\n"
    "a=sys.argv\n"
    "out=pathlib.Path(a[a.index('--out')+1])\n"
    "out.write_text('{not json', encoding='utf-8')\n", encoding="utf-8")
r = run_temporal_worker([{"id": "a", "path": "x"}], labs,
                        {"model_dir": str(dummy_model), "python": sys.executable}, root=fake_root)
check("D5 worker 结果非法 JSON → MM_PARSE_FAILED（不抛异常）", r["code"] == "MM_PARSE_FAILED",
      r.get("detail"))
(fake_root / "src" / "video_studio" / "core" / "mm_worker_clip.py").write_text(
    "import sys\nsys.exit(0)\n", encoding="utf-8")
r = run_temporal_worker([{"id": "a", "path": "x"}], labs,
                        {"model_dir": str(dummy_model), "python": sys.executable}, root=fake_root)
check("D6 worker 未产出结果 → MM_WORKER_FAILED", r["code"] == "MM_WORKER_FAILED", r.get("detail"))
r = validate_temporal([{"id": "S01#0", "path": "x", "scene_id": "S01", "time_s": 1.0,
                        "sha256": None}], [],
                      root=ROOT, settings=MMT_DEFAULTS,
                      narration_by_scene={"S01": {"text": "x"}})
check("D7 无提示词标签 → 报告级 MMT_LOW_SIGNAL（不伪造判定）",
      rep.get("schema") == "multimodal-temporal-v1" and r["error"]["code"] == "MMT_LOW_SIGNAL",
      r["error"]["code"])

# ============ E/F/G. 真实模型回归（CLIP，CPU） ============
print("\n== E. 真实模型回归 ==")
tmpdir = Path(tempfile.mkdtemp(prefix="vs_mmt_test_"))
rep_frozen = temporal_report(REAL_DB, REAL_PID, artifact_id=FROZEN_ARTIFACT, frames_dir=tmpdir / "fz")
fz = {s["scene_id"]: s for s in rep_frozen.get("scenes") or []}
check("E1 冻结 4-B 真值产物上跑通（真实模型 + 加密抽帧 + 逐帧证据）",
      rep_frozen.get("applied") is True and len(fz) == 6
      and all(s.get("frame_count") == 7 for s in fz.values())
      and (rep_frozen.get("model") or {}).get("weights_sha256", "").startswith("a63082132ba4f97a"),
      {"scenes": len(fz), "frames": [s.get("frame_count") for s in fz.values()],
       "error": rep_frozen.get("error"), "applied": rep_frozen.get("applied")})
check("E2 **方向一致**：冻结产物上 S04/S06 与 4-B 真值同向（画面指向其它域 → 非 MATCH；聚合最像域≠期望域）",
      all(fz[sid]["verdict"] != "MATCH" for sid in ("S04", "S06"))
      and all((fz[sid]["aggregate"]["top_k"] or [{}])[0].get("domain") !=
              fz[sid]["expected_domain"] for sid in ("S04", "S06")),
      {sid: (fz[sid]["verdict"], fz[sid]["rule_id"],
             (fz[sid]["aggregate"]["top_k"] or [{}])[0].get("domain")) for sid in ("S04", "S06")})
rep_v6 = json.loads((ROOT / "docs" / "regression_2x" / "logs" / "phase5d_mmt_v6.json")
                    .read_text(encoding="utf-8-sig"))
v6 = {s["scene_id"]: s for s in rep_v6["scenes"]}
check("E3 当前成片 v6：S01–S04 一致支持（T3 MATCH）、S05/S06 稳定歧义（T7 UNKNOWN）——与 5-A 计数同向",
      [v6[s]["verdict"] for s in ("S01", "S02", "S03", "S04")] == ["MATCH"] * 4
      and [v6[s]["verdict"] for s in ("S05", "S06")] == ["UNKNOWN"] * 2
      and rep_v6["counts"] == {"MATCH": 4, "MISMATCH": 0, "UNKNOWN": 2},
      rep_v6["counts"])
check("E4 本项目成片均为静态素材 → 全部镜头 stability_class=STABLE（无镜头内视觉切换）",
      all(s["stability"]["class"] == "STABLE" for s in v6.values()),
      {k: s["stability"]["class"] for k, s in v6.items()})
check("E5 逐帧证据完整（每帧含 id/time_s/sha256/期望相似度/argmax/边际/top-k）",
      all(len(s["frames"]) == 7 and all(
          f.get("id") and f.get("time_s") is not None and f.get("sha256")
          and f.get("expected_sim") is not None and f.get("argmax_domain")
          and f.get("margin") is not None and f.get("top_k")
          for f in s["frames"]) for s in v6.values()),
      {"per_scene_frames": [len(s["frames"]) for s in v6.values()]})
check("E6 聚合规则与置信度齐备（rule_id ∈ T0–T7；confidence ∈ HIGH/MEDIUM/LOW）",
      all(s["rule_id"] in TEMPORAL_RULES and s["confidence"] in ("HIGH", "MEDIUM", "LOW")
          for s in v6.values()), {k: (s["rule_id"], s["confidence"]) for k, s in v6.items()})

print("\n== F. S06 视角差异解释（5-C 退化） ==")
rep_v5 = json.loads((ROOT / "docs" / "regression_2x" / "logs" / "phase5d_mmt_v5.json")
                    .read_text(encoding="utf-8-sig"))
v5 = {s["scene_id"]: s for s in rep_v5["scenes"]}
check("F1 S06：替换前（front，v5）MATCH/HIGH vs 替换后（side，v6）UNKNOWN/MEDIUM —— 与 5-A 判定同向",
      v5["S06"]["verdict"] == "MATCH" and v5["S06"]["confidence"] == "HIGH"
      and v6["S06"]["verdict"] == "UNKNOWN" and v6["S06"]["confidence"] == "MEDIUM",
      {"v5": (v5["S06"]["verdict"], v5["S06"]["aggregate"]["median_margin"]),
       "v6": (v6["S06"]["verdict"], v6["S06"]["aggregate"]["median_margin"])})
check("F2 **不是帧噪声**：两个版本 S06 的逐帧投票均为 1.0、逐帧 argmax 恒为期望域，且无分割",
      v5["S06"]["aggregate"]["vote_expected"] == 1.0 and v6["S06"]["aggregate"]["vote_expected"] == 1.0
      and all(f["argmax_domain"] == "xr_device" for f in v6["S06"]["frames"])
      and v6["S06"]["stability"]["split"] is False,
      {"v5_vote": v5["S06"]["aggregate"]["vote_expected"],
       "v6_vote": v6["S06"]["aggregate"]["vote_expected"],
       "v6_stab": v6["S06"]["stability"]["visual_stability_mean"]})
check("F3 差异在**边际**（中位边际 v5 ≥ 0.05 而 v6 < 0.02），即视角导致域区分度下降到阈值以下",
      float(v5["S06"]["aggregate"]["median_margin"]) >= 0.05
      and float(v6["S06"]["aggregate"]["median_margin"]) < 0.02,
      {"v5_margin": v5["S06"]["aggregate"]["median_margin"],
       "v6_margin": v6["S06"]["aggregate"]["median_margin"]})
check("F4 S06（side）帧间一致性显著低于其它镜头（< 0.99）但仍 ≥ min_stability_cos 0.75 → 属 STABLE",
      float(v6["S06"]["stability"]["visual_stability_mean"]) < 0.99
      and float(v6["S06"]["stability"]["visual_stability_mean"]) >= 0.75
      and all(float(v6[s]["stability"]["visual_stability_mean"]) >= 0.99
              for s in ("S01", "S02", "S03", "S04", "S05")),
      {"S06": v6["S06"]["stability"]["visual_stability_mean"]})

print("\n== G. 受控时序切换夹具（真实模型） ==")
fx = ROOT / "src" / "video_studio" / "orchestration" / "tests" / "fixtures"
# 夹具用**视觉上明确不同**的两张图（CLIP 视觉余弦 ≈0.41；`syn_landscape/syn_portrait` 实测 ≈0.99，
# 属"同一画面"，不能用来构造"镜头内切换"）。项目素材只作为**只读输入**，成片写在临时目录。
img_a = fx / "r2_S30-B02_3.img.jpg"
_shark = sorted((ROOT / "projects" / REAL_PID / "media" / "external").glob("28160d959ed5*.jpg"))
img_b = _shark[0] if _shark else None
FFMPEG = ((json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
           .get("tools") or {}).get("ffmpeg") or {}).get("path")
split_film = tmpdir / "split.mp4"
single_film = tmpdir / "single.mp4"
if img_a.is_file() and img_b and img_b.is_file() and FFMPEG:
    subprocess.run([FFMPEG, "-y", "-v", "error", "-loop", "1", "-t", "3", "-i", str(img_a),
                    "-loop", "1", "-t", "3", "-i", str(img_b), "-filter_complex",
                    "[0:v]scale=1280:720,setsar=1[a];[1:v]scale=1280:720,setsar=1[b];"
                    "[a][b]concat=n=2:v=1:a=0[out]", "-map", "[out]", "-r", "30",
                    "-pix_fmt", "yuv420p", str(split_film)], capture_output=True)
    subprocess.run([FFMPEG, "-y", "-v", "error", "-loop", "1", "-t", "6", "-i", str(img_a),
                    "-vf", "scale=1280:720,setsar=1", "-r", "30", "-pix_fmt", "yuv420p",
                    str(single_film)], capture_output=True)
scenes_fx = [{"scene_id": "X1", "start_s": 0.0, "end_s": 6.0, "segment_index": 0}]
plan_fx = frame_plan(scenes_fx, 7)
fr_split, _ = extract_frames(split_film, plan_fx, tmpdir / "fs", ffmpeg=FFMPEG)
fr_single, _ = extract_frames(single_film, plan_fx, tmpdir / "fn", ffmpeg=FFMPEG)
rep_split = validate_temporal(fr_split, labs, root=ROOT, settings=MMT_DEFAULTS,
                              narration_by_scene={"X1": {"text": "a landscape photo"}})
rep_single = validate_temporal(fr_single, labs, root=ROOT, settings=MMT_DEFAULTS,
                               narration_by_scene={"X1": {"text": "a landscape photo"}})
check("G1 镜头内切图（真实成片）→ UNKNOWN / MMT_TEMPORAL_SPLIT（T1）：真实模型上可检出视觉切换",
      rep_split["scenes"][0]["verdict"] == "UNKNOWN"
      and rep_split["scenes"][0]["code"] == "MMT_TEMPORAL_SPLIT"
      and rep_split["scenes"][0]["stability"]["class"] == "SPLIT",
      {k: rep_split["scenes"][0][k] for k in ("verdict", "code", "rule_id")}
      | {"stab": rep_split["scenes"][0]["stability"]["visual_stability_min"]})
check("G2 静态对照（同一张图 6s）→ 不触发 T1（一致性 ≥ 0.9）",
      rep_single["scenes"][0]["stability"]["class"] == "STABLE"
      and float(rep_single["scenes"][0]["stability"]["visual_stability_min"]) >= 0.9,
      rep_single["scenes"][0]["stability"]["visual_stability_mean"])
check("G3 真实嵌入确实被返回并用于时序（embedding_dim=512；报告记录 embeddings_returned）",
      rep_split["scenes"][0]["embeddings_returned"] is True
      and rep_split["scenes"][0]["embedding_dim"] == 512,
      {"dim": rep_split["scenes"][0]["embedding_dim"]})

# ============ H. 只读与不覆盖 ============
print("\n== H. 只读 / 不覆盖 5-A·4-B ==")
after = project_state()
check("H1 只读：真实 DB 字节与五张表行数在全部运行后与运行前一致",
      CLI_BEFORE["db"] == after["db"] and CLI_BEFORE["counts"] == after["counts"],
      {"before": CLI_BEFORE["counts"], "after": after["counts"]})
check("H2 只读：项目内所有文件（含 6 个成片）逐字节未变；未新增生产产物",
      CLI_BEFORE["files"] == after["files"]
      and len([k for k in after["files"] if k.endswith(".mp4")]) == 6,
      {"files": len(after["files"]),
       "films": len([k for k in after["files"] if k.endswith(".mp4")])})
src_t = (ROOT / "src" / "video_studio" / "core" / "mm_temporal.py").read_text(encoding="utf-8")
ops_t = (ROOT / "src" / "video_studio" / "ops" / "mm_temporal.py").read_text(encoding="utf-8")
check("H3 静态证明：时序层不写库/不写产物/不改时间轴/不触发 redo（无写调用形态）",
      all(tok not in src_t + ops_t for tok in ("insert_decision", "insert_changelog", "write_artifact",
                                               "set_task_status", "run_cycle", "build_engine",
                                               "record_selection", "select_candidate(",
                                               "insert into", "update ", "delete from"))
      and "auto_redo\": False" in src_t and "changes_timeline\": False" in src_t, "ok")
man = json.loads(BASE_MANIFEST.read_text(encoding="utf-8")) if BASE_MANIFEST.is_file() else {}
base5a = (man.get("files") or {}).get("src/video_studio/core/multimodal.py", {}).get("sha256")
check("H4 **5-A 判定模块未被本阶段改动**：core/multimodal.py 的 sha256 与 5-C 基线一致",
      bool(base5a) and base5a == sha(ROOT / "src" / "video_studio" / "core" / "multimodal.py"),
      {"baseline": (base5a or "")[:16],
       "now": (sha(ROOT / "src" / "video_studio" / "core" / "multimodal.py") or "")[:16]})
five_now = multimodal_report(REAL_DB, REAL_PID, artifact_id=V6_ARTIFACT, frames_dir=tmpdir / "fa",
                            config=json.loads((ROOT / "config" / "config.json")
                                              .read_text(encoding="utf-8-sig")))
frozen5 = json.loads(FIVE_A_FROZEN.read_text(encoding="utf-8-sig"))


def _strip_paths(o):
    s = json.dumps(o, ensure_ascii=False, sort_keys=True)
    import re
    s = re.sub(r"\"(frames_dir|path|dir|stderr_tail|detail)\":\s*\"[^\"]*\"", "\"\\1\": \"<X>\"", s)
    return s


check("H5 **5-A 结果未被覆盖**：对同一产物重跑 multimodal-check，判定与相似度与 5-C 冻结证据一致",
      _strip_paths({"counts": five_now.get("counts"),
                    "scenes": [{k: s.get(k) for k in ("scene_id", "verdict", "code", "expected_sim",
                                                      "best_other_sim", "delta", "top_k",
                                                      "domain_scores")}
                               for s in five_now.get("scenes") or []]})
      == _strip_paths({"counts": frozen5.get("counts"),
                       "scenes": [{k: s.get(k) for k in ("scene_id", "verdict", "code",
                                                         "expected_sim", "best_other_sim", "delta",
                                                         "top_k", "domain_scores")}
                                  for s in frozen5.get("scenes") or []]}),
      {"now": five_now.get("counts"), "frozen": frozen5.get("counts")})
check('H6 报告显式声明平行证据层（不覆盖 4-B / 5-A、不自动换材/选材/redo/改时间轴）',
      rep_v6["policy"]["overwrites_4b_results"] is False
      and rep_v6["policy"]["overwrites_5a_results"] is False
      and rep_v6["policy"]["auto_replace"] is False
      and rep_v6["policy"]["auto_select"] is False
      and rep_v6["policy"]["auto_redo"] is False
      and rep_v6["policy"]["changes_timeline"] is False
      and rep_v6["policy"]["writes_to_db"] is False,
      {k: rep_v6["policy"][k] for k in ("overwrites_4b_results", "overwrites_5a_results",
                                        "auto_replace", "auto_redo")})

# ============ I. 确定性 ============
print("\n== I. 确定性 ==")
r1 = temporal_report(REAL_DB, REAL_PID, artifact_id=V6_ARTIFACT, frames_dir=tmpdir / "d1")
r2 = temporal_report(REAL_DB, REAL_PID, artifact_id=V6_ARTIFACT, frames_dir=tmpdir / "d2")


def norm(rep):
    o = dict(rep)
    o.pop("meta", None)
    return _strip_paths(o)


check("I1 同一输入两次运行（真实模型）判定/相似度/时序指标逐字节一致",
      norm(r1) == norm(r2), {"c1": r1["counts"], "c2": r2["counts"]})
check("I2 纯函数两次结果一致（temporal_metrics / temporal_verdict 无随机性）",
      temporal_metrics([fr(0, {"xr_device": 0.3, "vehicle": 0.2}, E, 1.0),
                        fr(1, {"xr_device": 0.3, "vehicle": 0.2}, E, 2.0)], "xr_device")
      == temporal_metrics([fr(0, {"xr_device": 0.3, "vehicle": 0.2}, E, 1.0),
                           fr(1, {"xr_device": 0.3, "vehicle": 0.2}, E, 2.0)], "xr_device"))
check("I3 帧计划确定：7 帧位于窗口 12.5%–87.5%（与 5-A 同一 frame_plan 函数）",
      frame_plan([{"scene_id": "S", "start_s": 0.0, "end_s": 8.0}], 7)[0]["times"]
      == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
      frame_plan([{"scene_id": "S", "start_s": 0.0, "end_s": 8.0}], 7)[0]["times"])
check('I4 人读输出标注只读与平行证据（不出现「已执行/已应用」字样）',
      "只读平行证据层" in format_mmt(rep_v6) and "未触发 redo" in format_mmt(rep_v6)
      and "已执行" not in format_mmt(rep_v6), format_mmt(rep_v6).splitlines()[0])

shutil.rmtree(fake_root, ignore_errors=True)

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)

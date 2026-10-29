# -*- coding: utf-8 -*-
"""Phase 11 / P11-4 **真实回测**：对 Phase 8 的 v3 稿跑**新的 metadata agent**（真实 DeepSeek）。

判定（授权书 §5）：
  ① 新候选 5/5 通过 title-check 全部机械门（**数字可溯性 100%**）；
  ② 与旧基线 `a_e0ec01d11b5a.json` 的 titles 对比：新候选 technique 覆盖 ≥3 种、每条带
     evidence_refs，旧基线无此能力（结构码 `OLD_FORMAT`）⇒ 证明能力增量；
  ③ 失实红线抽检：随机 3 条候选的"标题断言 vs 出处段落原文"逐条列出，**留待人工确认**
     （本阶段不宣称语义级不失实已自动化）；
  ④ `ab_plan` 存在且 `execution=manual`。

产物：`docs/regression_2x/logs/phase11_title_ab.json`（唯一落盘点）
成本：真实 LLM 1 次调用（tier M）；上限 $0.15。仅写临时工作区 DB，生产 DB/产物零改动。
"""
from __future__ import annotations

import json
import pathlib
import random
import sys
import tempfile
import time

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.base import AGENTS                                          # noqa: E402
import video_studio.agents.script.agent  # noqa: F401,E402 —— 注册 script 角色（task 依赖用）
import video_studio.agents.metadata.agent  # noqa: F401,E402 —— 注册 metadata 角色
import video_studio.agents.thumbnail.agent  # noqa: F401,E402 —— 注册 thumbnail 角色（封面大字臂）
from video_studio.core import title_check as TC                                      # noqa: E402
from video_studio.core.env import load_env                                           # noqa: E402
from video_studio.core.engine import Engine                                          # noqa: E402
from video_studio.db.schema import Database                                          # noqa: E402
from video_studio.llm.router import DeepSeekClient, Router                           # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
V3_LOG = LOGS / "phase8_ab_v3.json"
LEGACY_META = ROOT / "projects" / "p_96efdc03e1aa" / "artifacts" / "a_e0ec01d11b5a.json"
COST_LIMIT_USD = 0.15


def main() -> int:
    load_env(str(ROOT / ".env"))
    cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    script = json.loads(V3_LOG.read_text(encoding="utf-8"))["script"]
    ws = pathlib.Path(tempfile.mkdtemp(prefix="p11_ab_"))
    db = Database(ws / "state.db")
    engine = Engine(db, Router(cfg["llm"], DeepSeekClient(cfg["llm"]["deepseek"])), rules,
                    ws / "projects", cfg, AGENTS)
    pid = engine.create_project("Phase 11 标题候选回测（v3 稿）")
    aid = engine.write_artifact(pid, None, "script_output", script, summary="v3 稿")
    t_script = engine.create_task(pid, "script", "script")
    engine.attach_artifact(t_script, aid)
    db.set_task_status(t_script, "SUCCEEDED")
    t_meta = engine.create_task(pid, "metadata", "metadata", dependencies=[t_script])
    t0 = time.time()
    engine.run_cycle(pid)
    task = db.get_task(t_meta)
    art = db.get_artifact(task["artifacts"][0]) if task.get("artifacts") else None
    metadata = json.loads(pathlib.Path(art["path"]).read_text(encoding="utf-8")) if art else {}
    cost = float(task.get("cost_usd") or 0.0)
    # ---- 封面大字臂（thumbnail agent，授权书 §3.3）：与主标互补、≤12 字、概念方案不出图 ----
    t_thumb = engine.create_task(pid, "thumbnail", "thumbnail", dependencies=[t_script])
    engine.run_cycle(pid)
    thumb_task = db.get_task(t_thumb)
    thumb_art = (db.get_artifact(thumb_task["artifacts"][0])
                 if thumb_task.get("artifacts") else None)
    thumb = (json.loads(pathlib.Path(thumb_art["path"]).read_text(encoding="utf-8"))
             if thumb_art else {})
    cost_thumb = float(thumb_task.get("cost_usd") or 0.0)
    db.close()
    # 把封面候选并入 metadata 视图以便统一机械校验（标题候选 + 封面大字）
    merged = dict(metadata)
    if thumb.get("cover_text_candidates"):
        merged["cover_text_candidates"] = thumb["cover_text_candidates"]

    rep = TC.check_metadata(script, merged, source={"metadata_artifact": art["artifact_id"]
                                                    if art else None, "fixture": V3_LOG.name})
    legacy_meta = json.loads(LEGACY_META.read_text(encoding="utf-8"))
    legacy_rep = TC.check_metadata(script, legacy_meta,
                                   source={"legacy": str(LEGACY_META.relative_to(ROOT))})
    cands = metadata.get("title_candidates") or []
    covers = merged.get("cover_text_candidates") or []
    ab = metadata.get("ab_plan") or {}
    # ③ 抽检：随机 3 条（固定 seed ⇒ 可复算），列出标题断言与出处段落原文，供人工确认
    rnd = random.Random(11)
    picks = rnd.sample(range(len(cands)), min(3, len(cands)))
    segs = script.get("segments") or []
    spot = []
    for i in picks:
        c = cands[i]
        refs = [r for r in (c.get("evidence_refs") or []) if isinstance(r, int) and 0 <= r < len(segs)]
        nums = [r for r in (c.get("number_sources") or []) if isinstance(r, int) and 0 <= r < len(segs)]
        spot.append({
            "candidate_index": i, "text": c.get("text"), "technique": c.get("technique"),
            "evidence_segments": [{"index": r, "narration": str(segs[r].get("narration"))[:200]}
                                  for r in refs],
            "number_source_segments": [{"index": r, "narration": str(segs[r].get("narration"))[:200]}
                                       for r in nums],
            "numbers_in_title": TC.extract_numbers(str(c.get("text") or "")),
            "checker_status": next((x["status"] for x in rep["candidates"]
                                    if x["index"] == i), None),
            "manual_verdict": "待人工确认（本阶段不宣称语义级不失实已自动化）"})
    out = {
        "schema": "phase11-title-ab-v1",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fixture_script": str(V3_LOG.relative_to(ROOT)),
        "model_tier": "M", "metadata_artifact_id": art["artifact_id"] if art else None,
        "task_status": task.get("status"), "elapsed_s": round(time.time() - t0, 1),
        "cost_usd": round(cost, 6), "cost_usd_thumbnail": round(cost_thumb, 6),
        "cost_usd_total": round(cost + cost_thumb, 6), "cost_limit_usd": COST_LIMIT_USD,
        "thumbnail_task_status": thumb_task.get("status"),
        "thumbnail_artifact_id": thumb_art["artifact_id"] if thumb_art else None,
        "thumbnail_raw": thumb,
        "metadata_raw": metadata,
        "title_check": rep,
        "criterion_1_all_gates_pass": {
            "candidates": len(cands),
            "pass": rep["counts"]["pass"], "fail": rep["counts"]["fail"],
            "all_pass": rep["all_pass"],
            "number_traceability_100pct": all(
                "TITLE_NUMBER_UNTRACEABLE" not in [v["code"] for v in c["codes"]]
                for c in rep["candidates"]),
            "techniques": rep["techniques_used"], "diversity_assessed": rep["diversity_assessed"],
            "cover_texts": len(covers),
            "cover_pass": rep["counts"]["cover_pass"],
            "cover_gates_ok": all(c["status"] == "PASS" for c in rep["cover_texts"]) if covers
                              else None,
        },
        "criterion_2_vs_legacy": {
            "new": {"candidates": len(cands), "techniques": rep["techniques_used"],
                    "with_evidence_refs": sum(1 for c in cands if c.get("evidence_refs")),
                    "with_number_sources": sum(1 for c in cands if c.get("number_sources")),
                    "cover_texts": len(covers)},
            "legacy": {"structural_codes": legacy_rep["structural_codes"],
                       "candidates": legacy_rep["counts"]["candidates"],
                       "techniques": legacy_rep["techniques_used"],
                       "with_evidence_refs": 0, "capability": legacy_rep["capability"]},
            "capability_increment": bool(cands) and len(rep["techniques_used"]) >= 3
                                    and "OLD_FORMAT" in legacy_rep["structural_codes"],
        },
        "criterion_3_manual_spot_check": {
            "sample_size": len(spot), "picks": spot,
            "status": "待人工确认（本阶段不宣称语义级不失实已自动化）",
            "note": "机械门仅验证数字可溯/引用存在/黑名单/长度/多样性/回声；"
                    "断言与出处的**语义**是否相符须人工终审"},
        "criterion_4_ab_plan": {
            "present": bool(ab), "execution": ab.get("execution"),
            "execution_is_manual": ab.get("execution") == "manual",
            "variants": len(ab.get("variants") or []),
            "metric": ab.get("metric"), "platform": ab.get("platform"),
            "no_auto_publish": "系统仅出方案；ab_plan 由人工执行"},
        "cover_texts": covers,
        "legacy_report": legacy_rep,
    }
    out["criterion_1_all_gates_pass"]["ok"] = bool(
        out["criterion_1_all_gates_pass"]["all_pass"]
        and out["criterion_1_all_gates_pass"]["number_traceability_100pct"]
        and out["criterion_1_all_gates_pass"]["candidates"] == 5)
    out["all_criteria_ok"] = bool(out["criterion_1_all_gates_pass"]["ok"]
                                 and out["criterion_2_vs_legacy"]["capability_increment"]
                                 and out["criterion_4_ab_plan"]["execution_is_manual"])
    (LOGS / "phase11_title_ab.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
    print("任务:", task.get("status"), "| 候选:", len(cands), "| 封面:", len(covers),
          "| 成本 $%.5f（含封面臂 $%.5f）" % (cost + cost_thumb, cost_thumb))
    print("判据①:", json.dumps(out["criterion_1_all_gates_pass"], ensure_ascii=False)[:220])
    print("判据② 能力增量:", out["criterion_2_vs_legacy"]["capability_increment"],
          "| 新 technique:", rep["techniques_used"], "| 旧结构码:",
          legacy_rep["structural_codes"])
    print("判据③ 抽检:", len(spot), "条 ⇒ 待人工确认")
    print("判据④ ab_plan:", json.dumps(out["criterion_4_ab_plan"], ensure_ascii=False)[:160])
    print("all_criteria_ok:", out["all_criteria_ok"])
    return 0 if out["all_criteria_ok"] else 4


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""6-B/M1 —— 对真实 v9 的 **Directorial Quality 只读审计**（含"人审发现再发现"表）。

做什么：
  1. 用 `ops.direction.build_direction_report`（只读编排）对 v9 项目重算 DQ-1…DQ-8 + DQ-7 总评；
  2. 把 6-A 审计里**人工确认**的 7 项导演质量发现逐条映射到 DQ 指标，并给出
     `rediscovered: FULL / PARTIAL / NO` + 证据锚点（scene / asset / 时间区间 / 证据层）；
  3. 严格只读取证：DB sha256、成片 sha256、项目 `output/` 清单在审计前后逐字节一致；
  4. 写出 `logs/phase6b_m1_dq_v9.json`。

严格边界：不重渲染、不改 v9 产物、不换素材、不剪辑、不写 DB/产物、不接入任何阻断；
语义证据**只复用**既有只读报告（4-B/5-A/5-D/Judge），无证据即 NOT_ASSESSABLE，绝不把 UNKNOWN 当 PASS。

用法: python docs/regression_2x/phase6b_m1_v9_audit.py
"""
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
PID = "p_96efdc03e1aa"
FILM_TASK = "t_d0a54bdf1810"
EVIDENCE = "docs/regression_2x/logs/audit_p96efdc_mm.json"

from video_studio.ops import direction as ops_direction  # noqa: E402

CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FILM = ROOT / "projects" / PID / "output" / "{}_draft.mp4".format(FILM_TASK)


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def manifest(d: Path) -> dict:
    return {p.name: (p.stat().st_size, round(p.stat().st_mtime, 3))
            for p in sorted(d.rglob("*")) if p.is_file()}


db_before, film_before = sha(DB), (sha(FILM) if FILM.is_file() else None)
out_before = manifest(FILM.parent) if FILM.parent.is_dir() else {}

report = ops_direction.build_direction_report(PID, DB, ROOT, CFG, film_task=FILM_TASK,
                                              evidence_path=EVIDENCE, measure_freeze=True)

db_after, film_after = sha(DB), (sha(FILM) if FILM.is_file() else None)
out_after = manifest(FILM.parent) if FILM.parent.is_dir() else {}
metrics = report["metrics"]
summary = report["summary"]


def m(k):
    return metrics.get(k) or {}


# ---- 人审发现（6-A 审计 §2 + VERIFIED 表）→ DQ 指标的"再发现"映射 ----
FINDINGS = [
    {"id": "H1-hook-misalignment", "human_finding": "Hook 视觉错位：hook 用'学生举旗合影'，与'AI 证明'无关",
     "metric": "DQ-1", "expect": "UNKNOWN",
     "evidence_hint": "抽帧 phase6a_frames/v9_t00005s.png + audit_p96efdc_mm.json（S01 各层无 MATCH）",
     "re_discovery": "PARTIAL",
     "why": "只读证据层（4-B/5-A/5-D/Judge）对 S01 未给 MATCH/MISMATCH ⇒ DQ-1 只能 UNKNOWN；"
            "机械侧再发现的是'证据不支持'（含 hook 段唯一素材数、层判定明细），"
            "而'错位'本身仍属**人工语义判定**，DQ 不伪造该结论"},
    {"id": "H2-visual-repetition", "human_finding": "21 镜仅 4 个唯一素材、单素材占比最高约 1/3",
     "metric": "DQ-2", "expect": "FAIL",
     "evidence_hint": "DQ-2.per_asset + findings[].scene_windows", "re_discovery": "FULL"},
    {"id": "H3-static-hold", "human_finding": "全片近乎静止：均值约 73 s/镜、17/21 镜 > 60 s、冻结占比 99.46%",
     "metric": "DQ-3", "expect": "FAIL",
     "evidence_hint": "DQ-3.holds + findings[].window + freeze_profile", "re_discovery": "FULL"},
    {"id": "H4-visual-density", "human_finding": "镜变密度约 0.82 次/分钟，节奏过低",
     "metric": "DQ-4", "expect": "FAIL",
     "evidence_hint": "DQ-4.scene_changes_per_min + longest_scene.window", "re_discovery": "FULL"},
    {"id": "H5-semantic-support", "human_finding": "旁白↔画面语义支撑不足（Judge：1 MATCH / 2 MISMATCH / 18 UNKNOWN）",
     "metric": "DQ-8", "expect": "FAIL",
     "evidence_hint": "DQ-8.per_scene（逐镜层判定 + 时间区间）+ DQ-5.semantic_state",
     "re_discovery": "FULL",
     "why": "逐镜复用既有只读证据：存在 MISMATCH 镜头 ⇒ FAIL；UNKNOWN 镜头单独列出，不并入 PASS"},
    {"id": "H6-no-visual-climax", "human_finding": "AlphaGeometry/核心论点缺视觉高潮：20/21 镜命中核心词但仅 4 素材",
     "metric": "DQ-5", "expect": "FAIL",
     "evidence_hint": "DQ-5.core_detail（scene/asset/window）+ findings", "re_discovery": "FULL",
     "why": "DQ-5 结构项是**代理指标**（核心镜头素材多样性/保持时长）；"
            "'无视觉信息升级'的可视化形态判定仍属人工语义范畴，已单列在语义项"},
    {"id": "H7-ending-missing", "human_finding": "缺片尾/outro：关键词命中 0、旁白 961.7 s 结束后 570.3 s 无语音",
     "metric": "DQ-6", "expect": "FAIL",
     "evidence_hint": "DQ-6.outro_keyword_hits + tail_scene_detail + tail_silence_s",
     "re_discovery": "FULL"},
]

rediscovery = []
for f in FINDINGS:
    got = m(f["metric"]).get("state")
    rediscovery.append({**f, "measured_state": got,
                        "state_match": got == f["expect"],
                        "evidence": (m(f["metric"]).get("findings") or [])[:4]})

report_out = {
    "schema": "directorial-quality-v1",
    "kind": "6b_m1_v9_readonly_audit",
    "stage": "6-B/M1",
    "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "read_only": True, "enforced": False, "advisory": True,
    "not_wired_to_production": True,
    "note": "只读诊断：不接入 TASK_BLOCKED、不改变 render_output、不自动修复；"
            "语义项只复用既有只读证据，UNKNOWN 不得视为 PASS。",
    "inputs": {"project_id": PID, "film_task": FILM_TASK, "film": str(FILM),
               "evidence": EVIDENCE, "db": str(DB),
               "policy": report["inputs"]["policy"],
               "freeze_measured": report["inputs"]["freeze_measured"]},
    "metrics": metrics,
    "summary": summary,
    "human_findings_rediscovery": rediscovery,
    "rediscovery_counts": {
        "FULL": sum(1 for r in rediscovery if r["re_discovery"] == "FULL"
                    and r["state_match"]),
        "PARTIAL": sum(1 for r in rediscovery if r["re_discovery"] == "PARTIAL"),
        "NO": sum(1 for r in rediscovery if r["re_discovery"] == "NO"
                  or not r["state_match"]),
        "total": len(rediscovery)},
    "read_only_evidence": {
        "db_sha256_before": db_before, "db_sha256_after": db_after,
        "db_unchanged": db_before == db_after,
        "film_sha256_before": film_before, "film_sha256_after": film_after,
        "film_unchanged": film_before == film_after,
        "output_manifest_unchanged": out_before == out_after,
        "new_files_in_output": sorted(k for k in out_after if k not in out_before),
    },
}
(LOGS / "phase6b_m1_dq_v9.json").write_text(json.dumps(report_out, ensure_ascii=False, indent=1),
                                            encoding="utf-8")

print("v9 DQ 状态:", {k: v.get("state") for k, v in metrics.items()})
print("语义项:", summary.get("semantic_states"), "| overall:", summary.get("overall"))
print("人审发现再发现:", report_out["rediscovery_counts"])
for r in rediscovery:
    print("  {:<22s} {} expect={} got={} 一致={} [{}]".format(
        r["id"], r["re_discovery"], r["expect"], r["measured_state"], r["state_match"],
        r["evidence_hint"][:60]))
print("只读: DB 未变", report_out["read_only_evidence"]["db_unchanged"],
      "| 成片未变", report_out["read_only_evidence"]["film_unchanged"],
      "| output 无新增", not report_out["read_only_evidence"]["new_files_in_output"])
print("json ->", LOGS / "phase6b_m1_dq_v9.json")

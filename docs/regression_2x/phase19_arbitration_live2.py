# -*- coding: utf-8 -*-
"""P19-4 后置：用**生产核验函数**复现逐景核验（拿到完整 failed_scenes），再跑 P19-1 仲裁链。

`EditingAgent._verify_scene_frames` 是纯函数（不写 DB），可直接复用来取得
与渲染门**完全一致**的核验结果（含 full failed_scenes，不受任务错误字段 2000 字截断影响）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.env import load_env                                     # noqa: E402
load_env(R / ".env")
from video_studio.core import render_arbitration as ARB                         # noqa: E402
from video_studio.agents.editing.agent import EditingAgent                     # noqa: E402
from video_studio.core.materials import policy_from_config                     # noqa: E402
from video_studio.tools.base import ToolContext                                # noqa: E402

fix = json.loads((R / "output/phase19_p19_4_sandbox/fixture.json").read_text(encoding="utf-8"))
pid = fix["sandbox_project_id"]
proj = R / "projects" / pid
film = next((proj / "output").glob("*.mp4"))
cfg = json.loads((R / "config/config.json").read_text(encoding="utf-8"))

con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row
sel = {}
for r in con.execute("select payload from events where project_id=? and type='MATERIAL_TIMELINE'",
                     (pid,)):
    for d in json.loads(r["payload"]).get("decisions") or []:
        sel[d["scene_id"]] = d
con.close()

# 用脚本声明时长重建窗口（与 _build_material_timeline 同公式）
script = json.loads((R / "output/phase13e_script_sandbox/script_dcv2_derived_v1.json")
                    .read_text(encoding="utf-8"))
timeline, cursor = [], 0.0
for s in script["segments"]:
    sid = s["scene_id"]
    d0 = max(float(s["duration_s"]), 3.0)
    d = sel.get(sid) or {}
    timeline.append({"scene_id": sid, "start_s": round(cursor, 3),
                     "end_s": round(cursor + d0, 3),
                     "selected_asset": d.get("selected_asset") or {},
                     "fallback_state": d.get("fallback_state"),
                     "insufficiency_class": d.get("insufficiency_class")})
    cursor += d0
timeline[-1]["end_s"] = round(max(timeline[-1]["end_s"], cursor + 2.0), 3)

refs = []
for sid, d in sel.items():
    a = d.get("selected_asset") or {}
    if a.get("path"):
        refs.append({"asset_id": a.get("asset_id"), "path": a["path"], "usable": True})
ctx = ToolContext(role="editing", project_id=pid, project_dir=proj, db=None, config=cfg)
policy = policy_from_config(cfg)

class _Engine:
    def project_dir(self, p):
        return proj

ev, summary = EditingAgent._verify_scene_frames(_Engine(), ctx, film, timeline,
                                                refs_pool=refs, policy=policy)
print("复现核验: checked={} failed={} min_corr={}".format(
    len(summary.get("checked_scenes") or []), len(summary.get("failed_scenes") or []),
    summary.get("min_corr")))
for f in summary.get("failed_scenes") or []:
    print("  {} expected={} corr_expected={} corr_best={} t={}".format(
        f["scene_id"], f.get("expected"), f.get("corr_expected"), f.get("corr_best"),
        f.get("sample_t")))

verification = {"failed_scenes": summary.get("failed_scenes") or [],
                "method": summary.get("method"), "min_corr": summary.get("min_corr"),
                "checked_scenes": summary.get("checked_scenes") or []}
out, report = ARB.apply_arbitration(verification=verification,
                                    frame_dir=proj / "artifacts", timeline=timeline,
                                    engine=None, root=R, config=cfg)
print()
print("仲裁: 开关={} 调用={} 放行={} 阻断={} 成本=${:.4f}".format(
    report.get("enabled"), report.get("called"),
    len(report.get("arbitrated") or []), len(report.get("still_failed") or []),
    report.get("cost_usd") or 0.0))
for r in report.get("records") or []:
    v = r.get("vlm") or {}
    print("  {} corr={} -> {} | VLM={} | {}".format(
        r["scene_id"], r["orig_failure"].get("corr_expected"), r["final"],
        v.get("presence"), str(v.get("reason"))[:58]))
print()
print("最终 failed_scenes:", [f.get("scene_id") for f in out.get("failed_scenes") or []])

res = {
    "schema": "phase19-p19-4-arbitration-live-v2",
    "sandbox_project_id": pid,
    "film": str(film.relative_to(R)).replace("\\", "/"),
    "film_bytes": film.stat().st_size,
    "render_wall_clock_s": 115.1,
    "render_output_registered": False,
    "reproduced_with_production_verifier": True,
    "verification": {k: verification[k] for k in ("method", "min_corr")},
    "verification_failed_scenes": verification["failed_scenes"],
    "checked_scenes": verification["checked_scenes"],
    "arbitration_config": {k: v for k, v in ARB.resolve_config(cfg, root=R)[0].items()},
    "arbitration_report": {k: v for k, v in report.items() if k != "records"},
    "arbitration_records": report.get("records"),
    "failed_scenes_after_arbitration": out.get("failed_scenes"),
    "reselect": fix.get("reselect"),
    "note": ("核验用生产纯函数 `EditingAgent._verify_scene_frames` 复现；"
             "仲裁用 `core/render_arbitration.apply_arbitration`（与门内同一代码路径）。"),
    "vlm_budget_usd": 0.5,
}
p = L / "phase19_p19_4_arbitration_live.json"
p.write_text(json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("->", p.relative_to(R).as_posix())

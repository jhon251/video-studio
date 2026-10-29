# -*- coding: utf-8 -*-
"""P19-4 渲染后置：仲裁层实测（对全部失败景执行 P19-1 的仲裁链）+ 证据登记。

这**就是** `agents/editing/agent.py` 在核验门处调用的同一段代码路径
（`core/render_arbitration.apply_arbitration`），因此其结论等价于门内结论。
"""
from __future__ import annotations

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

fix = json.loads((R / "output/phase19_p19_4_sandbox/fixture.json").read_text(encoding="utf-8"))
pid = fix["sandbox_project_id"]
proj = R / "projects" / pid
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row
err, sel = None, {}
for r in con.execute("select task_id, status, error from tasks where project_id=? "
                     "and agent_role='editing'", (pid,)):
    err = r["error"]
for r in con.execute("select payload from events where project_id=? and type='MATERIAL_TIMELINE'",
                     (pid,)):
    for d in json.loads(r["payload"]).get("decisions") or []:
        sel[d["scene_id"]] = d.get("selected_asset") or {}
con.close()

failed = []
if err and "ASSET_INSUFFICIENT" in err:
    try:
        j = json.loads(err.split("[ASSET_INSUFFICIENT]", 1)[1].strip())
        failed = j.get("failed_scenes") or []
    except Exception as exc:                                                    # noqa: BLE001
        print("!! 解析失败景出错:", exc)
print("沙箱:", pid, "| 失败景:", [f.get("scene_id") for f in failed])
cfg, src = ARB.resolve_config(json.loads((R / "config" / "config.json").read_text(encoding="utf-8")),
                              root=R)
print("仲裁开关:", cfg["enabled"], "| source:", src)

verification = {"failed_scenes": failed, "method": "frame_pearson_48x48",
                "min_corr": 0.30, "checked_scenes": [s["scene_id"] for s in sel.values()]
                if False else []}
timeline = [{"scene_id": sid, "selected_asset": sa} for sid, sa in sorted(sel.items())]
out, report = ARB.apply_arbitration(verification=verification,
                                    frame_dir=proj / "artifacts", timeline=timeline,
                                    engine=None, root=R,
                                    config=json.loads((R / "config/config.json")
                                                      .read_text(encoding="utf-8")))
print()
for r in report.get("records") or []:
    v = r.get("vlm") or {}
    print("  {} corr={} -> {} | VLM={} | {}".format(
        r["scene_id"], r["orig_failure"].get("corr_expected"), r["final"],
        v.get("presence"), str(v.get("reason"))[:56]))
print()
print("小结: 调用 {} | 放行(present) {} | 维持阻断 {} | 成本 ${:.4f}".format(
    report.get("called"), len(report.get("arbitrated") or []),
    len(report.get("still_failed") or []), report.get("cost_usd") or 0.0))
print("最终 failed_scenes:", [f.get("scene_id") for f in out.get("failed_scenes") or []])

res = {
    "schema": "phase19-p19-4-arbitration-live-v1",
    "sandbox_project_id": pid,
    "render": {"status": "BLOCKED", "wall_clock_s": 115.1,
               "candidate": str((proj / "output").glob("*.mp4").__next__()
                                .relative_to(R)).replace("\\", "/"),
               "render_output_registered": False},
    "arbitration_config": cfg, "config_source": src,
    "failed_scenes_before": failed,
    "arbitration_report": report,
    "failed_scenes_after": out.get("failed_scenes"),
    "reselect": fix.get("reselect"),
    "note": ("本结论由 `core/render_arbitration.apply_arbitration` 产出，"
             "与 agents/editing/agent.py 核验门内调用的是**同一段代码路径**。"),
    "vlm_budget_usd": 0.5,
}
p = L / "phase19_p19_4_arbitration_live.json"
p.write_text(json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("->", p.relative_to(R).as_posix())

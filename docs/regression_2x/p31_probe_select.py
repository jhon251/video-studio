# -*- coding: utf-8 -*-
"""定论：直接调用**生产函数** `EditingAgent._build_material_timeline` 复现渲染将使用的素材绑定，
再用 `core.direction.asset_reuse` 复算 DQ-2。零副作用（不建项目、不写 DB、不渲染）。

对照三组输入：
  A) 裸池（本地路径池，无 _p30_binding）—— 复现 agent 的自动选材
  B) 池 + `_p30_binding`（P30 渲染实际输入）
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import narration as NAR                                # noqa: E402
from video_studio.core import direction as DIR                                # noqa: E402
from video_studio.agents.editing.agent import EditingAgent                    # noqa: E402
from video_studio.core.materials import policy_from_config                    # noqa: E402

SCRIPT = R / "output" / "phase27_script_sandbox" / "script_p27_v41_40seg.json"
VOICE = R / "output" / "phase20_voice_sandbox" / "voice_output_40seg_v21.json"
VISUAL = R / "projects/p_96efdc03e1aa/artifacts/a_a6279580600a.json"
POOL = L / "phase16_retrieval_payload.json"


def show(tag, tl):
    out = DIR.asset_reuse(tl)
    print("--- {} ---".format(tag))
    print("  景数={} unique={} max_share={} total_s={} state={}".format(
        len(tl), out["unique_assets"], out["max_asset_share"], out["total_s"], out["state"]))
    for k, v in sorted(out["per_asset"].items(), key=lambda kv: -kv[1]["share"])[:6]:
        print("    {:<26} scenes={:<3} secs={:<8.2f} share={:.4f}".format(
            str(k)[:26], v["scenes"], v["seconds"], v["share"]))
    nod = [s["scene_id"] for s in tl if not (s.get("selected_asset") or {}).get("asset_id")]
    print("  无素材景 {}: {}".format(len(nod), nod))
    return out


def main() -> int:
    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    voice = json.loads(VOICE.read_text(encoding="utf-8"))
    shots = json.loads(VISUAL.read_text(encoding="utf-8")).get("shots") or []
    plan = NAR.narration_plan(script, voice)
    wins = plan["segments"]
    segdurs = [w["actual_s"] for w in wins]

    pool_raw = json.loads(POOL.read_text(encoding="utf-8"))["candidates"]
    # 转成 _build_material_timeline 需要的池结构
    media = R / "projects/p_96efdc03e1aa/media"
    pool = []
    for c in pool_raw:
        rel = c.get("relative_path") or ""
        p = media / rel if rel else None
        pool.append({"asset_id": "asset_" + str(c["sha256"])[:12], "name": c.get("name") or "",
                     "sha256": c["sha256"], "path": str(p) if p else "",
                     "relative_path": rel, "bytes": c.get("bytes"),
                     "width": c.get("width"), "height": c.get("height"),
                     "license": c.get("license"), "match_score": c.get("match_score"),
                     "usable": True, "verified": True,
                     "provider": c.get("provider"), "source_id": c.get("source_id"),
                     "source_url": c.get("source_url"), "attribution": c.get("attribution"),
                     "license_cleared": c.get("license_cleared")})

    kw = dict(policy=policy_from_config(None), material_provided=True,
              excluded_pool=None, provider_requested=False, human_selections={},
              segment_durations=segdurs, pause_budget_s=plan["pause_budget_s"],
              trailing_pad_s=plan["trailing_pad_s"])
    tlA = EditingAgent._build_material_timeline(script, shots, pool, **kw)
    a = show("A) 裸池自动选材（生产函数）", tlA)

    # B) 使用 P30 的 _p30_binding（人为固定绑定）
    retr = json.loads((R / "projects/p_8b48148d4bf3/artifacts/a_331e853a4bb9.json")
                      .read_text(encoding="utf-8"))
    bind = retr.get("_p30_binding") or {}
    by_sha = {c["sha256"]: c for c in pool}
    tlB = []
    for i, s in enumerate(tlA):
        sid = s["scene_id"]
        sha = bind.get(sid)
        s2 = dict(s)
        if sha and sha in by_sha:
            c = by_sha[sha]
            s2["selected_asset"] = {"asset_id": c["asset_id"], "sha256": sha,
                                    "name": c["name"], "path": c["path"],
                                    "relative_path": c["relative_path"]}
        tlB.append(s2)
    b = show("B) 强制 P30 _p30_binding", tlB)

    print()
    print("自动选材 == P30 绑定 ?  dominant(A)={:.4f} dominant(B)={:.4f}".format(
        a["max_asset_share"], b["max_asset_share"]))
    # 落盘
    (R / "output/p31_probe" / "selection_repro.json").write_text(json.dumps(
        {"schema": "p31-selection-repro-v1",
         "A_auto": {k: v for k, v in a.items() if k != "findings"},
         "B_p30binding": {k: v for k, v in b.items() if k != "findings"},
         "scene_ids": [s["scene_id"] for s in tlA]}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

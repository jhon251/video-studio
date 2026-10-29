# -*- coding: utf-8 -*-
"""Phase 42 / P42-1 验证：片级内容排除是否生效（候选域中 2442c39e 归零）。"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.agents.editing.agent import EditingAgent as EA                 # noqa: E402
from video_studio.core import materials as MAT                                   # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
BAN = "2442c39e8002"


def main() -> int:
    script = json.loads((R / "output/phase36_script_sandbox/script_p36_v65_36seg.json")
                        .read_text(encoding="utf-8"))
    pool = json.loads((L / "phase33_retrieval_payload.json").read_text(encoding="utf-8"))
    allc = [c for c in pool["candidates"] if c.get("path")]
    print("池（排除前）: {} 张".format(len(allc)))
    tl = EA._build_material_timeline(script, [], allc,
                                     policy=MAT.policy_from_config(None),
                                     material_provided=True)
    alloc = getattr(tl, "allocation", {}) or {}
    ce = alloc.get("content_exclusions") or {}
    print("排除开关: banned={} | evidence={} 条 | error={}".format(
        [b[:14] for b in (ce.get("banned") or [])], len(ce.get("evidence") or []),
        ce.get("error")))
    print()
    # 候选域中是否还有被禁素材
    in_cands = [d["scene_id"] for d in tl
                if any(BAN in str(c.get("asset_id")) or BAN in str(c.get("sha256"))
                       for c in (d.get("candidates") or []))]
    in_sel = [d["scene_id"] for d in tl
              if BAN in str(((d.get("selected_asset") or {}).get("asset_id")))
              or BAN in str(((d.get("selected_asset") or {}).get("sha256")))]
    empt = [d["scene_id"] for d in tl if not (d.get("candidates") or [])]
    print("① 被禁素材仍在**候选域**的景: {} ⇒ {}".format(
        in_cands or "无", "PASS" if not in_cands else "FAIL"))
    print("② 被禁素材仍被**选中**的景: {} ⇒ {}".format(
        in_sel or "无", "PASS" if not in_sel else "FAIL"))
    print("③ 排除后**空域**景: {} 个 ⇒ {}".format(
        len(empt), empt or "无"))
    print()
    ex = [(d["scene_id"], d.get("content_excluded_candidates")) for d in tl
          if d.get("content_excluded_candidates")]
    print("逐景排除计数（前 8）: {}".format(ex[:8]))
    print("有候选被排除的景数: {}".format(len(ex)))
    width = collections.Counter(len(d.get("candidates") or []) for d in tl)
    print("候选域分布（排除后）: {}".format(dict(sorted(width.items()))))
    (L / "p42_1_exclusion.json").write_text(json.dumps({
        "schema": "p42-1-content-exclusion-v1",
        "banned": BAN, "pool_before": len(allc),
        "still_in_candidates": in_cands, "still_selected": in_sel,
        "empty_domain_after": empt,
        "scenes_with_excluded_candidates": len(ex),
        "domain_histogram": {str(k): v for k, v in sorted(width.items())},
        "evidence": ce.get("evidence"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("-> docs/regression_2x/logs/p42_1_exclusion.json")
    return 0 if (not in_cands and not in_sel) else 1


if __name__ == "__main__":
    raise SystemExit(main())

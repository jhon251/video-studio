# -*- coding: utf-8 -*-
"""P16-3 连通性探针：单查询、不下载（验证治理路径与网络可达）。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
PID = "p_96efdc03e1aa"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.tools.material_provider import MaterialQuery                  # noqa: E402
from video_studio.tools.provider_wikimedia import WikimediaCommonsProvider      # noqa: E402
from video_studio.tools.base import ToolContext                                 # noqa: E402
from video_studio.agents.retrieval.agent import kw_tokens                       # noqa: E402

cfg = json.loads((R / "config" / "config.json").read_text(encoding="utf-8"))
ctx = ToolContext(role="retrieval", project_id=PID, project_dir=R / "projects" / PID,
                  db=None, config=cfg)
prov = WikimediaCommonsProvider(policy={"max_requests": 3, "search_limit": 6})
q = MaterialQuery(text="four color theorem proof diagram", scene_id="S03", limit=6,
                  kinds=("image",), keywords=kw_tokens("four color theorem proof diagram"))
print("search:", q.text)
try:
    found = prov.search(q, ctx)
except Exception as exc:                                                        # noqa: BLE001
    print("搜索异常:", type(exc).__name__, exc)
    print("stats:", json.dumps({k: v for k, v in prov.stats.items()
                                if k != "response_digests"}, ensure_ascii=False))
    print("digests:", json.dumps(prov.stats.get("response_digests"), ensure_ascii=False)[:600])
    sys.exit(1)
print("候选:", len(found))
for c in found:
    print("  - {:52s} | lic={:16s} class={:18s} cleared={} {}x{} score={}".format(
        (c.name or "")[:52], str(c.license)[:16], str(getattr(c, "license_class", ""))[:18],
        getattr(c, "license_cleared", None), c.width, c.height, c.match_score))
print()
print("stats:", json.dumps({k: v for k, v in prov.stats.items()
                            if k != "response_digests"}, ensure_ascii=False))
print("请求留痕条数:", len(prov.stats.get("response_digests") or []))

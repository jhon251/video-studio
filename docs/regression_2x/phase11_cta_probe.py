# -*- coding: utf-8 -*-
"""Phase 11 P11-1 只读探针：无 CTA 稿件在 1/3 采样下 CTA 维度是否统一 NOT_ASSESSABLE。"""
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.ops import retention as OPS                                       # noqa: E402

V2 = json.loads((R / "docs/regression_2x/logs/phase8_ab_v2.json").read_text(
    encoding="utf-8"))["script"]
cache = json.loads((R / "docs/regression_2x/logs/phase10_retention_cache.json").read_text(
    encoding="utf-8"))
for n in (1, 3):
    rep = OPS.evaluate(V2, cache=cache, llm=True, samples=n, taken_at="P11")
    llm = rep["llm"]
    rub = llm.get("rubric") or {}
    print("samples={} status={} cta={}".format(n, llm.get("status"),
                                               json.dumps(rub.get("cta_naturalness"),
                                                          ensure_ascii=False)[:120]))
    if "aggregation" in llm:
        print("   agg.cta:", json.dumps(llm["aggregation"]["cta_naturalness"],
                                        ensure_ascii=False)[:170])
    print("   cta_absent_semantics:", str(llm.get("cta_absent_semantics"))[:60])
    print("   validate:", OPS.validate_report(rep))

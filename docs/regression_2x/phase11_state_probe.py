# -*- coding: utf-8 -*-
"""Phase 11 §1 只读核对：config 钉定值、旧基线 metadata 产物、v3 稿脚本。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
print(" config.json sha256:", hashlib.sha256((R / "config/config.json").read_bytes()).hexdigest()[:16],
      "（须保持 7b03424846f1）")
p = R / "projects/p_96efdc03e1aa/artifacts/a_e0ec01d11b5a.json"
j = json.loads(p.read_text(encoding="utf-8"))
print(" 旧基线 metadata keys:", sorted(j.keys()))
pl = j.get("platforms") or []
print(" platforms:", len(pl), "| 首平台 keys:", sorted(pl[0].keys()) if pl else None)
if pl:
    print(" title:", str(pl[0].get("title"))[:80])
    print(" tags n:", len(pl[0].get("tags") or []), "| chapters n:", len(pl[0].get("chapters") or []))
    print(" description 前 90:", str(pl[0].get("description"))[:90])
v = json.loads((R / "docs/regression_2x/logs/phase8_ab_v3.json").read_text(encoding="utf-8"))
segs = (v.get("script") or {}).get("segments") or []
print(" v3 稿段数:", len(segs), "| 首句:", str(segs[0].get("narration"))[:70])
print(" v3 稿 titles:", json.dumps((v.get("script") or {}).get("titles"), ensure_ascii=False)[:120])

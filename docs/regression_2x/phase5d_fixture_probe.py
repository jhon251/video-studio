# -*- coding: utf-8 -*-
"""5-D 夹具探针：算候选图片两两 CLIP 视觉余弦，挑出"视觉差异足够大"的一组做镜头内切换夹具。"""
import itertools
import json
import pathlib
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core.mm_temporal import _sha256, cosine, run_temporal_worker  # noqa: E402

fx = ROOT / "src" / "video_studio" / "orchestration" / "tests" / "fixtures"
media = ROOT / "projects" / "p_f4b466a4a024" / "media" / "external"
cands = [fx / "syn_landscape.jpg", fx / "syn_portrait.jpg", fx / "syn_a.jpg", fx / "syn_b.jpg",
         fx / "r2_S02-B02_0.img.jpg", fx / "r2_S30-B02_3.img.jpg", fx / "syn_lowres.jpg"]
cands += sorted(media.glob("*.jpg"))[:4]
cands = [p for p in cands if p.is_file()]
labels = [{"id": "l", "text": "anything"}]
tmp = pathlib.Path(tempfile.mkdtemp(prefix="vs_mmt_probe_"))
res = run_temporal_worker([{"id": p.name, "path": str(p)} for p in cands], labels,
                          {}, root=ROOT, workdir=tmp)
emb = res.get("embeddings") or {}
print("ok:", res.get("ok"), "images:", len(emb))
pairs = []
for a, b in itertools.combinations(cands, 2):
    if a.name in emb and b.name in emb:
        pairs.append((round(cosine(emb[a.name], emb[b.name]), 4), a.name, b.name))
pairs.sort()
print("\n最不相似 8 对：")
for c, a, b in pairs[:8]:
    print("  cos={:<8} {} | {}".format(c, a, b))
print("\n最相似 4 对：")
for c, a, b in pairs[-4:]:
    print("  cos={:<8} {} | {}".format(c, a, b))

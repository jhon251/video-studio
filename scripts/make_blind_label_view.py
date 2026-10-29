"""生成盲测标注视图（供人工先标注 truth label；判决仍使用收集的原始文本）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from video_studio.tools.search_provider import _strip_tags  # noqa: E402

col = json.loads((ROOT / "projects" / "_drafts" / "r1_blind_collection.json").read_text(encoding="utf-8"))
lines = []
idx = 0
for rec in col["claims"]:
    for r in rec["results"]:
        idx += 1
        text = _strip_tags(r["page"].get("text") or "")[:350]
        lines.append(f"### [{idx}] claim={rec['claim_id']} fetch={r['page'].get('status')}")
        lines.append(f"CLAIM: {rec['claim_text'][:80]}")
        lines.append(f"TITLE: {(r['title'] or '')[:100]}")
        lines.append(f"SNIP:  {(r['snippet'] or '')[:180]}")
        lines.append(f"TEXT:  {text.replace(chr(10), ' ')}")
        lines.append(f"URL:   {r['url'][:100]}")
        lines.append("")
path = ROOT / "projects" / "_drafts" / "r1_blind_labeling_view.txt"
path.write_text("\n".join(lines), encoding="utf-8")
print("total candidates:", idx)
print("written:", path)

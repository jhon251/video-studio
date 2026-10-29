"""生成 Stage 5 dev 集标注视图（人工先标注；随后才允许用于 few-shot/开发）。"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from video_studio.tools.search_provider import _strip_tags  # noqa: E402

col = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_collection.json").read_text(encoding="utf-8"))
db = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
db.row_factory = sqlite3.Row

lines = []
idx = 0
for rec in col["claims"]:
    for r in rec["results"]:
        idx += 1
        text = _strip_tags(r["page"].get("text") or "")[:350]
        lines.append(f"### [D{idx:03d}] claim={rec['claim_id']} fetch={r['page'].get('status')}")
        lines.append(f"CLAIM: {rec['claim_text'][:80]}")
        lines.append(f"TITLE: {(r['title'] or '')[:100]}")
        lines.append(f"SNIP:  {(r['snippet'] or '')[:180]}")
        lines.append(f"TEXT:  {text.replace(chr(10), ' ')}")
        lines.append(f"URL:   {r['url'][:100]}")
        lines.append("")

# 未使用历史 Evidence（第一轮入库但未进入任何现有集合）
used_urls = set()
for f in ("evidence_regression_r1.json",):
    for s in json.loads((ROOT / "tests" / "data" / f).read_text(encoding="utf-8"))["samples"]:
        used_urls.add(s["evidence"].get("url", ""))
used_urls |= {r["url"] for rec in json.loads((ROOT / "projects" / "_drafts" / "r1_blind_collection.json")
                .read_text(encoding="utf-8"))["claims"] for r in rec["results"]}
used_urls |= {s["evidence"]["url"] for s in json.loads((ROOT / "tests" / "data" / "contradicts_stress.json")
                .read_text(encoding="utf-8"))["samples"]}
linked = {r["evidence_id"]: [x["claim_id"] for x in db.execute(
    "SELECT claim_id FROM claim_evidence WHERE evidence_id=?", (r["evidence_id"],))]
    for r in db.execute("SELECT evidence_id FROM evidence WHERE project_id='p_f2215875dd49'")}
claims_map = {c["claim_id"]: c["text"] for c in db.execute(
    "SELECT claim_id, text FROM claims WHERE project_id='p_f2215875dd49'")}
for r in db.execute("SELECT * FROM evidence WHERE project_id='p_f2215875dd49'"):
    if (r["url"] or "") in used_urls:
        continue
    idx += 1
    cids = linked.get(r["evidence_id"], [])
    claim = claims_map.get(cids[0], "") if cids else ""
    lines.append(f"### [D{idx:03d}] claim={cids[0] if cids else '?'} fetch=stored")
    lines.append(f"CLAIM: {claim[:80]}")
    lines.append(f"TITLE: ")
    lines.append(f"SNIP:  ")
    lines.append(f"TEXT:  {(r['excerpt'] or '')[:350]}")
    lines.append(f"URL:   {(r['url'] or '')[:100]}")
    lines.append("")

path = ROOT / "projects" / "_drafts" / "s5_dev_labeling_view.txt"
path.write_text("\n".join(lines), encoding="utf-8")
print("total candidates:", idx)
print("written:", path)

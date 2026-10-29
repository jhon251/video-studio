"""Stage 3.1.4 指标分析器（测量工具，只读；可同时分析 3.1.3 基线与 3.1.4 结果）。

关键口径：
- rights_reject    = 候选被版权硬门槛淘汰（match_score is None）
- semantic_reject  = 候选通过版权但语义分 < 45（未达 Primary 资格）
- no_safe_match    = 无任何候选达到语义下限的镜头
- retrieval_miss   = no_safe_match 镜头中，检索回的候选与主题相关词零命中
                    （"源里有但没搜到"的代理指标；源里确实没有的情况标注 source_absence）
- relevant_recall@K = 镜头检索回的候选（全部，含被拒）中至少 1 条命中主题相关词
RELEVANT_KEYWORDS 仅用于测量（分析器侧），不参与系统代码。
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]

KEYWORDS = {
    "yuan": ["rice", "paddy", "yuan", "grain", "agricultur", "seed", "field"],
    "zhenghe": ["ship", "sailing", "voyage", "zheng he", "fleet", "boat", "maritime", "sail"],
    "darkmatter": ["dark matter", "galaxy", "universe", "telescope", "cosmos", "nebula", "star"],
    "drip": ["drip", "irrigation", "water", "pipe", "greenhouse", "field", "farm"],
    "bread": ["bread", "dough", "baker", "baking", "yeast", "flour", "oven", "loaf"],
    "chongqing": ["chongqing", "city", "street", "night", "skyline", "river", "yangtze"],
    "qinghai": ["train", "railway", "plateau", "tibet", "mountain", "snow", "rail"],
    "marathon": ["marathon", "runner", "running", "race", "jogging", "runner"],
    "freedom": ["sky", "bird", "landscape", "open", "running", "walking", "field"],
    "homesick": ["home", "kitchen", "cooking", "village", "family", "train", "courtyard"],
    "tea": ["tea", "teapot", "cup", "brew", "leaves", "teacup"],
    "coffee": ["coffee", "roast", "bean", "grind", "barista", "espresso"],
    "busy": ["clock", "watch", "time", "calendar", "schedule", "hourglass"],
    "phone": ["smartphone", "phone", "mobile", "screen", "notification"],
    "study": ["book", "study", "reading", "library", "notebook", "desk"],
    "nightcity": ["night", "city", "street", "skyline", "lights"],
    "jarvis": ["robot", "ai", "artificial", "chatbot", "machine", "computer"],
}
BAD_TOKENS = ["typewriter", "astronaut", "spacewalk", "manuscript", "iskendername",
              "data center", "world war", "wwi", "sim card", "handset"]


def analyze(pkg_dir: Path, theme: str) -> dict:
    shots_path = pkg_dir / "shot_mapping" / "all_shots.json"
    if not shots_path.exists():
        return {"theme": theme, "dir": str(pkg_dir), "missing": True}
    shots = json.loads(shots_path.read_text(encoding="utf-8"))["shots"]
    ns = json.loads(shots_path.read_text(encoding="utf-8"))["no_safe_match"]
    mats = json.loads((pkg_dir / "metadata" / "materials.json").read_text(encoding="utf-8"))["materials"]
    log = json.loads((pkg_dir / "search_log" / "search_log.json").read_text(encoding="utf-8"))
    kw = KEYWORDS.get(theme, [])

    by_shot = {}
    for m in mats:
        by_shot.setdefault(m["shot_id"], []).append(m)

    rights_reject = semantic_reject = 0
    no_safe = len(ns)
    retrieval_miss = 0
    source_absence = 0
    relevant_recalled = 0
    broll_shots = 0
    false_match = 0
    reuse = 0
    primary_ok = 0
    primary_count = 0
    queries = set()
    sources = set()

    for o in log.get("queries", []):
        for q in o.get("outcomes", []):
            queries.add(q.get("query", ""))

    for sid, slot in shots.items():
        if slot["material_kind"] != "broll":
            continue
        broll_shots += 1
        mats_s = by_shot.get(sid, [])
        sources.update(m.get("source_url", "") for m in mats_s)
        rr = sum(1 for m in mats_s if m.get("match_score") is None)
        sr = sum(1 for m in mats_s if m.get("match_score") is not None
                 and (m.get("score_detail") or {}).get("semantic_match", 0) < 45)
        rights_reject += rr
        semantic_reject += sr
        hit = any(any(k in ((m.get("visual_description") or "") + " " + m.get("source_url", "")).lower()
                       for k in kw) for m in mats_s)
        if hit:
            relevant_recalled += 1
        rec = slot.get("primary")
        if rec:
            primary_count += 1
            d = (rec.get("visual_description") or "").lower()
            if any(b in d for b in BAD_TOKENS):
                false_match += 1
            else:
                primary_ok += 1
            if rec.get("reuse_penalty") or rec.get("diversity_penalty"):
                reuse += 1
        else:
            # no_safe：区分 retrieval miss 与拒绝类
            if not hit:
                retrieval_miss += 1
    return {
        "theme": theme, "dir": str(pkg_dir),
        "broll_shots": broll_shots,
        "primary_count": primary_count, "primary_ok": primary_ok,
        "false_match": false_match, "reuse": reuse,
        "no_safe_match": no_safe,
        "retrieval_miss": retrieval_miss,
        "rights_reject": rights_reject, "semantic_reject": semantic_reject,
        "relevant_recall": relevant_recalled,
        "relevant_recall_rate": round(relevant_recalled / broll_shots, 3) if broll_shots else 0,
        "query_diversity": len(queries), "source_diversity": len(sources),
    }


def main():
    themes = sys.argv[1].split(",")
    pkg_dir = ROOT / "output" / "stage31_testpkgs"
    out_path = Path(sys.argv[2])
    rows = []
    for t in themes:
        d = pkg_dir / t / sys.argv[3]
        r = analyze(d, t)
        rows.append(r)
        if not r.get("missing"):
            print(f"[{t}] Primary {r['primary_ok']}/{r['primary_count']} | 假匹配 {r['false_match']} "
                  f"| NO_SAFE {r['no_safe_match']} | Miss {r['retrieval_miss']} "
                  f"| rights拒 {r['rights_reject']} | sem拒 {r['semantic_reject']} "
                  f"| recall {r['relevant_recall']}/{r['broll_shots']} ({r['relevant_recall_rate']}) "
                  f"| query去重 {r['query_diversity']} | 源去重 {r['source_diversity']}")
        else:
            print(f"[{t}] 缺失 {d}")
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("已写", out_path)


if __name__ == "__main__":
    main()

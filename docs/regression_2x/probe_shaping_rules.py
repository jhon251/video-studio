"""3.x Phase 3-A：离线证明查询整形规则（不依赖网络，确定性）。

取真实项目 p_f4b466a4a024 的 retrieval 产物里**实际使用过的查询文本**，
对同一文本分别套用"旧规则（按空白取前 N 词）"与"新规则（latin_preferred）"，
把两者结果并排写入 logs/phase3a_shaping_rules.txt —— 用于说明 run 1 为何 0 命中、
以及修复后查询变成了什么。
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.tools.provider_wikimedia import WikimediaCommonsProvider  # noqa: E402

PID = "p_f4b466a4a024"
OUT = ROOT / "docs" / "regression_2x" / "logs" / "phase3a_shaping_rules.txt"


def newest_of_type(types: tuple) -> dict | None:
    con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(
        "select * from artifacts where project_id=? and type in ({}) order by created_at".format(
            ",".join("?" * len(types))), (PID, *types))]
    con.close()
    if not rows:
        return None
    d = json.loads(Path(rows[-1]["path"]).read_text(encoding="utf-8"))
    return d if isinstance(d, dict) else {"payload": d}


def old_rule(text: str, n: int = 3) -> str:
    seen, out = set(), []
    for w in str(text or "").replace("。", " ").replace(".", " ").split():
        w = w.strip()
        if not w or w.lower() in seen:
            continue
        seen.add(w.lower())
        out.append(w)
        if len(out) >= n:
            break
    return " ".join(out)


retr = newest_of_type(("retrieval_candidates",))
lines = ["3-A 查询整形离线证明（项目 {}）".format(PID), "=" * 78, ""]
if not retr:
    lines.append("未找到 retrieval 产物：无法离线证明。")
else:
    payload = retr.get("payload") or retr
    qs = payload.get("queries") or []
    if not qs and payload.get("query"):
        qs = [{"query": payload["query"], "scene_id": "retrieval"}]
    if payload.get("material_providers"):
        lines.append("run 1 记录的 provider 统计（节选）：")
        lines.append(json.dumps(payload["material_providers"], ensure_ascii=False)[:1200])
        lines.append("")
    if not qs:
        lines.append("retrieval 产物顶层键：{}".format(sorted(payload)[:20]))
    lines.append("retrieval 产物记录 {} 条查询；逐条对照：".format(len(qs)))
    lines.append("")
    for q in qs:
        text = q.get("query") or q.get("text") or ""
        shaped, meta = WikimediaCommonsProvider.shape_query(text, 4)
        rec = {"scene": q.get("scene_id") or q.get("shot_index"),
               "query_chars": len(text),
               "old_rule_used": old_rule(text, 3),
               "recorded_used(run1)": (q.get("query_shaping") or {}).get("used"),
               "new_rule_used": shaped,
               "new_rule_mode": meta["mode"],
               "latin_available": meta["latin_available"]}
        lines.append(json.dumps(rec, ensure_ascii=False))
    lines += ["", "结论：", "- run 1 使用旧规则（按空白切分）→ 中文旁白无空格 → 整块被当作一个"
              "词，AND 检索在 Commons 上 0 命中；", "- 新规则优先取拉丁/数字词（latin_preferred）"
              "→ 查询变为可被英文语料命中的品牌/型号词；", "- 无拉丁词的查询仍退回 CJK 词块"
              "（cjk_only）——命中率低属**已知限制**，不伪造。"]
sys.stdout.reconfigure(errors="replace")
print("\n".join(lines))
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\nwritten", OUT)

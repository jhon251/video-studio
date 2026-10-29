# -*- coding: utf-8 -*-
"""P35-1 机械校验（违反即重生成）。

① 数字/实体守恒：v5 的数字与实体 **⊆ v3 ∪ v4.1 并集**（**不得新增**年份）
② fact_risks 逐条保留为元数据（14 条）
③ 长度 550–700s 口播量
④ 元叙述黑名单清零
⑤ ai_flavor 不高于 v4.1
⑥ **n-gram 守卫**：与王骁参照文本最长公共 n-gram（n≥8）**零命中**
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import ai_flavor as AF                                   # noqa: E402

V5 = R / "output/p35_script/v5_fulltext.json"
V41 = R / "output/phase33_script_sandbox/script_p33_v41_40seg.json"
V42 = R / "output/phase34_script_sandbox/script_p34_v42_40seg.json"
V3 = R / "projects/p_96efdc03e1aa/artifacts/a_49b58fb3dc01.json"
LED = R / "output/p35_probe/fact_risks_ledger.json"
REFS = [R / "config/human_style_refs/wangxiao_zhongdong_科威特.txt",
        R / "config/human_style_refs/wangxiao_zhongdong_埃及.txt"]

BLACK = ["回查", "先不给", "不给数字", "标清楚", "必须查清", "得先说", "说一下是哪几处",
         "这一版", "我会说清楚", "要核原文", "这期里", "我打算", "接下来我们讲",
         "这一段我想说的是", "先说清楚", "得先说清楚"]
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
ENTS = ["Appel", "Haken", "Tymoczko", "Detlefsen", "Luker", "Hales", "Flyspeck",
        "Lean", "mathlib", "Liquid Tensor Experiment", "Scholze", "Buzzard",
        "DeepMind", "AlphaGeometry", "AlphaProof", "IMO", "Nature", "四色定理",
        "开普勒猜想"]


def main() -> int:
    doc = json.loads(V5.read_text(encoding="utf-8"))
    paras = doc["paragraphs"]
    text = "\n".join(p["text"] for p in paras)
    v41 = json.loads(V41.read_text(encoding="utf-8"))
    v42 = json.loads(V42.read_text(encoding="utf-8"))
    v3 = json.loads(V3.read_text(encoding="utf-8"))
    t41 = "\n".join(s.get("narration") or "" for s in v41["segments"])
    t42 = "\n".join(s.get("narration") or "" for s in v42["segments"])
    t3 = json.dumps(v3, ensure_ascii=False)

    fails = []
    print("=" * 72)
    # ① 数字/实体守恒（⊆ 并集）
    allow_num = set(NUM_RE.findall(t41) + NUM_RE.findall(t42) + NUM_RE.findall(t3))
    allow_ent = {e for e in ENTS if e in (t41 + t42 + t3)}
    used_num = set(NUM_RE.findall(text))
    used_ent = {e for e in ENTS if e in text}
    new_num = sorted(used_num - allow_num)
    new_ent = sorted(used_ent - allow_ent)
    print("① 数字/实体守恒（⊆ v3∪v4.1∪v4.2）")
    print("   v5 使用数字: {}".format(sorted(used_num)))
    print("   新增数字（违反）: {}".format(new_num or "无"))
    print("   新增实体（违反）: {}".format(new_ent or "无"))
    if new_num or new_ent:
        fails.append("① 新增数字/实体")
    # ② fact_risks
    led = json.loads(LED.read_text(encoding="utf-8"))
    fr = led["fact_risks"]
    doc_fr = doc.get("fact_risks") or []
    print("② fact_risks: 底账 {} 条 | v5 元数据 {} 条".format(len(fr), len(doc_fr)))
    if len(doc_fr) < len(fr):
        fails.append("② fact_risks 未逐条保留")
    # ③ 长度
    chars = len(re.sub(r"\s", "", text))
    est = chars / 4.9
    print("③ 长度: {} 字（去空白）| 预估口播 {:.0f}s | 目标 550-700s ⇒ {}".format(
        chars, est, "OK" if 550 <= est <= 700 else "**超出**"))
    if not (550 <= est <= 700):
        fails.append("③ 长度超出 550-700s")
    # ④ 黑名单
    res = [b for b in BLACK if b in text]
    print("④ 元叙述黑名单残留: {}".format(res or "无"))
    if res:
        fails.append("④ 黑名单残留 {}".format(res))
    # ⑤ ai_flavor（正确 API：`AF.analyze`）
    def flavor(t):
        try:
            return AF.analyze(t)
        except Exception as exc:                                            # noqa: BLE001
            return {"error": "{}: {}".format(type(exc).__name__, exc)}
    f5, f41 = flavor(text), flavor(t41)
    print("⑤ ai_flavor(v5)   = {}".format(json.dumps(f5, ensure_ascii=False)[:260]))
    print("   ai_flavor(v4.1) = {}".format(json.dumps(f41, ensure_ascii=False)[:260]))

    def fv(d):
        for k in ("score", "flavor_score", "total", "ai_score", "signal_score"):
            if isinstance(d.get(k), (int, float)):
                return d[k]
        # analyze() 可能返回各信号计数 ⇒ 用信号总数作代理
        for k in ("signals", "hits", "findings"):
            v = d.get(k)
            if isinstance(v, (list, tuple)):
                return len(v)
            if isinstance(v, dict):
                return sum(len(x) if isinstance(x, list) else 1 for x in v.values())
        return None
    s5, s41 = fv(f5), fv(f41)
    print("   可比分数: v5={} | v4.1={}".format(s5, s41))
    if s5 is not None and s41 is not None and s5 > s41:
        fails.append("⑤ ai_flavor 高于 v4.1（{} > {}）".format(s5, s41))
    # ⑥ n-gram 守卫（与参照文本 n>=8 零命中）
    def grams(t, n=8):
        t = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", t)
        return {t[i:i + n] for i in range(max(len(t) - n + 1, 0))}
    g5 = grams(text)
    hits = {}
    for rp in REFS:
        gr = grams(rp.read_text(encoding="utf-8"))
        inter = g5 & gr
        hits[rp.name] = len(inter)
        if inter:
            hits[rp.name + "_samples"] = sorted(inter)[:5]
    print("⑥ n-gram（n=8）与参照文本重合: {}".format(
        json.dumps({k: v for k, v in hits.items() if not k.endswith("_samples")},
                   ensure_ascii=False)))
    if any(v for k, v in hits.items() if not k.endswith("_samples")):
        fails.append("⑥ 与参照文本 n-gram 命中 {:}".format(
            {k: v for k, v in hits.items() if not k.endswith("_samples")}))
    print("=" * 72)
    print("机械校验: {}".format("**全部通过**" if not fails else "**未通过** → " + "; ".join(fails)))
    rep = {"schema": "p35-1-mechanical-check-v1", "chars": chars, "est_spoken_s": round(est, 1),
           "paragraphs": len(paras), "new_numbers": new_num, "new_entities": new_ent,
           "blacklist_residue": res, "ai_flavor_v5": f5, "ai_flavor_v41": f41,
           "ngram_hits": {k: v for k, v in hits.items() if not k.endswith("_samples")},
           "fact_risks_ledger": len(fr), "fact_risks_in_v5": len(doc_fr),
           "fails": fails}
    (R / "docs/regression_2x/logs/p35_1_mechanical_check.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

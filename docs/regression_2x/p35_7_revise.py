# -*- coding: utf-8 -*-
"""P35-1 修订轮：把 ai_flavor 信号压到 **不高于 v4.1**（`其实` 等推进词清零），
其余（叙事脊柱/数字实体守恒/黑名单/长度）保持不变。"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import urllib.request

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.env import load_env                                  # noqa: E402
from video_studio.core import ai_flavor as AF                               # noqa: E402

V5 = R / "output/p35_script/v5_fulltext.json"
V41 = R / "output/phase33_script_sandbox/script_p33_v41_40seg.json"
sys.path.insert(0, str(R / "docs" / "regression_2x"))
import p35_5_write_v5 as G                                                  # noqa: E402


def adv(t):
    a = AF.analyze(t)
    return a["advance_marker_count"], a["advance_marker_hits"]


def main() -> int:
    load_env(R / ".env")
    cfg = json.loads((R / "config/config.json").read_text(encoding="utf-8"))
    llm = cfg["llm"]
    key = os.environ.get(llm["deepseek"]["api_key_env"])
    pr = llm["pricing"][llm["tiers"]["F"]["model"]]["off_peak"]
    doc = json.loads(V5.read_text(encoding="utf-8"))
    t = "\n\n".join(p["text"] for p in doc["paragraphs"])
    v41 = json.loads(V41.read_text(encoding="utf-8"))
    t41 = "\n\n".join(s.get("narration") or "" for s in v41["segments"])
    n5, hits5 = adv(t)
    n41, hits41 = adv(t41)
    print("修订前: v5 advance={} {} | v4.1 advance={} {}".format(n5, hits5, n41, hits41))

    body = json.dumps({
        "model": llm["tiers"]["F"]["model"],
        "messages": [
            {"role": "system", "content": G.SYSTEM},
            {"role": "user", "content":
             "下面是一篇已成型的口播稿全文。请做**最小改动的表达修订**，只处理两件事：\n"
             "① 删掉或改写全部**推进词/口头禅**：「其实」「实际上」「换句话说」「也就是说」"
             "「值得注意的是」「更重要的是」「总而言之」「综上所述」（**「最后」可以保留最多 1 处**）；\n"
             "② 把 1–2 处长句拆成短句（口语松弛感），**不得**改变任何事实、年份、数字、人名、机构；\n"
             "③ **不得**新增任何「不是A而是B」对称构式、设问自答对；\n"
             "④ **不得**添加核查腔/元叙述（回查/先不给/标清楚/这一版 等）；\n"
             "⑤ 总字数保持 **2,800–3,300 字**（去空白）；叙事顺序与分段（12 段）不变。\n\n"
             "返回严格 JSON，结构同输入：{\"title\":…,\"paragraphs\":[{\"id\":…,\"text\":…,"
             "\"intent\":…},…]}。\n\n【全文】\n" + t}],
        "max_tokens": 16000, "temperature": 0.5,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(
        llm["deepseek"]["base_url"].rstrip("/") + "/chat/completions",
        data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer {}".format(key)})
    with urllib.request.urlopen(req, timeout=600) as r:
        j = json.loads(r.read().decode("utf-8"))
    content = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
    u = j.get("usage") or {}
    cost = (u.get("prompt_tokens", 0) * pr["cache_miss"]
            + u.get("completion_tokens", 0) * pr["output"]) / 1_000_000
    print("usage={} | 估算 ${:.6f}".format(json.dumps(u, ensure_ascii=False), cost))
    new = json.loads(content)
    t2 = "\n\n".join(p["text"] for p in new["paragraphs"])
    n2, hits2 = adv(t2)
    chars = len(re.sub(r"\s", "", t2))
    print("修订后: advance={} {} | 字数 {} | 预估 {:.0f}s".format(
        n2, hits2, chars, chars / 4.9))
    # 回归校验（关键项）
    allow = set(re.findall(r"\d+(?:\.\d+)?", t41)) | set(
        re.findall(r"\d+(?:\.\d+)?", json.dumps(doc, ensure_ascii=False)))
    newnum = sorted(set(re.findall(r"\d+(?:\.\d+)?", t2)) - allow)
    BLACK = ["回查", "先不给", "不给数字", "标清楚", "必须查清", "得先说", "这一版",
             "我会说清楚", "要核原文", "这期里"]
    res = [b for b in BLACK if b in t2]
    ok = (n2 <= n41 and not newnum and not res and 2800 <= chars <= 3300)
    print("守恒新增数字={} | 黑名单残留={} | 判决={}".format(
        newnum or "无", res or "无", "OK 采纳" if ok else "**未达标**"))
    if ok:
        new["fact_risks"] = doc["fact_risks"]
        new["hook_map"] = doc.get("hook_map")
        new["cta_plan"] = doc.get("cta_plan")
        new["story_spine_check"] = doc.get("story_spine_check")
        new["entities_used"] = doc.get("entities_used")
        new["numbers_used"] = doc.get("numbers_used")
        new["_meta"] = dict(doc.get("_meta") or {})
        new["_meta"].update({"revision": "advance-marker-parity-vs-v41",
                             "cost_usd_total": round(
                                 float(new["_meta"].get("cost_usd") or 0) + cost, 6),
                             "advance_before": {"count": n5, "hits": hits5},
                             "advance_after": {"count": n2, "hits": hits2},
                             "v41_advance": {"count": n41, "hits": hits41},
                             "chars": chars})
        V5.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
        txt = ["# v5 全文（{} 段，{} 字，预估口播 {:.0f}s）".format(
            len(new["paragraphs"]), chars, chars / 4.9), ""]
        for p in new["paragraphs"]:
            txt.append(p["text"])
            txt.append("")
        (R / "output/p35_script/v5_fulltext.txt").write_text("\n".join(txt),
                                                             encoding="utf-8")
        print("-> 已采纳并写回 v5_fulltext.json / .txt")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

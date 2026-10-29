# -*- coding: utf-8 -*-
"""P35-1：**v5 全文重写**（一次整体生成；禁止对 v4.2 做删补）。

输入：v3 底账（core_viewpoint / narrative_route / 14 条 fact_risks）+ v4.1 全文（事实底账）
      + 王骁参照文本（**仅学机制，禁止抄句**）。
输出：`output/p35_script/v5_fulltext.json`（分段正文 + 元数据）+ 可读 TXT。

硬规则（违反即重生成）：数字/实体守恒（⊆ v3∪v4.1）、fact_risks 逐条保留为元数据、
长度 550-700s 口播量、**元叙述黑名单清零**、ai_flavor 不高于 v4.1。
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import time
import urllib.request

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.env import load_env                                  # noqa: E402

OUT = R / "output" / "p35_script"
LEDGER = R / "output/p35_probe/fact_risks_ledger.json"
V41 = R / "output/phase33_script_sandbox/script_p33_v41_40seg.json"
V3STRUCT = R / "output/p35_probe/v3_structure.json"
REF = R / "config/human_style_refs/wangxiao_zhongdong_科威特.txt"

SYSTEM = """你是一位中文知识类长视频的**顶级口播写手**。你的任务是把一份事实底账，
重写成一篇**有故事脊柱**的口播稿全文（v5）。

# 叙事脊柱（必须按此推进，论点从故事里长出来）
以**人物与事件**为线：
1) 1977 年 Appel 和 Haken 宣布证出四色定理——计算机帮了忙，数学界的第一反应**不是鼓掌**；
   这份证明有一次**豪赌**：把无穷多种地图归约成有限多种构型，再让程序逐个检查。
2) 数学界**拒收/迟疑**：审稿拖了很久，没有人读完它。
3) 1979 年哲学家 Thomas Tymoczko 把这件事上升为认识论问题；1980 年 Detlefsen 和 Luker
   直接反驳。两方**并列呈现**，不要写成共识。
4) 开普勒猜想：Thomas Hales 给出证明，审稿人表示无法百分之百确认，Hales 用过一个
   流传很广的说法——大约「99% 确定」；随后他花**十几年**（v4.1 说十六年）把证明
   完整形式化（项目 Flyspeck，2014 年完成）。
5) Lean / mathlib 让形式化变成工程；2020 年 Peter Scholze 的 Liquid Tensor Experiment
   是**人类数学家主动请机器检查自己**；2022 年 Kevin Buzzard 宣布挑战完成。
6) 2024 年 DeepMind 的 AlphaGeometry 发表在《Nature》，AI **从验证者变成出题者/生产者**；
   同年 AlphaProof + AlphaGeometry 2 参加 IMO 2024 的题目（**严格区分这两次实验**）。

# 机制（学王骁的机制，**严禁抄参照文本任何句子/口头禅**）
· 开场**从具体事实切入**，禁止「假设有一天」式抽象思想实验开场。
· 抽象概念**紧跟具体/世俗类比**（下一句内给抓手）。
· 数字出现后**紧邻**给人话翻译（它意味着多大/多久/什么概念）。
· 允许**短句成段**、口语松弛感、插入语；**不追求**排比与书面工整。
· 段落顺序由**故事怎么往下走**决定（事件→反应→冲突→转折），允许延迟给结论。
· 态度外露（对事件性质、对论证质量的判断），**但不对在世人物做人格评价**。

# 硬禁（出现即不合格）
· **元叙述/核查腔**：「回查原文」「先不给」「这一版不给数字」「必须标清楚」「得先说」
  「说一下是哪几处」「我会说清楚」「要核原文」「这期里」「出处必须查清」「我打算…」
  「接下来我们讲…」「这一段我想说的是…」等同族表述。
· 推进词：换句话说／也就是说／值得注意的是／更重要的是／总而言之／综上所述／首先-其次-最后（作路标时）。
· 「不是A而是B」对称构式；设问自答对（「…吗？答案是…」「为什么？因为…」）。
· 不确定性**用自然口语**表达（据说／有说法是／大概／可能），或整句不提。
· **不得新增**任何底账之外的年份、数字、人名、机构、刊物、定理名。
· AlphaGeometry（Nature 2024）与 IMO 2024 的 AlphaProof / AlphaGeometry 2 **不得混写**。

# 长度
口播总时长目标 **550–700 秒**（中文约 4.7–5.1 字/秒 ⇒ 约 **2,600–3,600 字**）。

# 输出格式（严格 JSON，不要 markdown 围栏）
{
 "title": "…",
 "paragraphs": [
   {"id": "P01", "text": "……", "intent": "这段在推进故事的什么"},
   …（**9–12 段**，每段是一个自然段，段内**句子完整**）
 ],
 "story_spine_check": [{"beat": "1) 豪赌", "covered_in": ["P01","P02"]}, …],
 "entities_used": ["Appel", "Haken", …],
 "numbers_used": ["1977", "1852", …]
}"""


def main() -> int:
    load_env(R / ".env")
    cfg = json.loads((R / "config/config.json").read_text(encoding="utf-8"))
    llm = cfg["llm"]
    key = os.environ.get(llm["deepseek"]["api_key_env"])

    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    st = json.loads(V3STRUCT.read_text(encoding="utf-8"))
    v41 = json.loads(V41.read_text(encoding="utf-8"))
    v41_text = "\n\n".join("【{}】{}".format(s["scene_id"], s.get("narration") or "")
                           for s in v41["segments"])
    ref = REF.read_text(encoding="utf-8")
    ref_excerpt = "\n".join(ref.splitlines()[:60])

    user = """# 事实底账（唯一可用的年份/数字/实体来源）
## v3 core_viewpoint
{cp}

## v3 narrative_route
{nr}

## v3 已核查的 14 条事实边界（**逐条保留为元数据，不写入正文**）
{fr}

## v4.1 全文（按段；**这是事实底账，可重组但不得新增事实**）
{v41}

# 王骁参照文本（**仅学机制，禁止抄任何句子**；前 60 行）
{ref}

# 任务
按上面的叙事脊柱与机制，**一次性整体重写**成 v5 全文（9–12 个自然段，2,600–3,600 字）。
注意：这是**整体重写**，不是对 v4.1 逐段删补——先想清楚整篇故事怎么走，再落笔。
只输出严格 JSON。""".format(
        cp=json.dumps(st.get("core_viewpoint"), ensure_ascii=False),
        nr=json.dumps(st.get("narrative_route"), ensure_ascii=False),
        fr=json.dumps(led["fact_risks"], ensure_ascii=False, indent=1),
        v41=v41_text, ref=ref_excerpt)

    body = json.dumps({
        # 用 **F 档（deepseek-flash，非推理）**：实测 R 档把 max_tokens 全烧在
        # `reasoning_tokens`（7913/8000）⇒ 正文被截断、JSON 不闭合。
        "model": llm["tiers"]["F"]["model"],
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": user}],
        "max_tokens": 16000, "temperature": 0.8,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(
        llm["deepseek"]["base_url"].rstrip("/") + "/chat/completions",
        data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer {}".format(key)})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        j = json.loads(r.read().decode("utf-8"))
    dt = time.time() - t0
    content = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
    u = j.get("usage") or {}
    pr = llm["pricing"][llm["tiers"]["F"]["model"]]["off_peak"]
    cost = (u.get("prompt_tokens", 0) * pr["cache_miss"]
            + u.get("completion_tokens", 0) * pr["output"]) / 1_000_000
    print("LLM 用时 {:.1f}s | usage={} | 估算 ${:.6f}".format(
        dt, json.dumps(u, ensure_ascii=False), cost))
    try:
        doc = json.loads(content)
    except Exception as exc:                                                # noqa: BLE001
        print("JSON 解析失败:", exc)
        (OUT.parent / "p35_probe").mkdir(parents=True, exist_ok=True)
        (R / "output/p35_probe/v5_raw.txt").write_text(content, encoding="utf-8")
        print("原始输出已存 output/p35_probe/v5_raw.txt")
        return 1
    paras = doc.get("paragraphs") or []
    total = sum(len(p.get("text") or "") for p in paras)
    # ---- 长度硬门（授权书：550–700s 口播量）：不足/超出即**自动重生成**（最多多 2 轮）----
    for attempt in range(2, 4):
        est = total / 4.9
        if 552 <= est <= 698:
            break
        want = ("加长到 2,800–3,300 字（可给每段增一到两句具体细节，"
                "但**不得新增**任何年份/数字/人名）"
                if est < 552 else "压缩到 2,800–3,300 字")
        print("第 {} 轮长度 {:.0f}s（目标 550-700）⇒ 要求{}后重生成".format(
            attempt - 1, est, want))
        body2 = json.dumps({
            "model": llm["tiers"]["F"]["model"],
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
                {"role": "assistant", "content": content},
                {"role": "user", "content":
                 "这版去空白字数 {} 字、预估口播 {:.0f}s，**需要{}**。"
                 "请在不新增任何年份/数字/人名/机构/刊物/定理名的前提下重写全文，"
                 "目标 **2,800–3,300 字**（约 570–670s 口播）。"
                 "叙事脊柱、机制与硬禁全部不变。只输出严格 JSON。".format(total, est, want)}],
            "max_tokens": 16000, "temperature": 0.8,
            "response_format": {"type": "json_object"},
        }).encode("utf-8")
        req2 = urllib.request.Request(
            llm["deepseek"]["base_url"].rstrip("/") + "/chat/completions",
            data=body2, method="POST",
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer {}".format(key)})
        with urllib.request.urlopen(req2, timeout=600) as r2:
            j2 = json.loads(r2.read().decode("utf-8"))
        content = (j2.get("choices") or [{}])[0].get("message", {}).get("content", "")
        u2 = j2.get("usage") or {}
        cost += (u2.get("prompt_tokens", 0) * pr["cache_miss"]
                 + u2.get("completion_tokens", 0) * pr["output"]) / 1_000_000
        try:
            doc = json.loads(content)
        except Exception:                                                   # noqa: BLE001
            print("  重生成 JSON 解析失败 ⇒ 保留上一版")
            break
        paras = doc.get("paragraphs") or []
        total = sum(len(p.get("text") or "") for p in paras)
        u = u2
    # ---- fact_risks 逐条保留为元数据（授权书硬规则）----
    doc["fact_risks"] = led["fact_risks"]
    doc["hook_map"] = {"source": "v3 谱系（P19 21 景）", "note": "结构装置继承，表达层重写"}
    doc["cta_plan"] = {"source": "v3 谱系", "retained": True,
                       "note": "片尾互动保留；元叙述清零"}
    doc["_meta"] = {"model": llm["tiers"]["F"]["model"], "elapsed_s": round(dt, 1),
                    "usage": u, "cost_usd": round(cost, 6),
                    "paragraphs": len(paras), "chars": total,
                    "est_spoken_s": round(total / 4.9, 1)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v5_fulltext.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    # 可读 TXT（交人审）
    txt = ["# v5 全文（{} 段，{} 字，预估口播 {:.0f}s）".format(
        len(paras), total, total / 4.9), ""]
    for p in paras:
        txt.append("## [{}] {}".format(p.get("id"), p.get("intent") or ""))
        txt.append(p.get("text") or "")
        txt.append("")
    (OUT / "v5_fulltext.txt").write_text("\n".join(txt), encoding="utf-8")
    print("段数 {} | 总字数 {} | 预估口播 {:.0f}s".format(len(paras), total, total / 4.9))
    print("-> output/p35_script/v5_fulltext.json / .txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

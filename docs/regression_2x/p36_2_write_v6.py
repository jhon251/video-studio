# -*- coding: utf-8 -*-
"""P36-2：**v6 全文生成**（骨架级重构，走九拍节表）。

与 P35 的差异（授权书 §0）：不是句子修补，而是**骨架重排**——
五主角轮换 ⇒ **一个问题贯穿**；报幕式段首 ⇒ **钩子承接**；
工具陈列（Lean/mathlib）⇒ **折进 LTE 情节**；每段澄清拍 ⇒ **至多 1 处且顺嘴**。

产出：`output/p36_script/v6_fulltext.json` + 可读 TXT。
校验见 `p36_3_check.py`（机械全套）与 `p36_4_hookchain.py`（钩子衔接新门）。
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

OUT = R / "output" / "p36_script"
SHEET = R / "docs/regression_2x/logs/phase36_beatsheet.json"
V52 = R / "output/p35_script/v5_2_fulltext.json"
V41 = R / "output/phase33_script_sandbox/script_p33_v41_40seg.json"
REF = R / "config/human_style_refs/wangxiao_zhongdong_科威特.txt"

SYSTEM = """你是一位中文知识类长视频的**顶级口播写手**。把给定的**九拍节表**写成一篇口播稿全文（v6）。

# 唯一脊柱
全篇只回答一个问题：**「凭什么信」**——一份没有人读完过的证明，凭什么算证明。
所有事件、人物、数字都服务于这一个问题；**不要**写成"五位主角依次登场"的合集。

# 铁律（违反即不合格）
① **每段末句必须是钩子**（一个悬念/反常/未决的问题），**且下一段的段首必须直接承接它**
   ——用"接话"的方式开头（回答它、追问它、或把它推进一步），**禁止**另起炉灶。
   末段除外：末段**冷收 + 片尾 CTA**。
② **禁止报幕式段首**：不得以「换个场景 / 最能说明 / 现在最常被提到 / 接下来 / 下面 /
   最后说 / 再说一个 / 回到 / 说回 / 我们来看 / 先说 / 另外一件事 / 同一时间 /
   同一年 / 值得注意的是」及同族表述**开头**。
③ **澄清拍降级**：解释性插入语（"严格说""也就是说""指的纯粹是"…）**每段至多 1 处**，
   且必须**顺嘴**带过，不得停下来做定义。**禁止**独立成段的定义/边界说明。
④ **Lean / mathlib 不得单独成段**，只能作为 Liquid Tensor Experiment 的情节要素带出。
⑤ 抽象概念紧跟**具体或世俗类比**；数字出现后紧邻给**人话翻译**。
⑥ 允许短句成段、口语松弛；**不追求**排比工整。

# 硬禁
· 元叙述/核查腔：回查/先不给/不给数字/必须标清楚/得先说/我会说清楚/要核原文/这一版 等。
· 推进词：换句话说／也就是说／值得注意的是／更重要的是／总而言之／综上所述／首先-其次-最后。
· 「不是A而是B」对称构式；设问自答对（「…吗？答案是…」）。
· **不得新增**任何节表与底账之外的年份、数字、人名、机构、刊物、定理名。
· AlphaGeometry（Nature 2024）与 IMO 2024 的 AlphaProof / AlphaGeometry 2 **不得混写**。
· 片尾 CTA 必须是全文最后一句：「你要是手上有不一样的一手材料，发出来，比点赞有用。」

# 长度
口播 **550–700 秒**（约 **2,700–3,400 字**），**9 段**（每拍一段）。

# 输出格式（严格 JSON，不要围栏）
{
 "title": "…",
 "paragraphs": [
   {"id": "P01", "beat": "B1", "text": "……",
    "hook_sentence": "本段末句（原文照抄）",
    "answers_previous_hook": "本段首句如何承接上一段末句的钩子（说明）"},
   …（P01–P09）
 ],
 "spine_check": "一句话说明全文如何只回答『凭什么信』"
}"""


def main() -> int:
    load_env(R / ".env")
    cfg = json.loads((R / "config/config.json").read_text(encoding="utf-8"))
    llm = cfg["llm"]
    key = os.environ.get(llm["deepseek"]["api_key_env"])
    pr = llm["pricing"][llm["tiers"]["F"]["model"]]["off_peak"]

    sheet = json.loads(SHEET.read_text(encoding="utf-8"))
    v52 = json.loads(V52.read_text(encoding="utf-8"))
    v52_text = "\n\n".join("【{}】{}".format(p["id"], p["text"])
                           for p in v52["paragraphs"])
    v41 = json.loads(V41.read_text(encoding="utf-8"))
    ref = "\n".join(REF.read_text(encoding="utf-8").splitlines()[:50])
    beats_txt = "\n".join(
        "{id}｜{title}\n  事件: {ev}\n  人物: {cast}\n  钩子: {hook}".format(
            id=b["id"], title=b["title"], ev=b["event"],
            cast="、".join(b["cast"]) or "—", hook=b["hook"])
        for b in sheet["beats"])

    user = """# 九拍节表（**必须逐拍对应 9 段**）
{beats}

# 事实底账：v5.2 全文（数字/实体/类比的唯一来源）
{v52}

# 王骁参照文本（**仅学机制，禁止抄任何句子**）
{ref}

# 任务
按九拍节表，**一次性整体重写**成 v6（9 段，2,700–3,400 字）。
关键：这不是把 v5.2 改句子，而是**照节表重排骨架**。每段末句写钩子，
下一段开头**直接承接**那个钩子。\n**每段（末段除外）的最后一句必须是一个明确的问题句（以「？」结尾）或含「——」的未决句**，\n不要把钩子写成陈述性的收尾（例如「没人接得住。」这种不算）。只输出严格 JSON。""".format(
        beats=beats_txt, v52=v52_text, ref=ref)

    doc = None
    content, cost, usage = "", 0.0, {}
    for attempt in range(1, 4):
        body = json.dumps({
            "model": llm["tiers"]["F"]["model"],
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": user}],
            "max_tokens": 16000, "temperature": 0.75,
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
        content = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
        usage = j.get("usage") or {}
        cost += (usage.get("prompt_tokens", 0) * pr["cache_miss"]
                 + usage.get("completion_tokens", 0) * pr["output"]) / 1_000_000
        try:
            doc = json.loads(content)
        except Exception as exc:                                            # noqa: BLE001
            print("第 {} 轮 JSON 解析失败: {}".format(attempt, exc))
            continue
        paras = doc.get("paragraphs") or []
        chars = sum(len(re.sub(r"\s", "", p.get("text") or "")) for p in paras)
        print("第 {} 轮: {} 段 | {} 字 | 预估 {:.0f}s | {:.1f}s | ${:.6f}".format(
            attempt, len(paras), chars, chars / 4.9, time.time() - t0, cost))
        if len(paras) == 9 and 2700 <= chars <= 3400:
            break
        user += ("\n\n# 上一轮不合格\n上一轮 {} 段、{} 字。要求**恰好 9 段**且 "
                 "**2,700–3,400 字**。请重写，保持节表与铁律不变。".format(
                     len(paras), chars))
    if doc is None:
        (R / "output/p36_probe").mkdir(parents=True, exist_ok=True)
        (R / "output/p36_probe/v6_raw.txt").write_text(content, encoding="utf-8")
        print("全部轮次失败，原始输出已存")
        return 1

    paras = doc["paragraphs"]
    print()
    for p in paras:
        t = re.sub(r"\s", "", p.get("text") or "")
        print("  {} [{}] {:>4} 字 | 末句: {}".format(
            p.get("id"), p.get("beat"), len(t), (p.get("text") or "")[-34:]))
    doc["_meta"] = {"model": llm["tiers"]["F"]["model"], "usage": usage,
                    "cost_usd": round(cost, 6), "attempts": attempt,
                    "paragraphs": len(paras),
                    "chars": sum(len(re.sub(r"\s", "", p["text"])) for p in paras),
                    "beatsheet": "docs/regression_2x/logs/phase36_beatsheet.json"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v6_fulltext.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    print()
    print("-> " + str((OUT / "v6_fulltext.json").relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

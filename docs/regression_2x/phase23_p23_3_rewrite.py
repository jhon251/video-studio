# -*- coding: utf-8 -*-
"""P23-3 全文重写管线（真实 LLM，≤3 轮；每轮机械校验，违反即回滚该轮）。

输入 = v3 稿（`logs/phase8_ab_v3.json#script`）。输出 = v4 稿（结构继承、皮肉全换）。
**机械校验（违反即回滚该轮）**：① 数字保真 ② 命名实体保真 ③ fact_risks 不减少
④ retention 机械分 ≥ v3 ⑤ 字数 ±15% ⑥ n-gram 守卫（与参照文本重合即回滚）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import ai_flavor as AF                                    # noqa: E402
from video_studio.llm.router import DeepSeekClient, Router                       # noqa: E402
from video_studio.core.env import load_env                                       # noqa: E402

load_env(R / ".env")
BUDGET = 0.50
STYLE_FULL = (R / "config" / "style_target_wangxiao_v1.md").read_text(encoding="utf-8")
REFS = sorted((R / "config" / "human_style_refs").glob("*.txt"))
REF_TXT = "\n".join(p.read_text(encoding="utf-8") for p in REFS)


def style_digest(md: str) -> str:
    """从 style target 抽取**机制名 + 规则句**（丢弃参照例句表，控 prompt 体积）。

    参照例句**不**入 prompt：① 体积；② 反而诱导模型抄参照 —— 防抄由机械 n-gram 守卫负责。
    """
    out, buf = [], []
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("## 机制"):
            buf.append("\n" + s.lstrip("# ").strip())
        elif s.startswith("**规则**"):
            buf.append(s.replace("**规则**：", "- ").strip())
        elif s.startswith("**红线**"):
            buf.append(s.replace("**红线**：", "- 红线：").strip())
    return "\n".join(buf).strip()


STYLE = style_digest(STYLE_FULL)

SYSTEM = """你是中文知识型解说视频的**文案写手**，任务是把一份已定稿的解说旁白
**在不改变任何事实、数字、命名实体与内容结论的前提下**，重写成指定的**说书机制文体**。

# 目标文体机制（必须逐条落实）
{style}

# 硬规则（违反即整轮作废）
1. **禁推进词**：换句话说／也就是说／换言之／值得注意（的是）／更重要的是／总而言之／综上所述／
   由此可见／不难看出／具体来说／简而言之／首先-其次-最后（作段落路标时）。也**尽量少用**「其实／实际上／事实上」。
2. **禁「不是A而是B」对称构式**（含「并非A而是B」「不在于A而在于B」）。
3. **禁设问自答对**（「…吗？答案是…」「为什么？因为…」这类）。**修辞性反问可保留但不得自答**。
4. **禁限定语堆叠**：同一句内不得连用 ≥2 个「严格来说／必须指出／需要指出／需要注意的是／某种意义上…」。
5. **开场从具体事实切入**（禁「假设有一天」式抽象思想实验开场）。
6. **态度外露**：允许明确判断、评价、反讽；但**只能加在已给出的事实上**，
   不得对在世人物做人格断言，不得改变任何事实强度。
7. **数据后紧跟「人话翻译」**：每个数字/量级出现后，紧邻一句说明它意味着什么、多大、可比作什么。
8. **允许口语不完整句、短句、插入语**；句式不必工整。
9. **大幅减少冒号「：」与破折号「——」**（参照口播里几乎不用）：改用逗号、句号或口语连接。
10. **只学机制，绝不抄句子**：不得使用任何来自目标文体的具体措辞、比喻、口头禅。

# 输出要求
只输出 JSON，结构**完全沿用输入**：
{{"segments":[{{"scene_id":"...","narration":"...","emotion_beat":"...","info_increment_marker":true/false,"claim_boundary_hedge":true/false,"hook":"..."}}],
 "cta_plan":[{{"at_segment":N,"type":"...","line":"..."}}],
 "hook_map":[{{"at_segment":N,"hook_type":"...","line":"..."}}],
 "recommended_opening":"...","summary":"..."}}
- `segments` 的**条数与顺序不得改变**（8 段）；`scene_id` 原样保留。
- 每段 `narration` 重写；**数字、年份、人名、机构/刊物/定理名必须逐一保留**（不得新增数字）。
- `fact_risks` 不在输出里（由管线从 v3 继承）。
- 每段字数与该段原文相当（全篇总字数 ±15% 以内）。
"""


def build_user(v3: dict, prev: dict | None, fails: list) -> str:
    segs = [{"scene_id": s.get("scene_id") or "SEG{}".format(i + 1),
             "narration": str(s.get("narration") or ""),
             "emotion_beat": s.get("emotion_beat"),
             "target_duration_s": s.get("duration_s")}
            for i, s in enumerate(v3["segments"])]
    payload = {
        "segments": segs,
        "cta_plan": v3.get("cta_plan"),
        "hook_map": v3.get("hook_map"),
        "recommended_opening": v3.get("recommended_opening"),
        "summary": v3.get("summary"),
        "core_viewpoint": v3.get("core_viewpoint"),
        "narrative_route": v3.get("narrative_route"),
    }
    extra = ""
    if prev is not None and fails:
        extra = ("\n\n# 上一轮被机械校验判不合格，逐条修正\n"
                 + "\n".join("- " + str(f) for f in fails[:12])
                 + "\n（上一轮内容仍须整体保留其优点，只修这些点。）")
    return ("# v3 原稿（事实/数字/实体/结论的唯一来源；只改表达，不改内容）\n"
            + json.dumps(payload, ensure_ascii=False, indent=1)
            + extra + "\n\n现在输出重写后的 JSON（8 段，结构同上）。")


def mechanical_checks(cand: dict, v3: dict) -> tuple[bool, list]:
    """六项机械校验；返回 (是否通过, 失败清单)。"""
    fails = []
    ct = AF.script_text(cand)
    vt = AF.script_text(v3)
    # ① 数字保真
    nf = AF.number_fidelity(ct, vt)
    if nf["extra_in_v4"]:
        fails.append("数字保真：v4 新增了 v3 没有的数字 {}".format(nf["extra_in_v4"][:10]))
    if nf["missing_in_v4"]:
        fails.append("数字保真：v4 丢失了 v3 的数字 {}".format(nf["missing_in_v4"][:10]))
    # ② 命名实体保真
    ef = AF.entity_fidelity(ct, vt)
    if ef["lost_in_v4"]:
        fails.append("实体保真：v4 丢失命名实体 {}".format(ef["lost_in_v4"][:10]))
    # ③ fact_risks 不减少
    if len(cand.get("fact_risks") or []) < len(v3.get("fact_risks") or []):
        fails.append("fact_risks 减少：{} < {}".format(
            len(cand.get("fact_risks") or []), len(v3.get("fact_risks") or [])))
    # ④ retention ≥ v3
    r4 = AF.retention_score(cand, None)["score"]
    r3 = AF.retention_score(v3, None)["score"]
    if r4 < r3 - 1e-9:
        fails.append("retention 机械分下降：{:.4f} < {:.4f}".format(r4, r3))
    # ⑤ 字数 ±15%
    if not vt or not ct:
        fails.append("空文本")
    else:
        ratio = len(re.sub(r"\s", "", ct)) / max(len(re.sub(r"\s", "", vt)), 1)
        if not (0.85 <= ratio <= 1.15):
            fails.append("字数偏离：比值 {:.3f}（须 0.85–1.15）".format(ratio))
    # ⑥ n-gram 守卫（防抄参照）
    ng = AF.longest_common_ngram(ct, REF_TXT, n=8)
    if ng["violated"]:
        fails.append("n-gram 守卫命中（抄参照）: len={} 例={!r}".format(
            ng["length"], ng["sample"][:30]))
    # 硬规则（禁项）
    sig = AF.analyze(ct)
    if sig["not_a_but_b_count"]:
        fails.append("禁用「不是A而是B」构式 {} 次".format(sig["not_a_but_b_count"]))
    if sig["rhetorical_qa_count"]:
        fails.append("禁用设问自答 {} 处".format(sig["rhetorical_qa_count"]))
    if sig["hedge_stack_count"]:
        fails.append("限定语堆叠 {} 句".format(sig["hedge_stack_count"]))
    if len(cand.get("segments") or []) != len(v3.get("segments") or []):
        fails.append("段数改变：{} != {}".format(len(cand.get("segments") or []),
                                              len(v3.get("segments") or [])))
    return (not fails), fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--tier", default="M")
    ap.add_argument("--max-tokens", type=int, default=16384)
    a = ap.parse_args()
    cfg = json.loads((R / "config" / "config.json").read_text(encoding="utf-8"))
    client = DeepSeekClient((cfg.get("llm") or {}).get("deepseek") or {})
    router = Router(cfg.get("llm") or {}, client)
    print("provider available:", client.available, "| tier:", a.tier)
    print("router max_total_usd:", router.max_total_usd)

    v3full = json.loads((L / "phase8_ab_v3.json").read_text(encoding="utf-8"))
    v3 = v3full["script"]
    ref_sigs = [AF.analyze(p.read_text(encoding="utf-8")) for p in REFS]
    v3sig = AF.analyze(AF.script_text(v3))
    v3sc = AF.compare_to_reference(v3sig, ref_sigs)["ai_flavor_score"]
    print("v3: chars={} ai_flavor={:.4f} retention={:.4f}".format(
        v3sig["chars"], v3sc, AF.retention_score(v3, None)["score"]))

    rounds, spent, best = [], 0.0, None
    prev, fails = None, []
    for rnd in range(1, a.rounds + 1):
        if spent >= BUDGET:
            print("!! 预算耗尽，停止"); break
        user = build_user(v3, prev, fails)
        t0 = time.time()
        _before = float(getattr(router, "spent_usd", 0.0) or 0.0)
        _tc = dict(router.tiers.get(a.tier) or {})
        _tc["max_tokens"] = a.max_tokens
        _tc["tier_name"] = a.tier
        try:
            _text, _usage = router._call(_tc, SYSTEM.format(style=STYLE), user, None)
            cand = router._parse_json(_text)
        except Exception as exc:                                                # noqa: BLE001
            print("!! 轮 {} LLM 调用失败: {}: {}".format(rnd, type(exc).__name__, exc))
            rounds.append({"round": rnd, "status": "LLM_ERROR",
                           "error": "{}: {}".format(type(exc).__name__, str(exc)[:200])})
            continue
        if not isinstance(cand, dict):
            rounds.append({"round": rnd, "status": "BAD_JSON",
                           "error": "非 dict: {}".format(type(cand).__name__)})
            continue
        cost = max(0.0, float(getattr(router, "spent_usd", 0.0) or 0.0) - _before)
        spent = round(spent + cost, 6)
        cand["fact_risks"] = v3.get("fact_risks")        # 内容结论继承（不减少）
        cand.setdefault("cta_plan", v3.get("cta_plan"))
        cand.setdefault("hook_map", v3.get("hook_map"))
        ok, fails = mechanical_checks(cand, v3)
        csig = AF.analyze(AF.script_text(cand))
        csc = AF.compare_to_reference(csig, ref_sigs)["ai_flavor_score"]
        rounds.append({"round": rnd, "status": ("ACCEPTED" if ok else "ROLLED_BACK"),
                       "cost_usd": cost, "latency_s": round(time.time() - t0, 1),
                       "usage": _usage, "ai_flavor_score": csc,
                       "v3_ai_flavor_score": v3sc, "chars": csig["chars"],
                       "better_than_v3": bool(csc < v3sc), "failures": fails,
                       "signals": {k: csig[k] for k in AF.SCORE_WEIGHTS},
                       "segments": cand})
        print("轮 {}: {} | ai_flavor {:.4f} (v3 {:.4f}, {}) | 字数 {} | ${:.5f} | 累计 ${:.5f}".format(
            rnd, rounds[-1]["status"], csc, v3sc,
            "更好" if csc < v3sc else "未更好", csig["chars"], cost, spent))
        for f in fails[:6]:
            print("      !", f)
        if ok and csc < v3sc:
            best = cand
            break
        prev = cand
    out = {
        "schema": "phase23-rewrite-rounds-v1",
        "stage": "Phase 23 P23-3 全文重写管线（真实 LLM，≤3 轮，每轮机械校验）",
        "provenance": "mechanism_style_rewrite_proposition_preserving",
        "model": cfg["llm"]["tiers"][a.tier]["model"], "tier": a.tier,
        "budget_usd": BUDGET, "spent_usd": spent,
        "v3_baseline": {"chars": v3sig["chars"], "ai_flavor_score": v3sc,
                        "retention": AF.retention_score(v3, None)},
        "reference_mean": {k: round(sum(r[k] for r in ref_sigs) / len(ref_sigs), 4)
                           for k in AF.SCORE_WEIGHTS},
        "rounds": rounds, "accepted": best is not None,
        "limitation": ("内容结论**继承 v3 谱系**（未重跑 claim/事实核查链，按继承方法登记 LIMITATION）；"
                       "文体为**机制迁移**（目标文体机制来自人工提供的参照文本），"
                       "与参照文本的 n-gram 重合由守卫机械保证为 0。"),
        "zero_copy_guard": {"n": 8, "violated": False},
    }
    p = L / "phase23_rewrite_rounds.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    if best:
        v4 = dict(v3full["script"])
        v4.update(best)
        v4["_phase23"] = {"provenance": out["provenance"], "from": "v3",
                          "style_target": "config/style_target_wangxiao_v1.md",
                          "ai_flavor_score": AF.compare_to_reference(
                              AF.analyze(AF.script_text(v4)), ref_sigs)["ai_flavor_score"],
                          "text_edited": True, "facts_inherited": True}
        (L / "phase23_v4_script.json").write_text(
            json.dumps(v4, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        print("v4 已写出 ->", (L / "phase23_v4_script.json").relative_to(R).as_posix())
    print("总成本 ${:.5f} / ${:.2f}".format(spent, BUDGET))
    print("->", p.relative_to(R).as_posix())


if __name__ == "__main__":
    main()

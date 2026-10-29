# -*- coding: utf-8 -*-
"""Phase 8 §4：**离线 A/B 回测（真实 LLM，deepseek-flash）** —— Creator Style v2 vs v3。

同一选题简报（取 p_96efdc03e1aa 已确认结构 + 已核查资料摘要），分别用：
  · **A 臂（v2）**：改动前的 script agent 提示词**逐字复现**（规范文本用 v2 快照）
  · **B 臂（v3）**：当前生产提示词（`ScriptAgent.system_prompt`，含 v3 规范与留存元数据纪律）
各生成 1 版脚本，落盘 `docs/regression_2x/logs/phase8_ab_v2.json` / `phase8_ab_v3.json`。

纪律：
  · 成本硬上限 **$0.30**（累计超限立即中止，不继续调用）；逐调用记录 tokens/费用/时延。
  · 两臂用**完全相同**的后处理指标规则（同一函数），不针对任一方定制指标。
  · 真实 LLM 输出**不声称确定性**（同一提示两次调用结果可能不同）——本产物是**证据日志**。
  · 只读既有产物（DB 以 mode=ro 打开）；不写任何生产产物。

运行: python docs/regression_2x/phase8_ab_run.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sqlite3
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.script.agent import OUTPUT_SCHEMA, ScriptAgent              # noqa: E402
from video_studio.core.env import load_env                                           # noqa: E402
from video_studio.llm.router import DeepSeekClient, Router, compute_cost, price_band  # noqa: E402

COST_LIMIT_USD = 0.30
MODEL = "deepseek-flash"
#: 预算诊断（真实实测，见 docs/regression_2x/PHASE8_REPORT.md）：
#:   `deepseek-flash` 是**推理模型**——`reasoning_content`（隐藏推理）与 `content`（答案）共享
#:   `max_tokens`。尝试 1（4096）两臂 reasoning 吃满 ⇒ content 空；尝试 2（8192）v3 仍吃满。
#:   故取 **M 档配置自身的上限 16384**（config/config.json 的 llm.tiers.M.max_tokens，
#:   **未修改任何档位配置**），并为 8-12 段规模留出推理+答案预算。
MAX_TOKENS = 16384
#: 尝试 3（16384）v2 成功（12 段合法），v3 仍被推理吃满（out=16385）。
#: 为保证**两臂可比**，只改**两臂共用**的任务行（缩小规模 + 显式抑制长篇推理）——
#: 任何针对单臂的定制都会破坏 A/B 公平性，因此**不做**。
TASK_LINE = ("按规范写出口播脚本（6-8 段，每段 60-90 秒）；"
             "直接给出 JSON，不要长篇推理或解释。")
LOGS = R / "docs" / "regression_2x" / "logs"
V2_SNAPSHOT = R / "docs" / "regression_2x" / "phase8_style_v2_snapshot.md"

#: A 臂提示词：改动前原文**逐字复现**（v2 规范 + 原输出要求，无 v3 字段）
V2_PROMPT_TEMPLATE = (
    "你是视频文案写手。严格按已确认的结构与资料写旁白/解说/台词，分场输出，"
    "每段标注语气、预估时长与画面提示。你不改结构、不改核心观点、不自行发明事实"
    "（存疑处写进 visual_hint 或省略）。\n\n"
    "## 创作规范（必须遵守）\n"
    "{guide}\n\n"
    "## 输出要求\n"
    "按上述规范第十一节输出完整格式，映射到 JSON 字段：\n"
    "topic_understanding=选题理解；core_viewpoint=核心观点；narrative_route=叙事路线；\n"
    "segments=正文分场口播稿（每段：chapter/narration/tone/duration_s/visual_hint）；\n"
    "titles=5个标题；opening_alternatives=3个开头备选；fact_risks=事实风险；\n"
    "recommended_title=推荐标题；recommended_opening=推荐开头。\n"
    "输出严格 JSON。"
)

#: A 臂 schema：把当前 schema 中的 v3 字段**移除**，复现改动前结构
def v2_schema() -> dict:
    s = json.loads(json.dumps(OUTPUT_SCHEMA))
    for f in ("cta_plan", "hook_map"):
        s["properties"].pop(f, None)
    for f in ("emotion_beat", "retention_device"):
        s["properties"]["segments"]["items"]["properties"].pop(f, None)
    return s


def sha_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def load_brief() -> dict:
    """从既有产物构造简报（只读）。首选目标选题的结构/资料产物。"""
    con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix() + "?mode=ro",
                          uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    try:
        rows = {}
        for t in ("structure_output", "research_output"):
            r = con.execute("select artifact_id,path,summary from artifacts where type=? and "
                            "project_id='p_96efdc03e1aa' order by created_at limit 1",
                            (t,)).fetchone()
            if r:
                rows[t] = dict(r)
    finally:
        con.close()
    if "structure_output" not in rows:
        raise SystemExit("FAIL-CLOSED: p_96efdc03e1aa 缺少 structure_output，无法构造同款简报")
    st = json.loads(pathlib.Path(rows["structure_output"]["path"]).read_text(encoding="utf-8"))
    chapters = st.get("chapters") or []
    lines = ["选题：AI 证明人类无法理解的数学（人类数学家还有意义吗）",
             "核心问题：" + (chapters[0].get("title") if chapters else "AI 证明无人能懂的数学"),
             "结构摘要：" + (st.get("summary") or "")[:400],
             "已确认章节树（标题 / 目标 / 规划时长 s）："]
    for c in chapters:
        lines.append("- {}｜{}｜{}s".format(c.get("title", ""), (c.get("goal") or "")[:160],
                                           c.get("duration_s")))
    srcs = []
    if "research_output" in rows:
        rs = json.loads(pathlib.Path(rows["research_output"]["path"]).read_text(encoding="utf-8"))
        lines.append("已核查资料线索：" + (rs.get("summary") or "")[:500])
        cards = rs.get("source_cards") or []
        lines.append("可用资料卡数量：{}（只用已核查资料；数字/引语不确定处写入 fact_risks）"
                     .format(len(cards)))
        srcs.append({"role": "research_output", "artifact_id": rows["research_output"]["artifact_id"],
                     "sha256": hashlib.sha256(
                         pathlib.Path(rows["research_output"]["path"]).read_bytes()).hexdigest()})
    srcs.append({"role": "structure_output", "artifact_id": rows["structure_output"]["artifact_id"],
                 "sha256": hashlib.sha256(
                     pathlib.Path(rows["structure_output"]["path"]).read_bytes()).hexdigest()})
    return {"brief": "\n".join(lines), "sources": srcs}


# ---------------------------------------------------------------- 指标（两臂同一规则）
BARE_CTA = ("感谢观看", "一键三连", "记得点赞", "点赞关注", "关注我", "我们下期再见", "评论区告诉我",
            "别忘了三连", "求个三连")
CONFLICT_MARKERS = ("但", "然而", "其实", "反而", "矛盾", "反转", "问题", "为什么", "居然", "竟然",
                    "并非", "不是", "？", "?")
ANCHOR_RE = re.compile(r"(\d{4}|\d+\s*(年|篇|页|小时|天|%|％|倍|万|亿))")
HEDGE_MARKERS = ("可能", "尚无", "仍在", "推测", "争议", "不确定", "待查", "据", "或许")
INCREMENT_MARKERS = ("但", "其实", "真正", "反而", "代价", "限制", "关键", "问题在于", "然而",
                     "意外", "没想到")


def metrics(script: dict, raw_text: str) -> dict:
    segs = script.get("segments") or []
    narr = [str(s.get("narration") or "") for s in segs]
    first = narr[0] if narr else ""
    beats = [s.get("emotion_beat") for s in segs]
    valid_beats = [b for b in beats if b in ("curiosity", "tension", "payoff", "calm", "surprise")]
    cta_texts = [str((c or {}).get("line") or "") for c in (script.get("cta_plan") or [])]
    if not cta_texts:                                  # v2 无 cta_plan ⇒ 从正文找互动句（同一规则）
        cta_texts = [s for s in narr if any(m in s for m in BARE_CTA)
                     or any(k in s for k in ("想知道的看完", "看完", "评论区"))]
    bare = [t for t in cta_texts if any(m in t for m in BARE_CTA)]
    bound = [t for t in cta_texts if t not in bare and len(t) >= 12]
    increments = sum(1 for s in narr if any(m in s for m in INCREMENT_MARKERS))
    hedges = sum(1 for s in narr if any(m in s for m in HEDGE_MARKERS))
    risks = script.get("fact_risks") or []
    return {
        "json_valid": bool(script),
        "segments": len(segs),
        "declared_duration_s": round(sum(float(s.get("duration_s") or 0) for s in segs), 1),
        "hook_present_in_first_segment": bool(ANCHOR_RE.search(first))
                                         and any(m in first for m in CONFLICT_MARKERS),
        "hook_map_items": len(script.get("hook_map") or []),
        "emotion_beat_coverage": (round(len(valid_beats) / len(segs), 3) if segs else None),
        "retention_device_present": sum(1 for s in segs
                                        if str(s.get("retention_device") or "").strip()
                                        and s.get("retention_device") != "none"),
        "cta_count": len(cta_texts),
        "cta_bare_count": len(bare),
        "cta_content_bound_count": len(bound),
        "info_increment_marker_segments": increments,
        "claim_boundary_hedge_segments": hedges,
        "fact_risks_present": bool(risks),
        "fact_risks_count": len(risks),
        "narration_chars": sum(len(s) for s in narr),
        "raw_chars": len(raw_text),
    }


def parse_json(text: str) -> dict:
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:                                                   # noqa: BLE001
        i, j = t.find("{"), t.rfind("}")
        if i >= 0 and j > i:
            try:
                return json.loads(t[i:j + 1])
            except Exception:                                           # noqa: BLE001
                return {}
    return {}


def main() -> int:
    load_env(str(R / ".env"))
    cfg = json.loads((R / "config" / "config.json").read_text(encoding="utf-8"))
    client = DeepSeekClient(cfg["llm"]["deepseek"])
    if not client.available:
        print("FAIL-CLOSED: DEEPSEEK_API_KEY 不可用（.env / 环境变量）⇒ A/B 无法真实执行",
              file=sys.stderr)
        return 2
    brief = load_brief()
    v2_guide = V2_SNAPSHOT.read_text(encoding="utf-8")
    v3_system = ScriptAgent.system_prompt + Router._schema_hint(OUTPUT_SCHEMA)
    v2_system = (V2_PROMPT_TEMPLATE.format(guide=v2_guide)
                 + Router._schema_hint(v2_schema()))
    user = ("# 选题简报\n" + brief["brief"]
            + "\n\n# 任务\n" + TASK_LINE)

    arms = [("v2", v2_system, v2_schema(), V2_SNAPSHOT), ("v3", v3_system, OUTPUT_SCHEMA, None)]
    spent = 0.0
    out_paths = []
    summary_rows = []
    for label, system, schema, snap in arms:
        t0 = time.time()
        res = client.complete(MODEL, system, user, MAX_TOKENS)
        latency_ms = res.get("latency_ms", int((time.time() - t0) * 1000))
        usage = {k: res.get(k, 0) for k in ("prompt_tokens", "completion_tokens",
                                            "cache_hit_tokens", "cache_miss_tokens")}
        reasoning_tokens = int(res.get("reasoning_tokens") or 0)
        cost, band = compute_cost(res.get("model", MODEL), usage)
        spent += cost
        if spent > COST_LIMIT_USD:
            print("FAIL-CLOSED: 累计成本 ${:.4f} 超上限 ${:.2f} ⇒ 中止".format(spent, COST_LIMIT_USD),
                  file=sys.stderr)
            return 3
        script = parse_json(res.get("text", ""))
        m = metrics(script, res.get("text", ""))
        truncated = int(usage["completion_tokens"] or 0) >= MAX_TOKENS - 1
        content_empty = not (res.get("text") or "").strip()
        log = {
            "schema": "phase8-ab-arm-v1", "arm": label, "model": res.get("model", MODEL),
            "price_band": band, "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                                  time.gmtime()),
            "determinism_note": "真实 LLM 输出**不声称确定性**；本文件为证据日志",
            "output_truncated": truncated,
            "content_empty": content_empty,
            "reasoning_tokens": reasoning_tokens,
            "arm_status": ("EMPTY_CONTENT_REASONING_BUDGET" if content_empty
                           else "TRUNCATED" if truncated else "OK"),
            "attempt_note": ("尝试 1（4096）与尝试 2（8192）均因推理 token 吃满预算导致 content 为空，"
                             "已分别留档 phase8_ab_attempt1_truncated_*.json 与 "
                             "phase8_ab_attempt2_empty_*.json；本文件为尝试 3（16384 = M 档配置上限）"),
            "brief": brief["brief"], "brief_sources": brief["sources"],
            "style_guide": {"arm": "v3（当前 config/script_style_guide.md）" if label == "v3"
                            else "v2 快照（docs/regression_2x/phase8_style_v2_snapshot.md）",
                            "path": str((R / "config" / "script_style_guide.md"
                                         if label == "v3" else snap).relative_to(R)),
                            "sha256": sha_text(system)},
            "prompts": {"system_sha256": sha_text(system), "system_full": system,
                        "user_sha256": sha_text(user), "user_full": user},
            "output_schema_sha256": sha_text(json.dumps(schema, ensure_ascii=False,
                                                        sort_keys=True)),
            "usage": usage, "cost_usd": round(cost, 6), "cumulative_cost_usd": round(spent, 6),
            "latency_ms": latency_ms, "max_tokens": MAX_TOKENS,
            "json_valid": bool(script), "script": script, "raw_text": res.get("text", ""),
            "metrics": m,
        }
        p = LOGS / "phase8_ab_{}.json".format(label)
        p.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
        out_paths.append(p)
        summary_rows.append((label, m, cost, usage, latency_ms))
        print("[{}] json_valid={} truncated={} segments={} cost=${:.5f} tokens_in={} out={} "
              "latency={}ms".format(label, bool(script), truncated, m["segments"], cost,
                                    usage["prompt_tokens"], usage["completion_tokens"],
                                    latency_ms))

    print("\n=== A/B 对比（同一指标规则）===")
    keys = ["hook_present_in_first_segment", "hook_map_items", "emotion_beat_coverage",
            "retention_device_present", "cta_count", "cta_bare_count", "cta_content_bound_count",
            "info_increment_marker_segments", "claim_boundary_hedge_segments", "fact_risks_present",
            "fact_risks_count", "segments", "declared_duration_s", "narration_chars"]
    for k in keys:
        print("  {:34s} v2={!s:>8s}  v3={!s:>8s}".format(
            k, str(summary_rows[0][1].get(k)), str(summary_rows[1][1].get(k))))
    print("  总成本 ${:.5f}（上限 ${:.2f}）".format(spent, COST_LIMIT_USD))
    print("  产物:", ", ".join(str(x.relative_to(R)) for x in out_paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())

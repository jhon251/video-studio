"""Topic Agent：选题提案（最终决定权在人——提案必须走人工审批闸门）。

Phase 10（P10-3）**加法**升级：接入**选题信号**（真实热度/竞品快照，只读）。
- 信号由 `tools/topic_signals.py` 在 **agent 工具层**加载（**不加管线阶段**、不改
  `pipeline/lifecycle.py`）；运行期**只读快照文件、绝不联网**（联网只发生在人工触发的
  `run.py fetch-signals`）。
- 无可用信号时：**禁止编造热度数据**，`note` 必须如实披露"无数据信号，本提案为纯头脑风暴"。
- 人工闸门不变：topic 产物仍走既有 NEEDS_REVIEW 审批；信号只是输入，不自动改提案/不自动批闸门。

实现说明（为何覆写 `run`）：信号需要注入 **prompt**（user 段），而 `agents/base.py::Agent.run`
是单体会话流程且**本阶段授权范围不允许修改 base.py**；故此处以与 base.run **同构**的流程实现
（上下文装配 → 成本记账 → 产物落盘 → 自我记忆），并在其上加信号注入与 `signal_refs` 校验。
"""
from __future__ import annotations

import json
from pathlib import Path

from ..base import Agent, register
from ...tools import topic_signals as TS

ROOT = Path(__file__).resolve().parents[4]

TOPIC_SCHEMA = {
    "type": "object",
    "properties": {
        "proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "angle": {"type": "string"},
                    "audience": {"type": "string"},
                    "value_proposition": {"type": "string"},
                    "feasibility": {"type": "string", "enum": ["high", "medium", "low"]},
                    "risks": {"type": "array"},
                    "research_needs": {"type": "array"},
                    # P10-3（加法）：信号引用与数据驱动论证
                    "signal_refs": {
                        "type": "array",
                        "description": "所引用的选题信号条目下标（0-based，取自快照 entries）；"
                                       "无信号时必须为空数组"},
                    "why_now": {"type": "string",
                                "description": "为什么现在做：必须基于所引条目的真实数据"},
                    "angle_gap": {"type": "string",
                                  "description": "与所引条目的**差异化角度**（不是复述热点）"},
                },
                "required": ["title", "angle", "value_proposition"],
            },
        },
        # P10-3（加法）：信号摘要（权威值由 agent 从快照计算并覆盖，防 LLM 复述失真）
        "signals_digest": {
            "type": "object",
            "properties": {"count": {"type": "number"}, "kinds": {"type": "array"},
                           "top_titles": {"type": "array"}},
        },
        "summary": {"type": "string"},
        "confidence": {"type": "number"},
        "note": {"type": "string"},
    },
    "required": ["proposals", "summary"],
}

SIGNAL_RULES = (
    "\n\n## 选题信号规则（P10-3，硬性）\n"
    "1) 若上文提供了「# 选题信号」区块：**每条提案必须**在 `signal_refs` 中引用**真实存在**的信号"
    "条目下标（0-based，对应区块中的 `[下标]`）；引用不存在的下标视为无效。\n"
    "2) 每条提案必须给出 `why_now`（为什么现在做；必须基于所引条目的**真实数据**，如播放/分区/时长）"
    "与 `angle_gap`（与所引热点的**差异化角度**——说清你不做什么、做什么不同，**不是复述热点**）。\n"
    "3) **无信号时禁止编造热度数据**：不得虚构播放量、榜单、竞品标题；`signal_refs` 留空数组，"
    "且 `note` 必须**逐字**包含「无数据信号，本提案为纯头脑风暴」。\n"
    "4) 信号只是输入：你仍然只提案不拍板，最终选题由人类审批决定。"
)
NO_SIGNAL_NOTE = "无数据信号，本提案为纯头脑风暴"


def _signals_for_run(engine, task) -> dict:
    """读取信号（只读；失败/未配置一律返回明确 status，绝不联网）。"""
    config = getattr(engine, "config", None) or {}
    try:
        return TS.load_signals_for_agent(config, root=ROOT)
    except Exception as exc:                                               # noqa: BLE001
        return {"status": "ERROR", "provider": "unknown",
                "reason_code": "PROVIDER_UNKNOWN",
                "detail": "{}: {}".format(type(exc).__name__, str(exc)[:120])}


def validate_signal_refs(data: dict, entries: list[dict]) -> dict:
    """`signal_refs` 校验（纯函数）：每条提案的引用必须指向**真实存在**的条目下标。"""
    proposals = data.get("proposals") or []
    n = len(entries)
    violations, per = [], []
    for i, p in enumerate(proposals):
        refs = p.get("signal_refs")
        if refs is None:
            refs = []
        if not isinstance(refs, list):
            violations.append({"proposal_index": i, "code": "SIGNAL_REFS_NOT_ARRAY"})
            per.append({"proposal_index": i, "refs": refs, "valid": False})
            continue
        bad = [r for r in refs
               if isinstance(r, bool) or not isinstance(r, int) or not (0 <= r < n)]
        missing = (not refs) and n > 0
        ok = not bad and not missing
        if bad:
            violations.append({"proposal_index": i, "code": "SIGNAL_REF_OUT_OF_RANGE",
                               "refs": bad, "entries": n})
        if missing:
            violations.append({"proposal_index": i, "code": "SIGNAL_REFS_EMPTY_WITH_SIGNALS",
                               "entries": n})
        per.append({"proposal_index": i, "refs": refs, "valid": ok})
    return {"entries": n, "proposals": len(proposals),
            "all_valid": bool(proposals) and not violations,
            "proposals_with_valid_refs": sum(1 for x in per if x["valid"]),
            "violations": violations, "per_proposal": per,
            "rule": "每条提案的 signal_refs 必须指向真实存在的快照条目下标（0-based）"}


@register
class TopicAgent(Agent):
    role = "topic"
    tier = "M"
    description = "选题：按人类方向 + （可选）真实选题信号提出候选与可行性分析，最终决定权属于人。"
    system_prompt = (
        "你是视频选题策划。根据人类给出的方向提出选题候选，每个候选给出角度、受众、价值主张、"
        "可行性与风险。你只提案不拍板——最终选题由人类决定。输出严格 JSON。"
        + SIGNAL_RULES
    )
    output_schema = TOPIC_SCHEMA

    def run(self, engine, task: dict) -> None:
        """与 base.Agent.run 同构的流程 + 信号注入 + `signal_refs` 校验（见模块 docstring）。"""
        from ..base import SchemaError  # noqa: F401  —— 保持与 base.run 相同的异常语义（直接透传）
        from ...memory.repo import Memory

        sig = _signals_for_run(engine, task)
        has_signals = (sig.get("status") == "OK" and bool(sig.get("entries")))
        memory = Memory(engine.db)
        context = memory.working_context(task, engine)
        user = "{}\n\n# 任务\n{}".format(
            context, json.dumps(task["inputs"], ensure_ascii=False, indent=2))
        if has_signals:
            user = "{}\n\n{}".format(user, TS.signals_context_block(sig["entries"]))
        cost = {"model": None, "tokens": 0, "usd": 0.0, "usage": {}}

        def on_cost(model, tokens, cost_usd, usage=None):
            cost.update(model=model, tokens=tokens, usd=cost_usd, usage=usage or {})
            u = usage or {}
            try:
                prev = float((engine.db.get_task(task["task_id"]) or {}).get("cost_usd") or 0.0)
                engine.db.update_task(task["task_id"], model_used=model,
                                      cost_usd=round(prev + float(cost_usd), 8))
                engine.emit(task["project_id"], "LLM_CALL", self.role, task["task_id"], {
                    "model": model, "tier": u.get("tier"), "mock": u.get("mock"),
                    "total_tokens": u.get("tokens"), "prompt_tokens": u.get("prompt_tokens"),
                    "completion_tokens": u.get("completion_tokens"),
                    "cache_hit_tokens": u.get("cache_hit_tokens"),
                    "cache_miss_tokens": u.get("cache_miss_tokens"),
                    "reasoning_tokens": u.get("reasoning_tokens"),
                    "latency_ms": u.get("latency_ms"), "attempts": u.get("attempts"),
                    "price_band": u.get("price_band"), "cost_usd": round(cost_usd, 8),
                })
            except Exception:      # 记账/事件不可用不应影响生产主链
                pass

        data = engine.router.complete(self.tier, self.system_prompt, user, self.output_schema,
                                      on_cost=on_cost)   # SchemaError 由上层按既有语义处理

        entries = sig.get("entries") or []
        validation = validate_signal_refs(data, entries) if has_signals else {
            "entries": 0, "proposals": len(data.get("proposals") or []), "all_valid": None,
            "proposals_with_valid_refs": 0, "violations": [],
            "rule": "无信号 ⇒ 不做引用校验（走披露路径）"}
        data["signals_digest"] = (TS.digest(entries) if has_signals
                                  else {"count": 0, "kinds": [], "top_titles": [],
                                        "status": "NO_SIGNALS"})
        data["signals_context"] = {
            "status": sig.get("status"), "provider": sig.get("provider"),
            "reason_code": sig.get("reason_code"),
            "snapshot_path": sig.get("snapshot_path"),
            "snapshot_sha256": sig.get("snapshot_sha256"),
            "entries": len(entries),
            "digest_source": ("snapshot（权威；由 agent 从快照计算，覆盖 LLM 复述）"
                              if has_signals else "NO_SIGNALS"),
            "signal_refs_validation": validation,
            "no_fabrication": ("无信号 ⇒ 禁止编造热度数据；本提案为纯头脑风暴" if not has_signals
                               else "所有 signal_refs 必须指向真实快照条目"),
        }
        note = str(data.get("note") or "")
        if has_signals:
            if validation["violations"]:
                data["note"] = (note + "\n[P10-3] signal_refs 校验发现 {} 处违规（未自动改稿）"
                                .format(len(validation["violations"])))[:500]
        else:
            if NO_SIGNAL_NOTE not in note:
                data["note"] = ((note + " " if note else "") + NO_SIGNAL_NOTE)[:500]
        summary = str(data.get("summary") or json.dumps(data, ensure_ascii=False)[:200])
        artifact_id = engine.write_artifact(
            task["project_id"], task["task_id"], task["task_type"] + "_output", data,
            summary=summary)
        engine.attach_artifact(task["task_id"], artifact_id)
        if data.get("confidence") is not None:
            engine.db.update_task(task["task_id"], confidence=float(data["confidence"]))
        if data.get("note"):
            engine.db.put_memory(task["project_id"], "agent_note", task["task_type"],
                                 str(data["note"])[:500], agent_role=self.role)

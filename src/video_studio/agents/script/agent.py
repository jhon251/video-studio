"""Script Agent：文案/旁白——按已确认结构产出，不改结构不改观点。

风格规范：加载 config/script_style_guide.md（用户确认的全局创作标准）。
输出格式：选题理解 / 核心观点 / 叙事路线 / 正文(segments) / 5标题 / 3开头备选 / 事实风险。
"""

from __future__ import annotations

from pathlib import Path

from ..base import Agent, register

STYLE_GUIDE_PATH = Path(__file__).resolve().parents[4] / "config" / "script_style_guide.md"


def _load_style_guide() -> str:
    try:
        return STYLE_GUIDE_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""


EMOTION_BEATS = ("curiosity", "tension", "payoff", "calm", "surprise")


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "topic_understanding": {"type": "string"},       # 选题理解
        "core_viewpoint": {"type": "string"},            # 核心观点
        "narrative_route": {"type": "string"},           # 叙事路线
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chapter": {"type": "string"},
                    "narration": {"type": "string"},
                    "tone": {"type": "string"},
                    "duration_s": {"type": "number"},
                    "visual_hint": {"type": "string"},
                    # v3（加法）：留存元数据 —— 仅供结构核验/critic，**不入任何用户可见文本**
                    "emotion_beat": {"type": "string", "enum": list(EMOTION_BEATS)},
                    "retention_device": {"type": "string"},
                },
                "required": ["narration"],
            },
        },
        "titles": {"type": "array"},                     # 5 个标题
        "opening_alternatives": {"type": "array"},       # 3 个开头
        "fact_risks": {"type": "array"},                 # 事实风险
        # v3（加法）：留存结构元数据
        "cta_plan": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    # P10-1：语义**钉死为 0-based**（0 = 第一段）；越界 ⇒ 结构违规码
                    # CTA_AT_SEGMENT_OUT_OF_RANGE / CTA_AT_SEGMENT_INVALID（retention 机械层）
                    "at_segment": {"type": "number",
                                   "description": "0-based 段落下标（0 = 第一段）；"
                                                  "有效范围 0..segments.length-1"},
                    "type": {"type": "string"},
                    "line": {"type": "string"},
                },
                "required": ["at_segment", "type", "line"],
            },
        },
        "hook_map": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "opening": {"type": "string"},
                    "hook_type": {"type": "string"},
                },
                "required": ["hook_type"],
            },
        },
        "recommended_title": {"type": "string"},
        "recommended_opening": {"type": "string"},
        "summary": {"type": "string"},
        "confidence": {"type": "number"},
        "note": {"type": "string"},
    },
    "required": ["segments", "summary"],
}


@register
class ScriptAgent(Agent):
    role = "script"
    tier = "M"
    description = "文案：按已确认结构生成旁白/解说/台词，分场并标注画面提示。"
    system_prompt = (
        "你是视频文案写手。严格按已确认的结构与资料写旁白/解说/台词，分场输出，"
        "每段标注语气、预估时长与画面提示。你不改结构、不改核心观点、不自行发明事实"
        "（存疑处写进 visual_hint 或省略）。\n\n"
        "## 创作规范（必须遵守）\n"
        f"{_load_style_guide()}\n\n"
        "## 输出要求\n"
        "按上述规范输出完整格式，映射到 JSON 字段：\n"
        "topic_understanding=选题理解；core_viewpoint=核心观点；narrative_route=叙事路线；\n"
        "segments=正文分场口播稿（每段：chapter/narration/tone/duration_s/visual_hint/"
        "emotion_beat/retention_device）；\n"
        "titles=5个标题；opening_alternatives=3个开头备选；fact_risks=事实风险；\n"
        "cta_plan=1-2 条互动引导（每项：at_segment/type/line，必须与内容强绑定，禁止裸话术）；\n"
        "hook_map=3 个开头备选各自的钩子类型（每项：opening/hook_type）；\n"
        "recommended_title=推荐标题；recommended_opening=推荐开头。\n\n"
        "## 留存元数据纪律（v3，硬性）\n"
        "1) emotion_beat 每段必填，取值只能是 "
        + "/".join(EMOTION_BEATS) + "；全篇不得连续 3 个同类节拍。\n"
        "2) retention_device 每段填写该段承担的留存装置（信息增量点/悬念/反转/兑现），"
        "与规范 2.1「每 60-90 秒一个信息增量点」对应；没有就写 none，不得编造。\n"
        "3) **新增字段（emotion_beat / retention_device / cta_plan / hook_map）是元数据，"
        "绝不写进 narration 文本本身**：narration 里不得出现节拍名、钩子类型、"
        "CTA 标签或任何字段名；观众只会看到自然的口播。\n"
        "4) 不得为留存牺牲红线：不造假钩子、不夸大证据、不把推测写成事实。\n"
        "输出严格 JSON。"
    )
    output_schema = OUTPUT_SCHEMA

    def run(self, engine, task: dict) -> None:
        """**人工审稿优先**（2026-10-20）：若项目里存在 `media/script_review.json`
        （由 `run.py script-apply` 写入），则**不调 LLM**，直接以人工稿落产物。

        为什么：工程内没有梗/幽默的生产者，人的判断只能从这里进入流程；
        走"文件 + 新版本任务"的既有链路，`redo` 才能稳定复现人改过的稿。
        """
        try:
            from ...core import script_review as SR
            pdir = engine.project_dir(task["project_id"])
            reviewed = SR.load_review(pdir)
        except Exception:                                   # noqa: BLE001
            reviewed = None
        if not reviewed:
            return super().run(engine, task)
        data = dict(reviewed)
        data["source"] = "human_review"
        meta = dict(data.get("human_review") or {})
        data["summary"] = str(meta.get("notes") or
                              "人工审稿稿（{} 段）".format(len(data.get("segments") or [])))[:200]
        aid = engine.write_artifact(task["project_id"], task["task_id"],
                                    task["task_type"] + "_output", data,
                                    summary=data["summary"])
        engine.attach_artifact(task["task_id"], aid)
        try:
            engine.emit(task["project_id"], "SCRIPT_HUMAN_REVIEW", self.role,
                        task["task_id"],
                        {"segments": len(data.get("segments") or []),
                         "checklist": meta.get("checklist"),
                         "stats": meta.get("stats"),
                         "rule": "人工审稿稿优先于 LLM；redo 后仍生效"},
                        human_visible=True)
        except Exception:                                   # noqa: BLE001
            pass

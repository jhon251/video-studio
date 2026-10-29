"""Audio Agent：音频生产（响度标准化/混音方案）。V1：产出混音方案（确定性）。

Phase 3-B 起：方案里的目标值**取自 `core.audio` 的响度契约**（单一事实源），
并如实标注"母带链在渲染阶段由工具层真实执行"与"本阶段不做 BGM"——不写做不到的事。
"""

from ..base import Agent, register
from ...core.audio import (LOUDNESS_CONTRACT, limiter_filter, loudnorm_filter,
                           mastering_chain)


@register
class AudioAgent(Agent):
    role = "audio"
    tier = "-"
    needs_llm = False
    description = "音频：响度标准化与混音方案。不生成旁白（Voice 负责）。"

    def run(self, engine, task: dict) -> None:
        c = LOUDNESS_CONTRACT
        plan = {
            "targets": {
                "loudness": "{} LUFS".format(int(c["target_lufs"])),
                "true_peak": "{} dBTP".format(c["max_true_peak_dbtp"]),
                "tolerance_lu": c["tolerance_lu"],
                "target_lra": c["target_lra"],
            },
            "audio_chain": mastering_chain(),
            "chain_parts": {"loudnorm": loudnorm_filter(), "limiter": limiter_filter()},
            "steps": ["normalize", "limit", "master", "verify"],
            "summary": "混音方案：{} LUFS 标准化（±{} LU）+ 真峰 ≤ {} dBTP，渲染后实测校验".format(
                int(c["target_lufs"]), c["tolerance_lu"], c["max_true_peak_dbtp"]),
            "verification": {
                "method": c["method"],
                "policy": c["policy"],
                "enforced_at": "render（成片实测；不达标 fail-closed）",
            },
            "bgm": {"implemented": False,
                    "note": "本阶段（3-B）不做 BGM；交付音频=旁白母带（授权边界）"},
            "confidence": 1.0,
            "note": "方案即契约；响度母带链（loudnorm + alimiter）在渲染阶段真实执行，"
                    "并对成片用 ffmpeg ebur128 实测判定。",
        }
        aid = engine.write_artifact(task["project_id"], task["task_id"], "audio_plan",
                                    plan, summary=plan["summary"])
        engine.attach_artifact(task["task_id"], aid)
        engine.db.update_task(task["task_id"], confidence=1.0)

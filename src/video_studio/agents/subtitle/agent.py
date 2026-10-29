"""Subtitle Agent：字幕（V1：按脚本分段时间轴生成 SRT；ASR 在 provider 就绪后启用）。"""

from __future__ import annotations

import json

from ..base import Agent, register


def ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


@register
class SubtitleAgent(Agent):
    role = "subtitle"
    tier = "-"
    needs_llm = False
    description = "字幕：生成、校对、时间轴。不修改旁白内容，不负责烧录。"

    def run(self, engine, task: dict) -> None:
        segments = []
        for dep in task.get("dependencies", []):
            dep_task = engine.db.get_task(dep)
            for art_id in dep_task.get("artifacts", []):
                art = engine.db.get_artifact(art_id)
                if art["type"] == "script_output":
                    with open(art["path"], encoding="utf-8") as fh:
                        segments = json.load(fh).get("segments", [])
                    break
        from ...core.strip import strip_claims  # V2：用户可见字幕必须剥离标记
        from ...core.captions import build_cues, to_srt
        # 5-M：由"每段一条整段文案"改为**逐条字幕**（切分/折行/时间分配统一由 core.captions 负责）
        payload = [{"narration": strip_claims(s.get("narration", "")), "duration_s": s.get("duration_s")}
                   for s in segments]
        cues = build_cues(payload)
        srt = to_srt(cues)
        data = {"srt": srt, "segments": len(segments), "cues": len(cues),
                "summary": "字幕初稿：{} 段 → {} 条字幕（脚本时基，底部居中烧录）".format(
                    len(segments), len(cues)),
                "confidence": 0.9,
                "note": "V1 脚本时基；ASR 对轴待 asr provider 配置；切分/折行/时间分配见 core.captions"}
        aid = engine.write_artifact(task["project_id"], task["task_id"], "subtitle",
                                    data, summary=data["summary"])
        engine.attach_artifact(task["task_id"], aid)
        # 同时落 .srt 文件（供剪辑工具烧录）
        (engine.project_dir(task["project_id"]) / "artifacts" / f"{aid}.srt").write_text(srt, encoding="utf-8")
        engine.db.update_task(task["task_id"], confidence=0.9)

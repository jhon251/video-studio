"""QA Agent：最终质检。V1：技术质检（FFprobe 探测成片）+ 内容核对清单。

技术项为确定性检查（无 LLM）；内容核对在 V2 引入 M 档辅助。
"""

from __future__ import annotations

from ..base import Agent, register


@register
class QAAgent(Agent):
    role = "qa"
    tier = "M"
    needs_llm = False
    description = "最终质检：技术验收（音画/时长/编码）+ 内容核对。验收独立于生产岗。"

    def run(self, engine, task: dict) -> None:
        from ...tools.ffmpeg_tool import FFmpegTool
        from ...tools.base import ToolContext, ToolError

        # 找 render 产物
        render_path = None
        for dep in task.get("dependencies", []):
            dep_task = engine.db.get_task(dep)
            for art_id in dep_task.get("artifacts", [])[::-1]:
                art = engine.db.get_artifact(art_id)
                if art["type"] == "render_output":
                    import json as _json
                    with open(art["path"], encoding="utf-8") as fh:
                        render_path = _json.load(fh).get("output")
                    break
            if render_path:
                break

        checks = []
        verdict = "pass"
        if render_path is None:
            checks.append({"item": "render_output", "result": "missing", "detail": "未找到成片产物"})
            verdict = "fail"
        else:
            ctx = ToolContext(role="qa", project_id=task["project_id"],
                              project_dir=engine.project_dir(task["project_id"]),
                              db=engine.db, config=engine.config)
            try:
                probe = FFmpegTool().execute({"op": "probe", "inputs": [render_path]}, ctx)
                streams = probe.data["streams"]
                has_video = any(s["codec_type"] == "video" for s in streams)
                has_audio = any(s["codec_type"] == "audio" for s in streams)
                duration = max((float(s.get("duration") or 0) for s in streams), default=0)
                checks += [
                    {"item": "video_stream", "result": "ok" if has_video else "fail", "detail": "存在视频流"},
                    {"item": "audio_stream", "result": "ok" if has_audio else "warn", "detail": "存在音频流"},
                    {"item": "duration", "result": "ok" if duration > 0 else "fail",
                     "detail": f"时长 {duration:.2f}s"},
                ]
                if not has_video or duration <= 0:
                    verdict = "fail"
            except ToolError as exc:
                checks.append({"item": "probe", "result": "deferred", "detail": str(exc)[:120]})
                verdict = "fail"

        data = {"verdict": verdict, "checks": checks,
                "summary": f"QA 结论: {verdict}（{len(checks)} 项检查）",
                "confidence": 1.0, "note": "V1 技术质检；内容核对人工执行"}
        aid = engine.write_artifact(task["project_id"], task["task_id"], "qa_report",
                                    data, summary=data["summary"])
        engine.attach_artifact(task["task_id"], aid)
        engine.db.update_task(task["task_id"], confidence=1.0)
        if verdict == "fail":
            engine.emit(task["project_id"], "QA_FAILED", "qa", task["task_id"],
                        {"checks": len(checks)}, human_visible=True)

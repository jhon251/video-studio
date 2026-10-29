"""Asset Manager Agent：素材登记入册（V1：扫描项目 media 目录，产出素材索引产物）。

确定性任务，不需要 LLM。素材删除必须人工确认——本 Agent 无删除能力。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..base import Agent, register

MEDIA_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".mp3", ".wav", ".m4a", ".flac",
              ".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf", ".docx", ".txt", ".md"}


@register
class AssetAgent(Agent):
    role = "asset"
    tier = "-"
    needs_llm = False
    description = "素材管理：登记入册、标签、索引、授权状态；不挑选素材、不删除素材。"

    def run(self, engine, task: dict) -> None:
        media_dir = engine.project_dir(task["project_id"]) / "media"
        index = []
        for path in sorted(media_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in MEDIA_EXTS:
                continue
            index.append({
                "path": str(path.relative_to(media_dir)),
                "name": path.name,
                "ext": path.suffix.lower(),
                "size": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()[:65536]).hexdigest()[:16],
                "license": "unchecked",
            })
        # 3.x-Preflight：素材来源状态显式标注（加法字段，不改契约）
        tools_cfg = engine.config.get("tools", {})
        prov = {k: (tools_cfg.get(k) or {}).get("provider", "none") for k in ("search", "image", "video")}
        mode = "local_ingest" if index else "none"
        data = {"files": index, "material_mode": mode,
                "material_mode_reason": ("项目 media/ 已登记 {} 个本地素材（run.py ingest）".format(len(index))
                                         if index else
                                         "项目 media/ 为空，且 search/image/video provider 均为 none → 无素材"),
                "material_providers": prov,
                "summary": f"素材索引：{len(index)} 个文件（mode={mode}）",
                "confidence": 1.0,
                "note": "素材授权状态待 Compliance 复核；无素材时成片退化为纯色底+烧录字幕（不伪造素材）"}
        artifact_id = engine.write_artifact(task["project_id"], task["task_id"],
                                            "asset_index", data, summary=data["summary"])
        engine.attach_artifact(task["task_id"], artifact_id)
        engine.db.update_task(task["task_id"], confidence=1.0)

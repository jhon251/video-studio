"""朗读稿/发布稿导出：从项目的 script 产物生成零标记文本（V2 第四阶段）。

用法：python scripts/export_script.py <project_id> [输出路径]
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.core.strip import strip_claims, has_claims  # noqa: E402
from video_studio.db.schema import Database  # noqa: E402


def find_script(db: Database, project_id: str) -> dict | None:
    for t in db.list_tasks(project_id):
        if t["task_type"] != "script":
            continue
        for art_id in t["artifacts"]:
            art = db.get_artifact(art_id)
            if art and art["type"] == "script_output":
                with open(art["path"], encoding="utf-8") as fh:
                    return json.load(fh)
    return None


def build_script_text(script: dict) -> str:
    """从 script 产物生成零标记朗读稿文本（供导出与测试复用）。"""
    lines = ["（本稿由 video-studio 自动导出，已剥离全部内部标记）", ""]
    for i, seg in enumerate(script.get("segments", []), 1):
        narration = strip_claims(seg.get("narration", "").strip())
        if not narration:
            continue
        lines.append(f"【第 {i} 段】")
        lines.append(narration)
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python scripts/export_script.py <project_id> [输出路径]")
        return 2
    project_id = sys.argv[1]
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "voice_ref" / "朗读稿_导出.txt"
    db = Database(ROOT / "projects" / "video_studio.db")
    script = find_script(db, project_id)
    db.close()
    if script is None:
        print("未找到 script 产物")
        return 1
    text = build_script_text(script)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    if has_claims(text):
        print(f"错误：导出稿仍含标记 -> {out_path}")
        return 1
    print(f"朗读稿已导出（零标记已验证）: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

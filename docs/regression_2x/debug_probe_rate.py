"""调试：probe_audio_rate 为何拿不到采样率（真实文件 + 真实 ToolContext）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core.audio import probe_audio_rate  # noqa: E402
from video_studio.tools.base import ToolContext  # noqa: E402
from video_studio.tools.ffmpeg_tool import FFmpegTool  # noqa: E402

cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
ctx = ToolContext(role="probe", project_id=None, project_dir=ROOT, db=None, config=cfg)
target = ROOT / "projects" / "p_f4b466a4a024" / "media" / "voice" / "narration.mp3"
print("target:", target.name, target.is_file())
print("probe_audio_rate ->", probe_audio_rate(ctx, target))
res = FFmpegTool().execute({"op": "probe", "inputs": [str(target)]}, ctx)
print("probe data keys:", sorted((res.data or {}).keys()))
for s in (res.data or {}).get("streams") or []:
    print("  stream:", json.dumps(s, ensure_ascii=False)[:220])

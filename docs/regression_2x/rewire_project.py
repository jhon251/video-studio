"""One-off recovery: rewire downstream tasks stuck on a superseded (blocked) task.

Uses production code path Engine.rewire_dependents (no manual DB surgery, no gate bypass).

Usage: python docs/regression_2x/rewire_project.py <project_id> [task_type]
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from video_studio.cli import build_engine  # noqa: E402
from video_studio.core.env import load_env  # noqa: E402

load_env(ROOT / ".env")
cfg = json.loads((ROOT / "config" / "config.real.json").read_text(encoding="utf-8"))
engine = build_engine(cfg)

pid = sys.argv[1]
ttype = sys.argv[2] if len(sys.argv) > 2 else "render"
tasks = [t for t in engine.db.list_tasks(pid) if t["task_type"] == ttype]
blocked = [t for t in tasks if t["status"] in ("BLOCKED", "FAILED")]
good = [t for t in tasks if t["status"] == "SUCCEEDED"]
print("{} 任务：{} 个，其中 BLOCKED/FAILED {} 个，SUCCEEDED {} 个".format(
    ttype, len(tasks), len(blocked), len(good)))
for t in tasks:
    print("  {} v{} {} deps={}".format(t["task_id"], t["version"], t["status"], t["dependencies"]))
if not blocked or not good:
    print("无需重连（缺少 blocked 或 succeeded 任务）")
    raise SystemExit(0)
newest_good = sorted(good, key=lambda t: t["version"])[-1]
total = 0
for b in blocked:
    n = engine.rewire_dependents(pid, b["task_id"], newest_good["task_id"])
    total += n
    print("重连 {} -> {}：影响 {} 个下游任务".format(b["task_id"], newest_good["task_id"], n))
print("合计重连下游任务数:", total)

"""打印某个基线/快照里关键文件的 sha256 前 16 位（供报告/BASELINE_README 引用）。

用法: python docs/regression_2x/print_3a_fingerprints.py [tag]   # 默认 3.x-phase3a-baseline
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
TAG = sys.argv[1] if len(sys.argv) > 1 else "3.x-phase3a-baseline"
man = json.loads((ROOT / "docs" / "regression_2x" / "baseline" /
                  "baseline_manifest_{}.json".format(TAG)).read_text(encoding="utf-8"))
want = [
    "src/video_studio/core/materials.py",
    "src/video_studio/tools/material_provider.py",
    "src/video_studio/tools/provider_wikimedia.py",
    "src/video_studio/agents/editing/agent.py",
    "src/video_studio/agents/retrieval/agent.py",
    "src/video_studio/agents/voice/agent.py",
    "src/video_studio/core/engine.py",
    "src/video_studio/tools/ffmpeg_tool.py",
    "tests/attribution_compliance_test.py",
    "tests/material_provider_test.py",
    "tests/material_taxonomy_test.py",
    "tests/scene_assembly_test.py",
    "config/config.json",
    "config/config.real.provider.json",
    "run.py",
    "pyproject.toml",
]
print("tag={} files={} source_bytes={}".format(
    man["tag"], man["file_count"], man["source_bytes"]))
print("zip_sha256={}".format(man["zip_sha256"]))
for rel in want:
    e = man["files"].get(rel)
    print("  {:56s} {} {}".format(rel, (e["sha256"][:16] if e else "NOT-IN-ZIP"),
                                  (e["bytes"] if e else "")))

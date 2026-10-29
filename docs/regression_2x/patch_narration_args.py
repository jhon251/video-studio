"""Replace the tail of EditingAgent._narration_args with the Phase 2-A/B implementation."""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
TARGET = ROOT / "src/video_studio/agents/editing/agent.py"
TAIL = ROOT / "docs/regression_2x/_narration_args_tail.py"

src = TARGET.read_text(encoding="utf-8")
marker = '        fade = f"fade=t=in:st=0:d=0.6,fade=t=out:st='
idx = src.index(marker)
new = src[:idx] + TAIL.read_text(encoding="utf-8")
TARGET.write_text(new, encoding="utf-8")
import ast
ast.parse(new)
print("patched:", TARGET.name, "| new length:", len(new), "chars")
TAIL.unlink()
print("scratch removed:", TAIL.name)

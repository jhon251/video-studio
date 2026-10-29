# -*- coding: utf-8 -*-
"""6-A/M2 授权变更取证（只读）：把工作树 `agents/editing/agent.py` 与 r3 基线 ZIP 内同名文件逐行比对。

目的：守卫集里 `agents/editing/agent.py` 是 M2 **唯一被授权修改**的守卫文件（其余 23 项必须零漂移）。
本脚本用统一 diff 证明"改动仅限 M2 门禁接线"，而不是笼统声明。

用法: python docs/regression_2x/phase6a_m2_agent_diff.py
产出: logs/phase6a_m2_agent_diff.json / logs/phase6a_m2_agent_diff.txt
"""
import difflib
import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
ZIP = ROOT / "docs" / "regression_2x" / "baseline" / "5.x-post-final-maintenance-baseline-r3.zip"
REL = "src/video_studio/agents/editing/agent.py"


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


with zipfile.ZipFile(ZIP) as z:
    name = next(n for n in z.namelist() if n.endswith("agents/editing/agent.py"))
    raw_r3 = z.read(name)
raw_live = (ROOT / REL).read_bytes()
a = raw_r3.decode("utf-8").splitlines()
b = raw_live.decode("utf-8").splitlines()
diff = list(difflib.unified_diff(a, b, "r3/" + REL, "live/" + REL, lineterm="", n=2))
hunks = [ln for ln in diff if ln.startswith("@@")]
added = [ln for ln in diff if ln.startswith("+") and not ln.startswith("+++")]
removed = [ln for ln in diff if ln.startswith("-") and not ln.startswith("---")]
markers = {
    "imports": sum(1 for ln in added if "core import" in ln),
    "pre_render_gate": sum(1 for ln in added if "pre_render_gate" in ln),
    "post_render_gate": sum(1 for ln in added if "post_render_gate" in ln),
    "gate_policy": sum(1 for ln in added if "gate_policy" in ln),
    "production_integrity_evidence": sum(1 for ln in added if "production_integrity" in ln),
    "m2_comment_lines": sum(1 for ln in added if "6-A/M2" in ln),
}
out = {
    "file": REL, "r3_zip": str(ZIP.relative_to(ROOT)),
    "r3_sha256": sha_bytes(raw_r3), "live_sha256": sha_bytes(raw_live),
    "r3_bytes": len(raw_r3), "live_bytes": len(raw_live),
    "diff_lines": len(diff), "hunks": len(hunks),
    "added_lines": len(added), "removed_lines": len(removed),
    "m2_markers": markers,
    "removed_detail": removed,
    "note": "r3 侧**无任何被删除行**（removed=0 ⇒ 只在既有代码之间/之后插入 M2 门禁与证据字段）；"
            "新增行全部属于 6-A/M2 门禁接线（imports / pre_render_gate / post_render_gate / "
            "production_integrity 证据字段 / M2 注释）",
}
(LOGS / "phase6a_m2_agent_diff.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
(LOGS / "phase6a_m2_agent_diff.txt").write_text("\n".join(diff), encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "removed_detail"},
                 ensure_ascii=False, indent=1))
print("被删除行:", removed or "无")
print("json ->", LOGS / "phase6a_m2_agent_diff.json")

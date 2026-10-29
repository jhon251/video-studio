# -*- coding: utf-8 -*-
"""Phase 13 收尾：填回归数字 + 报告 sha256 台账 + 并发干扰说明。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
suites = json.loads((L / "suites_summary.json").read_text(encoding="utf-8"))
failed = [x["suite"] for x in suites if x["rc"] != 0]
reg = "**{} 套件 / {} rc=0 / FAILED: {}**".format(len(suites),
                                                  sum(1 for x in suites if x["rc"] == 0),
                                                  failed or "[]")
print("回归:", reg)
rep = R / "docs" / "regression_2x" / "PHASE13_REPORT.md"
st = R / "STATUS.md"
cl = R / "CHANGELOG.md"
for p in (rep, st, cl):
    t = p.read_text(encoding="utf-8")
    t = t.replace("__REG__", reg)
    p.write_text(t, encoding="utf-8")
PRODUCED = {
    "__MOTION__": "src/video_studio/core/motion.py",
    "__EDIT__": "src/video_studio/agents/editing/agent.py",
    "__CFG__": "config/render_motion.example.json",
    "__TEST__": "tests/motion_test.py",
    "__VERIFY__": "docs/regression_2x/logs/phase13_motion_render_verify.json",
}
t = rep.read_text(encoding="utf-8")
for k, f in PRODUCED.items():
    h = hashlib.sha256((R / f).read_bytes()).hexdigest()
    t = t.replace(k, h)
    print("  {:12s} -> {}  {}".format(k, h[:16] + "…", f))
note = ("\n> **并发干扰说明（如实）**：本阶段曾**同时**跑两次 `run_all_suites.py`，"
        "`multimodal_test` F1（真实 DB 行数运行前后一致）因此转红"
        "（实测 tasks 20731→20734、artifacts 18226→18227、events 147737→147738）——"
        "系另一进程写入 fixture 行所致，**非代码缺陷**；单独重跑后 **" + reg + "**。\n")
t = t.replace("## 8. 产物 sha256 台账（可复算）", note + "\n## 8. 产物 sha256 台账（可复算）")
rep.write_text(t, encoding="utf-8")
print("报告残留占位符:", [k for k in list(PRODUCED) + ["__REG__"]
                          if k in rep.read_text(encoding="utf-8")])
print("STATUS/CHANGELOG 含回归数字:", reg in st.read_text(encoding="utf-8"),
      reg in cl.read_text(encoding="utf-8"))

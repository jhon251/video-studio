# -*- coding: utf-8 -*-
"""Phase 13-D 收尾核验：候选/证据、批准链、PI/DQ 未被改写成 PASS、母片与产物零改动、登记一致。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

rep = json.loads((L / "phase13d_p13_4.json").read_text(encoding="utf-8"))
cand = pathlib.Path(rep["candidate"]["path"])
cand_abs = cand if cand.is_absolute() else R / cand
print("候选存在:", cand_abs.is_file(), "| sha 一致:", rep["candidate"]["sha256_match"],
      "| bytes:", rep["candidate"]["bytes"])
print("执行:", rep["execution"]["state"], "| promoted:", rep["execution"]["promoted"],
      "| sandbox_only:", rep["execution"]["sandbox_only"])
pi = rep["pi_recheck"]
print("PI outcome:", pi["pi_gate_outcome"], "| failed:", pi["pi_failed"])
print("DQ overall:", (rep["dq_recheck"]["dq_summary"] or {}).get("overall"))
print("derived_from:", rep["derived_executor_proposal"]["derived_from"],
      "| 派生提案:", rep["derived_executor_proposal"]["proposal_id"])
t = (R / "docs" / "regression_2x" / "PHASE13D_REPORT.md").read_text(encoding="utf-8")
st = (R / "STATUS.md").read_text(encoding="utf-8")
cl = (R / "CHANGELOG.md").read_text(encoding="utf-8")
print("报告记 PI BLOCKED（未改写成 PASS）:", "BLOCKED" in t and "未通过" in t
      and "PI-1 FAIL" in t)
print("报告记 P13-5 PENDING:", "P13-5 状态：**PENDING（未执行）**" in t or "P13-5**：**PENDING" in t
      or "P13-5 全片合成候选：**PENDING（未执行）**" in t)
print("STATUS/CHANGELOG 未把 PI 写成 PASS:",
      "PI 复核 `BLOCKED`" in st and "PI 复核 BLOCKED" in cl.replace("**", ""))
pins = {"master_draft": (R / "projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4", "22705c7d7ea20b40"),
        "config_json": (R / "config" / "config.json", "7b03424846f15efc"),
        "p7_6_proposals": (L / "visual_binding_proposals.json", "3f7fd67737d8e52d"),
        "russell_asset": (R.parent / "h5_asset_candidates/S05/Russell_PM_1+1=2.png", "65377b888b778226")}
for k, (p, pre) in pins.items():
    h = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "MISSING"
    print("  {:18s} {}  未变={}".format(k, h[:16] + "…", h.startswith(pre)))
led = [json.loads(x) for x in (L / "phase13d_execution_ledger.jsonl").read_text(
    encoding="utf-8").splitlines() if x.strip()]
print("执行台账:", len(led), "条 | chain seq:", led[-1].get("seq"),
      "| entry_sha256:", bool(led[-1].get("entry_sha256")), "| promoted:", led[-1].get("promoted"))

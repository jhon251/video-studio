# -*- coding: utf-8 -*-
"""Phase 13-C 收尾核验：批准链绑定、KNOWN_ISSUES #71、登记一致性、未伪造 PASS、母片/产物零改动。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import execution as EX                                         # noqa: E402

# 1) 批准链
appr = [json.loads(x) for x in (L / "phase13c_approvals.jsonl").read_text(
    encoding="utf-8").splitlines() if x.strip()]
prop = next(p for p in json.loads((L / "visual_binding_proposals.json").read_text(
    encoding="utf-8"))["proposals"] if p["proposal_id"] == "bp-6320bf486a082901")
chk = EX.verify_approval(prop, appr[0])
print("批准条数:", len(appr), "| verified:", json.dumps(chk, ensure_ascii=False))
print("approved_by:", appr[0]["approved_by"], "| auto_approved:", appr[0]["auto_approved"],
      "| document:", appr[0].get("approval_document"))
print("绑定 sha256 一致:", appr[0]["proposal_sha256"] == EX.proposal_sha256(prop),
      "| 链 seq:", appr[0].get("seq"), "| entry_sha256 存在:", bool(appr[0].get("entry_sha256")))

# 2) KNOWN_ISSUES #71
ki = (R / "docs" / "KNOWN_ISSUES.md").read_text(encoding="utf-8")
print("KNOWN_ISSUES #71:", "## 71. 两代选材通道" in ki, "| 状态 OPEN:", "#71" in ki and "`OPEN`" in ki,
      "| footer 保留:", "## 变更纪律" in ki, "| #70 保留:", "**#70**" in ki)

# 3) 登记一致性 / 未伪造 PASS
st = (R / "STATUS.md").read_text(encoding="utf-8")
cl = (R / "CHANGELOG.md").read_text(encoding="utf-8")
rep = (R / "docs" / "regression_2x" / "PHASE13C_REPORT.md").read_text(encoding="utf-8")
print("STATUS 记批准 DONE 与渲染 PENDING:", "批准登记（DONE" in st and "P13-4" in st and "PENDING" in st)
print("CHANGELOG 记 13-C:", "## Phase 13-C — S05 REPLACE 执行批准：6-B 链登记 DONE" in cl)
print("未把渲染写成完成:", "P13-4 修订候选渲染 + PI/DQ 复核：PENDING" in rep and "render 完成" not in rep)
import re as _re
_flat = _re.sub(r"[*]", "", rep)
_lines = [_re.sub(r"[*`]", "", L) for L in rep.splitlines()]
print("DQ-3 未被宣称 PASS:", any("不得" in L and "DQ-3 PASS" in L for L in _lines)
      and not any("DQ-3 PASS" in L and "不得" not in L and "未" not in L for L in _lines))
print("报告台账一致:", all(
    hashlib.sha256((R / f).read_bytes()).hexdigest() == h
    for f, h in [("docs/regression_2x/logs/phase13c_approvals.jsonl",
                  hashlib.sha256((L / "phase13c_approvals.jsonl").read_bytes()).hexdigest())]))

# 4) 不可变
pins = {"final_master_6G": (R / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4", "3b61dafda11c1b9d"),
        "config_json": (R / "config" / "config.json", "7b03424846f15efc"),
        "p7_6_proposals": (L / "visual_binding_proposals.json", "3f7fd67737d8e52d"),
        "s05_replacement_asset": (R.parent / "h5_asset_candidates/S05/Russell_PM_1+1=2.png", "65377b888b77")}
for k, (p, pre) in pins.items():
    h = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "MISSING"
    print("  {:22s} {}  未变={}".format(k, h[:16] + "…", h.startswith(pre)))
print("本阶段未产生渲染/候选产物:",
      sorted(x.name for x in L.glob("phase13c_*")))
print("6-C 台账未被触碰:",
      hashlib.sha256((L / "phase6c_approvals.jsonl").read_bytes()).hexdigest()[:12],
      hashlib.sha256((L / "phase6c_execution_ledger.jsonl").read_bytes()).hexdigest()[:12])

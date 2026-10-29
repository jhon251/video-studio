# -*- coding: utf-8 -*-
"""Phase 13-C / P13-4 步 1：按 **6-B 提案审批链**登记人工批准（转录 human:project-owner 的书面授权）。

- 依据：Phase 13-C 授权书 §0 + 用户本条消息（human:project-owner 签发）——**显式授权 Agent 转录登记**，
  故 §0 的"不代写"规则适用范围已被人工书面解除（登记于同一记录的理由/溯源字段）。
- 绑定：`bp-6320bf486a082901` + `proposal_sha256`（由 `core.execution.proposal_sha256` 对 **P7-6 真实提案内容**计算）。
- 产物：`docs/regression_2x/logs/phase13c_approvals.jsonl`（**新文件**，不覆盖 6-C 的 approvals ledger）。
- 只写审批记录；**不写 execution ledger、不渲染、不动母片**（执行在后续步骤）。
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import execution as EX                                         # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
PROPOSALS = LOGS / "visual_binding_proposals.json"
APPROVALS = LOGS / "phase13c_approvals.jsonl"
TARGET = "bp-6320bf486a082901"

props = json.loads(PROPOSALS.read_text(encoding="utf-8"))
prop = next(p for p in props["proposals"] if p["proposal_id"] == TARGET)
print("提案:", prop["proposal_id"], "| scene:", prop["scene_id"], "| decision:", prop["decision"])
print("P7-6 登记 deterministic_hash:", prop["deterministic_hash"][:24], "…")
print("previous → candidate:", prop.get("previous_asset_id"), "→", prop.get("candidate_id"))
print("proposal_sha256（本阶段计算）:", EX.proposal_sha256(prop)[:24], "…")

REASON = ("批准 P7-6 REPLACE 提案：S05 由 ast-6c3fc5af91ed650d 替换为 ast-92ca33138ffe64f4"
          "（Russell《数学原理》1+1=2 页，PD-US/PUBLIC_DOMAIN）。依据 = P7-6 REPLACE 提案"
          "（coverage=COVERED）+ Phase 12 许可覆盖层解锁（HAS_RECORD/PUBLIC_DOMAIN/PASS）+ "
          "H5 阶段 Russell 页人工验收先例 + M2 台账对该场景原素材的人工否决。")
PROVENANCE = ("Phase 13-C 授权书 §0（human:project-owner 签发，明示批准提案 bp-6320bf486a082901）; "
              "用户消息授权 Agent 通过 6-B 提案审批链**转录**该批准; "
              "approval_document=\"Phase 13-C 授权书 §0 + 本消息（human:project-owner 签发）\"; "
              "前置：docs/regression_2x/logs/phase13c_stop_decision.json（§0 规则登记）；"
              "许可证据：docs/regression_2x/logs/license_overlay_v1.json"
              "（ast-92ca33138ffe64f4 → PUBLIC_DOMAIN）")

at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
rec = EX.make_approval(prop, "APPROVE", "human:project-owner", REASON, PROVENANCE, at=at)
rec["approval_document"] = "Phase 13-C 授权书 §0 + 本消息（human:project-owner 签发）"
rec["recorded_by"] = "agent:transcription（人工书面授权转录；非代写）"
rec["human_note"] = {"authorized_by": "human:project-owner",
                     "authorization": "Phase 13-C 授权书 §0 + 本消息",
                     "scope": "仅本提案 bp-6320bf486a082901；不含其它提案"}
rec = EX.append_approval(APPROVALS, rec)
chk = EX.verify_approval(prop, rec)
print("approval_id:", rec["approval_id"], "| approved_by:", rec["approved_by"],
      "| at:", rec["approved_at"])
print("绑定校验（verify_approval）:", json.dumps(chk, ensure_ascii=False))
print("链字段 seq/prev/entry:", rec.get("seq"), str(rec.get("prev_sha256"))[:12],
      str(rec.get("entry_sha256"))[:12])
print("落盘:", APPROVALS.name, "| 行数:",
      len([x for x in APPROVALS.read_text(encoding="utf-8").splitlines() if x.strip()]))
sys.exit(0 if chk.get("ok") else 3)

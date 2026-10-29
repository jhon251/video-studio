# -*- coding: utf-8 -*-
"""Phase 13-C §0：登记阻止 AI 代写 human 身份记录的明文规则 ⇒ STOP（不执行批准登记）。

本脚本**只写一份登记文件**（agent 自述，非 human 身份记录），不改 DB/产物/母片。
"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
RULE = R / "docs" / "PRODUCTION_RUN01_HUMAN_PREFLIGHT_CHECKLIST.md"
txt = RULE.read_text(encoding="utf-8", errors="replace").replace("\ufeff", "")
lines = txt.splitlines()
quotes = []
for i, line in enumerate(lines, 1):
    if any(k in line for k in ("必须由项目负责人本人签发", "不得代写", "不得自动写入 APPROVED",
                               "不构成任何 APPROVED 记录", "只能以新签核记录追加")):
        quotes.append({"line": i, "text": line.strip()})
out = {
    "schema": "phase13c-stop-decision-v1",
    "decision": "STOP_NO_EXECUTION",
    "trigger_clause": "Phase 13-C 授权书 §0：若仓库存在阻止 AI 会话代写 human 身份记录的明文规则，"
                      "则不执行、登记该规则出处后 STOP。",
    "rule_source": {
        "path": str(RULE.relative_to(R)).replace("\\", "/"),
        "sha256": hashlib.sha256(RULE.read_bytes()).hexdigest(),
        "verbatim_quotes": quotes,
        "scope_analysis": "规则位于 Production Run 01 人工前置项清单：① 针对其**三项人工签核记录**"
                          "（如 output/pre_flight_signoff/…）要求项目负责人**本人签发**；"
                          "② 同时明文禁止**系统/Agent 代写结论、自动写入 APPROVED**；"
                          "③ 声明本文件本身不构成任何 APPROVED 记录。"
                          "虽为**分项规则**（非全仓通用条款），但其措辞直接约束 Agent 对 human 签核记录的写入行为 ⇒ "
                          "按授权书 §0 的保守解释，**不代写**。",
    },
    "precedent_reference": {
        "path": "docs/regression_2x/logs/phase6c_approvals.jsonl",
        "note": "既有 6-B/6-C 批准记录 `approved_by=human:director(6-C)`，由阶段执行器在**项目所有者授权书**"
                "基础上登记（字段含 proposal_sha256/provenance/human_note/auto_approved）。"
                "该先例表明：授权书可作为批准依据并由执行器**登记**；但本条规则的明文措辞要求"
                "**由人本人签发**，两种口径存在冲突 ⇒ 依用户铁律『现实与描述冲突时以现实为准并登记差异』"
                "并按 §0 的 STOP 指令处理。",
    },
    "not_executed": [
        "未写 decisions / changelog 中任何 human 身份批准记录",
        "未创建 phase13c 批准文件或执行 ledger 条目",
        "未渲染 S05 修订候选（P13-4）",
        "未产出全片合成候选（P13-5）",
        "未触碰母片 / 既有候选 / Phase 7–12 产物 / config.json",
    ],
    "read_only_operations_only": True,
    "remaining_pending": {"P13-4": "PENDING（未执行）", "P13-5": "PENDING（未产出）"},
    "unblock_options_for_human": [
        {"option": 1, "action": "由项目负责人本人在本地执行既有 CLI（人工签发路径）：",
         "command": "python run.py select-candidate p_96efdc03e1aa --scene S05 "
                    "--asset ast-92ca33138ffe64f4 --by human:project-owner "
                    "--reason \"Phase 13-C 授权书 §0：P7-6 REPLACE 提案 + Phase 12 许可解锁(PUBLIC_DOMAIN) "
                    "+ H5 人工验收先例 + M2 对原素材的人工否决\"",
         "note": "该命令写 decisions（既有表、既有语义），是仓库既有的『人工归属决定』通道"},
        {"option": 2, "action": "若希望由 Agent 登记（转录而非代写），请在下一条消息中明确写："
                               "『我（human:project-owner）授权 Agent 转录本节批准为 decisions/changelog 记录』"
                               "——即显式解除本条规则的适用范围（需人工书面指示）"},
    ],
    "agent_identity_note": "本文件由 Agent 撰写，内容为**规则登记与 STOP 说明**，"
                           "不含任何 human 签名、不含 APPROVED 结论。",
}
p = R / "docs" / "regression_2x" / "logs" / "phase13c_stop_decision.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("规则出处:", out["rule_source"]["path"], "| sha256:", out["rule_source"]["sha256"][:16])
for q in quotes:
    print("  L{}: {}".format(q["line"], q["text"][:110]))
print("登记文件:", p.name)
print("DECISION:", out["decision"], "| PENDING:", out["remaining_pending"])

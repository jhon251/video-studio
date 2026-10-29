"""V2 第五阶段测试：Claim 级人工审核闭环 + 强制审核 + 生产闸门 + changelog。"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.db.schema import Database  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.core.ids import new_id  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402
from video_studio.hitl.service import HITL  # noqa: E402

for mod in ("orchestrator", "pm", "topic", "research", "source_verify", "structure",
            "script", "fact_check", "critic", "asset", "retrieval", "visual", "editing",
            "voice", "audio", "subtitle", "thumbnail", "platform", "metadata",
            "compliance", "qa", "analyst", "claim_extractor", "evidence", "conflict_detector"):
    __import__(f"video_studio.agents.{mod}.agent")
from video_studio.agents.base import AGENTS  # noqa: E402


def make_claim(db, pid, cid, text, ctype="FACT", risk="HIGH", status="NEEDS_HUMAN"):
    db.insert_claim({"claim_id": cid, "project_id": pid, "segment_ref": "S1", "text": text,
                     "type": ctype, "risk": risk, "markers": [],
                     "status": status, "human_review_required": True})


def main() -> int:
    workspace = Path(tempfile.mkdtemp(prefix="vs_hitl2_"))
    db = Database(workspace / "state.db")
    config = json.loads((ROOT / "config" / "config.example.json").read_text(encoding="utf-8"))
    config["tools"]["ffmpeg"] = {"path": str(ROOT / "bin" / "ffmpeg.exe"),
                                 "ffprobe": str(ROOT / "bin" / "ffprobe.exe")}
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    engine = Engine(db, Router(config["llm"], MockLLM()), rules, workspace / "projects",
                    config, AGENTS)
    hitl = HITL(engine, config)
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    pid = engine.create_project("第五阶段测试")

    # script 任务（供 reject 重做链）
    t_script = engine.create_task(pid, "script", "script")
    aid = engine.write_artifact(pid, t_script, "script_output",
                                {"segments": [], "summary": "s"}, summary="脚本")
    engine.attach_artifact(t_script, aid)
    db.set_task_status(t_script, "SUCCEEDED")
    # fact_check 任务（供 revise 重做）
    t_fc = engine.create_task(pid, "fact_check", "fact_check")
    db.set_task_status(t_fc, "SUCCEEDED")

    # ========== 1) 未审核 Claim 阻塞生产闸门 ==========
    make_claim(db, pid, "c_001", "2024年1月，Neuralink完成第一例人体植入", risk="CRITICAL")
    t_visual = engine.create_task(pid, "visual_plan", "visual")
    ready_ids = [t["task_id"] for t in engine.dispatchable(pid)]
    check("未审核 Claim 阻塞生产任务", t_visual not in ready_ids)

    # ========== 2) 正常审核通过 ==========
    hitl.decide_claim("c_001", "approve", "官方来源确认")
    c = db.get_claim("c_001")
    check("approve → VERIFIED", c["status"] == "VERIFIED" and not c["human_review_required"])
    logs = db.list_changelog(pid, "claim", "c_001")
    check("changelog 记录完整", len(logs) == 1
          and logs[0]["before_summary"] == "NEEDS_HUMAN"
          and logs[0]["after_summary"] == "VERIFIED"
          and logs[0]["reason"] == "官方来源确认"
          and logs[0]["human_confirmed"] is True
          and logs[0]["changed_by"] == "human")
    check("decision 留痕", any(d["node"] == "claim_c_001" and d["state"] == "APPROVED"
                               for d in [dict(r) for r in db.conn.execute(
                                   "SELECT * FROM decisions").fetchall()]))
    ready_ids = [t["task_id"] for t in engine.dispatchable(pid)]
    check("审核通过后生产任务解封", t_visual in ready_ids)

    # ========== 3) Reject → 回到 script/verification ==========
    make_claim(db, pid, "c_002", "某机构完成首次突破", risk="HIGH")
    hitl.decide_claim("c_002", "reject", "表述无依据")
    check("reject → REJECTED", db.get_claim("c_002")["status"] == "REJECTED")
    scripts = [t for t in db.list_tasks(pid) if t["task_type"] == "script"]
    extracts = [t for t in db.list_tasks(pid) if t["task_type"] == "claim_extract"]
    check("reject 重做 script", len(scripts) == 2 and scripts[-1]["status"] == "PENDING")
    check("reject 重建提取链", len(extracts) == 1
          and extracts[0]["dependencies"] == [scripts[-1]["task_id"]])
    check("reject changelog", any(l["after_summary"] == "REJECTED"
                                  for l in db.list_changelog(pid, "claim", "c_002")))

    # ========== 4) Revise → 重新核查 ==========
    make_claim(db, pid, "c_003", "某公司完成首例植入", risk="HIGH")
    hitl.decide_claim("c_003", "revise", "表述需精确化",
                      revised_text="2024年1月，某公司完成首例人体植入")
    c3 = db.get_claim("c_003")
    check("revise 更新文本", c3["text"].startswith("2024年1月"))
    check("revise → UNVERIFIED", c3["status"] == "UNVERIFIED" and not c3["human_review_required"])
    fcs = [t for t in db.list_tasks(pid) if t["task_type"] == "fact_check"]
    check("revise 重做 fact_check", len(fcs) == 2 and fcs[-1]["status"] == "PENDING")
    check("revise changelog 记录前后文本",
          any(l["before_summary"].startswith("text=") and l["after_summary"].startswith("text=")
              for l in db.list_changelog(pid, "claim", "c_003")))
    # 补证据 → 重新核查跑通（人工来源必须显式标注支持关系：added_by=human ≠ DIRECT_SUPPORT）
    db.insert_evidence({"evidence_id": new_id("e"), "project_id": pid,
                        "source": "官方公告", "source_type": "official",
                        "publication_date": "2024-01-29", "reliability": "high",
                        "excerpt": "2024年1月完成首例人体植入", "added_by": "human",
                        "support_level": "DIRECT_SUPPORT"})
    db.link_claim_evidence("c_003", db.list_evidence(pid)[0]["evidence_id"])
    engine.run_cycle(pid)
    c3b = db.get_claim("c_003")
    check("重新核查完成", c3b["status"] in ("VERIFIED", "NEEDS_HUMAN")
          and c3b["conclusion"] in ("Confirmed", "Mostly Confirmed"))

    # ========== 5) CRITICAL / 无证据 / 冲突 → 强制人工 ==========
    make_claim(db, pid, "c_004", "某公司实现世界最大规模部署", risk="CRITICAL", status="UNVERIFIED")
    db.update_claim("c_004", human_review_required=False)
    t_fc2 = engine.create_task(pid, "fact_check", "fact_check", inputs={"claim_ids": ["c_004"]})
    engine.run_cycle(pid)
    check("CRITICAL+无证据 → 强制人工", db.get_claim("c_004")["status"] == "NEEDS_HUMAN")
    check("进入待审列表", any(c["claim_id"] == "c_004" for c in hitl.pending_claims(pid)))

    make_claim(db, pid, "c_005", "某公司完成首例植入", risk="HIGH", status="UNVERIFIED")
    db.update_claim("c_005", human_review_required=False)
    e1, e2 = new_id("e"), new_id("e")
    for eid, src, date, num in ((e1, "官方新闻稿", "2024-01-29", "1"), (e2, "权威媒体", "2024-02-28", "2")):
        db.insert_evidence({"evidence_id": eid, "project_id": pid, "source": src,
                            "source_type": "official" if eid == e1 else "media",
                            "publication_date": date, "reliability": "high",
                            "excerpt": f"报道{num}例植入", "added_by": "test"})
        db.link_claim_evidence("c_005", eid)
    t_cf = engine.create_task(pid, "conflict_check", "conflict_detector",
                              inputs={"claim_ids": ["c_005"]})
    engine.run_cycle(pid)
    check("多源冲突 → 强制人工", db.get_claim("c_005")["status"] == "NEEDS_HUMAN"
          and len(db.list_conflicts(pid)) >= 1)

    # ========== 6) claim_context 完整性 ==========
    ctx = hitl.claim_context("c_004")
    check("claim_context 五要素齐全", all(k in ctx for k in
          ("claim", "evidence", "conflicts", "skeptic_issues", "verification"))
          and ctx["claim"]["claim_id"] == "c_004")

    # ========== 7) Skeptic fatal → 强制人工 ==========
    make_claim(db, pid, "c_006", "某公司完成首例植入", risk="HIGH", status="VERIFIED")
    db.update_claim("c_006", human_review_required=False)
    t_sk = engine.create_task(pid, "skeptic_check", "critic",
                              inputs={"target_claim_ids": ["c_006"]})
    # 用 LLM 报告模拟 fatal 攻击
    engine.router.client.responses["挑战报告"] = {
        "verdict": "PASS",
        "issues": [{"severity": "fatal", "category": "fact", "claim_ids": ["c_006"],
                    "claim": "x", "challenge": "重大风险", "required_action": "consult_human"}],
        "summary": "fatal 测试", "confidence": 0.5, "note": ""}
    engine.run_cycle(pid)
    c6 = db.get_claim("c_006")
    check("Skeptic fatal → 强制人工（结论不变）", c6["status"] == "NEEDS_HUMAN"
          and c6.get("conclusion") is None or c6.get("conclusion") == "Confirmed")

    db.close()
    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

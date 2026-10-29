"""V2 第二阶段测试：claim_extractor / evidence / conflict_detector。

覆盖：注册接入、提取（含绝对化 CRITICAL、标记复用、类型分级）、证据登记与关联、
离线模式、冲突检测（必审+人工路由）、异常输入容错、数据链路完整性。
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.db.schema import Database  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402

import video_studio.agents.claim_extractor.agent  # noqa: F401,E402
import video_studio.agents.evidence.agent  # noqa: F401,E402
import video_studio.agents.conflict_detector.agent  # noqa: F401,E402
import video_studio.agents.orchestrator.agent  # noqa: F401,E402
import video_studio.agents.pm.agent  # noqa: F401,E402
import video_studio.agents.topic.agent  # noqa: F401,E402
import video_studio.agents.research.agent  # noqa: F401,E402
import video_studio.agents.source_verify.agent  # noqa: F401,E402
import video_studio.agents.structure.agent  # noqa: F401,E402
import video_studio.agents.script.agent  # noqa: F401,E402
import video_studio.agents.fact_check.agent  # noqa: F401,E402
import video_studio.agents.critic.agent  # noqa: F401,E402
import video_studio.agents.asset.agent  # noqa: F401,E402
import video_studio.agents.retrieval.agent  # noqa: F401,E402
import video_studio.agents.visual.agent  # noqa: F401,E402
import video_studio.agents.editing.agent  # noqa: F401,E402
import video_studio.agents.voice.agent  # noqa: F401,E402
import video_studio.agents.audio.agent  # noqa: F401,E402
import video_studio.agents.subtitle.agent  # noqa: F401,E402
import video_studio.agents.thumbnail.agent  # noqa: F401,E402
import video_studio.agents.platform.agent  # noqa: F401,E402
import video_studio.agents.metadata.agent  # noqa: F401,E402
import video_studio.agents.compliance.agent  # noqa: F401,E402
import video_studio.agents.qa.agent  # noqa: F401,E402
import video_studio.agents.analyst.agent  # noqa: F401,E402
from video_studio.agents.base import AGENTS  # noqa: E402

SCRIPT = {
    "segments": [
        {"chapter": "开场", "narration": "2022年，桐人戴上NerveGear，意识沉入艾恩葛朗特。",
         "duration_s": 10, "visual_hint": ""},
        {"chapter": "人体试验", "narration": "2024年1月，Neuralink完成第一例人体植入，受试者用意念下棋。",
         "duration_s": 10, "visual_hint": ""},
        {"chapter": "预测", "narration": "乐观情景：2030年代可能出现消费级脑机接口，但只是增强交互。",
         "duration_s": 10, "visual_hint": ""},
        {"chapter": "历史", "narration": "早在[CLAIM:007]1968年萨瑟兰造出第一台头戴显示器。",
         "duration_s": 10, "visual_hint": ""},
    ],
    "summary": "测试脚本",
}

SOURCE_CARDS = {
    "source_cards": [
        {"origin": "Neuralink 官方新闻稿", "summary": "首例人体植入完成", "quote": "2024年1月首例植入完成",
         "retrieval_path": "search", "doubts": []},
        {"origin": "科技媒体 报道", "summary": "首例植入报道", "quote": "媒体称植入完成",
         "retrieval_path": "search", "doubts": []},
    ],
    "summary": "资料卡",
}


def main() -> int:
    workspace = Path(tempfile.mkdtemp(prefix="vs_agents2_"))
    db = Database(workspace / "state.db")
    config = json.loads((ROOT / "config" / "config.example.json").read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    engine = Engine(db, Router(config["llm"], MockLLM()), rules, workspace / "projects", config, AGENTS)
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    check("25 个 Agent 已注册", len(AGENTS) == 25, f"(实际 {len(AGENTS)})")
    for role in ("claim_extractor", "evidence", "conflict_detector"):
        check(f"{role} 已接入注册表", role in AGENTS)

    pid = engine.create_project("V2 第二阶段测试")

    # ---------- claim_extractor ----------
    script_aid = engine.write_artifact(pid, None, "script_output", SCRIPT, summary="脚本")
    t1 = engine.create_task(pid, "claim_extract", "claim_extractor",
                            inputs={"script_ref": script_aid})
    engine.run_cycle(pid)
    task1 = db.get_task(t1)
    check("提取任务完成", task1["status"] == "SUCCEEDED", f"({task1['status']})")

    claims = db.list_claims(pid)
    texts = [c["text"] for c in claims]
    check("提取到声明", len(claims) >= 3, f"({len(claims)} 条)")
    check("绝对化表述识别为 CRITICAL",
          any("第一例" in c["text"] and c["risk"] == "CRITICAL" and c["markers"] for c in claims))
    check("CRITICAL 自动标记需人工", any(c["risk"] == "CRITICAL" and c["human_review_required"]
                                     for c in claims))
    check("预测句分类为 PREDICTION",
          any("2030年代" in c["text"] and c["type"] == "PREDICTION" for c in claims))
    check("既有标记 [CLAIM:007] 被沿用",
          any(c["claim_id"] == "c_007" and "1968" in c["text"] for c in claims))

    art = db.get_artifact(task1["artifacts"][0])
    with open(art["path"], encoding="utf-8") as fh:
        map_data = json.load(fh)
    internal_text = json.dumps(map_data.get("segments_internal", []), ensure_ascii=False)
    check("内部稿含自动标注", "[CLAIM:c_00" in internal_text)
    events = db.events_since(pid, 0)
    check("CLAIMS_EXTRACTED 事件", any(e["type"] == "CLAIMS_EXTRACTED" for e in events))

    # ---------- evidence（离线模式） ----------
    cards_aid = engine.write_artifact(pid, None, "source_cards", SOURCE_CARDS, summary="资料卡")
    t2 = engine.create_task(pid, "evidence_index", "evidence",
                            inputs={"source_cards_ref": cards_aid,
                                    "manual_sources": [
                                        {"source": "人工提供的个人观察", "source_type": "secondary",
                                         "publication_date": "2024-02-01",
                                         "reliability": "low", "excerpt": "Neuralink 植入在2月才公开"}],
                                    })
    engine.run_cycle(pid)
    task2 = db.get_task(t2)
    check("证据登记任务完成", task2["status"] == "SUCCEEDED", f"({task2['status']})")
    evs = db.list_evidence(pid)
    check("证据已登记（离线，无任何 API）", len(evs) >= 3, f"({len(evs)} 条)")
    check("来源分级 official 正确",
          any(e["source"] == "Neuralink 官方新闻稿" and e["source_type"] == "official" for e in evs))

    neuralink_claim = next(c for c in claims if "第一例" in c["text"])
    linked = db.evidence_for_claim(neuralink_claim["claim_id"])
    check("claim→evidence 关联", len(linked) >= 2, f"({len(linked)} 条)")
    c2 = db.get_claim(neuralink_claim["claim_id"])
    check("source_count 回写", c2["source_count"] == len(linked))
    check("EVIDENCE_INDEXED 事件",
          any(e["type"] == "EVIDENCE_INDEXED" for e in db.events_since(pid, 0)))

    # ---------- conflict_detector ----------
    # 数值矛盾场景：两条证据的数字表述不一致（发布日期差异本身不构成冲突）
    from video_studio.core.ids import new_id
    e_conflict = new_id("e")
    db.insert_evidence({"evidence_id": e_conflict, "project_id": pid,
                        "source": "Neuralink 官方新闻稿（修订版）", "source_type": "official",
                        "publication_date": "2024-02-29", "reliability": "high",
                        "excerpt": "完成2例人体植入", "added_by": "fact_check"})
    db.link_claim_evidence(neuralink_claim["claim_id"], e_conflict)
    ev_official = next(e for e in evs if e["source"] == "Neuralink 官方新闻稿")
    db.conn.execute("UPDATE evidence SET excerpt=? WHERE evidence_id=?",
                    ("完成1例人体植入", ev_official["evidence_id"]))
    db.conn.commit()

    t3 = engine.create_task(pid, "conflict_check", "conflict_detector",
                            inputs={"claim_ids": [neuralink_claim["claim_id"]]})
    engine.run_cycle(pid)
    task3 = db.get_task(t3)
    check("冲突检测任务完成", task3["status"] == "SUCCEEDED", f"({task3['status']})")
    conflicts = db.list_conflicts(pid)
    check("数值矛盾触发冲突", len(conflicts) >= 1, f"({len(conflicts)} 处)")
    check("冲突必审标记", all(c["human_review_required"] is True for c in conflicts))
    check("冲突描述含数值不一致", any("数值表述不一致" in (c["description"] or "")
                                  for c in conflicts))
    check("claim 转入 NEEDS_HUMAN",
          db.get_claim(neuralink_claim["claim_id"])["status"] == "NEEDS_HUMAN")
    check("CONFLICT_DETECTED 事件(human_visible)",
          any(e["type"] == "CONFLICT_DETECTED" and e["human_visible"]
              for e in db.events_since(pid, 0)))

    # ---------- 人工决策闭环（数据层，HITL 命令在第五阶段） ----------
    db.update_claim(neuralink_claim["claim_id"], status="VERIFIED", conclusion="Confirmed",
                    confidence="High", human_review_required=False)
    db.insert_decision({"decision_id": new_id("d"), "project_id": pid, "node": "claim_人工",
                        "made_by": "human", "state": "APPROVED", "rationale": "以官方日期为准"})
    db.insert_changelog(pid, "claim", neuralink_claim["claim_id"], "human",
                        "人工裁定来源日期", "NEEDS_HUMAN", "VERIFIED", human_confirmed=True)
    chain_ok = (db.get_claim(neuralink_claim["claim_id"])["status"] == "VERIFIED"
                and len(db.evidence_for_claim(neuralink_claim["claim_id"])) >= 2
                and len(db.list_conflicts(pid)) >= 1
                and len(db.list_changelog(pid, "claim", neuralink_claim["claim_id"])) == 1)
    check("链路完整：claim→evidence→source→conflict→human→changelog", chain_ok)

    # ---------- 异常输入容错 ----------
    pid2 = engine.create_project("异常测试")
    t4 = engine.create_task(pid2, "claim_extract", "claim_extractor",
                            inputs={"script_ref": "a_不存在"})
    engine.run_cycle(pid2)
    check("缺失脚本引用不崩溃（空提取）", db.get_task(t4)["status"] == "SUCCEEDED")
    t5 = engine.create_task(pid2, "evidence_index", "evidence", inputs={})
    engine.run_cycle(pid2)
    check("无输入证据登记不崩溃（空索引）", db.get_task(t5)["status"] == "SUCCEEDED")
    t6 = engine.create_task(pid2, "conflict_check", "conflict_detector", inputs={})
    engine.run_cycle(pid2)
    check("无多证据时冲突检测不崩溃（空报告）", db.get_task(t6)["status"] == "SUCCEEDED")

    db.close()
    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

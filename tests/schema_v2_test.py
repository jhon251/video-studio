"""V2 第一阶段测试：schema + changelog。

覆盖：
1. 全新库建表（11 张表）
2. V1 旧库迁移兼容：旧表旧数据不动，新表补齐
3. claims/evidence/conflicts/changelog CRUD 与关联
4. 追溯链：script → claim → evidence → source → verification → human decision → changelog
"""

import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.db.schema import Database  # noqa: E402

V1_TABLES = {"projects", "tasks", "events", "artifacts", "decisions", "memories"}
V2_TABLES = {"claims", "evidence", "claim_evidence", "conflicts", "changelog"}


def tables(db_path: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    return names


def main() -> int:
    workspace = Path(tempfile.mkdtemp(prefix="vs_schema2_"))
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    # 1. 全新库
    db_path = workspace / "fresh.db"
    db = Database(db_path)
    all_tables = tables(str(db_path))
    check("全新库 11 张表齐全", V1_TABLES | V2_TABLES <= all_tables,
          f"(实际 {len(all_tables)} 张)")

    # 2. V1 旧库迁移兼容
    old_path = workspace / "old_v1.db"
    conn = sqlite3.connect(old_path)
    conn.execute("""CREATE TABLE projects (
        project_id TEXT PRIMARY KEY, name TEXT NOT NULL, goal TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'ACTIVE', created_at REAL NOT NULL, updated_at REAL NOT NULL)""")
    conn.execute("INSERT INTO projects VALUES('p_old','老项目','老目标','ACTIVE',1.0,2.0)")
    conn.commit()
    conn.close()
    db2 = Database(old_path)
    proj = db2.get_project("p_old")
    t2 = tables(str(old_path))
    check("旧项目数据保留", proj is not None and proj["goal"] == "老目标")
    check("旧库补齐 V2 新表", V2_TABLES <= t2, f"(共 {len(t2)} 张)")

    # 3. 追溯链全链路
    pid = "p_trace"
    db2.create_project(pid, "追溯测试", "验证 claim→evidence→source→verification→human→changelog")
    tid = "t_script"
    # claim
    db2.insert_claim({
        "claim_id": "c_023", "project_id": pid, "task_id": tid, "segment_ref": "S07",
        "text": "2024年1月，Neuralink完成第一例人体植入",
        "type": "FACT", "risk": "CRITICAL", "markers": ["第一例"], "status": "NEEDS_HUMAN",
    })
    c = db2.get_claim("c_023")
    check("claim 写入", c is not None and c["risk"] == "CRITICAL" and c["markers"] == ["第一例"])
    # evidence + 关联
    db2.insert_evidence({
        "evidence_id": "e_118", "project_id": pid, "source": "Neuralink 官方新闻稿",
        "source_type": "official", "publication_date": "2024-01-29",
        "reliability": "high", "excerpt": "首例人体植入完成", "url": "https://x",
        "added_by": "fact_check",
    })
    db2.link_claim_evidence("c_023", "e_118")
    evs = db2.evidence_for_claim("c_023")
    check("claim→evidence 追溯", len(evs) == 1 and evs[0]["source_type"] == "official")
    check("evidence→claim 反向", db2.claims_for_evidence("e_118") == ["c_023"])
    # verification
    db2.update_claim("c_023", status="VERIFIED", conclusion="Confirmed",
                     confidence="High", source_count=1, human_review_required=False)
    c = db2.get_claim("c_023")
    check("verification 状态更新", c["conclusion"] == "Confirmed" and c["confidence"] == "High")
    # conflict
    db2.insert_conflict({
        "conflict_id": "f_007", "project_id": pid, "claim_id": "c_023",
        "source_a": "e_118", "source_b": "e_119",
        "description": "日期冲突", "authority_comparison": "A 官方 > B 媒体",
        "recommended": "以官方为准", "confidence": "High", "human_review_required": True,
    })
    f = db2.get_conflict("f_007")
    check("conflict 写入且必审", f is not None and f["human_review_required"] is True)
    # human decision → changelog
    db2.insert_decision({
        "decision_id": "d_901", "project_id": pid, "node": "claim_c_023",
        "made_by": "human", "state": "APPROVED", "rationale": "官方来源确认",
    })
    db2.insert_changelog(pid, "claim", "c_023", "human", "人工裁定来源日期",
                         "UNVERIFIED", "VERIFIED", human_confirmed=True)
    logs = db2.list_changelog(pid, "claim", "c_023")
    check("human decision→changelog", len(logs) == 1 and logs[0]["human_confirmed"] is True)
    # 全链路：script → claim → evidence → source → verification → human → changelog
    chain_ok = (c is not None and len(evs) == 1 and f is not None and len(logs) == 1)
    check("追溯链完整（七环）", chain_ok)

    db.close()
    db2.close()
    failed = [c_ for c_ in checks if not c_[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

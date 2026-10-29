"""《永生选题》离线核查模拟（质量层验收，provider 强制 none，零网络）。

与 verify_yongsheng.py 相同的 p2b 管线（script → claim_extract → evidence →
skeptic → fact_check → conflict_detect），但强制离线 provider，验证新质量层
不会对 62 条 Claim 产生"异常放行"：

- 结论分布必须等于离线基线：Unsupported 52 / Mostly Confirmed 10 / Confirmed 0
- NEEDS_HUMAN 必须等于基线 51
- 所有 FACT 人工条的 verification_path 必须为 NO_RELIABLE_SOURCE（离线无来源）
- 不得出现在线专属路径（SEARCH_FAILED / FETCH_FAILED / NO_RELEVANT_RESULT /
  INSUFFICIENT_EVIDENCE），不得出现 CONTRADICTS 自动判 False
"""

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from video_studio.db.schema import Database  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402
from video_studio.tools.search_provider import resolve_provider  # noqa: E402
from verify_yongsheng import SCRIPT, OFFLINE_BASELINE_NEEDS_HUMAN  # noqa: E402

for mod in ("script", "critic", "fact_check", "claim_extractor", "evidence",
            "conflict_detector", "pm", "topic"):
    __import__(f"video_studio.agents.{mod}.agent")
from video_studio.agents.base import AGENTS  # noqa: E402

OFFLINE_ONLY_PATHS = {"SEARCH_FAILED", "FETCH_FAILED",
                      "NO_RELEVANT_RESULT", "INSUFFICIENT_EVIDENCE"}


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    project_name = sys.argv[1] if len(sys.argv) > 1 else "yongsheng-offline-sim"
    db = Database(ROOT / "projects" / "video_studio.db")
    config = json.loads((ROOT / "config" / "config.yongsheng.json").read_text(encoding="utf-8"))
    # 强制离线：质量层离线模拟不依赖任何在线 provider
    config["tools"]["search"] = {"provider": "none", "api_key_env": None}
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    provider = resolve_provider(config)
    print(f"SEARCH_PROVIDER={provider.name}")

    engine = Engine(db, Router(config["llm"], MockLLM(config["llm"]["mock"]["responses"],
                    config["llm"]["mock"]["default"])), rules, ROOT / "projects", config, AGENTS)
    pid = engine.create_project("大脑放进电脑，人真的能永生吗？离线质量层模拟", project_name)

    t_script = engine.create_task(pid, "script", "script")
    aid = engine.write_artifact(pid, t_script, "script_output", SCRIPT, summary="用户定稿")
    engine.attach_artifact(t_script, aid)
    db.set_task_status(t_script, "SUCCEEDED")

    t_ce = engine.create_task(pid, "claim_extract", "claim_extractor", dependencies=[t_script],
                              inputs={"phase": "p2b_verification"})
    t_ev = engine.create_task(pid, "evidence_index", "evidence", dependencies=[t_ce],
                              inputs={"phase": "p2b_verification"})
    engine.create_task(pid, "skeptic_check", "critic", dependencies=[t_ce],
                       inputs={"phase": "p2b_verification"})
    engine.create_task(pid, "fact_check", "fact_check", dependencies=[t_ce, t_ev],
                       inputs={"phase": "p2b_verification"})
    engine.create_task(pid, "conflict_check", "conflict_detector", dependencies=[t_ce],
                       inputs={"phase": "p2b_verification"})

    for _ in range(30):
        n = engine.run_cycle(pid)
        if n == 0:
            break

    claims = db.list_claims(pid)
    fc = [t for t in db.list_tasks(pid) if t["task_type"] == "fact_check"][0]
    fc_checks = {}
    for art_id in fc["artifacts"]:
        art = db.get_artifact(art_id)
        with open(art["path"], encoding="utf-8") as fh:
            for r in json.load(fh).get("checks", []):
                fc_checks[r["claim_id"]] = r

    rows = []
    for c in claims:
        r = fc_checks.get(c["claim_id"], {})
        rows.append({
            "claim_id": c["claim_id"],
            "text": c["text"],
            "type": c["type"],
            "risk": c["risk"],
            "conclusion": r.get("conclusion"),
            "verification_path": r.get("verification_path"),
            "search_stats": r.get("search_stats"),
            "human_review_required": bool(c["human_review_required"]),
            "reasoning": r.get("reasoning") or "",
            "status": c["status"],
        })

    concl = Counter((r["conclusion"] or "None") for r in rows)
    needs = [r for r in rows if r["human_review_required"]]
    paths = Counter((r["verification_path"] or "None") for r in rows)
    evidence_registered = len(db.list_evidence(pid))

    check("claim 总数 = 62", len(rows) == 62, f"({len(rows)})")
    check("无来源异常放行：Confirmed = 0", concl.get("Confirmed", 0) == 0, f"({dict(concl)})")
    check("结论分布等于离线基线：Unsupported 52 / Mostly 10",
          concl.get("Unsupported", 0) == 52 and concl.get("Mostly Confirmed", 0) == 10,
          f"({dict(concl)})")
    check("NEEDS_HUMAN = 离线基线 51", len(needs) == OFFLINE_BASELINE_NEEDS_HUMAN,
          f"({len(needs)})")
    check("无 False 结论（不存在证据来源，绝不自动判假）", concl.get("False", 0) == 0)
    check("离线登记证据数 = 0", evidence_registered == 0, f"({evidence_registered})")

    fact_human = [r for r in needs if r["type"] == "FACT"]
    check("FACT 人工条 verification_path 全部 = NO_RELIABLE_SOURCE",
          len(fact_human) > 0 and all(r["verification_path"] == "NO_RELIABLE_SOURCE"
                                      for r in fact_human),
          f"({len(fact_human)} 条, paths={Counter(r['verification_path'] for r in fact_human)})")
    non_fact_human = [r for r in needs if r["type"] != "FACT"]
    check("非 FACT 人工条 verification_path = TYPE_CHECKED",
          all(r["verification_path"] == "TYPE_CHECKED" for r in non_fact_human),
          f"({len(non_fact_human)} 条)")
    check("离线运行不出现在线专属路径（SEARCH_FAILED/FETCH_FAILED/NO_RELEVANT_RESULT/INSUFFICIENT_EVIDENCE）",
          not (set(paths) & OFFLINE_ONLY_PATHS), f"({dict(paths)})")
    check("在线检索统计字段为空（离线未检索）",
          all(r.get("search_stats") is None for r in rows))

    stats = {
        "project": pid,
        "provider": provider.name,
        "claim_total": len(rows),
        "conclusion": dict(concl),
        "verification_path": dict(paths),
        "needs_human": len(needs),
        "offline_baseline_needs_human": OFFLINE_BASELINE_NEEDS_HUMAN,
        "evidence_registered": evidence_registered,
    }
    out = ROOT / "projects" / "_drafts" / f"{project_name}_离线质量层模拟报告.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"stats": stats, "rows": rows},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"REPORT={out}")

    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    db.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

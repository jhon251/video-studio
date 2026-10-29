"""V2 第三阶段测试：fact_check 逐 Claim 核查 + Skeptic 7 类攻击 + SearchProvider 双模式。"""

import copy
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
from video_studio.tools.search_provider import (  # noqa: E402
    EvidenceCandidate, FetchedPage, SearchResult, register_search_provider)

import video_studio.agents.claim_extractor.agent  # noqa: F401,E402
import video_studio.agents.evidence.agent  # noqa: F401,E402
import video_studio.agents.conflict_detector.agent  # noqa: F401,E402
import video_studio.agents.fact_check.agent  # noqa: F401,E402
import video_studio.agents.critic.agent  # noqa: F401,E402
import video_studio.agents.pm.agent  # noqa: F401,E402
import video_studio.agents.topic.agent  # noqa: F401,E402
from video_studio.agents.base import AGENTS  # noqa: E402


class FakeSearchProvider:
    """可插拔在线 provider 测试桩：搜索结果必须经 fetch+extract 才成为证据。"""
    name = "fake_search"
    api_key_env = None

    def search(self, query, max_results=5):
        return [SearchResult(url="https://fake/1", title="Neuralink 官方发布",
                             snippet="首例人体植入", date="2024-01-29")]

    def fetch(self, url):
        return FetchedPage(url=url, ok=True, title="Neuralink 官方发布",
                           text="官方新闻稿：2024年1月完成第一例人体植入")

    def extract_evidence(self, page, claim):
        return EvidenceCandidate(excerpt="官方新闻稿：2024年1月完成第一例人体植入",
                                 source="Neuralink 官方发布", source_type="official",
                                 publication_date="2024-01-29", reliability="high")


register_search_provider(FakeSearchProvider())


def build(config_overrides=None):
    workspace = Path(tempfile.mkdtemp(prefix="vs_fc2_"))
    db = Database(workspace / "state.db")
    config = json.loads((ROOT / "config" / "config.example.json").read_text(encoding="utf-8"))
    if config_overrides:
        config = config_overrides(config)
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    mock = MockLLM({"挑战报告": {"verdict": "PASS", "issues": [], "summary": "LLM 部分",
                                 "confidence": 0.5, "note": ""}})
    engine = Engine(db, Router(config["llm"], mock), rules, workspace / "projects", config, AGENTS)
    return engine


def claim(db, pid, cid, text, ctype="FACT", risk="HIGH", markers=None):
    db.insert_claim({"claim_id": cid, "project_id": pid, "segment_ref": "S1", "text": text,
                     "type": ctype, "risk": risk, "markers": markers or [],
                     "status": "UNVERIFIED", "human_review_required": False})


def evidence(db, pid, cid, eid, source, stype, rel, date=None, excerpt=None, contradicts=False):
    # 测试桩模拟"已评估"证据：显式标注支持关系（未标注的默认语义是未评估，见 V2.0.2）
    db.insert_evidence({"evidence_id": eid, "project_id": pid, "source": source,
                        "source_type": stype, "publication_date": date, "reliability": rel,
                        "excerpt": ("【矛盾证据】" if contradicts else "") + (excerpt or f"{source} 摘录"),
                        "support_level": ("CONTRADICTS" if contradicts else "DIRECT_SUPPORT"),
                        "added_by": "test"})
    db.link_claim_evidence(cid, eid)


def run_fc(engine, pid, claim_ids):
    tid = engine.create_task(pid, "fact_check", "fact_check", inputs={"claim_ids": claim_ids})
    engine.run_cycle(pid)
    task = engine.db.get_task(tid)
    art = engine.db.get_artifact(task["artifacts"][0])
    with open(art["path"], encoding="utf-8") as fh:
        records = json.load(fh)["checks"]
    by_id = {r["claim_id"]: r for r in records}
    return task, by_id


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    # ============ 场景组 1：结论逻辑（离线模式，provider=none） ============
    engine = build()
    db = engine.db
    pid = engine.create_project("结论逻辑")
    claim(db, pid, "c_001", "2024年1月，Neuralink完成第一例人体植入", risk="CRITICAL", markers=["第一例"])
    claim(db, pid, "c_002", "Quest 3 于2023年发售", risk="HIGH")
    claim(db, pid, "c_003", "Vision Pro 于2024年发售", risk="HIGH")
    claim(db, pid, "c_004", "某论文成果已经商业化", risk="HIGH")
    evidence(db, pid, "c_001", "e_001", "Neuralink 官方新闻稿", "official", "high", "2024-01-29")
    evidence(db, pid, "c_001", "e_002", "权威媒体 报道", "media", "medium", "2024-01-30")
    evidence(db, pid, "c_002", "e_003", "Meta 官方发布", "official", "high", "2023-10-10")
    evidence(db, pid, "c_003", "e_004", "Apple 官方发布", "official", "high", "2024-02-02")
    evidence(db, pid, "c_003", "e_005", "科技媒体 报道", "media", "medium", "2024-02-03")
    evidence(db, pid, "c_004", "e_006", "某大学论文", "academic", "high", "2023-05-01")
    _, by_id = run_fc(engine, pid, ["c_001", "c_002", "c_003", "c_004"])
    check("多来源互相支持 → Confirmed", by_id["c_001"]["conclusion"] == "Confirmed")
    check("单官方来源 → Confirmed", by_id["c_002"]["conclusion"] == "Confirmed")
    check("多来源支持 → Confirmed(2)", by_id["c_003"]["conclusion"] == "Confirmed")
    check("逻辑跳跃（论文≠商业化）→ 人工", by_id["c_004"]["human_review_required"] is True
          and "逻辑跳跃" in by_id["c_004"]["reasoning"])

    # ============ 场景组 2：无来源 / 潜在冲突 / 显式矛盾 ============
    pid2 = engine.create_project("边界场景")
    claim(db, pid2, "c_101", "某机构完成首次突破", risk="HIGH")
    claim(db, pid2, "c_102", "某公司实现世界最大规模部署", risk="CRITICAL", markers=["世界最大"])
    evidence(db, pid2, "c_102", "e_101", "企业宣传稿", "media", "high", "2024-01-01")
    evidence(db, pid2, "c_102", "e_102", "匿名来源", "secondary", "low", None)
    claim(db, pid2, "c_103", "某公司完成首例植入", risk="HIGH")
    evidence(db, pid2, "c_103", "e_103", "官方公告", "official", "high", "2024-01-01",
             excerpt="公司明确否认完成任何植入", contradicts=True)
    _, by_id = run_fc(engine, pid2, ["c_101", "c_102", "c_103"])
    check("无来源 → Unsupported（非 False）", by_id["c_101"]["conclusion"] == "Unsupported")
    check("无来源 HIGH → 提示人工", by_id["c_101"]["human_review_required"] is True)
    check("可靠性差≥2 仅潜在冲突：不判 Disputed",
          by_id["c_102"]["conclusion"] in ("Mostly Confirmed", "Unsupported")
          and "潜在冲突" in by_id["c_102"]["reasoning"])
    check("潜在冲突 → 提示人工（不自动裁决）", by_id["c_102"]["human_review_required"] is True)
    check("显式矛盾证据 → Disputed 且必走人工（不自动判 False）",
          by_id["c_103"]["conclusion"] == "Disputed" and by_id["c_103"]["human_review_required"] is True)

    # ============ 场景组 3：非 FACT 类型 ============
    pid3 = engine.create_project("类型核查")
    claim(db, pid3, "c_201", "预测：2030年代可能出现消费级脑机接口", ctype="PREDICTION", risk="MEDIUM")
    claim(db, pid3, "c_202", "我的判断是这条路值得期待", ctype="OPINION", risk="LOW")
    claim(db, pid3, "c_203", "因此完全潜行还很遥远", ctype="INFERENCE", risk="MEDIUM")
    claim(db, pid3, "c_204", "意识上传至今没有答案", ctype="UNKNOWN", risk="LOW")
    claim(db, pid3, "c_205", "预测：2030年代将首次实现完全潜行", ctype="PREDICTION", risk="CRITICAL",
          markers=["首次"])
    _, by_id = run_fc(engine, pid3, ["c_201", "c_202", "c_203", "c_204", "c_205"])
    check("PREDICTION 无来源不判错", by_id["c_201"]["conclusion"] == "Mostly Confirmed")
    check("OPINION 不按事实判错", by_id["c_202"]["conclusion"] == "Mostly Confirmed")
    check("INFERENCE 无前提证据 → Unsupported 标注",
          by_id["c_203"]["conclusion"] == "Unsupported")
    check("UNKNOWN 保留未知", by_id["c_204"]["conclusion"] is None)
    check("预测+绝对化 → 人工复核", by_id["c_205"]["human_review_required"] is True)

    # ============ 场景组 4：多源真正矛盾 → 冲突 → 人工 ============
    pid4 = engine.create_project("来源冲突")
    claim(db, pid4, "c_301", "某公司2024年1月完成首例植入", risk="HIGH")
    evidence(db, pid4, "c_301", "e_301", "官方新闻稿", "official", "high", "2024-01-29")
    evidence(db, pid4, "c_301", "e_302", "权威媒体", "media", "medium", "2024-02-28")
    db.insert_conflict({"conflict_id": new_id("f"), "project_id": pid4, "claim_id": "c_301",
                        "source_a": "e_301", "source_b": "e_302", "description": "日期冲突",
                        "human_review_required": True, "status": "OPEN"})
    _, by_id = run_fc(engine, pid4, ["c_301"])
    check("已登记冲突 → Disputed", by_id["c_301"]["conclusion"] == "Disputed")
    check("冲突 → 人工审核", by_id["c_301"]["human_review_required"] is True)

    # ============ 场景组 5：在线模式（可插拔 provider） ============
    engine5 = build(lambda c: {**c, "tools": {**c["tools"], "search": {
        "provider": "fake_search", "api_key_env": None}}})
    db5 = engine5.db
    pid5 = engine5.create_project("在线模式")
    claim(db5, pid5, "c_401", "2024年1月完成第一例人体植入", risk="HIGH")
    task, by_id = run_fc(engine5, pid5, ["c_401"])
    art = engine5.db.get_artifact(task["artifacts"][0])
    with open(art["path"], encoding="utf-8") as fh:
        provider_name = json.load(fh)["provider"]
    check("在线 provider 被解析", provider_name == "fake_search")
    check("搜索结果经 fetch+extract 成为证据",
          by_id["c_401"]["conclusion"] == "Confirmed" and len(by_id["c_401"]["evidence_refs"]) == 1)
    check("新证据已入库且来源分级 official",
          any(e["source_type"] == "official" for e in db5.list_evidence(pid5)))

    # 无 Key 自动降级：provider 需要密钥但未设置 → OfflineProvider
    engine6 = build(lambda c: {**c, "tools": {**c["tools"], "search": {
        "provider": "needs_key_provider", "api_key_env": "NO_SUCH_KEY"}}})
    from video_studio.tools.search_provider import resolve_provider
    prov6 = resolve_provider(engine6.config)
    check("无 Key 自动降级 OfflineProvider", prov6.name == "offline")

    # ============ 场景组 6：Skeptic 攻击 ============
    pid6 = engine.create_project("Skeptic")
    claim(db, pid6, "c_501", "2024年1月，Neuralink完成第一例人体植入", risk="CRITICAL",
          markers=["第一例"])
    evidence(db, pid6, "c_501", "e_501", "Neuralink 官方新闻稿", "official", "high", "2024-01-29")
    _, by_id = run_fc(engine, pid6, ["c_501"])
    before = db.get_claim("c_501")
    t_critic = engine.create_task(pid6, "skeptic_check", "critic",
                                  inputs={"target_claim_ids": ["c_501"], "target_artifacts": []})
    engine.run_cycle(pid6)
    critic_task = db.get_task(t_critic)
    critic_art = db.get_artifact(critic_task["artifacts"][0])
    with open(critic_art["path"], encoding="utf-8") as fh:
        report = json.load(fh)
    rule_issues = [i for i in report["issues"] if i.get("claim_ids")]
    check("Skeptic 质疑指向具体 claim_id",
          len(rule_issues) >= 1 and all("c_501" in (i.get("claim_ids") or []) for i in rule_issues))
    cats = {i["category"] for i in rule_issues}
    check("7 类攻击维度可用（至少命中 3 类）",
          len(cats & {"time", "entity", "number", "causality", "over_inference",
                      "headline_gap", "hallucination"}) >= 3, f"({cats})")
    after = db.get_claim("c_501")
    check("质疑不改变 claim 事实结论",
          after["conclusion"] == before["conclusion"] and after["status"] == before["status"])

    engine.db.close()
    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

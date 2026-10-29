"""V2 搜索证据质量层专项测试（layer 4→1→3→2 验收）。

覆盖：
- support_level 语义：只描述 Evidence↔Claim 支持关系，不等于事实真假
  （CONTRADICTS → Disputed 不自动 False；DIRECT_SUPPORT → 综合判断不自动 Confirmed）
- 关键词规则仅是候选预筛；讨论级提取才产出 support_level
- 候选预筛：URL 有效性 / 域名黑名单 / 关键词重叠
- 候选排序：来源优先级
- schema：support_level 列 + 旧库迁移 + 默认值（仅历史兼容）
- fact_check 综合：support + reliability + source_count + diversity + type + risk
- SEARCH_EVIDENCE 事件可追溯到 claim_id；verification_path 可区分
- IRRELEVANT / CONTEXT_ONLY 不入证据库；离线无来源 → NO_RELIABLE_SOURCE
"""

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.db.schema import Database  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402
from video_studio.tools.search_provider import (  # noqa: E402
    EvidenceCandidate, FetchedPage, SearchResult, REGISTRY,
    _claim_tokens, _extract_from_page, filter_candidates, order_candidates,
    register_search_provider)

import video_studio.agents.fact_check.agent  # noqa: F401,E402
import video_studio.agents.evidence.agent  # noqa: F401,E402
from video_studio.agents.base import AGENTS  # noqa: E402

QUALITY_RULES = json.loads((ROOT / "config" / "search_quality.json").read_text(encoding="utf-8"))

CLAIM_4 = {"claim_id": "c_x", "project_id": "p_x", "text": "首例 人体 植入 手术", "type": "FACT"}


def _body_ok(text: str) -> str:
    return text if len(text) >= QUALITY_RULES["relevance"]["min_body_len"] else text + "。" * 60


# ---------------- 可插拔测试 provider（免网络） ----------------
class _StubBing:
    """替换 REGISTRY['bing']，保证测试零网络且回退链可被验证。"""
    name = "bing"
    api_key_env = None

    def search(self, query, max_results=5):
        return []

    def fetch(self, url):
        return FetchedPage(url=url, ok=False)

    def extract_evidence(self, page, claim):
        return None


class _DirectProvider:
    name = "sq_direct"
    api_key_env = None

    def search(self, query, max_results=5):
        return [SearchResult(url="https://www.gov.cn/news/1",
                             title="官方公告：首例 人体 植入 手术",
                             snippet="官方发布")]

    def fetch(self, url):
        return FetchedPage(url=url, ok=True, title="官方公告",
                           text="根据官方新闻稿，该公司在 2024 年完成了首例 人体 植入 手术，"
                                "这一进展已获得多家权威媒体转载报道。")

    def extract_evidence(self, page, claim):
        return EvidenceCandidate(excerpt=page.text, source="官方 公告", source_type="official",
                                 reliability="high", support_level="DIRECT_SUPPORT")


class _IrrelevantProvider:
    name = "sq_irrelevant"
    api_key_env = None

    def search(self, query, max_results=5):
        return [SearchResult(url="https://example.com/a", title="首例 人体 植入 手术 资讯", snippet="")]

    def fetch(self, url):
        return FetchedPage(url=url, ok=True, title="x",
                           text="这是一段无关的网页正文，讨论天气与美食，与检索主题没有关系。" * 2)

    def extract_evidence(self, page, claim):
        return None  # IRRELEVANT


class _ContextProvider:
    name = "sq_context"
    api_key_env = None

    def search(self, query, max_results=5):
        return [SearchResult(url="https://example.com/b", title="行业新闻", snippet="首例 相关")]

    def fetch(self, url):
        return FetchedPage(url=url, ok=True, title="行业新闻",
                           text="该公司发布会上提到了行业内的首例 案例，但未给出更多细节。" * 2)

    def extract_evidence(self, page, claim):
        return EvidenceCandidate(excerpt=page.text, source="行业新闻", source_type="media",
                                 reliability="medium", support_level="CONTEXT_ONLY")


class _BlacklistProvider:
    name = "sq_blacklist"
    api_key_env = None

    def search(self, query, max_results=5):
        return [SearchResult(url="https://barcode-maker.com/tool/1",
                             title="首例 人体 植入 手术 生成器", snippet="")]

    def fetch(self, url):
        return FetchedPage(url=url, ok=True, text="x" * 100)

    def extract_evidence(self, page, claim):
        return EvidenceCandidate(excerpt="x" * 100, source="x", support_level="DIRECT_SUPPORT")


class _FetchFailProvider:
    name = "sq_fetchfail"
    api_key_env = None

    def search(self, query, max_results=5):
        return [SearchResult(url="https://example.com/c", title="首例 人体 植入 手术 报道", snippet="")]

    def fetch(self, url):
        return FetchedPage(url=url, ok=False)

    def extract_evidence(self, page, claim):
        return None


class _SearchFailProvider:
    name = "sq_searchfail"
    api_key_env = None

    def search(self, query, max_results=5):
        raise RuntimeError("provider down")

    def fetch(self, url):
        return FetchedPage(url=url, ok=False)

    def extract_evidence(self, page, claim):
        return None


def build(provider_name="none"):
    workspace = Path(tempfile.mkdtemp(prefix="vs_sq_"))
    db = Database(workspace / "state.db")
    config = json.loads((ROOT / "config" / "config.example.json").read_text(encoding="utf-8"))
    config["tools"]["search"] = {"provider": provider_name, "api_key_env": None}
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    mock = MockLLM({"挑战报告": {"verdict": "PASS", "issues": [], "summary": "LLM 部分",
                                 "confidence": 0.5, "note": ""}})
    return Engine(db, Router(config["llm"], mock), rules, workspace / "projects", config, AGENTS)


def claim(db, pid, cid, text, ctype="FACT", risk="LOW", markers=None):
    db.insert_claim({"claim_id": cid, "project_id": pid, "segment_ref": "S1", "text": text,
                     "type": ctype, "risk": risk, "markers": markers or [],
                     "status": "UNVERIFIED", "human_review_required": False})


def evidence(db, pid, cid, eid, source, stype, rel, support_level="DIRECT_SUPPORT", excerpt=None):
    db.insert_evidence({"evidence_id": eid, "project_id": pid, "source": source,
                        "source_type": stype, "reliability": rel,
                        "excerpt": excerpt or f"{source} 摘录", "added_by": "test",
                        "support_level": support_level})
    db.link_claim_evidence(cid, eid)


def run_fc(engine, pid, claim_ids):
    tid = engine.create_task(pid, "fact_check", "fact_check", inputs={"claim_ids": claim_ids})
    engine.run_cycle(pid)
    task = engine.db.get_task(tid)
    art = engine.db.get_artifact(task["artifacts"][0])
    with open(art["path"], encoding="utf-8") as fh:
        records = json.load(fh)["checks"]
    return task, {r["claim_id"]: r for r in records}


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    # ============ 组 1：support_level 语义（搜索层单元） ============
    check("EvidenceCandidate 缺省 support_level=DIRECT_SUPPORT（仅历史兼容）",
          EvidenceCandidate(excerpt="x", source="s").support_level == "DIRECT_SUPPORT")

    r_ok = SearchResult(url="https://example.com/1", title="首例 人体 植入 手术 报道", snippet="")
    r_black = SearchResult(url="https://barcode-maker.com/tool", title="首例 人体 植入 手术 生成器")
    r_pattern = SearchResult(url="https://cool-downloadpage.net/x", title="首例 人体 植入 手术")
    r_bad_url = SearchResult(url="ftp://example.com/x", title="首例 人体 植入 手术")
    r_no_kw = SearchResult(url="https://example.com/2", title="天气", snippet="美食")
    kept, rejected = filter_candidates([r_ok, r_black, r_pattern, r_bad_url, r_no_kw],
                                       CLAIM_4, QUALITY_RULES)
    check("预筛：黑名单域名拒绝", rejected.get("BLACKLISTED_DOMAIN", 0) == 2, f"({rejected})")
    check("预筛：非法 URL 拒绝", rejected.get("BAD_URL", 0) == 1, f"({rejected})")
    check("预筛：无关键词重叠拒绝", rejected.get("NO_KEYWORD_OVERLAP", 0) == 1, f"({rejected})")
    check("预筛：正常候选保留", [x.url for x in kept] == ["https://example.com/1"])

    # 排序在预筛之后（filter_candidates 负责回填 domain），与 _online_gather 调用顺序一致
    to_order, _ = filter_candidates([
        SearchResult(url="https://bbs.example.com/t/1", title="首例 人体 植入 手术 论坛讨论",
                     snippet="y" * 50),
        SearchResult(url="https://www.nature.com/articles/a", title="首例 人体 植入 手术 论文",
                     snippet="z" * 50)],
        CLAIM_4, QUALITY_RULES)
    ordered = order_candidates(to_order, CLAIM_4, QUALITY_RULES)
    check("排序：学术来源优先于论坛/媒体", ordered[0].domain == "www.nature.com")

    # 讨论级提取（claim 词元为空格分隔的中文词，保证词元粒度可控）
    claim_c = {"claim_id": "c_x", "project_id": "p_x", "text": "首例 人体 植入 手术 2024"}
    page = lambda body: FetchedPage(url="https://example.com/p", ok=True, text=body)  # noqa: E731
    cand = _extract_from_page(page(_body_ok(
        "针对相关报道，公司于昨日 否认 完成首例 人体 植入 的说法，并强调 2024 年该手术并未开展，相关传闻不实。")),
        claim_c, QUALITY_RULES)
    check("提取：否定语境 → CONTRADICTS", cand.support_level == "CONTRADICTS")
    cand = _extract_from_page(page(_body_ok(
        "根据官方新闻稿，该公司在 2024 年 3 月完成了首例 人体 植入 手术，"
        "这一消息已获得多家权威媒体报道与转载。")), claim_c, QUALITY_RULES)
    check("提取：多关键词+关键数字 → DIRECT_SUPPORT", cand.support_level == "DIRECT_SUPPORT")
    cand = _extract_from_page(page(_body_ok(
        "根据官方新闻稿，该公司已经完成了首例 人体 植入 手术，"
        "这一进展获得了多家媒体的广泛报道与转载。")), CLAIM_4, QUALITY_RULES)
    check("提取：>=3 关键词（无数字）→ DIRECT_SUPPORT", cand.support_level == "DIRECT_SUPPORT")
    cand = _extract_from_page(page(_body_ok(
        "有媒体报道称，这可能是行业内首例 人体 相关试验，"
        "但具体进展与细节均未对外公布，官方暂未回应。")), CLAIM_4, QUALITY_RULES)
    check("提取：2 关键词 → PARTIAL_SUPPORT", cand.support_level == "PARTIAL_SUPPORT")
    cand = _extract_from_page(page(_body_ok(
        "该公司在近期发布会上提到了行业内的一些首例 案例，"
        "但未给出更多技术细节与数据说明。")), CLAIM_4, QUALITY_RULES)
    check("提取：1 关键词 → CONTEXT_ONLY（不构成讨论，不入库）",
          cand.support_level == "CONTEXT_ONLY")
    check("提取：正文过短 → None（IRRELEVANT）",
          _extract_from_page(FetchedPage(url="https://e.com", ok=True, text="首例 人体"),
                             CLAIM_4, QUALITY_RULES) is None)
    check("提取：无任何关键词出现 → None（IRRELEVANT）",
          _extract_from_page(FetchedPage(url="https://e.com", ok=True,
                                         text="这家公司主要生产消费电子产品，产品销往全球多个市场，"
                                              "受到消费者的广泛欢迎。"),
                             CLAIM_4, QUALITY_RULES) is None)
    check("提取：claim 无词元 → None（IRRELEVANT）",
          _extract_from_page(FetchedPage(url="https://e.com", ok=True, text="x" * 100),
                             {"claim_id": "c", "text": ""}, QUALITY_RULES) is None)

    # ============ 组 2：schema 层（support_level 列 + 迁移 + 未评估=NULL） ============
    ws = Path(tempfile.mkdtemp(prefix="vs_sq_schema_"))
    db_new = Database(ws / "new.db")
    info_new = {r[1]: r for r in db_new.conn.execute("PRAGMA table_info(evidence)")}
    check("新库 evidence 表含 support_level 列", "support_level" in info_new)
    check("新库 support_level 列可空（未评估=NULL）", info_new["support_level"][3] == 0)
    db_new.insert_evidence({"evidence_id": "e_def", "project_id": "p1", "source": "s1"})
    db_new.insert_evidence({"evidence_id": "e_exp", "project_id": "p1", "source": "s2",
                            "support_level": "PARTIAL_SUPPORT"})
    check("未标注 support_level → NULL（未评估，不默认 DIRECT_SUPPORT）",
          db_new.get_evidence("e_def")["support_level"] is None)
    check("插入显式 support_level 生效",
          db_new.get_evidence("e_exp")["support_level"] == "PARTIAL_SUPPORT")
    db_new.close()

    # 迁移 A：V2.0.0 老库（无 support_level 列）→ 加列可空，历史行 NULL（未评估）
    old_path = ws / "old.db"
    old = sqlite3.connect(str(old_path))
    old.execute("""CREATE TABLE evidence (
        evidence_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, source TEXT NOT NULL,
        source_type TEXT NOT NULL DEFAULT 'unknown', publication_date TEXT,
        reliability TEXT NOT NULL DEFAULT 'unknown', excerpt TEXT, url TEXT,
        added_by TEXT, task_id TEXT, created_at REAL NOT NULL)""")
    old.execute("INSERT INTO evidence(evidence_id, project_id, source, created_at)"
                " VALUES('e_old','p_old','s_old',1.0)")
    old.commit()
    old.close()
    db_mig = Database(old_path)
    info_mig = {r[1]: r for r in db_mig.conn.execute("PRAGMA table_info(evidence)")}
    check("迁移A：support_level 列已添加且可空",
          "support_level" in info_mig and info_mig["support_level"][3] == 0)
    check("迁移A：历史行未评估=NULL（不默认 DIRECT_SUPPORT）",
          db_mig.list_evidence("p_old")[0]["support_level"] is None)
    db_mig.close()

    # 迁移 B：V2.0.1 库（support_level NOT NULL DEFAULT 'DIRECT_SUPPORT'）→ 重建为可空，
    #         历史行已存值原样保留，新行可存 NULL
    v201_path = ws / "v201.db"
    v201 = sqlite3.connect(str(v201_path))
    v201.execute("""CREATE TABLE evidence (
        evidence_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, source TEXT NOT NULL,
        source_type TEXT NOT NULL DEFAULT 'unknown', publication_date TEXT,
        reliability TEXT NOT NULL DEFAULT 'unknown', excerpt TEXT, url TEXT,
        added_by TEXT, task_id TEXT,
        support_level TEXT NOT NULL DEFAULT 'DIRECT_SUPPORT',
        created_at REAL NOT NULL)""")
    v201.execute("INSERT INTO evidence(evidence_id, project_id, source, support_level, created_at)"
                 " VALUES('e_v201','p_v201','s_v201','DIRECT_SUPPORT',1.0)")
    v201.commit()
    v201.close()
    db_v201 = Database(v201_path)
    info_v201 = {r[1]: r for r in db_v201.conn.execute("PRAGMA table_info(evidence)")}
    check("迁移B：NOT NULL 旧约束重建为可空", info_v201["support_level"][3] == 0)
    check("迁移B：历史行已存值原样保留",
          db_v201.list_evidence("p_v201")[0]["support_level"] == "DIRECT_SUPPORT")
    db_v201.insert_evidence({"evidence_id": "e_null", "project_id": "p_v201",
                             "source": "s_null"})
    check("迁移B：重建后新行可存 NULL（未评估）",
          db_v201.get_evidence("e_null")["support_level"] is None)
    db_v201.close()

    # ============ 组 3：离线综合（provider=none，库内证据） ============
    engine = build("none")
    db = engine.db
    pid = engine.create_project("离线综合")
    claim(db, pid, "q_001", "某机构完成首例 人体 植入", risk="LOW")
    claim(db, pid, "q_002", "某机构完成首例 人体 植入", risk="LOW")
    claim(db, pid, "q_003", "某机构完成首例 人体 植入", risk="LOW")
    claim(db, pid, "q_004", "某机构完成首例 人体 植入", risk="CRITICAL", markers=["首例"])
    claim(db, pid, "q_005", "某机构完成首例 人体 植入", risk="HIGH")
    claim(db, pid, "q_006", "某机构完成首例 人体 植入", risk="LOW")
    claim(db, pid, "q_007", "某机构完成首例 人体 植入", risk="LOW")
    evidence(db, pid, "q_001", "e_101", "科技媒体", "media", "medium",
             support_level="PARTIAL_SUPPORT")
    evidence(db, pid, "q_002", "e_102", "官方公告", "official", "high",
             support_level="DIRECT_SUPPORT")
    evidence(db, pid, "q_003", "e_103", "官方公告", "official", "high",
             support_level="CONTRADICTS", excerpt="官方否认完成任何植入")
    evidence(db, pid, "q_004", "e_104", "企业宣传稿", "media", "medium",
             support_level="DIRECT_SUPPORT")
    evidence(db, pid, "q_005", "e_105", "科技媒体", "media", "medium",
             support_level="PARTIAL_SUPPORT")
    evidence(db, pid, "q_007", "e_106", "某百科", "encyclopedia", "medium",
             support_level="CONTEXT_ONLY")
    _, by_id = run_fc(engine, pid, ["q_001", "q_002", "q_003", "q_004", "q_005", "q_006", "q_007"])
    check("综合：仅 PARTIAL → Mostly Confirmed（不自动 Confirmed）",
          by_id["q_001"]["conclusion"] == "Mostly Confirmed"
          and by_id["q_001"]["verification_path"] == "PARTIAL_SUPPORT")
    check("综合：DIRECT+官方 high → Confirmed（多因素综合而非仅支持关系）",
          by_id["q_002"]["conclusion"] == "Confirmed"
          and by_id["q_002"]["human_review_required"] is False)
    check("CONTRADICTS → Disputed 且必走人工（禁止自动 False）",
          by_id["q_003"]["conclusion"] == "Disputed"
          and by_id["q_003"]["conclusion"] != "False"
          and by_id["q_003"]["human_review_required"] is True
          and by_id["q_003"]["verification_path"] == "CONTRADICTS")
    check("CRITICAL + 仅 medium 直接支持 → 保留人工（不因搜到证据绕过）",
          by_id["q_004"]["human_review_required"] is True)
    check("HIGH + 仅 PARTIAL → 保留人工",
          by_id["q_005"]["human_review_required"] is True)
    check("离线无来源 → Unsupported + 人工，path=NO_RELIABLE_SOURCE",
          by_id["q_006"]["conclusion"] == "Unsupported"
          and by_id["q_006"]["human_review_required"] is True
          and by_id["q_006"]["verification_path"] == "NO_RELIABLE_SOURCE")
    check("库内 CONTEXT_ONLY 证据不参与综合（不自动放行）",
          by_id["q_007"]["conclusion"] == "Unsupported")

    # 非 FACT 类型返回 verification_path=TYPE_CHECKED
    claim(db, pid, "q_008", "因此这条结论还需要更多验证", ctype="INFERENCE", risk="MEDIUM")
    _, by8 = run_fc(engine, pid, ["q_008"])
    check("非 FACT 类型核查记录 verification_path=TYPE_CHECKED",
          by8["q_008"].get("verification_path") == "TYPE_CHECKED")
    engine.db.close()

    # ============ 组 4：在线候选→证据（fake provider，零网络） ============
    REGISTRY["bing"] = _StubBing()   # 隔离真实网络，回退链可测
    for p in (_DirectProvider(), _IrrelevantProvider(), _ContextProvider(),
              _BlacklistProvider(), _FetchFailProvider(), _SearchFailProvider()):
        register_search_provider(p)

    eng_d = build("sq_direct")
    pid_d = eng_d.create_project("在线直接支持")
    claim(eng_d.db, pid_d, "r_001", "首例 人体 植入 手术", risk="LOW")
    _, by_d = run_fc(eng_d, pid_d, ["r_001"])
    check("在线：DIRECT+official high → Confirmed",
          by_d["r_001"]["conclusion"] == "Confirmed")
    check("在线：证据入库且 support_level=DIRECT_SUPPORT",
          any(e["support_level"] == "DIRECT_SUPPORT" for e in eng_d.db.list_evidence(pid_d)))
    evs = [e for e in eng_d.db.events_since(pid_d) if e["type"] == "SEARCH_EVIDENCE"]
    check("SEARCH_EVIDENCE 事件存在且 payload 含 claim_id",
          len(evs) == 1 and evs[0]["payload"].get("claim_id") == "r_001")
    keys = set(evs[0]["payload"])
    check("SEARCH_EVIDENCE 含检索统计（可追溯/可区分）",
          {"query", "search_results", "relevant", "fetched", "usable"} <= keys)
    check("检索记录含 verification_path=DIRECT_SUPPORT",
          by_d["r_001"]["verification_path"] == "DIRECT_SUPPORT")
    eng_d.db.close()

    eng_c = build("sq_context")
    pid_c = eng_c.create_project("CONTEXT_ONLY 不入库")
    claim(eng_c.db, pid_c, "r_002", "首例 人体 植入 手术", risk="LOW")
    _, by_c = run_fc(eng_c, pid_c, ["r_002"])
    check("在线：CONTEXT_ONLY 候选不入证据库",
          len(eng_c.db.list_evidence(pid_c)) == 0)
    check("在线：全部候选不入库 → Unsupported + path=INSUFFICIENT_EVIDENCE",
          by_c["r_002"]["conclusion"] == "Unsupported"
          and by_c["r_002"]["verification_path"] == "INSUFFICIENT_EVIDENCE")
    eng_c.db.close()

    eng_i = build("sq_irrelevant")
    pid_i = eng_i.create_project("IRRELEVANT 不入库")
    claim(eng_i.db, pid_i, "r_003", "首例 人体 植入 手术", risk="LOW")
    _, by_i = run_fc(eng_i, pid_i, ["r_003"])
    check("在线：IRRELEVANT（extract=None）不入证据库",
          len(eng_i.db.list_evidence(pid_i)) == 0
          and by_i["r_003"]["verification_path"] == "INSUFFICIENT_EVIDENCE")
    eng_i.db.close()

    eng_b = build("sq_blacklist")
    pid_b = eng_b.create_project("黑名单预筛")
    claim(eng_b.db, pid_b, "r_004", "首例 人体 植入 手术", risk="LOW")
    _, by_b = run_fc(eng_b, pid_b, ["r_004"])
    check("在线：域名黑名单拦截 → path=NO_RELEVANT_RESULT",
          by_b["r_004"]["verification_path"] == "NO_RELEVANT_RESULT"
          and len(eng_b.db.list_evidence(pid_b)) == 0)
    eng_b.db.close()

    eng_f = build("sq_fetchfail")
    pid_f = eng_f.create_project("抓取失败")
    claim(eng_f.db, pid_f, "r_005", "首例 人体 植入 手术", risk="LOW")
    _, by_f = run_fc(eng_f, pid_f, ["r_005"])
    check("在线：fetch 失败 → path=FETCH_FAILED（与搜不到区分）",
          by_f["r_005"]["verification_path"] == "FETCH_FAILED")
    eng_f.db.close()

    eng_s = build("sq_searchfail")
    pid_s = eng_s.create_project("搜索失败")
    claim(eng_s.db, pid_s, "r_006", "首例 人体 植入 手术", risk="LOW")
    _, by_s = run_fc(eng_s, pid_s, ["r_006"])
    check("在线：search 全部失败 → path=SEARCH_FAILED（与无相关结果区分）",
          by_s["r_006"]["verification_path"] == "SEARCH_FAILED")
    eng_s.db.close()

    # ============ 组 5：人工来源语义（added_by=human ≠ DIRECT_SUPPORT） ============
    # 同一个人工来源（同一 source、同一 added_by=human），三种显式支持关系 + 一个未标注
    eng_m = build("none")
    db_m = eng_m.db
    pid_m = eng_m.create_project("人工来源语义")
    same_src = "人工提供 来源（同一来源）"
    claim(db_m, pid_m, "m_001", "某机构完成首例 人体 植入", risk="LOW")
    claim(db_m, pid_m, "m_002", "某机构完成首例 人体 植入", risk="LOW")
    claim(db_m, pid_m, "m_003", "某机构完成首例 人体 植入", risk="LOW")
    claim(db_m, pid_m, "m_004", "某机构完成首例 人体 植入", risk="LOW")
    evidence(db_m, pid_m, "m_001", "e_m1", same_src, "official", "high",
             support_level="DIRECT_SUPPORT", excerpt="2024年完成首例 人体 植入")
    evidence(db_m, pid_m, "m_002", "e_m2", same_src, "official", "high",
             support_level="PARTIAL_SUPPORT", excerpt="部分完成 人体 植入 相关试验")
    evidence(db_m, pid_m, "m_003", "e_m3", same_src, "official", "high",
             support_level="CONTRADICTS", excerpt="官方否认完成任何植入")
    evidence(db_m, pid_m, "m_004", "e_m4", same_src, "official", "high",
             support_level=None, excerpt="未标注支持关系")
    _, by_m = run_fc(eng_m, pid_m, ["m_001", "m_002", "m_003", "m_004"])
    check("人工来源 DIRECT_SUPPORT（显式标注）→ Confirmed",
          by_m["m_001"]["conclusion"] == "Confirmed")
    check("人工来源 PARTIAL_SUPPORT（显式标注）→ Mostly Confirmed（不自动视为 DIRECT）",
          by_m["m_002"]["conclusion"] == "Mostly Confirmed"
          and by_m["m_002"]["conclusion"] != "Confirmed")
    check("人工来源 CONTRADICTS（显式标注）→ Disputed（不自动视为 DIRECT，也不自动 False）",
          by_m["m_003"]["conclusion"] == "Disputed"
          and by_m["m_003"]["conclusion"] not in ("Confirmed", "False")
          and by_m["m_003"]["human_review_required"] is True)
    check("同一人工来源三种标注产出三种不同结论（不被 added_by=human 统一视为 DIRECT）",
          len({by_m[k]["conclusion"] for k in ("m_001", "m_002", "m_003")}) == 3)
    check("未标注 support_level 的人工高质量来源 → 不提高结论（Unsupported + 人工）",
          by_m["m_004"]["conclusion"] == "Unsupported"
          and by_m["m_004"]["conclusion"] != "Confirmed"
          and by_m["m_004"]["human_review_required"] is True
          and by_m["m_004"]["verification_path"] == "UNEVALUATED_MANUAL")
    check("UNEVALUATED_MANUAL 与无来源 NO_RELIABLE_SOURCE 可区分",
          by_m["m_004"]["verification_path"] != "NO_RELIABLE_SOURCE")
    eng_m.db.close()

    # 证据登记链路：manual_sources 的 support_level 逐条透传，未标注存 NULL（未评估）
    eng_w = build("none")
    db_w = eng_w.db
    pid_w = eng_w.create_project("人工来源登记")
    claim(db_w, pid_w, "w_001", "某机构完成首例 人体 植入", risk="LOW")
    engine_w_task = eng_w.create_task(pid_w, "evidence_index", "evidence", inputs={"manual_sources": [
        {"source": "人工来源A", "source_type": "official", "reliability": "high",
         "excerpt": "2024年完成首例 人体 植入", "support_level": "DIRECT_SUPPORT"},
        {"source": "人工来源B", "source_type": "media", "reliability": "medium",
         "excerpt": "部分实现 人体 植入", "support_level": "PARTIAL_SUPPORT"},
        {"source": "人工来源C", "source_type": "official", "reliability": "high",
         "excerpt": "官方否认完成首例 人体 植入", "support_level": "CONTRADICTS"},
        {"source": "人工来源D", "source_type": "official", "reliability": "high",
         "excerpt": "未标注支持关系"},
    ]})
    eng_w.run_cycle(pid_w)
    reg = {e["source"]: e["support_level"] for e in db_w.list_evidence(pid_w)}
    check("登记链路：manual_sources 显式 support_level 逐条透传",
          reg.get("人工来源A") == "DIRECT_SUPPORT"
          and reg.get("人工来源B") == "PARTIAL_SUPPORT"
          and reg.get("人工来源C") == "CONTRADICTS")
    check("登记链路：未标注 support_level 的人工来源存 NULL（未评估）",
          "人工来源D" in reg and reg["人工来源D"] is None)
    check("登记链路任务完成", db_w.get_task(engine_w_task)["status"] == "SUCCEEDED")
    eng_w.db.close()

    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

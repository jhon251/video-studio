"""《永生选题》V2 在线核查管线驱动（真实搜索：bing 免密钥 / tavily 走 .env）。

流程：script(定稿) → claim_extract → evidence → skeptic → fact_check(在线检索)
→ conflict_detect → HITL 闸门。不改文案、不改 Claim。
输出：逐 Claim 全字段报告 + 统计 + 与离线基线的对比。
"""

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.core.env import load_env
load_env(ROOT / ".env")  # 密钥只从 .env 读取

from video_studio.db.schema import Database
from video_studio.core.engine import Engine
from video_studio.llm.router import MockLLM, Router
from video_studio.tools.search_provider import resolve_provider

for mod in ("script", "critic", "fact_check", "claim_extractor", "evidence",
            "conflict_detector", "pm", "topic"):
    __import__(f"video_studio.agents.{mod}.agent")
from video_studio.agents.base import AGENTS

SCRIPT = {
    "segments": [
        {"chapter": "开场", "duration_s": 55, "visual_hint": "",
         "narration": "《黑镜》里有个地方叫圣朱尼佩罗，人死了，意识搬进服务器，永远活在1987年的海滩上。《刀剑神域》的Underworld，也是一个把人脑塞进机器的故事。影视作品里，这一步经常一笔带过：扫描，上传，永生。今天我们把这三步拆开看：科学家们干到哪一步了，以及最后那一步，卡住的可能不是技术。"},
        {"chapter": "定义", "duration_s": 60, "visual_hint": "",
         "narration": "先把'大脑放进电脑'拆成三个动作。第一步，扫描：把大脑的结构完整读出来。第二步，复制：在电脑里重建一个功能一样的脑。第三步，转移：让'你'本人住进去。注意，这三步的难度不在一个量级，而'永生'这个词，把三步打包卖成了一个产品。后面就按这三步走。"},
        {"chapter": "扫描线", "duration_s": 60, "visual_hint": "",
         "narration": "先说扫描，这一步真有人在干。2023年，科学家完成了成年果蝇的全脑连接组——十四万个神经元，每条连接都画了出来，发在《科学》上。2025年，中国团队放出了毫米级的小鼠全脑图谱，这是目前最大的哺乳动物全脑连接组。进展神速，但请注意一个词：连接组。它画的是一张接线图，不是意识。果蝇被查了个底朝天，也没有因此学会写诗。"},
        {"chapter": "尺度", "duration_s": 55, "visual_hint": "",
         "narration": "从果蝇到人，差多远？人脑大约八百六十亿个神经元，突触按百万亿算。果蝇十四万，人比它多五个数量级，而且扫描精度要求每条连接都被记录。再看一个参照物：OpenWorm项目，模拟一条只有三百零二个神经元的线虫，跑了十几年，到现在也没人敢说那条虚拟线虫'活'了。三百个神经元尚且如此。"},
        {"chapter": "复制线", "duration_s": 60, "visual_hint": "",
         "narration": "假设扫描精度够了，还有第二道坎：一张接线图，装不下一个'你'。神经科学现在的基本共识是，记忆不是存在脑子里的文件，而是每次回忆时重新组装出来的。要复制的远不止连接关系：突触强度、神经递质、胶质细胞、甚至分子层面的状态——这张清单到底有多长，学界没有公认答案。换句话说，我们连'复制大脑需要读哪些信息'这个问题，都还没回答完整。"},
        {"chapter": "运行", "duration_s": 50, "visual_hint": "",
         "narration": "就算读出来了，第三步是运行。一块人脑，功耗二十瓦上下，用数据中心去模拟它，耗电可能是一座小城的规模。算力、能耗、散热，每一项都是钱。更麻烦的是，我们不知道模拟到什么颗粒度，'意识'才会出现——突触级别？分子级别？这个问题的答案，直接决定这个项目是贵，还是贵到永远做不起。"},
        {"chapter": "哲学墙一", "duration_s": 60, "visual_hint": "",
         "narration": "退一步说，技术全部到位，还有一道哲学的墙。有个老思想实验叫传送机：把你拆成原子，在火星重新组装，那个火星上的你，是你吗？上传大脑是同一个问题：扫描产生的那个副本，是'你'，还是一份关于你的高质量复制品？哲学家分两派，一派说信息一致，那就是你；另一派说，连续性断了就是断了。两派吵了几十年，没有结果。"},
        {"chapter": "哲学墙二", "duration_s": 55, "visual_hint": "",
         "narration": "把这个问题往生活里拉近一点。今晚睡一觉，明早醒来，你凭什么确定自己还是昨天那个人？日常里靠的是记忆和身体的连续。上传恰恰切断了两样：身体留在外面，记忆被复制了一份。假如副本醒来说'我是你'，原身还活着——谁拥有你的人生？这个问题难住的不只是哲学家，还有将来的继承法和离婚律师。"},
        {"chapter": "现实边缘", "duration_s": 55, "visual_hint": "",
         "narration": "这条线上已经有人在卖东西了。2018年，一家叫Nectome的创业公司推出'大脑保存'服务，宣传语大意是：现在把大脑冻存，将来上传成数字永生。定价一两万美元，一次付清。这家公司后来因为伦理争议翻了车，但它留下的问题还在：未来上传还没影，'卖念想'的生意已经开张了。"},
        {"chapter": "伦理法律", "duration_s": 50, "visual_hint": "",
         "narration": "还有一串现实问题排队等着：副本算人吗？它有权利吗？死后上传的法律地位是什么？谁有权删除一个'数字人'？今天的法律对这些问题基本空白。技术可以慢，社会规则必须提前想，否则等第一例真做出来那天，吵的就不是哲学，是官司。"},
        {"chapter": "结论", "duration_s": 55, "visual_hint": "",
         "narration": "把三层收拢，给一个冷静的判断。扫描：刚起步，图谱越来越细，几十年内还会有大进展。复制：没有时间表，因为连'该复制什么'都没定论。转移：可能压根不是技术问题。我的判断是，把永生押在上传上，买的是彩票，不是保险。真正确定的东西反而很朴素：趁身体还在这边，多留点真实的人生。"},
        {"chapter": "结尾", "duration_s": 45, "visual_hint": "",
         "narration": "回到最初的问题：大脑放进电脑，人能永生吗？结构上，科学家刚开始画图；功能上，没人敢给时间表；'你'能不能住进去，这个问题可能永远没有工程学的答案。假如有一天副本上线，对你说'我就是你'——你会觉得，自己永生了吗？评论区聊聊。"},
    ],
    "summary": "永生选题定稿（用户提供，核查前不改动）",
}

OFFLINE_BASELINE_NEEDS_HUMAN = 51  # 离线核查（无来源）基线


def main() -> int:
    project_name = sys.argv[1] if len(sys.argv) > 1 else "yongsheng-online"
    db = Database(ROOT / "projects" / "video_studio.db")
    config = json.loads((ROOT / "config" / "config.yongsheng.json").read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    provider = resolve_provider(config)
    print(f"SEARCH_PROVIDER={provider.name}")
    engine = Engine(db, Router(config["llm"], MockLLM(config["llm"]["mock"]["responses"],
                      config["llm"]["mock"]["default"])), rules, ROOT / "projects", config, AGENTS)
    pid = engine.create_project("大脑放进电脑，人真的能永生吗？在线核查", project_name)

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
    by_id = {c["claim_id"]: c for c in claims}
    fc = [t for t in db.list_tasks(pid) if t["task_type"] == "fact_check"][0]
    fc_checks = {}
    for art_id in fc["artifacts"]:
        art = db.get_artifact(art_id)
        with open(art["path"], encoding="utf-8") as fh:
            for r in json.load(fh).get("checks", []):
                fc_checks[r["claim_id"]] = r
    sk = [t for t in db.list_tasks(pid) if t["task_type"] == "skeptic_check"][0]
    attacks_by_claim = {}
    for art_id in sk["artifacts"]:
        art = db.get_artifact(art_id)
        with open(art["path"], encoding="utf-8") as fh:
            for a in json.load(fh).get("issues", []):
                for cid in a.get("claim_ids") or []:
                    attacks_by_claim.setdefault(cid, []).append(a)
    conflicts_by_claim = {}
    for c in db.list_conflicts(pid):
        conflicts_by_claim.setdefault(c["claim_id"], []).append(c)

    rows = []
    for c in claims:
        r = fc_checks.get(c["claim_id"], {})
        s = r.get("search_stats") or {}
        evs = db.evidence_for_claim(c["claim_id"])
        rel_map = {"high": 3, "medium": 2, "low": 1, "unknown": 0}
        quality = ("high" if any(e["reliability"] == "high" for e in evs)
                   else "medium" if any(e["reliability"] == "medium" for e in evs)
                   else "low" if evs else "none")
        rows.append({
            "claim_id": c["claim_id"],
            "text": c["text"],
            "risk": c["risk"], "type": c["type"],
            "conclusion": r.get("conclusion"),
            "confidence": r.get("confidence"),
            "evidence_refs": r.get("evidence_refs", []),
            "source_count": len(evs),
            "source_quality": quality,
            "skeptic_issues": [a["category"] for a in attacks_by_claim.get(c["claim_id"], [])],
            "conflict_status": "CONFLICT" if c["claim_id"] in conflicts_by_claim else "NONE",
            "human_review_required": bool(c["human_review_required"]),
            "human_review_reason": (r.get("reasoning") or "") if bool(c["human_review_required"]) else "",
            "status": c["status"],
            "verification_path": r.get("verification_path"),
            "query": s.get("query"),
            "provider_used": s.get("provider"),
            "fell_back": s.get("fell_back", 0),
            "chain_attempts": s.get("chain_attempts", []),
            "search_rejected": s.get("rejected", {}),
        })

    needs = [r for r in rows if r["human_review_required"]]
    concl = Counter((r["conclusion"] or "None") for r in rows)
    # ---------- 12 项日志聚合（纯统计，不改结论规则与阈值） ----------
    search_records = [r.get("search_stats") for r in fc_checks.values() if r.get("search_stats")]
    provider_usage: dict = {}
    for s in search_records:
        for a in s.get("chain_attempts", []):
            u = provider_usage.setdefault(a["provider"], {"attempts": 0, "served_results": 0})
            u["attempts"] += 1
            if a["results"] > 0:
                u["served_results"] += 1
    rejected_totals = Counter()
    fetched_ok = 0
    for s in search_records:
        fetched_ok += s.get("fetched", 0)
        for k, v in (s.get("rejected") or {}).items():
            rejected_totals[k] += v
    inserted = db.list_evidence(pid)
    inserted_levels = Counter((e.get("support_level") or "NULL") for e in inserted)
    attempted = len(search_records)
    success = sum(1 for s in search_records if s.get("search_results", 0) > 0)
    stats = {
        "project": pid,
        "provider": provider.name,
        "claim_total": len(rows),
        "risk": dict(Counter(c["risk"] for c in claims)),
        "conclusion": dict(concl),
        "verification_path": dict(Counter((r["verification_path"] or "None") for r in rows)),
        "needs_human": len(needs),
        "auto_passed": len(rows) - len(needs),
        "needs_human_reasons": Counter(
            (r["human_review_reason"][:40] or "?") for r in needs),
        "offline_baseline_needs_human": OFFLINE_BASELINE_NEEDS_HUMAN,
        "reduction_vs_offline": OFFLINE_BASELINE_NEEDS_HUMAN - len(needs),
        "search": {
            "attempted_claims": attempted,
            "search_success_claims": success,
            "search_success_rate": round(success / attempted, 4) if attempted else None,
            "raw_search_results": sum(s.get("search_results", 0) for s in search_records),
            "relevant_search_results": sum(s.get("relevant", 0) for s in search_records),
            "provider_usage": provider_usage,
            "fell_back_claims": sum(1 for s in search_records if s.get("fell_back")),
            "fetch_ok": fetched_ok,
            "fetch_failed": rejected_totals.get("FETCH_FAILED", 0),
            "rejected_reasons": dict(rejected_totals),
        },
        "evidence": {
            "registered": len(inserted),
            "support_levels": dict(inserted_levels),
            "extracted_levels": {
                "DIRECT_SUPPORT": inserted_levels.get("DIRECT_SUPPORT", 0),
                "PARTIAL_SUPPORT": inserted_levels.get("PARTIAL_SUPPORT", 0),
                "CONTRADICTS": inserted_levels.get("CONTRADICTS", 0),
                "CONTEXT_ONLY": rejected_totals.get("CONTEXT_ONLY", 0),
                "IRRELEVANT": rejected_totals.get("IRRELEVANT", 0),
            },
        },
        "skeptic_attacks": sum(len(v) for v in attacks_by_claim.values()),
        "conflicts": len(db.list_conflicts(pid)),
        "evidence_registered": len(inserted),
    }
    out = ROOT / "projects" / "_drafts" / f"{project_name}_在线核查报告.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"stats": stats, "rows": rows},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"REPORT={out}")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

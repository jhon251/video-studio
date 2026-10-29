"""4.x Phase 4-D 证据收集（**离线、只读、确定性**）：供给韧性底座的可核验证据。

产出（docs/regression_2x/logs/）：
  phase4d_taxonomy.json      —— 失败分类表（错误码 → 类别/可重试/处置）
  phase4d_retry_plan.json    —— 重试计划（429/超时/Retry-After/预算）
  phase4d_cache.json         —— 供给缓存行为（默认关闭 / 命中 / 过期 / 损坏 / 只存元数据）
  phase4d_paths.json         —— 八条路径的实测结果（含 fail-closed 判定）
  phase4d_failclosed.json    —— 引擎级 fail-closed 与"不污染"证据
  phase4d_evidence_summary.txt

用法：python docs/regression_2x/phase4d_evidence.py
"""
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.retrieval.agent import kw_tokens  # noqa: E402
from video_studio.core.supply import (SUPPLY_SCHEMA, SupplyCache, cache_key,  # noqa: E402
                                      classify_failure, degradation_plan, policy_fingerprint,
                                      retry_decision, summarize, taxonomy_table)
from video_studio.tools.base import ToolContext  # noqa: E402
from video_studio.tools.material_provider import (DEFAULT_POLICY, LocalCatalogProvider,  # noqa: E402
                                                 MaterialQuery, TransportError,
                                                 provider_from_config)
from video_studio.tools.supply import (ResilientSupply, candidate_from_metadata,  # noqa: E402
                                       candidate_metadata)

LOGS = ROOT / "docs" / "regression_2x" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
FFPROBE = ROOT / "bin" / "ffprobe.exe"
REAL_JPG = ROOT / "output" / "run03" / "asset_cache" / "files" / "r3_S01-B01_3.img.jpg"
REAL_DB = ROOT / "projects" / "video_studio.db"
LINES = []


def say(s):
    print(s, flush=True)
    LINES.append(str(s))


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


WORK = Path(tempfile.mkdtemp(prefix="vs_4d_evidence_"))
CAT = WORK / "catalog"
MEDIA = WORK / "media"
CAT.mkdir(parents=True, exist_ok=True)
MEDIA.mkdir(parents=True, exist_ok=True)
GOOD = WORK / "good.jpg"
shutil.copy2(REAL_JPG, GOOD)
NAME = "virtual reality headset demo.jpg"
TEXT = "virtual reality headset device form factor"
CTX = ToolContext(role="retrieval", project_id="p_4d_evidence", project_dir=WORK, db=None,
                  config={"tools": {"ffmpeg": {"path": str(FFMPEG), "ffprobe": str(FFPROBE)}}})


def catalogue(items):
    (CAT / "catalogue.json").write_text(json.dumps({"items": items}, ensure_ascii=False),
                                        encoding="utf-8")


def rec(path=None, url=None, license="CC BY-SA 4.0", source_id="s1", name=NAME):
    d = {"source_id": source_id, "name": name, "license": license,
         "attribution": "Evidence Author / CC BY-SA 4.0"}
    d["file" if path else "url"] = str(path or url)
    return d


def provider(items, policy=None, transport=None, cls=LocalCatalogProvider):
    catalogue(items)
    pol = {**DEFAULT_POLICY, "provider": "local_catalog", "catalog": str(CAT), "timeout_s": 5,
           "max_retries": 2, "rate_limit_backoff_s": 0.0, "backoff_base_s": 0.0, "max_backoff_s": 0.0,
           **(policy or {})}
    return cls(pol, transport=transport, catalog_dir=CAT)


def query(text=TEXT):
    return MaterialQuery(text=text, keywords=kw_tokens(text))


def run(prov, text=TEXT, cache_enabled=False):
    sup = ResilientSupply(prov, policy=prov.policy, project_dir=WORK, cache_enabled=cache_enabled)
    found, smeta = sup.search(query(text), CTX)
    fetched, fmeta = sup.fetch(found, CTX)
    verified = ResilientSupply.verified_only(fetched)
    rep = sup.report(fetched=fetched, facts=ResilientSupply.degradation_facts(
        has_verified_external=bool(verified), has_local_index=False, provider_requested=True))
    return sup, found, fetched, verified, smeta, fmeta, rep


class FixedTransport:
    def __init__(self, code, retry_after_s=None):
        self.code, self.retry_after_s, self.calls = code, retry_after_s, 0

    def get(self, url, max_bytes, timeout_s):
        self.calls += 1
        raise TransportError(self.code, "注入：{}".format(self.code),
                             retry_after_s=self.retry_after_s)


say("=== 4.x Phase 4-D 供给韧性：证据（离线、只读）===")
say("schema={}  真实数据库 sha256={}…".format(SUPPLY_SCHEMA,
                                              sha256_file(REAL_DB)[:16] if REAL_DB.is_file() else "-"))

# 1) 分类表
tax = taxonomy_table()
(LOGS / "phase4d_taxonomy.json").write_text(json.dumps(tax, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
by_class = {}
for r in tax:
    by_class.setdefault(r["class"], []).append(r["code"])
say("\n[1] 失败分类表：{} 个错误码 → {}".format(
    len(tax), {k: len(v) for k, v in sorted(by_class.items())}))
for k in sorted(by_class):
    say("    {:<10s} {}".format(k, ", ".join(sorted(by_class[k]))))
say("    未登记码处理：{}".format(classify_failure("NOT_REGISTERED_CODE")))

# 2) 重试计划
pol = {"max_retries": 2, "rate_limit_retries": 3, "rate_limit_backoff_s": 10.0,
       "backoff_base_s": 0.2, "max_backoff_s": 30.0, "retry_after_max_s": 30.0}
plan = {
    "rate_limited_attempts": [retry_decision("PROVIDER_RATE_LIMITED", i, pol) for i in range(4)],
    "timeout_attempts": [retry_decision("PROVIDER_TIMEOUT", i, pol) for i in range(3)],
    "retry_after_45s": retry_decision("PROVIDER_RATE_LIMITED", 0, pol, retry_after_s=45),
    "retry_after_5s": retry_decision("PROVIDER_RATE_LIMITED", 0, pol, retry_after_s=5),
    "license_no_retry": retry_decision("ASSET_LICENSE_UNCLEAR", 0, pol),
    "http_404_no_retry": retry_decision("PROVIDER_HTTP_404", 0, pol),
}
(LOGS / "phase4d_retry_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
say("\n[2] 重试计划（有界、确定性）：429 → {}；超时 → {}".format(
    [p["sleep_s"] for p in plan["rate_limited_attempts"]],
    [p["sleep_s"] for p in plan["timeout_attempts"]]))
say("    Retry-After 45s → {}s（上限内采纳）；5s → {}s（不覆盖本地退避）；许可/404 → 不重试".format(
    plan["retry_after_45s"]["sleep_s"], plan["retry_after_5s"]["sleep_s"]))

# 3) 缓存行为
c_off = SupplyCache(WORK / "off", enabled=False)
c_on = SupplyCache(WORK / "on", enabled=True, ttl_s=900)
_, off_meta = c_off.get("k")
cands = [candidate_metadata(c) for c in provider([rec(GOOD)]).search(query(), CTX)]
key = cache_key("local_catalog", TEXT, 10, ("image",), {"virtual"}, {"provider": "local_catalog"})
c_on.put(key, cands)
hit, hit_meta = c_on.get(key)
restored = candidate_from_metadata(hit[0])
cache_ev = {"disabled_meta": off_meta, "hit_meta": hit_meta, "stats": c_on.stats,
            "stored_fields": sorted(cands[0].keys()),
            "restored": {"status": restored.status, "download_status": restored.download_status,
                         "license_cleared": restored.license_cleared,
                         "downloaded_path": restored.downloaded_path,
                         "verified": restored.to_candidate()["verified"]}}
(LOGS / "phase4d_cache.json").write_text(json.dumps(cache_ev, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
say("\n[3] 供给缓存：默认 {}；命中={}；恢复候选 status={} verified={}".format(
    off_meta["reason"], hit_meta["reason"], cache_ev["restored"]["status"],
    cache_ev["restored"]["verified"]))
say("    缓存字段（只存元数据）：{}".format(", ".join(cache_ev["stored_fields"])))

# 4) 八条路径
paths = []


def add(name, ok, detail):
    paths.append({"case": name, "fail_closed": bool(ok), "detail": detail})
    say("    {:<26s} fail_closed={} {}".format(name, bool(ok), json.dumps(
        detail, ensure_ascii=False)[:150]))


say("\n[4] 八条路径（离线注入）")
sup, found, fetched, verified, smeta, fmeta, rep = run(provider([rec(GOOD)]))
add("1 正常", len(verified) == 1 and rep["degradation"]["rung"] == "EXTERNAL_VERIFIED",
    {"verified": len(verified), "rung": rep["degradation"]["rung"]})

cprov = provider([rec(GOOD)])
sup2 = ResilientSupply(cprov, policy=cprov.policy, project_dir=WORK, cache_enabled=True)
f1, m1 = sup2.search(query("cache key A"), CTX)
f2, m2 = sup2.search(query("cache key A"), CTX)
v2 = ResilientSupply.verified_only(sup2.fetch(f2, CTX)[0])
add("2 缓存命中", m2.get("from_cache") is True and len(v2) == 1,
    {"from_cache": m2.get("from_cache"), "hits": sup2.cache.stats["hits"],
     "verified_after_refetch": len(v2)})

t429 = FixedTransport("PROVIDER_RATE_LIMITED")
sup4, f4_, fetched4, verified4, sm4, fmeta4, rep4 = run(provider([rec(url="https://e.invalid/a.jpg")],
                                                                transport=t429))
add("3 429 限流", t429.calls == 3 and not verified4
    and fetched4[0].error_code == "PROVIDER_RATE_LIMITED",
    {"attempts": t429.calls, "code": fetched4[0].error_code, "verified": len(verified4),
     "class": rep4["diagnostics"]["by_class"]})

t_to = FixedTransport("PROVIDER_TIMEOUT")
sup5, f5_, fetched5, verified5, sm5, fmeta5, rep5 = run(provider([rec(url="https://e.invalid/b.jpg")],
                                                                policy={"max_retries": 1},
                                                                transport=t_to))
add("4 超时", t_to.calls == 2 and not verified5
    and fetched5[0].error_code == "PROVIDER_TIMEOUT",
    {"attempts": t_to.calls, "code": fetched5[0].error_code, "verified": len(verified5)})

sup6, f6_, fetched6, verified6, sm6, fmeta6, rep6 = run(provider([]), text="完全不相关的主题")
add("5 空候选", fetched6 == [] and rep6["outcomes"] is None
    and rep6["degradation"]["rung"] in ("THEME_FALLBACK", "SOLID_COLOR_CARD", "BLOCKED_FOR_HUMAN"),
    {"found": len(f6_), "rung": rep6["degradation"]["rung"],
     "requires_human": rep6["degradation"]["requires_human"]})

sup7, f7_, fetched7, verified7, sm7, fmeta7, rep7 = run(
    provider([rec(WORK / "missing.jpg", source_id="s_missing")]))
add("6 下载失败", not verified7 and fetched7[0].error_code == "PROVIDER_DOWNLOAD_FAILED",
    {"code": fetched7[0].error_code, "download_status": fetched7[0].download_status,
     "verified": len(verified7)})

trunc = WORK / "trunc.jpg"
trunc.write_bytes(REAL_JPG.read_bytes()[:2048])
fake = WORK / "fake.jpg"
fake.write_text("not an image", encoding="utf-8")
sup8, f8_, fetched8, verified8, sm8, fmeta8, rep8 = run(
    provider([rec(trunc, source_id="s_trunc", name="virtual reality headset t.jpg"),
              rec(fake, source_id="s_fake", name="virtual reality headset f.jpg")]))
add("7 校验失败", not verified8
    and {"ASSET_TRUNCATED", "ASSET_TYPE_MISMATCH"} <= {c.error_code for c in fetched8},
    {"codes": sorted(c.error_code or "" for c in fetched8), "verified": len(verified8)})

lic_rows = []
for lic, want in ((None, "ASSET_LICENSE_MISSING"), ("unknown", "ASSET_LICENSE_UNCLEAR"),
                  ("fair use", "ASSET_LICENSE_RESTRICTED")):
    supL, fL_, fetchedL, verifiedL, smL, fmetaL, repL = run(
        provider([rec(GOOD, source_id="s_lic", license=lic,
                      name="virtual reality headset lic.jpg")]))
    lic_rows.append({"license": lic, "code": fetchedL[0].error_code, "want": want,
                     "needs_hitl": fetchedL[0].needs_hitl, "verified": len(verifiedL)})
add("8 许可不明/受限", all(r["code"] == r["want"] and r["needs_hitl"] and r["verified"] == 0
                          for r in lic_rows), lic_rows)

(LOGS / "phase4d_paths.json").write_text(json.dumps(paths, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
say("    八条路径 fail-closed：{}/{}".format(sum(1 for p in paths if p["fail_closed"]), len(paths)))

# 5) 引擎级 fail-closed + 不污染
say("\n[5] 引擎级 fail-closed 与不污染（临时工作区）")
from video_studio.agents.base import AGENTS  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402

import video_studio.agents.asset.agent  # noqa: E402,F401
import video_studio.agents.editing.agent  # noqa: E402,F401
import video_studio.agents.retrieval.agent  # noqa: E402,F401
import video_studio.agents.script.agent  # noqa: E402,F401

WS = Path(tempfile.mkdtemp(prefix="vs_4d_ev_engine_"))
CONFIG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
RULES = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
SCRIPT = {"segments": [{"chapter": "s1", "narration": TEXT, "duration_s": 4}], "summary": "4-D"}
ENG_JPG = WORK / "engine.jpg"
shutil.copy2(REAL_JPG, ENG_JPG)
MAT = {"provider": "local_catalog", "catalog": str(CAT), "timeout_s": 5, "max_retries": 2,
       "backoff_base_s": 0.0, "rate_limit_backoff_s": 0.0, "license_required": True}
real_db_before = sha256_file(REAL_DB)


def make_engine(material):
    cfg = json.loads(json.dumps(CONFIG))
    cfg["tools"]["material"] = material
    db = Database(WS / "state.db")
    return Engine(db, Router(cfg["llm"], MockLLM(cfg["llm"].get("mock", {}).get("responses", {}),
                                                 cfg["llm"].get("mock", {}).get("default", {}))),
                  RULES, WS / "projects", cfg, AGENTS), db


def proj_run(material, patch=None, render=True, reuse=None):
    if reuse:
        eng, db = reuse
        eng.config["tools"]["material"] = dict(material)
        pid = reuse[2]
        t_script = [t["task_id"] for t in db.list_tasks(pid) if t["agent_role"] == "script"][0]
    else:
        eng, db = make_engine(material)
        pid = eng.create_project("4-D evidence")
        t_script = eng.create_task(pid, "script", "script")
        aid = eng.write_artifact(pid, t_script, "script_output", SCRIPT, summary="脚本")
        eng.attach_artifact(t_script, aid)
        eng.db.set_task_status(t_script, "SUCCEEDED")
    import video_studio.tools.material_provider as mp
    orig = mp.LocalCatalogProvider
    if patch:
        mp.LocalCatalogProvider = patch
    try:
        t_ret = eng.create_task(pid, "retrieval", "retrieval", dependencies=[t_script])
        eng.run_cycle(pid, limit=4)
    finally:
        mp.LocalCatalogProvider = orig
    row = db.conn.execute("select path from artifacts where task_id=? and type='retrieval_candidates'"
                          " order by created_at desc limit 1", (t_ret,)).fetchone()
    ret = json.loads(Path(row["path"]).read_text(encoding="utf-8")) if row else None
    status, films = None, []
    if render:
        t_r = eng.create_task(pid, "render", "editing", dependencies=[t_script, t_ret])
        for _ in range(3):
            eng.run_cycle(pid, limit=4)
            if eng.db.get_task(t_r)["status"] not in ("PENDING", "DISPATCHED", "RUNNING"):
                break
        status = eng.db.get_task(t_r)["status"]
        films = sorted((eng.project_dir(pid) / "output").glob("*.mp4"))
    return eng, db, pid, t_ret, ret, status, films


class P429(LocalCatalogProvider):
    def search(self, q, ctx):
        raise TransportError("PROVIDER_RATE_LIMITED", "HTTP 429（证据注入）")


class PTimeout(LocalCatalogProvider):
    def search(self, q, ctx):
        raise TransportError("PROVIDER_TIMEOUT", "读取超时（证据注入）")


catalogue([rec(ENG_JPG)])
eng, db, pid, t_ret, ret, _s, _f = proj_run(MAT, render=False)
gated = eng, db, pid
proj_files_before = {str(p.relative_to(eng.project_dir(pid))): sha256_file(p)
                     for p in sorted(eng.project_dir(pid).rglob("*")) if p.is_file()}
tasks_before = len(db.list_tasks(pid))
arts_before = db.conn.execute("select count(*) from artifacts where project_id=?",
                              (pid,)).fetchone()[0]
events_before = len(db.events_since(pid, 0))
norm_verified = (ret or {}).get("external_verified")
norm_rung = (((ret or {}).get("external_provider") or {}).get("supply_report")
             or {}).get("degradation", {}).get("rung")

engA, dbA, pidA, t_rA, retA, statusA, filmsA = proj_run(MAT, patch=P429)
engB, dbB, pidB, t_rB, retB, statusB, filmsB = proj_run(MAT, patch=PTimeout)
provA = ((retA or {}).get("external_provider") or {})
real_db_after = sha256_file(REAL_DB)
proj_files_after = {str(p.relative_to(eng.project_dir(pid))): sha256_file(p)
                    for p in sorted(eng.project_dir(pid).rglob("*")) if p.is_file()}

fail_ev = {
    "normal": {"external_verified": norm_verified, "degradation_rung": norm_rung,
               "project": pid},
    "fail_429": {"project": pidA, "external_error": (retA or {}).get("external_error"),
                 "external_verified": (retA or {}).get("external_verified"),
                 "render_status": statusA, "films": [str(f) for f in filmsA],
                 "by_class": (provA.get("supply_report") or {}).get("diagnostics", {}).get("by_class"),
                 "degradation": (provA.get("supply_report") or {}).get("degradation")},
    "fail_timeout": {"project": pidB, "external_error": (retB or {}).get("external_error"),
                     "external_verified": (retB or {}).get("external_verified"),
                     "render_status": statusB, "films": [str(f) for f in filmsB]},
    "no_pollution": {
        "gated_project_files_unchanged": all(proj_files_after.get(k) == v
                                            for k, v in proj_files_before.items())
        and set(proj_files_before) == set(proj_files_after),
        "gated_tasks_before_after": [tasks_before, len(db.list_tasks(pid))],
        "gated_artifacts_before_after": [arts_before, db.conn.execute(
            "select count(*) from artifacts where project_id=?", (pid,)).fetchone()[0]],
        "gated_events_before_after": [events_before, len(db.events_since(pid, 0))],
        "render_output_artifacts": {
            "gated": db.conn.execute("select count(*) from artifacts where project_id=? and "
                                     "type='render_output'", (pid,)).fetchone()[0],
            "fail_429": dbA.conn.execute("select count(*) from artifacts where project_id=? and "
                                         "type='render_output'", (pidA,)).fetchone()[0],
            "fail_timeout": dbB.conn.execute("select count(*) from artifacts where project_id=? and "
                                             "type='render_output'", (pidB,)).fetchone()[0]},
        "attribution_artifacts": {
            "gated": db.conn.execute("select count(*) from artifacts where project_id=? and "
                                     "type='attribution'", (pid,)).fetchone()[0],
            "fail_429": dbA.conn.execute("select count(*) from artifacts where project_id=? and "
                                         "type='attribution'", (pidA,)).fetchone()[0]},
        "decisions_total": db.conn.execute("select count(*) from decisions").fetchone()[0],
        "changelog_total": db.conn.execute("select count(*) from changelog").fetchone()[0],
        "real_db_sha256_before": real_db_before, "real_db_sha256_after": real_db_after,
        "real_db_unchanged": real_db_before == real_db_after},
    "fail_closed_verdict": bool(
        (retA or {}).get("external_verified") == 0 and (retB or {}).get("external_verified") == 0
        and statusB == "BLOCKED" and not filmsA and not filmsB
        and (retA or {}).get("external_error") == "PROVIDER_RATE_LIMITED"
        and (retB or {}).get("external_error") == "PROVIDER_TIMEOUT"),
}
(LOGS / "phase4d_failclosed.json").write_text(json.dumps(fail_ev, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
np_ = fail_ev["no_pollution"]
say("    正常：external_verified={} rung={}".format(norm_verified, norm_rung))
say("    429：external_error={} render={} films={} 分类={}".format(
    fail_ev["fail_429"]["external_error"], statusA, len(filmsA),
    fail_ev["fail_429"]["by_class"]))
say("    超时：external_error={} render={} films={}".format(
    fail_ev["fail_timeout"]["external_error"], statusB, len(filmsB)))
say("    不污染：既有项目文件未变={} 任务 {} 产物 {} 事件 {} render_output={} attribution={}".format(
    np_["gated_project_files_unchanged"], np_["gated_tasks_before_after"],
    np_["gated_artifacts_before_after"], np_["gated_events_before_after"],
    np_["render_output_artifacts"], np_["attribution_artifacts"]))
say("    真实数据库未变={}（{}…）".format(np_["real_db_unchanged"],
                                          np_["real_db_sha256_before"][:16]))

# 6) 降级阶梯 + 默认配置
say("\n[6] 可控降级阶梯与默认配置")
for facts, want in (({"has_verified_external": True}, "EXTERNAL_VERIFIED"),
                    ({"has_local_index": True}, "LOCAL_INGEST"),
                    ({"theme_fallback_allowed": True}, "THEME_FALLBACK"),
                    ({"card_allowed": True}, "SOLID_COLOR_CARD"), ({}, "BLOCKED_FOR_HUMAN")):
    plan_row = degradation_plan(facts)
    say("    {:<22s} → {:<18s} requires_human={} 不变量={}".format(
        json.dumps(facts, ensure_ascii=False), plan_row["rung"], plan_row["requires_human"],
        plan_row["invariants"]))
p_none, err_none, _ = provider_from_config({"tools": {"material": {"provider": "none"}}})
say("    默认配置：DEFAULT_POLICY.provider={} supply_cache={}；provider_from_config(none) → {} err={}".format(
    DEFAULT_POLICY["provider"], DEFAULT_POLICY["supply_cache"], p_none, err_none))
say("    summarize 示例：{}".format(summarize([{"status": "VERIFIED"},
                                              {"status": "REJECTED",
                                               "error_code": "ASSET_LICENSE_UNCLEAR"}])))

(LOGS / "phase4d_evidence_summary.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")
print("\nwritten", LOGS / "phase4d_evidence_summary.txt")

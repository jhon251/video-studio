"""4.x Phase 4-E 单测：检索质量量化与 A/B 基准（**全离线、确定性**）。

覆盖（授权重点 1–5）：
  A. 词典与分词：词形归一 / 词边界匹配（禁止碎片桥）/ 2 字符缩写（vr、hmd）保留
  B. 打分器 v1（冻结）与 v2（改进）：**v1 的逐字单字符关键词缺陷**被固定为可复现证据
  C. 固定测试集 A/B 全量指标：TP / FP / UNKNOWN 与域命中率、top1、空结果正确率（**数值冻结**，漂移即失败）
  D. 中文输入 / 英文输入 / 同义多语言 / 无结果·弱结果 / 歧义（UNKNOWN）逐组结果
  E. 无结果 → 空候选（不制造假匹配）；歧义 → UNKNOWN（不等于语义正确）
  F. 检索改进**不绕过** 4-B、许可门禁与素材校验；4-B 真值钉定未被改动
  G. 默认行为不变：`tools.retrieval` 缺省 = v1 + 不扩展；离线可运行

用法：python tests/retrieval_quality_test.py
"""
import hashlib
import json
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import retrieval_quality as rq  # noqa: E402

BENCH_PATH = ROOT / "tests" / "retrieval_bench_v1.json"
SEMANTICS_LEXICON = ROOT / "src" / "video_studio" / "core" / "lexicons" / "semantics_v1.json"
SEMANTICS_LEXICON_SHA = "083e8d55c9899706"          # 4-B 词表指纹前缀（不得被 4-E 改动）
TRUTH_ARTIFACT = "a_2ed5f41d6b58"                    # 4-B 真值钉定产物（不得被 4-E 改动）
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:220] if detail else ""))


def sha_prefix(p: Path, n=16) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:n]


BENCH = json.loads(BENCH_PATH.read_text(encoding="utf-8"))
CORPUS, QUERIES, K = BENCH["corpus"], BENCH["queries"], int(BENCH.get("k") or 5)
LEX = rq.load_retrieval_lexicon()

# ============ A. 词典与分词 ============
print("== A. 词典与分词（词形归一 / 词边界 / 缩写）==")
check("A1 词典可加载并带版本与 sha256（可审计）",
      LEX.get("version") == "retrieval-synonyms-v1" and len(str(LEX.get("sha256"))) == 64,
      rq.lexicon_fingerprint(LEX))
check("A2 12 个概念与 4-B 的 12 个域对齐",
      sorted({c["domain"] for c in LEX["concepts"]}) == sorted(BENCH["domains"]),
      sorted({c["domain"] for c in LEX["concepts"]}))
check("A3 简单复数归一（headsets→headset / goggles→goggle / boxes→box / policies→policy）",
      rq.normalize_latin("headsets") == "headset" and rq.normalize_latin("goggles") == "goggle"
      and rq.normalize_latin("boxes") == "box" and rq.normalize_latin("policies") == "policy",
      [rq.normalize_latin(x) for x in ("headsets", "goggles", "boxes", "policies")])
check("A4 2 字符缩写保留（v1 会丢弃）：vr/hmd 进入 token",
      {"vr", "hmd"} <= rq.tokens_v2("VR HMD 设备")["latin"],
      sorted(rq.tokens_v2("VR HMD 设备")["latin"]))
check("A5 词边界匹配：'es' 不命中 'Azores'（碎片桥防护，4-B 同类缺陷）",
      rq._word_boundary_hit("es", "azores") is False
      and rq._word_boundary_hit("azores", "tiburon azul azores") is True)
check("A6 中文虚词不进单字集合（的/了/在 被去除，二元组保留）",
      "的" not in rq.tokens_v2("虚拟现实的头显")["cjk_chars"]
      and "虚拟" in rq.tokens_v2("虚拟现实的头显")["cjk_bigrams"])

# ============ B. v1 缺陷证据 ============
print("== B. v1（冻结）缺陷证据 ==")
# v1 的 kw_tokens 把去空格后的**每个字符**都当关键词：拉丁文本贡献单字母（z/q…），
# 中文文本贡献单字（面/在/的…）。因此无意义输入也会命中（假匹配），实测两例：
fake1 = rq.score_v1("Meta Quest 3 front View.jpg", "zzzq 不存在的主题内容")
fake2 = rq.score_v1("VR头显_侧面_展示.jpg", "咖啡与面包的早餐")
check("B1 v1 单字符关键词导致假匹配（单字母 'q' / 单字 '面'）—— 可复现证据",
      fake1["score"] == 1 and fake2["score"] == 1
      and {"q"} <= set(fake1["keywords"]) and {"面"} <= set(fake2["keywords"]),
      {"zzzq->Quest": fake1["score"], "咖啡面包->侧面": fake2["score"]})
v1_latin = rq.score_v1("Virtual reality headset.jpg", "virtual reality headset")
v2_latin = rq.score_v2("Virtual reality headset.jpg", "virtual reality headset", LEX)
check("B2 v2 对同一正例同样命中并给出概念（**分数不可跨版本比较**：v1 分数被字符级关键词抬高）",
      v1_latin["score"] > 0 and v2_latin["score"] > 0 and "xr_device" in v2_latin["concepts"],
      {"v1": v1_latin["score"], "v2": v2_latin["score"]})
v1_zh = rq.score_v1("Virtual reality headset.jpg", "虚拟现实头显的镜片特写")
check("B3 v1 对中文查询 + 英文命名素材 = 0 命中（中文检索的真实缺陷）",
      v1_zh["score"] == 0, v1_zh)

# ============ C. 固定测试集 A/B（数值冻结） ============
print("== C. 固定测试集 A/B（{} 查询 / {} 语料 / k={}）==".format(
    len(QUERIES), len(CORPUS), K))
AB1 = rq.ab_compare(QUERIES, CORPUS, k=K, lex=LEX)
AB2 = rq.ab_compare(QUERIES, CORPUS, k=K, lex=LEX)
check("C1 可复算：两次运行结果逐字节一致（确定性）",
      json.dumps(AB1, ensure_ascii=False, sort_keys=True)
      == json.dumps(AB2, ensure_ascii=False, sort_keys=True))
A, B = AB1["A_v1_frozen"]["summary"], AB1["B_v2_improved"]["summary"]
FROZEN = {
    "A": {"TP": 19, "FP": 39, "UNKNOWN": 10, "domain_hit_rate": 0.6875,
          "top1_correct_rate": 0.5625, "precision_strict": 0.2794, "empty_correct_rate": 0.6667},
    "B": {"TP": 43, "FP": 18, "UNKNOWN": 10, "domain_hit_rate": 1.0,
          "top1_correct_rate": 1.0, "precision_strict": 0.6056, "empty_correct_rate": 1.0},
}
got = {
    "A": {"TP": A["candidate_level"]["TP"], "FP": A["candidate_level"]["FP"],
          "UNKNOWN": A["candidate_level"]["UNKNOWN"],
          "domain_hit_rate": A["query_level"]["domain_hit_rate"],
          "top1_correct_rate": A["query_level"]["top1_correct_rate"],
          "precision_strict": A["candidate_level"]["precision_strict"],
          "empty_correct_rate": A["query_level"]["empty_correct_rate"]},
    "B": {"TP": B["candidate_level"]["TP"], "FP": B["candidate_level"]["FP"],
          "UNKNOWN": B["candidate_level"]["UNKNOWN"],
          "domain_hit_rate": B["query_level"]["domain_hit_rate"],
          "top1_correct_rate": B["query_level"]["top1_correct_rate"],
          "precision_strict": B["candidate_level"]["precision_strict"],
          "empty_correct_rate": B["query_level"]["empty_correct_rate"]},
}
check("C2 A（v1 冻结）指标 == 冻结值（漂移即失败，须新建 bench v2）", got["A"] == FROZEN["A"], got["A"])
check("C3 B（v2 改进）指标 == 冻结值（漂移即失败）", got["B"] == FROZEN["B"], got["B"])
d = AB1["delta_B_minus_A"]
check("C4 改进幅度：TP +{}/ FP {}/ 域命中率 +{}/ top1 +{}".format(
    d["TP"], d["FP"], d["domain_hit_rate"], d["top1_correct_rate"]),
    d["TP"] == 24 and d["FP"] == -21 and d["domain_hit_rate"] == 0.3125
    and d["top1_correct_rate"] == 0.4375 and d["empty_correct_rate"] == 0.3333, d)
check("C5 UNKNOWN 在 A/B 两侧一致（改进**不把歧义洗成正确**）",
      A["candidate_level"]["UNKNOWN"] == B["candidate_level"]["UNKNOWN"] == 10)

# ============ D. 分组结果（中文/英文/同义多语言/无结果弱结果/歧义） ============
print("== D. 分组结果 ==")
ga, gb = A["by_group"], B["by_group"]
check("D1 中文组（zh）：A 域命中 {:.0%} → B {:.0%}（TP {} → {}）".format(
    ga["zh"]["domain_hit_rate"], gb["zh"]["domain_hit_rate"], ga["zh"]["TP"], gb["zh"]["TP"]),
    ga["zh"]["domain_hit_rate"] == 0.4 and gb["zh"]["domain_hit_rate"] == 1.0
    and ga["zh"]["TP"] == 3 and gb["zh"]["TP"] == 14, {"A": ga["zh"], "B": gb["zh"]})
check("D2 英文组（en）：A top-k 噪声大（FP {}）→ B FP {}、命中率 {}".format(
    ga["en"]["FP"], gb["en"]["FP"], gb["en"]["domain_hit_rate"]),
    ga["en"]["FP"] == 18 and gb["en"]["FP"] == 5 and gb["en"]["domain_hit_rate"] == 1.0,
    {"A": ga["en"], "B": gb["en"]})
check("D3 同义/多语言组（syn）：A TP {} FP {} → B TP {} FP {}".format(
    ga["syn"]["TP"], ga["syn"]["FP"], gb["syn"]["TP"], gb["syn"]["FP"]),
    ga["syn"]["TP"] == 9 and ga["syn"]["FP"] == 12 and gb["syn"]["TP"] == 18
    and gb["syn"]["FP"] == 4, {"A": ga["syn"], "B": gb["syn"]})
check("D4 无结果组（none）：A 假匹配 FP {} → B FP {}（不制造假匹配）".format(
    ga["none"]["FP"], gb["none"]["FP"]),
    ga["none"]["FP"] == 4 and gb["none"]["FP"] == 0, {"A": ga["none"], "B": gb["none"]})
check("D5 歧义组（amb）：A/B 均全部记 UNKNOWN（pico/galaxy 品牌 vs 地名/星系）",
      ga["amb"]["UNKNOWN"] == gb["amb"]["UNKNOWN"] == 10
      and ga["amb"]["TP"] == gb["amb"]["TP"] == 0, {"A": ga["amb"], "B": gb["amb"]})
check("D6 弱结果组（weak）：B 命中 food_drink（语料仅 1 条该域），A 为 0",
      ga["weak"]["TP"] == 0 and gb["weak"]["TP"] == 1, {"A": ga["weak"], "B": gb["weak"]})

# ============ E. 无结果 / 歧义的正确行为 ============
print("== E. 无结果与歧义的正确行为 ==")
rows_b = {r["query_id"]: r for r in AB1["B_v2_improved"]["rows"]}
rows_a = {r["query_id"]: r for r in AB1["A_v1_frozen"]["rows"]}
check("E1 期望无结果的查询：B 全部返回空候选（UNKNOWN/空，而不是硬凑）",
      all(rows_b[q]["retrieved_n"] == 0 for q in ("weak_02", "none_01", "none_02")),
      {q: rows_b[q]["retrieved_n"] for q in ("weak_02", "none_01", "none_02")})
check("E2 A 在 none_02 上制造 4 条假匹配（v1 单字符缺陷的直接后果）",
      rows_a["none_02"]["retrieved_n"] == 4 and rows_a["none_02"]["FP"] == 4,
      {"A_none_02": rows_a["none_02"]["retrieved_n"]})
check("E3 歧义查询的候选全部记 UNKNOWN（检索到 ≠ 语义正确）",
      all(c["verdict"] == "UNKNOWN" for c in rows_b["amb_01"]["retrieved"] + rows_b["amb_02"]["retrieved"])
      and rows_b["amb_01"]["TP"] == 0 and rows_b["amb_02"]["TP"] == 0)
check("E4 逐条可解释：每个候选带 domain/score/概念/歧义形式",
      all(("domain" in c and "score" in c and "concepts" in c and "ambiguous_forms" in c)
          for q in ("zh_01", "syn_03", "amb_01") for c in rows_b[q]["retrieved"]),
      rows_b["zh_01"]["retrieved"][0] if rows_b["zh_01"]["retrieved"] else None)

# ============ F. 不绕过 4-B / 许可 / 素材校验 ============
print("== F. 检索改进不绕过 4-B、许可门禁与素材校验 ==")
check("F1 4-B 词表 sha256 前缀未变（4-E 未改语义知识库）",
      sha_prefix(SEMANTICS_LEXICON, 16) == SEMANTICS_LEXICON_SHA,
      sha_prefix(SEMANTICS_LEXICON, 16))
sem_test = (ROOT / "tests" / "semantic_check_test.py").read_text(encoding="utf-8")
check("F2 4-B 真值仍钉在 {}".format(TRUTH_ARTIFACT),
      "TRUTH_ARTIFACT = \"{}\"".format(TRUTH_ARTIFACT) in sem_test)
rq_src = (ROOT / "src" / "video_studio" / "core" / "retrieval_quality.py").read_text(encoding="utf-8")
check("F3 检索层不做语义判定：不导入 semantics、不产出 verdict/fallback 结论",
      "core.semantics" not in rq_src and "verify_scene" not in rq_src and "MISMATCH" not in rq_src)
scored = rq.score_v2("VR头显_镜片特写_fairuse.jpg", "虚拟现实头显", LEX)
check("F4 侵权素材在检索层仍只是'候选'（检索层无许可结论字段）",
      "license" not in scored and "verified" not in scored
      and scored["score"] > 0, {k: scored[k] for k in ("score", "concepts")})

# ============ G. 默认行为不变 + 离线 ============
print("== G. 默认行为不变与离线 ==")
default = rq.retrieval_settings({})
optin = rq.retrieval_settings({"tools": {"retrieval": {"scoring": "v2", "query_expansion": True}}})
typo = rq.retrieval_settings({"tools": {"retrieval": {"scoring": "v3-typo"}}})
check("G1 缺省 = v1 + 不扩展（不改变既有行为）；显式配置才启用 v2",
      default == {"scoring": "v1", "query_expansion": False, "source": "default(v1)",
                  "known_scorers": ["v1", "v2"]}
      and optin["scoring"] == "v2" and optin["query_expansion"] is True
      and typo["scoring"] == "v1",
      {"default": default, "optin": optin, "typo": typo})
check("G2 v1 打分器仍是原实现（直接引用既有 kw_tokens/score，未复制改写）",
      "from ..agents.retrieval.agent import kw_tokens, score" in
      (ROOT / "src" / "video_studio" / "core" / "retrieval_quality.py").read_text(encoding="utf-8"))
orig_socket = socket.socket
try:
    def _blocked(*a, **kw):
        raise RuntimeError("network blocked in test")
    socket.socket = _blocked                    # type: ignore[assignment]
    offline = rq.ab_compare(QUERIES, CORPUS, k=K, lex=rq.load_retrieval_lexicon())
    ok_offline = offline["B_v2_improved"]["summary"]["candidate_level"]["TP"] == 43
finally:
    socket.socket = orig_socket                 # type: ignore[assignment]
check("G3 全离线：禁用 socket 后 A/B 仍可复算（不依赖网络）", ok_offline)

# ============ H. 引擎级：中文查询 + 查询扩展 + 许可/校验门禁（不绕过） ============
print("== H. 引擎级端到端（中文查询 → 扩展 → 门禁不绕过） ==")
import shutil  # noqa: E402
import tempfile  # noqa: E402

from video_studio.agents.base import AGENTS  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402

import video_studio.agents.asset.agent  # noqa: E402,F401
import video_studio.agents.editing.agent  # noqa: E402,F401
import video_studio.agents.retrieval.agent  # noqa: E402,F401
import video_studio.agents.script.agent  # noqa: E402,F401

REAL_JPG = ROOT / "output" / "run03" / "asset_cache" / "files" / "r3_S01-B01_3.img.jpg"
WS = Path(tempfile.mkdtemp(prefix="vs_4e_engine_"))
CAT = WS / "catalog"
CAT.mkdir(parents=True, exist_ok=True)
GOOD = WS / "good.jpg"
FAIR = WS / "fair.jpg"
TRUNC = WS / "trunc.jpg"
shutil.copy2(REAL_JPG, GOOD)
shutil.copy2(REAL_JPG, FAIR)
TRUNC.write_bytes(REAL_JPG.read_bytes()[:2048])
(CAT / "catalogue.json").write_text(json.dumps({"items": [
    {"source_id": "s_good", "name": "Virtual reality headset demo.jpg", "file": str(GOOD),
     "license": "CC BY-SA 4.0", "attribution": "T / CC BY-SA 4.0"},
    {"source_id": "s_fair", "name": "Virtual reality headset fairuse.jpg", "file": str(FAIR),
     "license": "fair use", "attribution": "T / fair use"},
    {"source_id": "s_trunc", "name": "VR头显_截断测试.jpg", "file": str(TRUNC),
     "license": "CC BY 4.0", "attribution": "T / CC BY 4.0"},
]}, ensure_ascii=False), encoding="utf-8")
CONFIG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
RULES = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
SCRIPT = {"segments": [{"chapter": "s1", "narration": "虚拟现实头显的展示", "duration_s": 4}],
          "summary": "4-E retrieval quality"}


def engine_retrieval(label, retrieval_cfg):
    cfg = json.loads(json.dumps(CONFIG))
    cfg["tools"]["material"] = {"provider": "local_catalog", "catalog": str(CAT), "timeout_s": 5,
                               "license_required": True}
    if retrieval_cfg is not None:
        cfg["tools"]["retrieval"] = retrieval_cfg
    db = Database(WS / "state_{}.db".format(label))
    eng = Engine(db, Router(cfg["llm"], MockLLM(cfg["llm"].get("mock", {}).get("responses", {}),
                                               cfg["llm"].get("mock", {}).get("default", {}))),
                 RULES, WS / "projects", cfg, AGENTS)
    pid = eng.create_project("4-E {}".format(label))
    t_script = eng.create_task(pid, "script", "script")
    aid = eng.write_artifact(pid, t_script, "script_output", SCRIPT, summary="脚本")
    eng.attach_artifact(t_script, aid)
    eng.db.set_task_status(t_script, "SUCCEEDED")
    t_ret = eng.create_task(pid, "retrieval", "retrieval", dependencies=[t_script])
    eng.run_cycle(pid, limit=4)
    row = db.conn.execute("select path from artifacts where task_id=? and type='retrieval_candidates'"
                          " order by created_at desc limit 1", (t_ret,)).fetchone()
    ret = json.loads(Path(row["path"]).read_text(encoding="utf-8")) if row else None
    db.close()
    return ret or {}


v2 = engine_retrieval("v2", {"scoring": "v2", "query_expansion": True})
v1 = engine_retrieval("v1", None)
v2_codes = sorted({(c.get("error_code") or "") for c in (v2.get("external_rejected") or [])})
v2_ext = [c for c in (v2.get("candidates") or []) if c.get("provider") == "local_catalog"]
check("H1 中文查询 + 查询扩展 → 英文命名素材被检索到并通过校验（external_verified={}）".format(
    v2.get("external_verified")),
    v2.get("external_verified") == 1 and len(v2_ext) == 1
    and v2_ext[0]["name"] == "Virtual reality headset demo.jpg", v2_ext)
check("H2 同一批候选里：fair use 被许可门禁拦下、截断文件被素材校验拦下（**未绕过**）",
      "ASSET_LICENSE_RESTRICTED" in v2_codes and "ASSET_TRUNCATED" in v2_codes
      and all("fairuse" not in (c.get("name") or "") for c in v2_ext)
      and all("截断" not in (c.get("name") or "") for c in v2_ext), v2_codes)
check("H3 默认配置（v1，无扩展）对同一中文查询 = 0 外部候选（改进确实来自 4-E 的 opt-in 能力）",
      v1.get("external_verified") == 0
      and not [c for c in (v1.get("candidates") or []) if c.get("provider") == "local_catalog"],
      {"v1_verified": v1.get("external_verified"), "v1_mode": v1.get("material_mode")})
check("H4 检索配置被如实记录（scoring/query_expansion/扩展词/词典指纹）",
      (v2.get("retrieval_config") or {}).get("scoring") == "v2"
      and (v2.get("retrieval_config") or {}).get("query_expansion") is True
      and (v2.get("retrieval_config") or {}).get("expanded_terms")
      and str((v2.get("retrieval_config") or {}).get("lexicon")).startswith("retrieval-synonyms-v1"),
      v2.get("retrieval_config"))

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)

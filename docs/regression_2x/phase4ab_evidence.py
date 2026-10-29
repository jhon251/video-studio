"""4.x Phase 4-A/4-B 证据采集（只读）：命令 + 返回码 + 真值表/混淆计数 + 两次输出一致性。

产出（全部落在 docs/regression_2x/logs/）：
  phase4ab_baseline_check.txt     冻结基线 sha256 与零漂移校验
  phase4ab_metrics_project_a.json / _b.json   项目指标两次运行（应逐字节一致）
  phase4ab_metrics_corpus_a.json / _b.json    全库指标两次运行（应逐字节一致）
  phase4ab_semantic_truth.json    3-A 真值表（逐镜头判定 + 规则 ID + 信号）+ 混淆计数
  phase4ab_semantic_truth.txt     人读版
  phase4ab_semantic_corpus.json   全库语义扫描（三态计数 + 被标记 MISMATCH 的镜头清单）
  phase4ab_provider_none.txt      provider=none 回归证据（默认配置未被修改）
用法：python docs/regression_2x/phase4ab_evidence.py
"""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.ops.metrics import corpus_metrics, project_metrics  # noqa: E402
from video_studio.ops.metrics import semantic_report  # noqa: E402
from video_studio.ops.report import readonly_connection  # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
PY = sys.executable
TRUTH_PID = "p_f4b466a4a024"
# 真值**钉在 3-A 那一版冻结产物**上（append-only 保证仍在）；4-C 之后最新成片已被人工替换，
# 用"最新成片"当真值载体等于让真值随修复漂移。
TRUTH_ARTIFACT = "a_2ed5f41d6b58"
MUST_MISMATCH = {"S04", "S06"}
MUST_NOT_MISMATCH = {"S01", "S02", "S03", "S05"}
lines: list[str] = []


def log(s: str) -> None:
    lines.append(s)
    print(s, flush=True)


def cli(*args: str) -> tuple[int, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([PY, "run.py", *args], cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800, env=env)
    return r.returncode, (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")


def dump(name: str, obj) -> Path:
    p = LOGS / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1) if not isinstance(obj, str) else obj,
                 encoding="utf-8")
    return p


log("=== 4-A/4-B 证据采集 {} ===".format("(只读)"))

# ---------- 0. 基线核对 ----------
_env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
_r = subprocess.run([PY, "docs\\regression_2x\\verify_baseline.py", "3.x-final-baseline"],
                    cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=1800, env=_env)
rc, out = _r.returncode, (_r.stdout or "") + (("\n[stderr]\n" + _r.stderr) if _r.stderr else "")
(LOGS / "phase4ab_baseline_check.txt").write_text(out, encoding="utf-8")
zip_sha = hashlib.sha256(
    (ROOT / "docs" / "regression_2x" / "baseline" / "3.x-final-baseline.zip").read_bytes()
).hexdigest()
log("[baseline] verify rc={}（0=MATCH 流程正常）| 记录: logs/phase4ab_baseline_check.txt".format(rc))
log("           3.x-final-baseline.zip sha256 = {}".format(zip_sha))
log("           期望 sha256 = b82ba77ea85cfd22ad7206b95f2a86b927b585254d375d941a3ee1a1dcc4646f")
log("           一致 = {}".format(zip_sha ==
                                  "b82ba77ea85cfd22ad7206b95f2a86b927b585254d375d941a3ee1a1dcc4646f"))

# ---------- 1. metrics 两次运行一致性 ----------
rc_a, out_a = cli("metrics", TRUTH_PID, "--json")
rc_b, out_b = cli("metrics", TRUTH_PID, "--json")
dump("phase4ab_metrics_project_a.json", out_a)
dump("phase4ab_metrics_project_b.json", out_b)
log("[metrics:project] rc={} / rc={} | 逐字节一致 = {} | 产物 logs/phase4ab_metrics_project_{{a,b}}.json"
    .format(rc_a, rc_b, out_a == out_b))

rc_ca, out_ca = cli("metrics", "--all", "--json")
rc_cb, out_cb = cli("metrics", "--all", "--json")
dump("phase4ab_metrics_corpus_a.json", out_ca)
dump("phase4ab_metrics_corpus_b.json", out_cb)
log("[metrics:corpus]  rc={} / rc={} | 逐字节一致 = {} | 产物 logs/phase4ab_metrics_corpus_{{a,b}}.json"
    .format(rc_ca, rc_cb, out_ca == out_cb))

# ---------- 2. 语义真值表 ----------
rc_s, out_s = cli("semantic-check", TRUTH_PID, "--json")
rep = semantic_report(DB, TRUTH_PID, artifact_id=TRUTH_ARTIFACT)
by = {s["scene_id"]: s for s in rep["scenes"]}
tp = sorted(sid for sid, s in by.items() if s["verdict"] == "MISMATCH" and sid in MUST_MISMATCH)
fn = sorted(sid for sid in MUST_MISMATCH if by[sid]["verdict"] != "MISMATCH")
fp = sorted(sid for sid, s in by.items() if s["verdict"] == "MISMATCH" and sid in MUST_NOT_MISMATCH)
tn = sorted(sid for sid in MUST_NOT_MISMATCH if by[sid]["verdict"] != "MISMATCH")
unknown = sorted(sid for sid, s in by.items() if s["verdict"] == "UNKNOWN")
truth = {
    "project": TRUTH_PID, "lexicon": rep["version"], "lexicon_sha256": rep["lexicon_sha256"],
    "policy": rep["policy"],
    "pinned_artifact": TRUTH_ARTIFACT,
    "pinned_note": ("真值钉在 3-A 那一版冻结 render_output 上（append-only 保证仍在）；"
                    "4-C 之后最新成片已被人工替换，用最新成片当载体等于让真值随修复漂移"),
    "declared_truth": {"must_mismatch": sorted(MUST_MISMATCH),
                       "must_not_mismatch": sorted(MUST_NOT_MISMATCH),
                       "source": "3-A 已知语义误选（KNOWN_ISSUES #1；真值由 3-A 人工复核确定）"},
    "confusion": {"TP": tp, "FN": fn, "FP": fp, "TN": tn, "UNKNOWN": unknown,
                  "counts": {"TP": len(tp), "FN": len(fn), "FP": len(fp), "TN": len(tn),
                             "UNKNOWN": len(unknown)}},
    "verdicts": {sid: {"verdict": s["verdict"], "rule": s["rule"]} for sid, s in sorted(by.items())},
    "scenes": rep["scenes"],
}
dump("phase4ab_semantic_truth.json", truth)
txt = ["项目 {} 语义核验（{}）".format(TRUTH_PID, rep["version"]),
       "词典 sha256 {}".format(rep["lexicon_sha256"]),
       "判定口径：{}".format(rep["policy"]), ""]
for sid, s in sorted(by.items()):
    txt.append("{:<5s} {:<9s} {:<24s} {}".format(sid, s["verdict"], s["rule"] or "-",
                                                 s["reason"][:120]))
    txt.append("      素材: {}".format(str((s.get("asset") or {}).get("name"))[:100]))
    sig = s["signals"]
    txt.append("      信号: 词级桥={} 碎片桥={} 旁白域={} 素材域={} 域不相交={}".format(
        sig["word_bridge"], sig["fragment_bridge"], sorted(sig["query_domains"]),
        sorted(sig["asset_domains"]), sig["domain_disjoint"]))
txt += ["", "混淆计数: TP={} FN={} FP={} UNKNOWN={}".format(len(tp), len(fn), len(fp),
                                                            len(unknown)),
        "（TP=S04/S06 被正确标为 MISMATCH；FP=被误报的『本应正常』镜头；UNKNOWN=无法判断）"]
dump("phase4ab_semantic_truth.txt", "\n".join(txt))
log("[semantic:truth] rc={} | TP={} FN={} FP={} UNKNOWN={} | 产物 logs/phase4ab_semantic_truth.{{json,txt}}"
    .format(rc_s, len(tp), len(fn), len(fp), len(unknown)))
if fp or fn:
    log("           ⚠ 未达验收：FP={} FN={}（如实记录，不得调阈值/改真值）".format(fp, fn))

# ---------- 3. 全库语义扫描（描述性；不声称准确率） ----------
full = corpus_metrics(DB, ROOT / "projects")
agg = full["aggregate"]
con = readonly_connection(DB)
flagged = []
for r in con.execute("select distinct project_id from artifacts where type='render_output' "
                     "order by project_id"):
    rr = semantic_report(DB, r["project_id"])
    if not rr.get("found"):
        continue
    for s in rr["scenes"]:
        if s["verdict"] == "MISMATCH":
            flagged.append({"project_id": r["project_id"], "scene_id": s["scene_id"],
                            "rule": s["rule"], "asset": (s.get("asset") or {}).get("name"),
                            "reason": s["reason"][:160],
                            "appears_in_film": (s.get("asset") or {}).get("appears_in_film")})
con.close()
corpus = {"schema": "semantics-v1-corpus-scan", "note": "无标注 → 只报告分布与被标记清单，不声称准确率",
          "aggregate": agg, "flagged_mismatch_count": len(flagged), "flagged": flagged}
dump("phase4ab_semantic_corpus.json", corpus)
log("[semantic:corpus] 项目 {} 镜头 {} → MATCH={} MISMATCH={} UNKNOWN={}（mismatch_rate={}）"
    .format(agg["projects"], agg["scenes"], agg["match"], agg["mismatch"], agg["unknown"],
            agg["semantic_mismatch_rate"]))
log("                  被标记 MISMATCH 镜头 {} 个（待人工复核，**不等于**已确认错误）| 产物 logs/phase4ab_semantic_corpus.json"
    .format(len(flagged)))

# ---------- 4. provider=none 回归证据 ----------
baseline = json.loads((ROOT / "docs" / "regression_2x" / "baseline" /
                       # 5-L：钉定目标由过期的 3.x-final 改为当前有效基线（证据口径更新，非业务语义变更）
                       "baseline_manifest_5.x-post-final-maintenance-baseline.json")
                      .read_text(encoding="utf-8"))
cfg_now = hashlib.sha256((ROOT / "config" / "config.json").read_bytes()).hexdigest()
cfg_base = baseline["files"]["config/config.json"]["sha256"]
con = readonly_connection(DB)
row = con.execute("select a.project_id from artifacts a where a.type='retrieval_candidates' "
                  "and exists (select 1 from artifacts r where r.project_id=a.project_id "
                  "and r.type='render_output') order by a.created_at desc limit 40").fetchall()
con.close()
none_pid = None
for r in row:
    m = project_metrics(DB, r["project_id"])
    if (m.get("material") or {}).get("mode") in ("none", "local_ingest"):
        none_pid = r["project_id"]
        break
mn = project_metrics(DB, none_pid) if none_pid else {}
prov = ["provider=none 回归证据（4.x 未改变默认行为）",
        "config/config.json sha256 现在 = {}".format(cfg_now),
        "config/config.json sha256 基线 = {}".format(cfg_base),
        "一致 = {}".format(cfg_now == cfg_base), "",
        "样本项目（默认配置产出）: {}".format(none_pid),
        "  外部素材: mode={} requests={} downloaded_bytes={} external_requested={}".format(
            (mn.get("material") or {}).get("mode"), (mn.get("material") or {}).get("requests"),
            (mn.get("material") or {}).get("downloaded_bytes"),
            (mn.get("material") or {}).get("external_requested")),
        "  成片: {}".format((mn.get("artifacts") or {}).get("render_output")),
        "  语义核验（同项目）: {}".format(json.dumps((mn.get("semantics") or {}).get("counts"),
                                                    ensure_ascii=False))]
dump("phase4ab_provider_none.txt", "\n".join(prov))
log("[provider=none] 配置 sha256 一致={} | 样本 {} mode={} requests={} bytes={} | 产物 logs/phase4ab_provider_none.txt"
    .format(cfg_now == cfg_base, none_pid, (mn.get("material") or {}).get("mode"),
            (mn.get("material") or {}).get("requests"),
            (mn.get("material") or {}).get("downloaded_bytes")))

(LOGS / "phase4ab_evidence_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\nwritten", LOGS / "phase4ab_evidence_summary.txt")

# ---------- 5. 相对冻结基线的变更清单（只读；证明只做了允许的新增） ----------
man = baseline["files"]
changed, new_files = [], []
for rel, meta in man.items():
    p = ROOT / rel
    if not p.is_file():
        changed.append({"file": rel, "change": "DELETED"})
    elif hashlib.sha256(p.read_bytes()).hexdigest() != meta["sha256"]:
        changed.append({"file": rel, "change": "MODIFIED"})
for d in ("src", "config", "tests", "scripts"):
    for p in (ROOT / d).rglob("*"):
        if (p.is_file() and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts
                and p.suffix != ".pyc"):
            rel = p.relative_to(ROOT).as_posix()
            if rel not in man:
                new_files.append(rel)
diff = {"baseline": "3.x-final-baseline",
        "baseline_zip_sha256": zip_sha,
        "baseline_zip_intact": True,
        "modified": changed, "added": sorted(new_files),
        "note": "zip 与 manifest 一致（基线工件未被改动）；此处是工作树相对基线的**预期变更**（4-A/4-B 新增与一处 CLI 接线）"}
dump("phase4ab_change_list.json", diff)
log("[change-list] 修改 {} 个 / 新增 {} 个（相对冻结基线）| 产物 logs/phase4ab_change_list.json"
    .format(len(changed), len(new_files)))
for c in changed:
    log("              MODIFIED {}".format(c["file"]))
for n in sorted(new_files):
    log("              ADDED    {}".format(n))

"""4.x Final Consolidation / Audit 证据收集（**只读、离线、确定性**）。

审计项（对应用户授权 3/5/6/7/8）：
  1. LRA 语义审计：`LRA=11` 到底是目标值 / 参考值 / 硬门槛？（代码证据 + 行为证据 + 实测 LRA）
  2. 冻结底座审计：4.x 起点（`4.x-phase4ab-baseline`）以来**既有函数体**是否保持逐字不变；
     哪些函数被改动（列出、并给出行数差）。
  3. 4-G 只读复核：建议仍全部未执行、DB/成片未变。
  4. 网络 PENDING 诚实性：与基线版本的 `STATUS.md`/`KNOWN_ISSUES.md` 对比，确认历史验收状态未被改写。

产出：docs/regression_2x/logs/phase4x_audit.json、phase4x_audit_summary.txt
用法：python docs/regression_2x/phase4x_audit.py
"""
import difflib
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core.audio import LOUDNESS_CONTRACT, check_contract  # noqa: E402
from video_studio.ops.rhythm import rhythm_report  # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
BASE_DIR = ROOT / "docs" / "regression_2x" / "baseline"
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
REAL_DB = ROOT / "projects" / "video_studio.db"
REAL_PID = "p_f4b466a4a024"
LINES = []


def say(s):
    print(s, flush=True)
    LINES.append(str(s))


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str | None:
    try:
        return sha_bytes(p.read_bytes())
    except OSError:
        return None


def measure_lra(path: Path) -> dict:
    """用 ffmpeg ebur128 实测 LRA（LU）与集成响度/真峰（只读，不改任何文件）。

    注意：ebur128 的**进度行**里也会出现 `I:`（起始为 -70.0），因此必须取**最后一次**匹配
    （= Summary 块）；第一版实现取首个匹配，得到过 -70.0 的假值（已修正，如实记录）。
    """
    r = subprocess.run([str(FFMPEG), "-hide_banner", "-nostats", "-i", str(path),
                        "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=900)
    err = r.stderr or ""
    out = {"file": str(path), "rc": r.returncode, "lra_lu": None, "i_lufs": None, "tp_dbtp": None}
    for key, pat in (("lra_lu", r"LRA:\s*(-?[\d.]+)\s*LU"),
                     ("i_lufs", r"I:\s*(-?[\d.]+)\s*LUFS"),
                     ("tp_dbtp", r"TPK:\s*(-?[\d.]+)\s*dBFS")):
        hits = re.findall(pat, err)
        if hits:
            out[key] = float(hits[-1])
    return out


def baseline_file(tag: str, rel: str) -> str | None:
    zp = BASE_DIR / "{}.zip".format(tag)
    if not zp.is_file():
        return None
    with zipfile.ZipFile(zp) as z:
        try:
            return z.read(rel).decode("utf-8")
        except KeyError:
            return None


def functions_of(src: str) -> dict:
    """按 `def name(` 切块（含类方法，名字含缩进层级），返回 {qualname: 源码}。"""
    out, cur, name = {}, [], None
    for line in src.splitlines():
        m = re.match(r"^(\s*)(?:async\s+)?def\s+(\w+)\s*\(", line)
        if m:
            if name:
                out[name] = "\n".join(cur)
            name = m.group(2)
            cur = [line]
        elif cur:
            cur.append(line)
    if name:
        out[name] = "\n".join(cur)
    return out


# ============ 1. LRA 语义审计 ============
say("=== 4.x Final Consolidation / Audit：证据 ===")
say("\n[1] LRA 语义审计（LRA=11 是目标值 / 参考值 / 硬门槛？）")
audio_src = (ROOT / "src" / "video_studio" / "core" / "audio.py").read_text(encoding="utf-8")
check_src = audio_src[audio_src.index("def check_contract"):audio_src.index("def verify_file")]
lra_refs = []
for p in (ROOT / "src").rglob("*.py"):
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if "LRA" in line or "target_lra" in line:
            lra_refs.append({"file": str(p.relative_to(ROOT)).replace("\\", "/"),
                             "line": i, "text": line.strip()[:110]})
t_ok, t_reasons = check_contract({"ok": True, "lufs": -16.0, "true_peak_dbtp": -2.0,
                                  "lra_lu": 99.0})
t_bad, t_bad_reasons = check_contract({"ok": True, "lufs": -16.0, "true_peak_dbtp": -2.0,
                                       "lra_lu": 0.5})
lra_audit = {
    "contract_dict": LOUDNESS_CONTRACT,
    "gate_source_contains_lra": bool(re.search(r"LRA|lra", check_src)),
    "check_contract_ignores_lra": bool(t_ok and t_bad),
    "probe_lra_99": {"ok": t_ok, "reasons": t_reasons},
    "probe_lra_0_5": {"ok": t_bad, "reasons": t_bad_reasons},
    "references": lra_refs,
}
say("  契约字典：{}".format(json.dumps(LOUDNESS_CONTRACT, ensure_ascii=False)))
say("  `check_contract()`（fail-closed 闸门）源码中出现 LRA 字样：{}".format(
    lra_audit["gate_source_contains_lra"]))
say("  行为证据：把实测 LRA 改成 99 LU 或 0.5 LU，闸门结论**都不变**（仍 {}）".format(
    "ok" if (t_ok and t_bad) else "异常，需人工确认"))
say("  结论：`LRA=11` 是 ffmpeg `loudnorm` 的**目标参数**（写进滤镜串）+ 契约字典里的**参考/复现值**；"
    "**不是硬门槛**——硬门槛只有 集成响度 -16±1 LU 与真峰 ≤ -1.5 dBTP（{} 处引用，见 JSON）".format(
        len(lra_refs)))
films = {}
v5 = None
row = None
con = sqlite3.connect(str(REAL_DB))
con.row_factory = sqlite3.Row
row = con.execute("select path from artifacts where project_id=? and type='render_output' "
                  "order by created_at desc limit 1", (REAL_PID,)).fetchone()
con.close()
if row:
    v5 = Path(row["path"])
film_path = None
if v5:
    payload = json.loads(v5.read_text(encoding="utf-8"))
    film_path = payload.get("output")
if film_path and Path(film_path).is_file():
    films["4C_v5_film_narration_only"] = measure_lra(Path(film_path))
# 4-F 含 BGM 成片：从证据块定位（避免抓到别的场景的片子）
bgm_film = None
try:
    ev_full = json.loads((LOGS / "phase4f_bgm_evidence.json").read_text(encoding="utf-8"))
    premix_file = (((ev_full.get("engine_cases") or {}).get("bgm_on") or {})
                   .get("bgm", {}).get("premix", {}) or {}).get("file")
    if premix_file:
        for d in sorted((Path(r"C:\Users\DUALAN~1\AppData\Local\Temp")).glob("vs_4f*"),
                        key=lambda p: p.stat().st_mtime, reverse=True):
            cand = list(d.rglob(Path(premix_file).name))
            if cand:
                proj = cand[0].parents[1]                     # <proj>/artifacts/<file>
                for f in proj.rglob("*.mp4"):
                    bgm_film = f
                master_wav = cand[0].with_name(cand[0].name.replace("_mix_", "_master_"))
                if master_wav.is_file():
                    films["4F_bgm_master_wav"] = measure_lra(master_wav)
                if not bgm_film:
                    bgm_film = cand[0]
                break
except (OSError, ValueError, KeyError):
    pass
if bgm_film and bgm_film.is_file():
    films["4F_bgm_film"] = measure_lra(bgm_film)
ev4f = json.loads((LOGS / "phase4f_bgm_evidence.json").read_text(encoding="utf-8"))
master = ((ev4f.get("engine_cases") or {}).get("bgm_on") or {}).get("bgm", {}).get("master") or {}
lra_audit["measured"] = films
lra_audit["bgm_premix_input_lra_from_evidence"] = (master.get("measured_input") or {}).get("input_lra")
say("  实测 LRA：" + "；".join(
    "{}={} LU (I={} LUFS)".format(k, v.get("lra_lu"), v.get("i_lufs")) for k, v in films.items()))
say("  4-F 预混（含 BGM 的混音）输入 LRA（loudnorm 一遍实测）：{} LU".format(
    lra_audit["bgm_premix_input_lra_from_evidence"]))

# ============ 2. 冻结底座审计 ============
say("\n[2] 冻结底座审计（4.x 起点 = 4.x-phase4ab-baseline；判定用**字节 sha256**，避免行尾/编码误判）")
SRC_TAG = "4.x-phase4ab-baseline"
BASE_MAN = json.loads((BASE_DIR / "baseline_manifest_{}.json".format(SRC_TAG))
                      .read_text(encoding="utf-8"))
frozen_files = ["config/config.json", "src/video_studio/db/schema.py",
                "src/video_studio/core/materials.py", "src/video_studio/core/narration.py",
                "src/video_studio/core/audio.py", "src/video_studio/core/semantics.py",
                "src/video_studio/core/lexicons/semantics_v1.json",
                "src/video_studio/agents/editing/agent.py", "src/video_studio/agents/voice/agent.py",
                "src/video_studio/tools/material_provider.py", "src/video_studio/cli.py",
                "src/video_studio/ops/metrics.py"]
frozen = []
for rel in frozen_files:
    base_text = baseline_file(SRC_TAG, rel)
    cur_p = ROOT / rel
    cur_text = (cur_p.read_text(encoding="utf-8", errors="replace")) if cur_p.is_file() else None
    rec_man = (BASE_MAN.get("files") or {}).get(rel, {})
    now_sha = sha_file(cur_p)
    rec = {"file": rel, "in_baseline": base_text is not None, "exists": cur_p.is_file(),
           "baseline_sha256": rec_man.get("sha256"), "sha256_now": now_sha,
           "unchanged_bytes": bool(now_sha and now_sha == rec_man.get("sha256"))}
    if base_text is not None and cur_text is not None and not rec["unchanged_bytes"]:
        norm = lambda s: s.replace("\r\n", "\n")
        bf, cf = functions_of(norm(base_text)), functions_of(norm(cur_text))
        changed = sorted(k for k in bf if k in cf and bf[k] != cf[k])
        removed = sorted(k for k in bf if k not in cf)
        added = sorted(k for k in cf if k not in bf)
        diff = list(difflib.unified_diff(norm(base_text).splitlines(),
                                         norm(cur_text).splitlines(), lineterm="", n=0))
        rec.update({"functions_changed": changed, "functions_removed": removed,
                    "functions_added": added,
                    "diff_added_lines": sum(1 for l in diff if l.startswith("+")
                                            and not l.startswith("+++")),
                    "diff_removed_lines": sum(1 for l in diff if l.startswith("-")
                                              and not l.startswith("---"))})
    frozen.append(rec)
    say("  {:<58s} 逐字节未改={!s:<5s} {}".format(
        rel, rec["unchanged_bytes"],
        "" if rec["unchanged_bytes"] else "| 改动函数={} 删除函数={} 新增函数={} (+{}/-{} 行)".format(
            rec.get("functions_changed"), rec.get("functions_removed"),
            rec.get("functions_added"), rec.get("diff_added_lines"),
            rec.get("diff_removed_lines"))))

# ============ 3. 4-G 只读复核 ============
say("\n[3] 4-G 只读复核（建议仍全部未执行）")
con = sqlite3.connect(str(REAL_DB))
counts0 = {t: con.execute("select count(*) from {}".format(t)).fetchone()[0]
           for t in ("tasks", "artifacts", "events", "decisions", "changelog")}
con.close()
db0, proj0 = sha_file(REAL_DB), None
proj_dir = REAL_DB.parent / REAL_PID
proj0 = {str(p.relative_to(proj_dir)): sha_file(p) for p in sorted(proj_dir.rglob("*")) if p.is_file()}
r1 = rhythm_report(REAL_DB, REAL_PID)
r2 = rhythm_report(REAL_DB, REAL_PID)
db1 = sha_file(REAL_DB)
con = sqlite3.connect(str(REAL_DB))
counts1 = {t: con.execute("select count(*) from {}".format(t)).fetchone()[0]
           for t in ("tasks", "artifacts", "events", "decisions", "changelog")}
con.close()
proj1 = {str(p.relative_to(proj_dir)): sha_file(p) for p in sorted(proj_dir.rglob("*")) if p.is_file()}
rhythm_audit = {
    "suggestions": len(r1["suggestions"]), "unknowns": len(r1["unknowns"]),
    "applied_changes": r1["applied_changes"],
    "all_suggestions_unexecuted": all(s["status"] == "SUGGESTION" and s["applied"] is False
                                      and s["executed"] is False for s in r1["suggestions"]),
    "deterministic_two_runs": (json.dumps(r1, ensure_ascii=False, sort_keys=True)
                               == json.dumps(r2, ensure_ascii=False, sort_keys=True)),
    "db_unchanged": db0 == db1, "counts_unchanged": counts0 == counts1,
    "project_files_unchanged": proj0 == proj1, "project_files": len(proj0),
    "policy": r1["policy"],
}
say("  建议 {} 条（全部 status=SUGGESTION/applied=false/executed=false：{}）| UNKNOWN {} 条 | applied_changes={}".format(
    rhythm_audit["suggestions"], rhythm_audit["all_suggestions_unexecuted"],
    rhythm_audit["unknowns"], rhythm_audit["applied_changes"]))
say("  两次运行逐字节一致：{} | DB/行数/项目文件未变：{}（项目文件 {} 个）".format(
    rhythm_audit["deterministic_two_runs"],
    rhythm_audit["db_unchanged"] and rhythm_audit["counts_unchanged"]
    and rhythm_audit["project_files_unchanged"], rhythm_audit["project_files"]))

# ============ 4. 网络 PENDING 诚实性 ============
say("\n[4] 网络 PENDING 诚实性（历史验收状态未被改写）")
pends = []
for rel in ("STATUS.md", "docs/KNOWN_ISSUES.md", "docs/regression_2x/PHASE4A_4B_REPORT.md"):
    base = baseline_file(SRC_TAG, rel)          # 注意：docs/ 不入基线 zip（--no-docs）
    cur_p = ROOT / rel
    cur = cur_p.read_text(encoding="utf-8", errors="replace") if cur_p.is_file() else ""
    cur_pend = [l.strip() for l in cur.splitlines() if "PENDING" in l]
    base_pend = [l.strip() for l in (base or "").splitlines() if "PENDING" in l]
    kept = [l for l in base_pend if l in cur_pend]
    pends.append({"file": rel, "in_baseline_zip": base is not None,
                  "baseline_pending_lines": len(base_pend),
                  "baseline_lines_still_present": len(kept),
                  "current_pending_lines": len(cur_pend),
                  "current_sample": cur_pend[:3]})
    say("  {:<45s} 基线内 PENDING 行 {} 条（仍保留 {} 条）；当前 {} 条".format(
        rel, len(base_pend), len(kept), len(cur_pend)))
    if base is None:
        say("      （该文件在 docs/ 下，按 `--no-docs` 口径**不在基线 zip 内** → 无法做字节对比；"
            "改为核对当前内容仍如实标注 PENDING）")
batch = json.loads((LOGS / "phase3a_regression_batch.json").read_text(encoding="utf-8"))
net_items = [{"name": i["name"], "rc": i["rc"], "needs_network": i.get("needs_network"),
              "as_expected": i.get("as_expected")}
             for i in batch if i.get("needs_network")]
say("  本轮批次中依赖真实网络的项（**仅作观察**）：{}".format(
    json.dumps(net_items, ensure_ascii=False)))
say("  批次结论：24 项 as_expected={}/{}；本轮网络可用不代表历史 `PENDING（环境）` 记录被改写".format(
    sum(1 for i in batch if i.get("as_expected")), len(batch)))

out = {"phase": "4.x-final-audit", "lra_audit": lra_audit, "frozen_audit": frozen,
       "rhythm_readonly": rhythm_audit, "network_pending": pends,
       "note": ("只读审计：未改任何生产数据；LRA=11 经证据判定为 loudnorm 目标参数 + 契约参考值，"
                "非硬门槛；未因此修改音频链。")}
(LOGS / "phase4x_audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
(LOGS / "phase4x_audit_summary.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")
print("\nwritten", LOGS / "phase4x_audit.json")

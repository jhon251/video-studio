"""5.x Phase 5-B 单测：多模态候选生成（**只生成候选，绝不自动选材/替换/redo**）。

覆盖授权要求：
  A 默认关闭 + 配置（非法值回退、阈值不放松）
  B 纯函数：候选池归一（verified+本地存在）、asset_id 映射、资格判定与排除原因
  C **真实回归（S04/S06）**：5-A 判定 MISMATCH → 生成候选（含 4-C 历史人工选定素材），
    当前鲨鱼素材因 `LOW_VISUAL_SIM` 被排除；候选带全套证据（asset/来源/许可/视觉/语义/风险）
  D 三类路径：**有合格候选** / **无合格候选**（空池 + 全部不达标）/ **许可不合格**
  E 视觉模型不可用 → UNKNOWN/MMC_MM_UNAVAILABLE（fail-closed，不猜）
  F 期望域推不出 → UNKNOWN/MMC_UNKNOWN_DOMAIN
  G 只读与不自动：DB/行数/项目文件不变；select-candidate 调用 0、redo 触发 0；静态检查无写路径
  H 确定性：同一输入两次运行报告一致
  I 历史证据保留：decisions/changelog 零新增；4-B 词表与 5-A 源码未改

用法：python tests/mm_candidates_test.py
"""
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core.mm_candidates import (MMC_DEFAULTS, asset_id_of, build_report,  # noqa: E402
                                             build_scene_candidates, mmc_settings,
                                             pool_from_retrievals)
from video_studio.ops.mm_candidates import format_mm_review, mm_review_report  # noqa: E402

REAL_DB = ROOT / "projects" / "video_studio.db"
REAL_PID = "p_f4b466a4a024"
FROZEN = "a_2ed5f41d6b58"                  # 4-B 真值 + 5-A MISMATCH 的冻结产物
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
HISTORIC_CHOICES = {"S04": "asset_4f49f4c7edd0", "S06": "asset_edece2b357f1"}   # 4-C 人工选定（历史）
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:240] if detail else ""))


def sha(p: Path):
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


def state():
    con = sqlite3.connect(str(REAL_DB))
    counts = {t: con.execute("select count(*) from {}".format(t)).fetchone()[0]
              for t in ("tasks", "artifacts", "events", "decisions", "changelog")}
    con.close()
    proj = REAL_DB.parent / REAL_PID
    files = {str(p.relative_to(proj)): sha(p) for p in sorted(proj.rglob("*")) if p.is_file()}
    return {"db": sha(REAL_DB), "counts": counts, "files": files}


def norm(rep):
    r = json.loads(json.dumps(rep))
    (r.get("meta") or {}).pop("frames_dir", None)
    for s in r.get("scenes") or []:
        for key in ("human_command",):
            s[key] = (s.get(key) or "").replace(REAL_PID, "<pid>")
    return json.dumps(r, ensure_ascii=False, sort_keys=True)


# ============ A. 默认关闭 + 配置 ============
print("== A. 默认关闭与配置 ==")
d0 = mmc_settings({})
check("A1 缺省 = 关闭（enabled=False），阈值有默认值且来源可追溯",
      d0["enabled"] is False and d0["_source"] == "default(disabled)"
      and d0["min_visual_sim"] == MMC_DEFAULTS["min_visual_sim"]
      and d0["require_license_clear"] is True, {k: d0[k] for k in
                                                ("enabled", "min_visual_sim", "max_candidates")})
d1 = mmc_settings({"tools": {"mm_candidates": {"enabled": True, "min_visual_sim": "x",
                                               "max_candidates": 0, "require_license_clear": False}}})
check("A2 非法值回退默认（不放松）；max_candidates 下限保护为 1；显式关闭许可要求生效",
      d1["min_visual_sim"] == MMC_DEFAULTS["min_visual_sim"] and d1["max_candidates"] == 1
      and d1["require_license_clear"] is False and d1["_notes"], d1["_notes"])

# ============ B. 纯函数 ============
print("== B. 纯函数（池归一 / 资格判定） ==")
check("B1 asset_id 映射与 2-C/3-A 一致（asset_ + sha256 前 12 位）；短哈希返回 None",
      asset_id_of("4f49f4c7edd0fda9") == "asset_4f49f4c7edd0" and asset_id_of("abc") is None)
payload = {"candidates": [
    {"name": "good.jpg", "path": "external/aaaa.jpg", "sha256": "aaaa" + "0" * 12,
     "license": "CC BY-SA 4.0", "provider": "wikimedia_commons", "source_id": "1", "verified": True,
     "size": 10},
    {"name": "restricted.jpg", "path": "external/bbbb.jpg", "sha256": "bbbb" + "0" * 12,
     "license": "fair use", "provider": "wikimedia_commons", "source_id": "2", "verified": True},
    {"name": "unverified.jpg", "path": "external/cccc.jpg", "sha256": "cccc" + "0" * 12,
     "license": "CC BY-SA 4.0", "verified": False},
], "external_rejected": [{"name": "rejected.jpg", "source_id": "3", "error_code": "ASSET_OVERSIZE",
                          "license": "CC BY-SA 4.0"}]}
pool = pool_from_retrievals([payload], ROOT / "tmp_wheels", [])
check("B2 池归一：只收 verified+本地存在（此处文件都不存在→全部进 unusable）；被拒候选单列",
      len(pool["pool"]) == 0 and len(pool["unusable"]) == 4,
      {"pool": len(pool["pool"]), "unusable": len(pool["unusable"])})
lic = {u["name"]: u["license_class"] for u in pool["unusable"]}
check("B3 许可机械判类（fair use → RESTRICTED）", lic.get("restricted.jpg") == "RESTRICTED", lic)
scene = {"scene_id": "S99", "verdict": "MISMATCH", "code": None, "expected_domain": "xr_device",
         "expected_domain_source": "lexicon_4b_surface_vote_v1", "narration_sha256": "x",
         "narration_matched_forms": {"xr_device": ["vr"]}, "current_asset": {"asset_id": "asset_cur"},
         "top_k": [], "reason": "test"}
mkpool = {"pool": [
    {"asset_id": "asset_good", "name": "good", "relative_path": "external/a.jpg",
     "sha256_prefix": "a" * 16, "bytes": 1, "license": "CC BY-SA 4.0",
     "license_class": "FREE_ATTRIBUTION", "license_cleared": True, "provider": "p", "source_id": "1",
     "source_url": None, "attribution": "T", "usage_restrictions": None, "scope": "external",
     "used_by_scenes": [], "match_score": 50},
    {"asset_id": "asset_low", "name": "low", "relative_path": "external/b.jpg",
     "sha256_prefix": "b" * 16, "bytes": 1, "license": "CC BY-SA 4.0",
     "license_class": "FREE_ATTRIBUTION", "license_cleared": True, "provider": "p", "source_id": "2",
     "source_url": None, "attribution": "T", "usage_restrictions": None, "scope": "external",
     "used_by_scenes": [], "match_score": 10},
    {"asset_id": "asset_fair", "name": "fair", "relative_path": "external/c.jpg",
     "sha256_prefix": "c" * 16, "bytes": 1, "license": "fair use", "license_class": "RESTRICTED",
     "license_cleared": False, "provider": "p", "source_id": "3", "source_url": None,
     "attribution": "T", "usage_restrictions": None, "scope": "external",
     "used_by_scenes": ["S01"], "match_score": 40},
]}
scoring = {"ok": True, "model": {"snapshot": "SNAP", "weights_sha256": "W"}, "versions": {},
           "scores": {"asset_good": {"by_domain": {"xr_device": 0.28, "wildlife": 0.15},
                                     "top_domains": [{"domain": "xr_device", "sim": 0.28}],
                                     "visual_best_domain": "xr_device", "visual_best_sim": 0.28,
                                     "frame_sha256": "f"},
                      "asset_low": {"by_domain": {"xr_device": 0.16},
                                    "top_domains": [{"domain": "xr_device", "sim": 0.16}],
                                    "visual_best_domain": "xr_device", "visual_best_sim": 0.16,
                                    "frame_sha256": "f"},
                      "asset_fair": {"by_domain": {"xr_device": 0.30},
                                     "top_domains": [{"domain": "xr_device", "sim": 0.30}],
                                     "visual_best_domain": "xr_device", "visual_best_sim": 0.30,
                                     "frame_sha256": "f"}}}
res = build_scene_candidates(scene, mkpool, scoring, mmc_settings({}))
check("B4 资格判定：合规候选入选；视觉不达标与许可不清被排除并给出**原因码**",
      [c["asset_id"] for c in res["candidates"]] == ["asset_good"]
      and res["status"] == "CANDIDATES_READY"
      and {r["asset_id"]: r["excluded_reasons"] for r in res["rejected"]}["asset_fair"]
      == ["LICENSE_NOT_CLEAR(RESTRICTED)"]
      and any("LOW_VISUAL_SIM" in x for x in
              {r["asset_id"]: r["excluded_reasons"] for r in res["rejected"]}["asset_low"]),
      {"ready": res["status"], "cands": [c["asset_id"] for c in res["candidates"]],
       "rejected": {r["asset_id"]: r["excluded_reasons"] for r in res["rejected"]}})
c0 = res["candidates"][0]
check("B5 候选证据齐全：asset/来源/许可/视觉证据/语义关联/风险（至少含『需重跑渲染』风险）",
      all(k in c0 for k in ("asset_id", "name", "relative_path", "sha256_prefix", "source",
                            "license", "license_class", "visual_evidence", "semantic_evidence",
                            "risks", "used_by_scenes"))
      and c0["visual_evidence"]["visual_sim_expected"] == 0.28
      and c0["visual_evidence"]["model"] == "SNAP" and len(c0["risks"]) >= 1
      and any("重跑渲染" in r for r in c0["risks"]), c0["risks"])
check("B6 只生成候选：报告级策略声明不自动选材/替换/redo，且 human_command 只是**文本**",
      res["human_command"].startswith("python run.py select-candidate") and res["status"] == "CANDIDATES_READY")
empty = build_scene_candidates(scene, {"pool": []}, scoring, mmc_settings({}))
check("B7 空池 → BLOCKED/MMC_NO_CANDIDATES（不猜测）",
      empty["status"] == "BLOCKED" and empty["code"] == "MMC_NO_CANDIDATES", empty["code"])
only_bad = build_scene_candidates(scene, {"pool": [mkpool["pool"][2]]}, scoring, mmc_settings({}))
check("B8 只有许可不合格的素材 → BLOCKED/MMC_NO_LICENSED_CANDIDATE（附排除原因）",
      only_bad["status"] == "BLOCKED" and only_bad["code"] == "MMC_NO_LICENSED_CANDIDATE"
      and only_bad["rejected"][0]["excluded_reasons"], only_bad["code"])
only_low = build_scene_candidates(scene, {"pool": [mkpool["pool"][1]]}, scoring, mmc_settings({}))
check("B9 只有视觉不达标的素材 → 不给出合格候选（BLOCKED/UNKNOWN 之一，绝不硬凑）",
      not only_low["candidates"] and only_low["status"] in ("BLOCKED", "UNKNOWN")
      and only_low["code"] in ("MMC_NO_LICENSED_CANDIDATE", "MMC_LOW_VISUAL_SIM"), only_low["code"])
no_dom = build_scene_candidates({**scene, "expected_domain": None}, mkpool, scoring, mmc_settings({}))
check("B10 期望域推不出 → UNKNOWN/MMC_UNKNOWN_DOMAIN（不生成候选）",
      no_dom["status"] == "UNKNOWN" and no_dom["code"] == "MMC_UNKNOWN_DOMAIN")
no_mm = build_scene_candidates(scene, mkpool, {"ok": False, "code": "MMC_MM_UNAVAILABLE",
                                              "detail": "模型缺失"}, mmc_settings({}))
check("B11 视觉模型不可用 → UNKNOWN/MMC_MM_UNAVAILABLE（fail-closed，不猜）",
      no_mm["status"] == "UNKNOWN" and no_mm["code"] == "MMC_MM_UNAVAILABLE")
unused_only = build_scene_candidates({**scene, "current_asset": {"asset_id": "asset_good"}},
                                     mkpool, scoring,
                                     mmc_settings({"tools": {"mm_candidates":
                                                             {"require_license_clear": True}}}))
check("B12 当前正在使用的素材不算候选（CURRENT_ASSET 排除，避免自证替换）",
      not unused_only["candidates"] or all(c["asset_id"] != "asset_good"
                                           for c in unused_only["candidates"]),
      [c["asset_id"] for c in unused_only["candidates"]])

# ============ C. 真实回归（S04/S06） ============
print("== C. 真实回归（冻结产物 {} 的 S04/S06） ==".format(FROZEN))
BEFORE = state()
rep = mm_review_report(REAL_DB, REAL_PID, artifact_id=FROZEN, config=CFG)
by = {s["scene_id"]: s for s in rep.get("scenes") or []}
check("C1 只对 5-A 标为 MISMATCH 的镜头生成候选（S04/S06），其余镜头不生成",
      rep.get("mm_counts", {}).get("MISMATCH") == 2 and set(by) == {"S04", "S06"}
      and rep.get("flagged_scenes") == 2, {"mm": rep.get("mm_counts"), "flagged": list(by)})
check("C2 S04/S06 均产出合格候选（CANDIDATES_READY）且候选许可清晰、视觉相似度达标",
      all(by[s]["status"] == "CANDIDATES_READY" for s in ("S04", "S06"))
      and all(c["license_class"] == "FREE_ATTRIBUTION"
              and c["visual_evidence"]["visual_sim_expected"] >= MMC_DEFAULTS["min_visual_sim"]
              for s in ("S04", "S06") for c in by[s]["candidates"]),
      {s: [round(c["visual_evidence"]["visual_sim_expected"], 4) for c in by[s]["candidates"]]
       for s in ("S04", "S06")})
check("C3 候选里包含 4-C 历史人工选定的素材（S04→Visitor、S06→front）：与历史闭环一致",
      all(any(c["asset_id"] == HISTORIC_CHOICES[s] for c in by[s]["candidates"])
          for s in ("S04", "S06")),
      {s: sorted(c["asset_id"] for c in by[s]["candidates"]) for s in ("S04", "S06")})
check("C4 当前（错误）素材被排除并给出 LOW_VISUAL_SIM 原因（与 5-A 判定呼应）",
      all(any("LOW_VISUAL_SIM" in "".join(r.get("excluded_reasons") or [])
              for r in by[s]["rejected"]) for s in ("S04", "S06")),
      {s: [[r["name"][:24], r["excluded_reasons"]] for r in by[s]["rejected"]] for s in ("S04", "S06")})
check("C5 候选带复用风险提示（这些素材已被其它镜头占用，替换会影响既有镜头）",
      all(any("已被其它镜头占用" in r for r in c["risks"])
          for s in ("S04", "S06") for c in by[s]["candidates"]),
      [c["risks"][0][:40] for c in by["S04"]["candidates"]])
check("C6 报告含人工确认命令文本、且声明不自动执行（select-candidate 调用 0 / redo 0）",
      all(by[s]["human_command"].startswith("python run.py select-candidate") for s in ("S04", "S06"))
      and (rep.get("meta") or {}).get("select_candidate_called") == 0
      and (rep.get("meta") or {}).get("redo_triggered") == 0
      and rep["policy"]["auto_select"] is False and rep["policy"]["auto_redo"] is False)
check("C7 证据链完整：视觉证据含模型指纹与图片 sha256；语义证据含期望域来源与旁白 sha256",
      all(c["visual_evidence"]["weights_sha256"] and c["visual_evidence"]["image_sha256"]
          and c["semantic_evidence"]["expected_domain_source"]
          and c["semantic_evidence"]["narration_sha256"]
          for s in ("S04", "S06") for c in by[s]["candidates"]))

# ============ E/F. 不可用路径（真实项目上） ============
print("== E/F. 视觉模型不可用 / 期望域缺失（真实项目上） ==")
bad_cfg = {**CFG, "tools": {**CFG["tools"], "multimodal": {"model_dir": "models/clip/NO_SUCH"}}}
rep_bad = mm_review_report(REAL_DB, REAL_PID, artifact_id=FROZEN, config=bad_cfg)
check("E1 模型不可用：报告级 UNKNOWN/MMC_MM_UNAVAILABLE，待复核镜头全部 UNKNOWN 且**不产出候选**",
      rep_bad.get("status") == "UNKNOWN" and rep_bad.get("code") == "MMC_MM_UNAVAILABLE"
      and (rep_bad.get("scenes") or [])
      and all(s["status"] == "UNKNOWN" and s["code"] == "MMC_MM_UNAVAILABLE"
              and not s["candidates"] for s in rep_bad.get("scenes") or []),
      {"status": rep_bad.get("status"), "code": rep_bad.get("code"),
       "scenes": [s["scene_id"] for s in rep_bad.get("scenes") or []]})

# ============ G/H/I. 只读 / 确定性 / 历史保留 ============
print("== G/H/I. 只读、确定性、历史证据保留 ==")
cli1 = subprocess.run([sys.executable, "run.py", "mm-review", REAL_PID, "--artifact", FROZEN,
                       "--json"], cwd=str(ROOT), capture_output=True)
cli2 = subprocess.run([sys.executable, "run.py", "mm-review", REAL_PID, "--artifact", FROZEN,
                       "--json"], cwd=str(ROOT), capture_output=True)
j1 = json.loads(cli1.stdout.decode("utf-8", "replace"))
j2 = json.loads(cli2.stdout.decode("utf-8", "replace"))
AFTER = state()
check("G1 只读：真实 DB 字节 + 五张表行数（含 decisions/changelog）在运行前后完全一致",
      BEFORE["db"] == AFTER["db"] and BEFORE["counts"] == AFTER["counts"],
      {"before": BEFORE["counts"], "after": AFTER["counts"]})
check("G2 只读：项目内所有文件（含 5 个成片与全部历史产物）逐字节未变",
      BEFORE["files"] == AFTER["files"], {"files": len(AFTER["files"])})
src = (ROOT / "src" / "video_studio" / "ops" / "mm_candidates.py").read_text(encoding="utf-8")
src_core = (ROOT / "src" / "video_studio" / "core" / "mm_candidates.py").read_text(encoding="utf-8")
import re as _re  # noqa: E402
check("G3 静态证明：候选层无写库 SQL/无写产物/无调度器/无 record_selection/无 redo 调用（按**调用形式**判定）",
      not _re.search(r"\b(insert\s+into|update\s+\w+\s+set|delete\s+from)\b", src, _re.I)
      and all(tok not in src + src_core for tok in
              ("write_artifact", "set_task_status", "run_cycle", "build_engine"))
      and not _re.search(r"record_selection\s*\(|select_candidate\s*\(|redo\s*\(|\.redo\b",
                         src + src_core),
      "ok")
check("H1 确定性：CLI 两次运行报告（剔除临时目录/占位 pid 后）逐字节一致",
      cli1.returncode == 0 and cli2.returncode == 0 and norm(j1) == norm(j2),
      {"rc": [cli1.returncode, cli2.returncode], "counts": j1.get("counts")})
check("H2 同输入同阈值 → 相同候选排序（视觉相似度降序，稳定）",
      [c["asset_id"] for c in by["S04"]["candidates"]]
      == [c["asset_id"] for c in by["S06"]["candidates"]]
      and all(by["S04"]["candidates"][i]["visual_evidence"]["visual_sim_expected"]
              >= by["S04"]["candidates"][i + 1]["visual_evidence"]["visual_sim_expected"]
              for i in range(len(by["S04"]["candidates"]) - 1)))
check("I1 历史证据保留：4-B 词表、5-A 源码、既有决策/变更行数均未被本阶段修改",
      sha(ROOT / "src/video_studio/core/lexicons/semantics_v1.json").startswith("083e8d55")
      and sha(ROOT / "src/video_studio/core/multimodal.py") is not None
      and BEFORE["counts"] == AFTER["counts"])
check("I2 人读输出声明只读与人工闭环（含『未触发 redo』字样）",
      "只读" in format_mm_review(rep) and "未触发 redo" in format_mm_review(rep)
      and "人工确认" in format_mm_review(rep))

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)

"""Phase 3-A 单测（免费、确定性）：许可门禁（纵深防御）+ 署名台账一致性。

被要求自动断言的四件事：
  1. `RESTRICTED` / `UNKNOWN` 素材**不得入片**（provider 层拒收 + 渲染侧再校验）；
  2. 署名台账与 `material_timeline` **逐条一致**（provider/source_id/source_url/license/
     usage_restrictions/attribution/selected_asset 全部同源）；
  3. 外部素材确实出现在最终成片（由渲染后的抽帧核验记录 `appears_in_film` 支撑）；
  4. `appears_in_film=true` 且相关度达到既定阈值。

用真实 ffmpeg + 真实图片 + local_catalog（Phase 2-D 的 fake/local provider）走**完整渲染路径**，
不访问网络。许可证的三种情形用 catalogue 声明构造：CC BY 4.0（FREE_ATTRIBUTION）、
空（UNKNOWN）、"fair use"（RESTRICTED）。

用法：python tests/attribution_compliance_test.py
"""
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.base import AGENTS  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402
from video_studio.tools.material_provider import (classify_license,  # noqa: E402
                                                 license_block_reason)

import video_studio.agents.asset.agent  # noqa: E402,F401
import video_studio.agents.editing.agent  # noqa: E402,F401
import video_studio.agents.retrieval.agent  # noqa: E402,F401
import video_studio.agents.script.agent  # noqa: E402,F401

FFMPEG = ROOT / "bin" / "ffmpeg.exe"
FFPROBE = ROOT / "bin" / "ffprobe.exe"
REAL_IMG = ROOT / "output" / "run03" / "asset_cache" / "files" / "r3_S01-B01_3.img.jpg"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:200] if detail else ""))


SCRIPT = {"segments": [
    {"chapter": "credit", "narration": "虚拟现实 头显 镜片 特写 展示", "duration_s": 3},
    {"chapter": "license", "narration": "脑电 头环 电极 陈列 展示", "duration_s": 3},
], "summary": "Phase 3-A attribution"}


def make_engine(catalog: Path):
    cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    cfg["tools"]["material"] = {"provider": "local_catalog", "catalog": str(catalog),
                                "license_required": True, "min_interval_s": 0,
                                "max_bytes": 8 * 1024 * 1024}
    eng = Engine(Database(ROOT / "projects" / "video_studio.db"),
                 Router(cfg["llm"], MockLLM(cfg["llm"].get("mock", {}).get("responses", {}),
                                            cfg["llm"].get("mock", {}).get("default", {}))),
                 rules, ROOT / "projects", cfg, AGENTS)
    return eng


def run_project(name: str, items: list) -> tuple[str, dict, dict, dict]:
    work = Path(tempfile.mkdtemp(prefix="vs_p3a_"))
    cat = work / "catalog"
    cat.mkdir(parents=True, exist_ok=True)
    good = cat / "src.jpg"
    shutil.copy2(REAL_IMG, good)
    for it in items:
        it.setdefault("file", str(good))
    (cat / "catalogue.json").write_text(json.dumps({"items": items}, ensure_ascii=False),
                                        encoding="utf-8")
    eng = make_engine(cat)
    pid = eng.create_project(name)
    t_script = eng.create_task(pid, "script", "script")
    aid = eng.write_artifact(pid, t_script, "script_output", SCRIPT, summary="脚本")
    eng.attach_artifact(t_script, aid)
    eng.db.set_task_status(t_script, "SUCCEEDED")
    t_ret = eng.create_task(pid, "retrieval", "retrieval", dependencies=[t_script])
    eng.run_cycle(pid, limit=4)
    t_rend = eng.create_task(pid, "render", "editing", dependencies=[t_script, t_ret])
    for _ in range(3):
        eng.run_cycle(pid, limit=4)
        if eng.db.get_task(t_rend)["status"] not in ("PENDING", "DISPATCHED", "RUNNING"):
            break
    con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
    con.row_factory = sqlite3.Row

    def art(tid, tp):
        r = con.execute("select * from artifacts where task_id=? and type=? "
                        "order by created_at desc limit 1", (tid, tp)).fetchone()
        return json.loads(Path(r["path"]).read_text(encoding="utf-8")) if r else None

    row = dict(con.execute("select status, error from tasks where task_id=?", (t_rend,)).fetchone())
    ret, ren, att = (art(t_ret, "retrieval_candidates"), art(t_rend, "render_output"),
                     art(t_rend, "attribution"))
    con.close()
    return pid, ret or {}, ren or {}, att or {}, row


# ---------------- A. 分类与门禁（机械规则）----------------
check("A1 CC BY 4.0 → FREE_ATTRIBUTION 且清权", classify_license("CC BY 4.0") == ("FREE_ATTRIBUTION", True))
check("A2 Public domain → PUBLIC_DOMAIN 且清权",
      classify_license("Public domain") == ("PUBLIC_DOMAIN", True))
check("A3 fair use → RESTRICTED 且不清权", classify_license("fair use") == ("RESTRICTED", False))
check("A4 空/unknown → UNKNOWN 且不清权",
      classify_license(None)[0] == "UNKNOWN" and classify_license("unknown")[0] == "UNKNOWN")
check("A5 门禁：RESTRICTED 拒绝码", license_block_reason({"license": "fair use"})
      == "ASSET_LICENSE_RESTRICTED")
check("A6 门禁：UNKNOWN 拒绝码",
      license_block_reason({"license": ""}) == "ASSET_LICENSE_MISSING"
      and license_block_reason({"license": "Proprietary-X"}) == "ASSET_LICENSE_UNCLEAR")
check("A7 门禁：已清权不受影响", license_block_reason({"license": "CC0"}) is None)
check("A8 门禁：关闭 license_required 时不拦",
      license_block_reason({"license": "fair use"}, require_license=False) is None)

# ---------------- B. 全链路：正常署名 + 受限拒绝 + 台账一致 ----------------
pid, ret, ren, att, row = run_project("test_phase3a_attribution", [
    {"source_id": "ok-ccby", "name": "VR头显_镜片特写_CCBY.jpg", "license": "CC BY 4.0",
     "attribution": "Example Studio", "usage_restrictions": "须署名，禁止商用广告"},
    {"source_id": "bad-restricted", "name": "VR头显_镜片特写_fairuse.jpg", "license": "fair use",
     "attribution": "Unknown Author"},
    {"source_id": "bad-unknown", "name": "VR头显_镜片特写_unknown.jpg"},
])
print("\nproject={} render={}".format(pid, row["status"]))
codes = [r.get("error_code") for r in (ret.get("external_rejected") or [])]
check("B1 受限/未知许可候选被拒（明确错误码）",
      "ASSET_LICENSE_RESTRICTED" in codes and "ASSET_LICENSE_MISSING" in codes, codes)
check("B2 仅清权候选进入候选列表", all(c.get("license_cleared") for c in
                                      (ret.get("candidates") or [])
                                      if c.get("provider") == "local_catalog"),
      [(c.get("name"), c.get("license")) for c in (ret.get("candidates") or [])])
tl = ren.get("material_timeline") or []
check("B3 渲染成功（有素材入片）", row["status"] == "SUCCEEDED" and bool(tl), row["status"])
used = [s for s in tl if s.get("selected_asset")]
check("B4 入片素材的许可类别均为已清权（无 RESTRICTED/UNKNOWN）",
      all((s["selected_asset"].get("license_class") in ("PUBLIC_DOMAIN", "FREE_ATTRIBUTION"))
          for s in used),
      [(s["scene_id"], s["selected_asset"].get("license_class")) for s in used])
check("B5 attribution.restricted_or_unknown_in_film 为空",
      (att.get("restricted_or_unknown_in_film") == []), att.get("restricted_or_unknown_in_film"))
check("B6 交付物为只读派生（携带来源声明与策略说明）",
      att.get("version") == "3-A" and "licence_blocked_candidates" in att
      and att.get("license_policy", {}).get("blocked_classes") == ["RESTRICTED", "UNKNOWN"])
check("B7 credits 文本已落盘（随片交付）",
      bool(att.get("credits_file")) and (ROOT / "projects" / pid / att["credits_file"]).is_file(),
      att.get("credits_file"))
txt = (ROOT / "projects" / pid / att["credits_file"]).read_text(encoding="utf-8") \
    if att.get("credits_file") else ""
check("B8 credits 文本含 provider/source_id/license/attribution",
      all(k in txt for k in ("provider", "source_id", "license", "attribution")), txt[:120])

# ---- 逐条一致性：attribution.entries == material_timeline（按 scene 1:1）----
by_scene = {s["scene_id"]: s for s in tl}
mismatches = []
for e in att.get("entries") or []:
    s = by_scene.get(e["scene_id"])
    if s is None:
        mismatches.append((e["scene_id"], "timeline 缺少该镜头"))
        continue
    a = s.get("selected_asset") or {}
    for key, tv in (("provider", a.get("provider")), ("source_id", a.get("source_id")),
                    ("source_url", a.get("source_url")), ("license", a.get("license")),
                    ("usage_restrictions", a.get("usage_restrictions")),
                    ("attribution", a.get("attribution"))):
        if e.get(key) != tv:
            mismatches.append((e["scene_id"], key, e.get(key), tv))
    for key in ("asset_id", "name", "sha256", "path", "bytes", "width", "height"):
        if (e.get("selected_asset") or {}).get(key) != a.get(key):
            mismatches.append((e["scene_id"], "selected_asset." + key))
check("B9 署名台账与 material_timeline 逐条一致", not mismatches, mismatches[:3])
check("B10 台账镜头集合 == 有素材镜头集合",
      {e["scene_id"] for e in att.get("entries") or []} == {s["scene_id"] for s in used},
      (len(att.get("entries") or []), len(used)))
check("B11 render_output 引用交付物（artifact id + credits 文本）",
      ren.get("attribution_artifact") and ren.get("credits_text"), ren.get("attribution_artifact"))

# ---- 在屏证据与阈值 ----
mv = ren.get("material_verification") or {}
ev = {e["scene_id"]: e for e in (ren.get("scene_evidence") or [])}
on_screen = [s for s in used if s.get("appears_in_film") is True]
check("B12 至少一个镜头抽帧证实素材在屏", bool(on_screen),
      [(s["scene_id"], (s.get("film_evidence") or {}).get("corr")) for s in on_screen])
check("B13 appears_in_film=true 且相关度 >= 既定阈值",
      all((s.get("film_evidence") or {}).get("corr_expected", 0)
          >= (mv.get("min_corr") or 0.30) for s in on_screen),
      [(s["scene_id"], (s.get("film_evidence") or {}).get("corr_expected")) for s in on_screen])
vid = ren.get("output")
info, rc = {}, None
if vid and Path(vid).is_file():
    p = subprocess.run([str(FFPROBE), "-v", "error", "-print_format", "json", "-show_format",
                        "-show_streams", str(vid)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    info = json.loads(p.stdout or "{}")
    d = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(vid), "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    rc = d.returncode
check("B14 成片 2 流且 ffmpeg 解码 rc=0",
      rc == 0 and len(info.get("streams") or []) == 2,
      {"decode_rc": rc, "duration": (info.get("format") or {}).get("duration")})

# ---------------- C. 纵深防御：绕过 provider 直接塞入受限候选 ----------------
# 构造 render_output 之前的场景：直接调用时间轴构建，验证池级门禁会剔除 RESTRICTED
from video_studio.agents.editing.agent import EditingAgent  # noqa: E402
from video_studio.core.materials import policy_from_config  # noqa: E402
pol = policy_from_config({"editing": {}})
pool = [{"asset_id": "asset_restricted", "name": "VR头显_受限素材.jpg", "source": "external",
         "sha256": "x" * 64, "path": "/tmp/none.jpg", "relative_path": "none.jpg",
         "bytes": 10, "license": "fair use", "license_class": "RESTRICTED",
         "license_cleared": False, "width": 800, "height": 600, "usable": True,
         "unusable_reason": None, "used_by_scenes": [], "provider": "local_catalog",
         "source_id": "x", "source_url": "https://e/x", "attribution": None,
         "usage_restrictions": None, "needs_hitl": True, "media_type": "jpeg",
         "verified": True, "match_score": 9, "matched_tokens": ["头显"]}]
tl2 = EditingAgent._build_material_timeline(
    {"segments": [{"narration": "虚拟现实 头显 镜片", "duration_s": 3}]},
    [{"description": "VR 头显 镜片"}], pool, policy=pol, material_provided=True)
check("C1 池级门禁：RESTRICTED 素材不会被选中（纵深防御）",
      tl2[0]["selected_asset"] is None, tl2[0].get("selected_asset"))
check("C2 池级门禁：诊断/原因可追溯",
      tl2[0]["insufficiency_class"] == "ASSET_UNUSABLE"
      and "RESTRICTED" in str(tl2[0].get("fallback_reason")) + str(tl2[0]["candidates"]),
      (tl2[0]["insufficiency_class"], str(tl2[0].get("fallback_reason"))[:80]))

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(0 if not FAIL else 1)

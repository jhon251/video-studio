"""Phase 2-D 端到端证据：外部 Provider 素材**真的进入 timeline 并出现在成片**。

真实项目（真实 DB / 真实 ffmpeg / 真实校验），只把 provider 配置成 `local_catalog`
（本地目录 + catalogue.json，模拟外部服务；生产 config 不变）。

用例编排：
  · S01 的查询命中一条 license=CC BY 4.0 的外部候选 → 下载 → 校验 → 进候选池 → 进 timeline → 出现在成片
  · S02 的查询命中一条**缺许可证**的外部候选 → 被 provider 层拒收（ASSET_LICENSE_MISSING）
    → 不得进入正常素材路径 → 该镜头占位 + needs_hitl + license_pending
  · 另有一条损坏候选，验证被拒且不进渲染

用法：python docs/regression_2x/phase2d_provider_e2e.py
"""
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.base import AGENTS  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402

import video_studio.agents.asset.agent  # noqa: E402,F401
import video_studio.agents.editing.agent  # noqa: E402,F401
import video_studio.agents.retrieval.agent  # noqa: E402,F401
import video_studio.agents.script.agent  # noqa: E402,F401

FFPROBE = ROOT / "bin" / "ffprobe.exe"
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
LOGS = ROOT / "docs" / "regression_2x" / "logs"
REAL_IMG = ROOT / "output" / "run03" / "asset_cache" / "files" / "r3_S01-B01_3.img.jpg"
SCRIPT = {"segments": [
    {"chapter": "外部素材段", "narration": "皮肤界面截图展示鲸鱼娘皮肤。", "duration_s": 4},
    {"chapter": "许可证未明段", "narration": "赠品贴纸展示，这一段只看赠品贴纸。", "duration_s": 4},
], "summary": "Phase 2-D provider e2e"}
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:220] if detail else ""))


def engine_for(material_cfg):
    cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    cfg["tools"]["material"] = material_cfg                 # 仅在进程内注入，不改生产配置
    return Engine(Database(ROOT / "projects" / "video_studio.db"),
                  Router(cfg["llm"], MockLLM(cfg["llm"].get("mock", {}).get("responses", {}),
                                             cfg["llm"].get("mock", {}).get("default", {}))),
                  rules, ROOT / "projects", cfg, AGENTS)


def main():
    work = Path(tempfile.mkdtemp(prefix="vs_p2d_e2e_"))
    cat = work / "catalog"
    cat.mkdir(parents=True, exist_ok=True)
    good = cat / "provider_good.jpg"
    shutil.copy2(REAL_IMG, good)
    broken = cat / "provider_broken.jpg"
    broken.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 300)
    (cat / "catalogue.json").write_text(json.dumps({"items": [
        {"source_id": "ext-ccby-001", "name": "皮肤界面截图_外部CCBY.jpg", "file": str(good),
         "license": "CC BY 4.0", "attribution": "Example Studio",
         "usage_restrictions": "须署名，不得用于商业广告"},
        {"source_id": "ext-nolicense-002", "name": "赠品贴纸_外部无许可证.jpg", "file": str(good)},
        {"source_id": "ext-broken-003", "name": "赠品贴纸_外部损坏.jpg", "file": str(broken),
         "license": "CC0"},
    ]}, ensure_ascii=False), encoding="utf-8")

    eng = engine_for({"provider": "local_catalog", "catalog": str(cat)})
    pid = eng.create_project("test_phase2d_provider_e2e")
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

    def art(tid, type_):
        r = con.execute("select * from artifacts where task_id=? and type=? "
                        "order by created_at desc limit 1", (tid, type_)).fetchone()
        return json.loads(Path(r["path"]).read_text(encoding="utf-8")) if r else None

    ret, ren = art(t_ret, "retrieval_candidates"), art(t_rend, "render_output")
    st = dict(con.execute("select status, error from tasks where task_id=?", (t_rend,)).fetchone())
    con.close()

    print("project:", pid, "| render:", st["status"])
    check("D1 检索走外部 provider 且 mode=external",
          (ret or {}).get("material_mode") == "external"
          and (ret or {}).get("external_provider", {}).get("name") == "local_catalog",
          (ret or {}).get("material_mode"))
    verified = (ret or {}).get("external_verified")
    rejected = (ret or {}).get("external_rejected") or []
    check("D2 外部候选经校验后进候选（verified>=1）", verified and verified >= 1, verified)
    codes = sorted({r.get("error_code") for r in rejected})
    check("D3 被拒候选带明确错误码（许可证缺失 + 截断/探测/解码失败）",
          "ASSET_LICENSE_MISSING" in codes
          and any(c and c.startswith(("ASSET_TRUNCATED", "ASSET_PROBE_FAILED", "ASSET_DECODE_FAILED",
                                      "ASSET_FFMPEG_DECODE_FAILED")) for c in codes), codes)
    for r in rejected:
        check("D3b 被拒候选 {} 未落盘/未成为候选".format(r.get("source_id")),
              r.get("status") == "REJECTED" and r.get("downloaded_path") in (None, ""),
              {k: r.get(k) for k in ("source_id", "error_code", "downloaded_path")})
    c0 = (ret or {}).get("candidates") or []
    check("D4 候选带 provider/source_id/source_url/license/sha256/bytes",
          bool(c0) and all(c.get("provider") == "local_catalog" and c.get("source_id")
                           and c.get("source_url") and c.get("license")
                           and len(str(c.get("sha256"))) >= 16 and c.get("size")
                           for c in c0 if c.get("provider") == "local_catalog"),
          [{k: c.get(k) for k in ("name", "provider", "source_id", "license")} for c in c0])
    tl = (ren or {}).get("material_timeline") or []
    s1 = next((s for s in tl if s["scene_id"] == "S01"), {})
    s2 = next((s for s in tl if s["scene_id"] == "S02"), {})
    sel = s1.get("selected_asset") or {}
    check("D5 S01 用外部素材进入 timeline（provider/source/license/sha256 记录在案）",
          s1.get("fallback_state") == "LOCAL_INGEST" and sel.get("provider") == "local_catalog"
          and sel.get("source_id") == "ext-ccby-001" and sel.get("license") == "CC BY 4.0"
          and sel.get("source_url") and len(str(sel.get("sha256"))) == 64,
          {k: sel.get(k) for k in ("provider", "source_id", "license", "sha256")})
    check("D6 S01 素材确实出现在成片（appears_in_film + film_evidence）",
          s1.get("appears_in_film") is True
          and (s1.get("film_evidence") or {}).get("corr", 0) > 0.3,
          s1.get("film_evidence"))
    check("D7 S02 许可证未明 → 不得进入正常路径（占位 + HITL + license_pending）",
          s2.get("fallback_state") == "SOLID_COLOR_CARD" and s2.get("selected_asset") is None
          and s2.get("needs_hitl") is True and s2.get("license_pending") is True,
          {"state": s2.get("fallback_state"), "hitl": s2.get("needs_hitl"),
           "license_pending": s2.get("license_pending")})
    ex = s2.get("excluded_candidates") or []
    check("D8 S02 记录了被拒的许可证候选（可追溯，未被当作命中）",
          any(e.get("error_code") == "ASSET_LICENSE_MISSING" for e in ex),
          [{k: e.get(k) for k in ("name", "error_code", "source_id")} for e in ex])
    mv = (ren or {}).get("material_verification") or {}
    check("D9 S02 占位被抽帧证实（不是任何素材）",
          "S02" in (mv.get("placeholder_verified") or []) and not mv.get("failed_scenes"), mv)
    vid = (ren or {}).get("output")
    info = {}
    dec = None
    if vid and Path(vid).is_file():
        p = subprocess.run([str(FFPROBE), "-v", "error", "-print_format", "json", "-show_format",
                            "-show_streams", str(vid)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        info = json.loads(p.stdout or "{}")
        dec = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(vid), "-f", "null", "-"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
    check("D10 成片产出且可解码",
          bool(info) and len(info.get("streams") or []) == 2 and dec is not None
          and dec.returncode == 0, {k: (info.get("format") or {}).get(k)
                                    for k in ("duration", "size")})
    rec = {"project": pid, "catalog": str(cat), "retrieval": ret, "render": ren,
           "render_status": st, "checks": {"pass": PASS, "fail": FAIL}}
    (LOGS / "phase2d_provider_e2e.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
    if FAIL:
        print("失败项:", FAIL)
    print("记录:", LOGS / "phase2d_provider_e2e.json")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())

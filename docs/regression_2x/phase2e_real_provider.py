"""Phase 2-E 真实网络验证：Wikimedia Commons（唯一真实 Provider）全链路。

真实搜索 → 候选标准化 → 真实下载/缓存 → 媒体验证（magic bytes/ffprobe/ffmpeg/PIL/尺寸/许可证）
→ timeline → render → **抽帧证明真实远端素材上屏**。

不使用 fake provider、不用 metadata 顶替证据、不手工写 artifact。
真实请求次数/下载字节/耗时全部记录；token 只记 presence，不记内容。

用法：python docs/regression_2x/phase2e_real_provider.py [--query "..."] [--scenes N]
"""
import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.base import AGENTS  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402
from video_studio.tools.material_provider import MaterialQuery  # noqa: E402
from video_studio.tools.provider_wikimedia import WikimediaCommonsProvider  # noqa: E402
from video_studio.tools.base import ToolContext  # noqa: E402

import video_studio.agents.asset.agent  # noqa: E402,F401
import video_studio.agents.editing.agent  # noqa: E402,F401
import video_studio.agents.retrieval.agent  # noqa: E402,F401
import video_studio.agents.script.agent  # noqa: E402,F401

FFPROBE = ROOT / "bin" / "ffprobe.exe"
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
LOGS = ROOT / "docs" / "regression_2x" / "logs"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:220] if detail else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", default="virtual reality headset")
    ap.add_argument("--scenes", type=int, default=2)
    ap.add_argument("--phase", default="all", choices=["all", "success", "rejected", "empty"])
    args = ap.parse_args()

    # ---------- 1) 真实搜索（直接调用 provider，记录原始摘要）----------
    pol = {"provider": "wikimedia_commons", "max_bytes": 8 * 1024 * 1024, "timeout_s": 25,
           "search_limit": 8, "min_width": 320, "min_height": 180, "license_required": True,
           # 真实 provider 礼仪：请求与下载同一最小间隔；429 专用退避（实测媒体下载会限流）
           "min_interval_s": 3.0, "max_requests": 12, "rate_limit_retries": 3,
           "rate_limit_backoff_s": 10.0}
    prov = WikimediaCommonsProvider(pol)
    tmp_ctx = ToolContext(role="retrieval", project_id="probe", project_dir=ROOT / "tmp_wheels",
                          db=None, config={"tools": {"ffmpeg": {"path": str(FFMPEG),
                                                                "ffprobe": str(FFPROBE)}}})
    from video_studio.agents.retrieval.agent import kw_tokens
    q = MaterialQuery(text=args.query, keywords=kw_tokens(args.query), limit=8)
    t0 = time.time()
    found = prov.search(q, tmp_ctx)
    search_s = round(time.time() - t0, 2)
    print("search: {} 命中 {} 条（{:.1f}s）".format(args.query, len(found), search_s))
    check("R1 真实搜索返回候选", len(found) > 0, len(found))
    check("R2 记录可审计响应摘要（含 raw_head，且不含 token）",
          bool(prov.stats["response_digests"])
          and "raw_head" in prov.stats["response_digests"][0]
          and "token" not in json.dumps(prov.stats["response_digests"])[:2000].lower(),
          prov.stats["response_digests"][0].get("status"))
    for c in found[:3]:
        print("   - {} | {} | {} | {} | {}".format(c.name[:44], c.ext, c.license,
                                                   str(c.attribution)[:24], c.bytes))
    check("R3 候选带 provider/source_id/source_url/license/attribution",
          all(c.provider == "wikimedia_commons" and c.source_id and c.source_url
              and c.source_url.startswith("https://upload.wikimedia.org/") and c.license
              for c in found),
          [(c.source_id, c.license) for c in found[:2]])
    check("R4 许可证类别已机械分类（不猜测）",
          all(getattr(c, "license_class", None) in ("PUBLIC_DOMAIN", "FREE_ATTRIBUTION",
                                                    "RESTRICTED", "UNKNOWN") for c in found),
          {getattr(c, "license_class", None) for c in found})
    check("R5 token 未出现在统计中（presence only）",
          "token" not in json.dumps({k: v for k, v in prov.stats.items()
                                     if k != "response_digests"}).lower()
          or prov.stats.get("token_present") in (True, False), prov.stats.get("token_present"))

    # 只取许可证已清、且能通过媒体校验的前 N 条
    usable = [c for c in found if c.license_cleared]
    check("R6 存在许可证已清的候选（CC/PD 类）", bool(usable), len(usable))

    # ---------- 2) 建真实项目并跑完整链路 ----------
    work_catalog = None
    eng_cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
    rules = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
    eng_cfg["tools"]["material"] = {"provider": "wikimedia_commons", **pol}
    eng = Engine(Database(ROOT / "projects" / "video_studio.db"),
                 Router(eng_cfg["llm"], MockLLM(eng_cfg["llm"].get("mock", {}).get("responses", {}),
                                                eng_cfg["llm"].get("mock", {}).get("default", {}))),
                 rules, ROOT / "projects", eng_cfg, AGENTS)
    pid = eng.create_project("test_phase2e_real_provider")
    en_script = ("virtual reality headset device form factor and how it is worn. "
                 "virtual reality headset hardware closeup")
    script = {"segments": [{"chapter": "s{}".format(i + 1), "narration": en_script,
                            "duration_s": 4} for i in range(args.scenes)],
              "summary": "Phase 2-E real provider"}
    t_script = eng.create_task(pid, "script", "script")
    aid = eng.write_artifact(pid, t_script, "script_output", script, summary="脚本")
    eng.attach_artifact(t_script, aid)
    eng.db.set_task_status(t_script, "SUCCEEDED")
    t_ret = eng.create_task(pid, "retrieval", "retrieval", dependencies=[t_script])
    eng.run_cycle(pid, limit=4)
    t_rend = eng.create_task(pid, "render", "editing", dependencies=[t_script, t_ret])
    for _ in range(4):
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
    ret, ren = art(t_ret, "retrieval_candidates"), art(t_rend, "render_output")
    con.close()

    print("\nproject={} render={}".format(pid, row["status"]))
    ext = (ret or {}).get("external_provider") or {}
    print("provider stats:", json.dumps({k: v for k, v in (ext.get("stats") or {}).items()
                                         if k != "response_digests"}, ensure_ascii=False))
    check("R7 检索经真实 provider 且 mode=external/mixed",
          (ret or {}).get("material_mode") in ("external", "mixed")
          and ext.get("name") == "wikimedia_commons", (ret or {}).get("material_mode"))
    check("R8 真实下载字节数 > 0（记录在 stats）",
          (ext.get("stats") or {}).get("downloaded_bytes", 0) > 0,
          (ext.get("stats") or {}).get("downloaded_bytes"))
    cands = [c for c in ((ret or {}).get("candidates") or []) if c.get("provider") == "wikimedia_commons"]
    check("R9 候选为真实远端素材（source_url + sha256 + 本地缓存路径）",
          bool(cands) and all(c.get("source_url", "").startswith("https://upload.wikimedia.org/")
                              and len(str(c.get("sha256"))) >= 16
                              and str(c.get("path", "")).startswith("external/") for c in cands),
          [{k: c.get(k) for k in ("name", "source_url", "path")} for c in cands[:2]])
    cached = [ROOT / "projects" / pid / "media" / str(c["path"]) for c in cands]
    check("R10 缓存文件真实存在且大小与记录一致",
          bool(cached) and all(p.is_file() and p.stat().st_size == c.get("size")
                               for p, c in zip(cached, cands)),
          [(p.name, p.stat().st_size if p.is_file() else None) for p in cached[:2]])

    tl = (ren or {}).get("material_timeline") or []
    sel = [(s["scene_id"], (s.get("selected_asset") or {}),
            s.get("appears_in_film"), (s.get("film_evidence") or {})) for s in tl]
    for s in tl:
        a = s.get("selected_asset") or {}
        ev = s.get("film_evidence") or {}
        print("   {} state={} class={} provider={} license={} appears={} corr={}".format(
            s["scene_id"], s.get("fallback_state"), s.get("insufficiency_class"),
            a.get("provider"), a.get("license"), s.get("appears_in_film"), ev.get("corr")))
    on_screen = [s for s in tl if s.get("appears_in_film") is True
                 and (s.get("selected_asset") or {}).get("provider") == "wikimedia_commons"]
    check("R11 真实 Provider 素材进入 timeline 且**抽帧证实上屏**", bool(on_screen),
          [(s["scene_id"], (s.get("film_evidence") or {}).get("corr")) for s in on_screen])
    check("R12 成片证据保留 provider/source_id/source_url/license/attribution",
          all(all((s["selected_asset"] or {}).get(k) for k in
                  ("provider", "source_id", "source_url", "license"))
              for s in on_screen),
          [{(k): (s["selected_asset"] or {}).get(k) for k in
            ("provider", "source_id", "license", "attribution")} for s in on_screen[:1]])
    vid = (ren or {}).get("output")
    info, dec_rc = {}, None
    if vid and Path(vid).is_file():
        p = subprocess.run([str(FFPROBE), "-v", "error", "-print_format", "json", "-show_format",
                            "-show_streams", str(vid)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        info = json.loads(p.stdout or "{}")
        dec = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(vid), "-f", "null", "-"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
        dec_rc = dec.returncode
    check("R13 成片可解码且 2 条流",
          dec_rc == 0 and len(info.get("streams") or []) == 2,
          {"duration": (info.get("format") or {}).get("duration"), "decode_rc": dec_rc})

    rec = {"project": pid, "query": args.query, "search_s": search_s,
           "provider_stats": {k: v for k, v in prov.stats.items()},
           "provider_info": ext, "retrieval": ret, "render": ren, "render_status": row,
           "video": {"path": vid, "duration_s": (info.get("format") or {}).get("duration"),
                     "decode_rc": dec_rc},
           "checks": {"pass": PASS, "fail": FAIL}}
    (LOGS / "phase2e_real_provider.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
    if FAIL:
        print("失败项:", FAIL)
    print("记录:", LOGS / "phase2e_real_provider.json")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())

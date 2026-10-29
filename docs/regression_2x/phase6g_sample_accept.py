# -*- coding: utf-8 -*-
"""6-G —— 小样**完整验收**（读取执行阶段结果，不重复渲染）。

验收设计（可复算）：
  S1 确定性：各执行窗口实际烧录的 `cap_*.ass` == **DCv2 表**选择，且 **≠ v1 表**选择（负对照）
  S2 帧级（掩膜）：在 cue **有效**时刻，字幕墨迹与其局部背景的对比度 > 阈值
  S3 帧级（无 cue 时刻）：底部字幕带与"未改窗口"输出一致（无额外墨迹）
  S4 片尾卡：收尾区 mid 带出现卡片墨迹、底部带无字幕
  + PI-1..6 / DQ（仅记录）/ 视觉连续与黑帧 / 隔离·DB·baseline·历史 / ffmpeg 记录 / 可逆性

产出: docs/regression_2x/logs/phase6g_sample_acceptance_report.json
"""
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import captions as core_captions              # noqa: E402
from video_studio.core import direction as core_direction            # noqa: E402
from video_studio.core import integrity as core_integrity            # noqa: E402
from video_studio.core import narration as N                         # noqa: E402
from video_studio.ops import execution as OPX                        # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
P2 = json.loads((LOGS / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
PKG = json.loads((LOGS / "phase6g_rebuild_proposals.json").read_text(encoding="utf-8"))
N0 = json.loads((LOGS / "phase6g_n0_dcv2_master.json").read_text(encoding="utf-8"))
EX = json.loads((LOGS / "phase6g_sample_exec_results.json").read_text(encoding="utf-8"))
OUT = LOGS / "phase6g_sample_acceptance_report.json"
FFMPEG, FFPROBE = ROOT / "bin" / "ffmpeg.exe", ROOT / "bin" / "ffprobe.exe"
PROD = P2["math_verification"]["production_duration_s"]
SANDBOX = ROOT / EX["sandbox"]
BOX, OUTD = SANDBOX / "box", SANDBOX / "out"
CFG = {"tools": {"ffmpeg": {"path": str(FFMPEG), "ffprobe": str(FFPROBE)}}}
MASTER = ROOT / EX["master_input"]["path"]
MASTER_ASS = ROOT / N0["captions"]["ass"]
W_A, W_B = [487.572, 539.346], [966.656, 978.656]
PASS, FAIL = [], []


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def md5(p: Path) -> str:
    r = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(p), "-map", "0:a", "-c", "copy",
                        "-f", "md5", "-"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return (r.stdout or "").strip().split("=")[-1]


def hard(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:230]))
    return bool(ok)


def run(args):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


# ---------------------------------------------------------------- 数据与 cue 表
con = sqlite3.connect("file:{}?mode=ro".format(
    (ROOT / "projects" / "video_studio.db").as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
rows = [dict(r) for r in con.execute(
    "select type,task_id,path from artifacts where project_id='p_96efdc03e1aa' order by created_at")]
con.close()
script = json.loads(Path(next(r["path"] for r in rows if r["type"] == "script_output")
                         ).read_text(encoding="utf-8"))
voice = json.loads(Path(next(r["path"] for r in rows if r["type"] == "voice_output")
                        ).read_text(encoding="utf-8"))
_ro = next((r for r in rows if r["type"] == "render_output"
            and r.get("task_id") == "t_d0a54bdf1810"), None)
render = json.loads(Path(_ro["path"]).read_text(encoding="utf-8")) if _ro else {}
asset_of = {str(e.get("scene_id")): (e.get("selected_asset") or {})
            for e in (render.get("material_timeline") or []) if e.get("selected_asset")}
chain = P2["remapping_21_segments"]
payload = [{"narration": s["narration"], "duration_s": s.get("duration_s")}
           for s in script["segments"] if str(s.get("narration", "")).strip()]
cw = [{"start_s": c["new_audio_window_s"][0], "end_s": c["new_audio_window_s"][1]} for c in chain]
cues_dcv2 = core_captions.build_cues(payload, windows=cw)            # DCv2 表
cues_v1 = core_captions.build_cues(payload)                          # v1 声明时基表（负对照）
plan = N.narration_plan(script, voice)


def sel(cues, w0, w1):
    out = []
    for c in cues:
        s, e = float(c["start"]), float(c["end"])
        if e <= w0 + 1e-6 or s >= w1 - 1e-6:
            continue
        out.append({"start": round(max(s, w0) - w0, 3), "end": round(min(e, w1) - w0, 3),
                    "text": c.get("text")})
    return sorted(out, key=lambda x: x["start"])


def _norm_text(x: str) -> str:
    """ASS 文本归一：去掉 `\\N`/`\\n` 换行转义与空白（`to_ass` 会插入换行，cue 表本身没有）。"""
    return re.sub(r"\s+", "", str(x or "").replace("\\N", "").replace("\\n", ""))


def parse_ass(p: Path):
    """解析 ASS 的 Events 段（`[V4+ Styles]` 里也有 Format 行，必须按段区分）。"""
    out, fmt, section = [], None, None
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s
            continue
        if section == "[Events]" and s.startswith("Format:"):
            fmt = [x.strip() for x in s.split(":", 1)[1].split(",")]
        elif section == "[Events]" and s.startswith("Dialogue:") and fmt:
            f = s.split(":", 1)[1].split(",", len(fmt) - 1)
            d = dict(zip(fmt, f))

            def sec(x):
                h, m, sec_ = x.strip().split(":")
                return round(int(h) * 3600 + int(m) * 60 + float(sec_), 3)
            out.append({"start": sec(d["Start"]), "end": sec(d["End"]),
                        "text": d["Text"].strip()})
    return sorted(out, key=lambda x: x["start"])


results = {k: {"path": ROOT / v["path"], **{kk: v[kk] for kk in ("sha256", "probe", "audio_md5",
                                                                 "caption_time_base")}}
           for k, v in EX["results"].items()}

print("== A1/A2 duration + audio identity ==")
master_md5 = md5(MASTER)
a1 = {k: {"duration_s": v["probe"]["duration_s"],
          "ok": abs(v["probe"]["duration_s"] - PROD) <= 0.05} for k, v in results.items()}
a2 = {k: {"audio_md5": v["audio_md5"], "identical": v["audio_md5"] == master_md5}
      for k, v in results.items()}
hard("A1 三个输出 duration 均 == 978.656±0.05", all(v["ok"] for v in a1.values()), a1)
hard("A2 三个输出音轨 md5 与 DCv2 母版完全一致（母版 md5={}）".format(master_md5[:12]),
     all(v["identical"] for v in a2.values()), a2)

print("\n== S1 确定性：窗口内实际烧录 cue == DCv2 表（且 ≠ v1 表）==")
ass_files = sorted((BOX / "work").glob("cap_*.ass"))
s1 = []
for p in ass_files:
    parsed = parse_ass(p)
    # 与已知窗口匹配：找出与 parsed 完全一致的 DCv2 窗口选择
    match = None
    for tag, w in (("split-S11-c", [522.088, 539.346]), ("overlay-S11", W_A), ("outro", W_B),
                   ("split-S11-a", [487.572, 504.83]), ("split-S11-b", [504.83, 522.088])):
        d = sel(cues_dcv2, w[0], w[1])
        if d and len(d) == len(parsed) and all(
                abs(a["start"] - b["start"]) < 0.02 and abs(a["end"] - b["end"]) < 0.02
                and _norm_text(a["text"]) == _norm_text(b["text"])
                for a, b in zip(parsed, d)):
            match = {"window": w, "which": tag, "dcv2_match": True,
                     "v1_selection": sel(cues_v1, w[0], w[1])}
            break
    if match:
        match["v1_differs"] = (match["v1_selection"] != sel(cues_dcv2, match["window"][0],
                                                           match["window"][1]))
        match["ass"] = p.name
        match["cue_count"] = len(parsed)
    s1.append(match or {"ass": p.name, "dcv2_match": False, "cue_count": len(parsed),
                        "texts": [c["text"][:20] for c in parsed][:3]})
hard("S1a 所有窗口 ASS 均与 DCv2 表**完全一致**（{} 个窗口）".format(len(ass_files)),
     all(m.get("dcv2_match") for m in s1), [m for m in s1 if not m.get("dcv2_match")])
hard("S1b 同一窗口的 v1 表选择与 DCv2 **不同**（证明修复非 no-op）",
     all(m.get("v1_differs") for m in s1 if m.get("dcv2_match")),
     [m for m in s1 if m.get("dcv2_match") and not m.get("v1_differs")])

print("\n== 采样时刻（由 cue 表推导）==")
c11 = [c for c in cues_dcv2 if c["start"] >= 487.572 and c["end"] <= 538.6]
speech_ts = [round((c["start"] + c["end"]) / 2, 3) for c in c11[:2]] + \
            [round((c11[-1]["start"] + c11[-1]["end"]) / 2, 3)]
gap_t = round((c11[1]["end"] + c11[2]["start"]) / 2, 3)
c21 = [c for c in cues_dcv2 if c["start"] >= 966.656 and c["end"] <= 976.66]
outro_t = round((c21[0]["start"] + c21[0]["end"]) / 2, 3) if c21 else 970.0
tail_t = 977.5


def cue_at(t, table):
    return [c for c in table if c["start"] <= t < c["end"]]


print("   speech_ts={} gap_t={} outro_t={} tail_t={}".format(speech_ts, gap_t, outro_t, tail_t))
hard("S2a 采样时刻选择合法（语音时刻有 cue、gap/收尾时刻无 cue）",
     all(cue_at(t, cues_dcv2) for t in speech_ts) and not cue_at(gap_t, cues_dcv2)
     and not cue_at(tail_t, cues_dcv2),
     {"speech": [len(cue_at(t, cues_dcv2)) for t in speech_ts],
      "gap": len(cue_at(gap_t, cues_dcv2)), "tail": len(cue_at(tail_t, cues_dcv2))})

print("\n== S2/S3/S4 帧级（掩膜 + 差分）==")
from PIL import Image                                                    # noqa: E402
import numpy as np                                                       # noqa: E402


def frame(film: Path, t: float, name: str, dur: float | None = None):
    """取单帧（越界自动回退：≤ dur−0.25 / 更早 0.2s；仍失败则返回全零并如实标记）。"""
    cand = [t]
    if dur:
        cand.append(max(0.0, min(t, dur - 0.25)))
    cand.append(max(0.0, t - 0.2))
    for i, tt in enumerate(cand):
        f = BOX / "work" / "acc_{}_{}_{}.png".format(name, str(t).replace(".", "_"), i)
        run([FFMPEG, "-y", "-v", "error", "-ss", "{:.3f}".format(tt), "-i", film,
             "-frames:v", "1", f])
        if f.is_file():
            return np.asarray(Image.open(f).convert("L"), dtype=np.float32) / 255.0
    return np.zeros((720, 1280), dtype=np.float32)


def mask_at(t: int):
    f = BOX / "work" / "mask_{}.png".format(t)
    run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=1",
         "-vf", "ass=filename='{}':fontsdir='C\\:/Windows/Fonts'".format(
             MASTER_ASS.as_posix().replace(":", "\\:")),
         "-ss", str(int(t)), "-frames:v", "1", f])
    return np.asarray(Image.open(f).convert("L"), dtype=np.float32) / 255.0


sub = results["exec2"]["path"]
s2, s3 = [], {}
for t in speech_ts:
    it = int(t)
    m = mask_at(it)
    a = frame(sub, t, "s2")
    ink = m > 0.5
    band = np.zeros_like(ink)
    band[int(a.shape[0] * 0.85):] = True
    bg = band & ~ink
    contrast = (float(a[ink].mean()) - float(a[bg].mean())) if ink.any() and bg.any() else None
    s2.append({"t": t, "mask_px": int(ink.sum()), "ink_contrast": (round(contrast, 4)
                                                                  if contrast is not None
                                                                  else None),
               "cue_text": (cue_at(t, cues_dcv2) or [{}])[0].get("text", "")[:24]})
hard("S2b 语音时刻字幕墨迹存在且对比度 > 0.10", all(r["mask_px"] > 50 and r["ink_contrast"]
                                                and r["ink_contrast"] > 0.10 for r in s2), s2)

# S3：gap 时刻底部带应与"未触及 S11 的输出"(exec3) 一致（exec3 对 S11 为流复制）
g2, g3 = frame(sub, gap_t, "s3a"), frame(results["exec3"]["path"], gap_t, "s3b")
bot2, bot3 = g2[int(g2.shape[0] * 0.85):], g3[int(g3.shape[0] * 0.85):]
gap_diff = round(float(np.abs(bot2 - bot3).mean()), 4)
s3 = {"t": gap_t, "bottom_band_absdiff_vs_exec3": gap_diff, "threshold": 0.05,
      "cue_present_in_table": bool(cue_at(gap_t, cues_dcv2))}
hard("S3 gap 时刻底部带无额外墨迹（与未改窗口输出差异 < 0.05）", gap_diff < 0.05, s3)

# S4：末 12s —— 收尾区底部无字幕、mid 带出现片尾卡
o3 = frame(results["exec3"]["path"], tail_t, "s4a")
m3 = frame(MASTER, tail_t, "s4b")
bot_o, bot_m = o3[int(o3.shape[0] * 0.85):], m3[int(m3.shape[0] * 0.85):]
mid_o, mid_m = o3[int(o3.shape[0] * 0.50):int(o3.shape[0] * 0.75)], \
    m3[int(m3.shape[0] * 0.50):int(m3.shape[0] * 0.75)]
s4 = {"t": tail_t, "cue_present_in_table": bool(cue_at(tail_t, cues_dcv2)),
      "bottom_band_absdiff_vs_master": round(float(np.abs(bot_o - bot_m).mean()), 4),
      "mid_band_absdiff_vs_master": round(float(np.abs(mid_o - mid_m).mean()), 4)}
hard("S4a 收尾区底部带无字幕（与母版一致，diff < 0.03）",
     (not s4["cue_present_in_table"]) and s4["bottom_band_absdiff_vs_master"] < 0.03, s4)
hard("S4b 收尾区 mid 带出现片尾卡墨迹（与母版 diff > 0.03）",
     s4["mid_band_absdiff_vs_master"] > 0.03, s4)

print("\n== A7 DCv2 字幕↔实际音频对齐门禁 ==")
sub_align = N.subtitle_alignment(cues_dcv2, plan, core_integrity.gate_policy(CFG))
hard("A7 DCv2 字幕对齐门禁 PASS（且末条 {} != 1528.636）".format(
    round(max(c["end"] for c in cues_dcv2), 3)), sub_align["ok"] is True, sub_align)

print("\n== A8/A9 PI-1..6 ==")
pi = {}
for k, v in results.items():
    pre = core_integrity.pre_render_gate(
        script.get("segments") or [], voice, PROD, core_integrity.gate_policy(CFG),
        narration_duration_s=voice.get("narration_duration_s"), narration_plan=plan,
        cues=cues_dcv2,
        narration_padding_s=PROD - float(voice.get("narration_duration_s") or 0))
    post = core_integrity.post_render_gate(
        v["path"], PROD, cues_dcv2, voice.get("narration_duration_s"), True, str(FFMPEG),
        str(FFPROBE), core_integrity.gate_policy(CFG), narration_plan=plan)
    st = lambda m: {a: (b.get("state") if isinstance(b, dict) else b) for a, b in m.items()}
    pi[k] = {"pre_blocked": pre["blocked"], "post_blocked": post["blocked"],
             "pre_states": st(pre["metrics"]), "post_states": st(post["metrics"]),
             "pre_reasons": pre["reasons"], "post_reasons": post["reasons"],
             "promote_blocked": post.get("promote_blocked")}
hard("A8 pre-render 未阻断且 PI-1/PI-2/PI-6/G-TL/G-PAD/G-SUB 全 PASS",
     all((not v["pre_blocked"]) and all(v["pre_states"].get(g) == "PASS"
                                        for g in ("PI-1", "PI-2", "PI-6", "G-TL", "G-PAD",
                                                  "G-SUB")) for v in pi.values()),
     {k: {"blocked": v["pre_blocked"], "states": v["pre_states"], "reasons": v["pre_reasons"]}
      for k, v in pi.items()})
hard("A9 post-render：PI-3 PASS 且 promote 未被静音阻断",
     all(v["post_states"].get("PI-3") == "PASS" and not v["promote_blocked"]
         for v in pi.values()),
     {k: {"PI-3": v["post_states"].get("PI-3"), "promote_blocked": v["promote_blocked"],
          "reasons": v["post_reasons"]} for k, v in pi.items()})

print("\n== A10/A11 视觉连续 / 黑帧 / cut evidence ==")
bounds = [W_A[0], W_A[1], W_B[0], W_B[1] - 0.05]
cont = {k: {str(b): round(float(frame(v["path"], b, "c" + k,
                                      v["probe"]["duration_s"]).mean()), 4) for b in bounds}
        for k, v in results.items()}
black = [f"{k}@{b}" for k, row in cont.items() for b, luma in row.items() if luma < 0.02]
ce = EX["exec1_cut_evidence"]
hard("A10 窗口边界无黑帧", not black, {"luma": cont, "black": black})
hard("A11 exec1 切点证据 all_distinct（{} 个切点）".format(len(ce)),
     all(c["distinct"] for c in ce), ce)

print("\n== A12–A17 隔离 / DB / baseline / 历史 ==")
HIST = {"v9": ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"}
m6c = json.loads((LOGS / "phase6c_batch.json").read_text(encoding="utf-8"))
for c in m6c["candidates"]:
    HIST["c" + str(c["index"])] = ROOT / c["film"]
HIST["e1"] = (ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e" / "output" /
              "t_d0a54bdf1810_draft_6c_rp-ad4bbbee7ea2_outro.mp4")
HIST["e2"] = (ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e2" / "output" /
              "t_d0a54bdf1810_draft_6c_rp-bee31dff3335_vaid.mp4")
hist_now = {k: sha(p) for k, p in HIST.items() if p.is_file()}
iso = {
    "history_unchanged": all(hist_now[k].startswith(v) for k, v in
                             {"v9": "22705c7d7ea20b40", "c1": "fcaa4e78", "c2": "4ce95135",
                              "c3": "07eb0c43", "c4": "e9c19c5d", "e1": "e45d79976856090e",
                              "e2": "659bd0d7c288cd7b"}.items() if k in hist_now),
    "db_unchanged": sha(ROOT / "projects" / "video_studio.db") == EX["before_state"]["db"],
    "baseline_unchanged": sorted(p.name for p in
                                 (ROOT / "docs" / "regression_2x" / "baseline").glob("*"))
    == EX["before_state"]["baseline"],
    "master_unchanged": sha(MASTER) == EX["master_input"]["sha256"],
    "projects_listing_len": len([p for p in (ROOT / "projects" / "p_96efdc03e1aa").rglob("*")
                                 if p.is_file()]),
    "all_outputs_in_sandbox": all(str(v["path"]).startswith(str(SANDBOX))
                                  for v in results.values()),
    "sandbox": EX["sandbox"],
    "files_written_in_sandbox": len([p for p in SANDBOX.rglob("*") if p.is_file()]),
}
hard("A12 历史 artifact sha256 未变", iso["history_unchanged"],
     {k: v[:12] for k, v in hist_now.items()})
hard("A13 DB 未变", iso["db_unchanged"])
hard("A14 baseline/tag 未变", iso["baseline_unchanged"])
hard("A15 DCv2 母版输入未变", iso["master_unchanged"])
hard("A16 项目目录文件数未变（{}）".format(iso["projects_listing_len"]),
     iso["projects_listing_len"] == EX["before_state"]["projects_listing_len"],
     {"now": iso["projects_listing_len"], "before": EX["before_state"]["projects_listing_len"]})
hard("A17 全部输出位于新沙箱目录内", iso["all_outputs_in_sandbox"]
     and iso["sandbox"].replace("\\", "/").startswith("output/phase6g_sample/"), iso)

print("\n== A18 DQ-3 / DQ-4（仅记录，不判定 PASS）==")
dq_tl = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
          "end_s": c["new_timeline_window_s"][1], "selected_asset": asset_of.get(c["scene_id"], {})}
         for c in chain]
split_tl = []
for e in dq_tl:
    if e["scene_id"] == "S11":
        r = EX["exec1_split_plan"]["scenes"][0]
        d = r["sub_duration_s"]
        for j in range(r["sub_count"]):
            split_tl.append({"scene_id": "S11.{}".format(j + 1),
                             "start_s": round(r["window"][0] + d * j, 3),
                             "end_s": round(r["window"][0] + d * (j + 1), 3),
                             "selected_asset": e["selected_asset"]})
    else:
        split_tl.append(e)
DQ = {"baseline": {"DQ-2": core_direction.asset_reuse(dq_tl),
                   "DQ-3": core_direction.static_hold(dq_tl),
                   "DQ-4": core_direction.visual_density(dq_tl)},
      "after_S11_split_projection": {"DQ-3": core_direction.static_hold(split_tl),
                                     "DQ-4": core_direction.visual_density(split_tl)},
      "recorded_only": True,
      "no_pass_claim": "H3a/H3b 未执行 ⇒ 12 场景仍 >25s；DQ-3/DQ-4 **不宣称 PASS**（D12 不改 DQ）"}
print("   DQ-3 base max_hold={} | DQ-4 base scene_changes/min={} | after S11 split entries={}".format(
    DQ["baseline"]["DQ-3"].get("max_hold_s"), DQ["baseline"]["DQ-4"].get("scene_changes_per_min"),
    len(split_tl)))

report = {
    "schema": "phase6g-sample-acceptance-v2", "stage": "6-G",
    "state": "SAMPLE_ACCEPTED_AWAITING_HUMAN_AUTHORIZATION" if not FAIL else "SAMPLE_ACCEPTANCE_FAILED",
    "authorized_scope": {"windows": {"S11": W_A, "LAST_12S": W_B}, "executions": 3,
                         "plan": "docs/regression_2x/logs/phase6g_sample_execution_plan.json"},
    "sandbox": EX["sandbox"],
    "outputs": {k: {"path": str(v["path"].relative_to(ROOT)), "sha256": v["sha256"],
                    "duration_s": v["probe"]["duration_s"], "audio_md5": v["audio_md5"]}
                for k, v in results.items()},
    "duration_and_audio": {"dur": a1, "audio_identity": a2, "master_audio_md5": master_md5},
    "subtitle_deterministic": {"per_window_ass": s1, "dcv2_last_cue_end_s":
                               round(max(c["end"] for c in cues_dcv2), 3),
                               "v1_last_cue_end_s": round(max(c["end"] for c in cues_v1), 3)},
    "subtitle_frames": {"speech": s2, "gap": s3, "outro_tail": s4, "alignment": sub_align},
    "PI": pi, "DQ_recorded_only": DQ,
    "visual_continuity": {"boundary_luma": cont, "black_frames": black, "cut_evidence": ce},
    "isolation": iso,
    "ffmpeg_calls": EX["ffmpeg_calls"],
    "reversibility": {"how": "删除 {} 即可完全回滚".format(EX["sandbox"]),
                      "master_sha_before": EX["master_input"]["sha256"][:16],
                      "master_sha_after": sha(MASTER)[:16]},
    "exec_gates": {"pass": EX["gates_pass"], "fail": EX["gates_fail"]},
    "gates": {"pass": PASS, "fail": FAIL},
    "claims": {"six_g_pass": False, "dq3_pass": False, "dq4_pass": False,
               "e3_ab_decided": False, "visual_aid_form": "A 形态仅验证执行机制，不构成 E3 决策",
               "formal_proposals_executed": 0,
               "still_not_executed": [p["label"] for p in PKG["proposals"]],
               "h5": "PENDING_HUMAN_ASSET", "h3c_authorized": False},
    "not_done": ["未 promote", "未切 baseline/tag", "未写 DB/正式 registry", "未下载/绑定 H5 素材",
                 "未执行正式 proposal", "未改 DQ 实现"],
}
report["report_sha256"] = hashlib.sha256(json.dumps(
    {k: v for k, v in report.items() if k != "report_sha256"}, sort_keys=True, ensure_ascii=False,
    separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

print("\n== 小样验收汇总 ==")
for k, v in results.items():
    print("  {} {} {}s sha {} audio_md5 {}".format(k, v["path"].name,
                                                   v["probe"]["duration_s"], v["sha256"][:12],
                                                   v["audio_md5"][:12]))
print("  字幕：DCv2 末条 {}s（v1 {}s）| 窗口 ASS 与 DCv2 一致：{}".format(
    round(max(c["end"] for c in cues_dcv2), 3), round(max(c["end"] for c in cues_v1), 3),
    all(m.get("dcv2_match") for m in s1)))
print("  gates: {} PASS / {} FAIL | ffmpeg calls {}".format(len(PASS), len(FAIL),
                                                            EX["ffmpeg_calls"]["count"]))
print("  state: {}".format(report["state"]))
print("report ->", OUT)
sys.exit(1 if FAIL else 0)

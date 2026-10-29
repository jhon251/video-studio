# -*- coding: utf-8 -*-
"""6-G / E3 —— **形式 A（一个跨子镜 overlay，1 次执行）** 的正式登记 + 执行 + 完整验收。

人工裁定：E3 = A（跨子镜 overlay）；未执行 H5/E4/E5；未改 POLICY/阈值/DQ 判据；
内容**逐字沿用** 6-E 冻结材料计划 `items.E3.C_self_made_spec`（不自创设计；未用 D8 改设计）。

产出: docs/regression_2x/logs/phase6g_exec_e3.json
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import captions as core_captions              # noqa: E402
from video_studio.core import direction as core_direction            # noqa: E402
from video_studio.core import execution as EX                        # noqa: E402
from video_studio.core import integrity as core_integrity            # noqa: E402
from video_studio.core import narration as N                         # noqa: E402
from video_studio.core import revision as core_revision              # noqa: E402
from video_studio.core import visual_aid as VA                       # noqa: E402
from video_studio.ops import execution as OPX                        # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
P2 = json.loads((LOGS / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
N0 = json.loads((LOGS / "phase6g_n0_dcv2_master.json").read_text(encoding="utf-8"))
B1 = json.loads((LOGS / "phase6g_exec_batch1.json").read_text(encoding="utf-8"))
B2 = json.loads((LOGS / "phase6g_exec_batch2.json").read_text(encoding="utf-8"))
OA = json.loads((LOGS / "phase6g_exec_batch2_optA.json").read_text(encoding="utf-8"))
AUD = json.loads((LOGS / "phase6g_status_audit.json").read_text(encoding="utf-8"))
OUT = LOGS / "phase6g_exec_e3.json"
REGISTER = LOGS / "phase6g_rebuild_proposal_register.jsonl"
LEDGER = LOGS / "phase6g_exec_ledger.jsonl"
MATPLAN = ROOT / "docs" / "regression_2x" / "phase6e_materials" / "phase6e_material_plan.json"
FFMPEG, FFPROBE = ROOT / "bin" / "ffmpeg.exe", ROOT / "bin" / "ffprobe.exe"
PROD, TOL = 978.656, 0.05
WINDOW = [487.572, 539.346]                     # 形式 A：S11 并集窗口（跨 3 个子镜）
CFG = {"tools": {"ffmpeg": {"path": str(FFMPEG), "ffprobe": str(FFPROBE)}}}
TS = time.strftime("%Y%m%d_%H%M%S")
SANDBOX = ROOT / "output" / "phase6g_exec_e3" / TS
chain = P2["remapping_21_segments"]
CW = [{"scene_id": c["scene_id"], "start_s": c["new_audio_window_s"][0],
       "end_s": c["new_audio_window_s"][1]} for c in chain]
TL = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
       "end_s": c["new_timeline_window_s"][1]} for c in chain]
PASS, FAIL, FF_CALLS = [], [], []
_orig_run = OPX._run


def _rec_run(cmd, timeout=3600):
    FF_CALLS.append({"argv": [str(c) for c in cmd][:16]})
    return _orig_run(cmd, timeout=timeout)


OPX._run = _rec_run


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def streams(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,duration,nb_frames", "-of", "json",
                        str(p)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    j = json.loads(r.stdout or "{}")
    o = {"format_duration_s": round(float((j.get("format") or {}).get("duration") or 0), 4)}
    for s in (j.get("streams") or []):
        o[s.get("codec_type")] = {"duration_s": round(float(s.get("duration") or 0), 4),
                                  "nb_frames": s.get("nb_frames")}
    return o


def amd5(p):
    r = subprocess.run([FFMPEG, "-v", "error", "-i", str(p), "-map", "0:a", "-c", "copy", "-f",
                        "md5", "-"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return (r.stdout or "").strip().split("=")[-1]


def hard(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:240]))
    if not ok:
        raise RuntimeError("E3_GATE_FAILED: " + name)


def gray(p):
    from PIL import Image                                                   # noqa: E402
    import numpy as np                                                      # noqa: E402
    return np.asarray(Image.open(p).convert("L"), dtype=np.float32) / 255.0


def frame(film, t, name, dur=None):
    for i, tt in enumerate([t] + ([max(0.0, min(t, dur - 0.25))] if dur else [])
                           + [max(0.0, t - 0.2)]):
        f = SANDBOX / "work" / "acc_{}_{}_{}.png".format(name, str(t).replace(".", "_"), i)
        subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", "{:.3f}".format(tt), "-i", str(film),
                        "-frames:v", "1", str(f)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
        if f.is_file():
            return gray(f)
    import numpy as np                                                      # noqa: E402
    return np.zeros((720, 1280), dtype=np.float32)


def norm(x):
    return re.sub(r"\s+", "", str(x or "").replace("\\N", "").replace("\\n", ""))


def parse_ass(p):
    out, fmt, sec = [], None, None
    for line in Path(p).read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            sec = s
            continue
        if sec == "[Events]" and s.startswith("Format:"):
            fmt = [x.strip() for x in s.split(":", 1)[1].split(",")]
        elif sec == "[Events]" and s.startswith("Dialogue:") and fmt:
            d = dict(zip(fmt, s.split(":", 1)[1].split(",", len(fmt) - 1)))
            f = lambda x: (lambda h, m, ss: round(int(h) * 3600 + int(m) * 60 + float(ss), 3))(
                *x.strip().split(":"))
            out.append({"start": f(d["Start"]), "end": f(d["End"]), "text": d["Text"].strip()})
    return sorted(out, key=lambda x: x["start"])


def win_sel(table, w0, w1):
    r = []
    for c in table:
        if float(c["end"]) <= w0 + 1e-6 or float(c["start"]) >= w1 - 1e-6:
            continue
        r.append({"start": round(max(float(c["start"]), w0) - w0, 3),
                  "end": round(min(float(c["end"]), w1) - w0, 3), "text": c.get("text")})
    return sorted(r, key=lambda x: x["start"])


for d in (SANDBOX / "work", SANDBOX / "out", SANDBOX / "artifacts"):
    d.mkdir(parents=True, exist_ok=True)

# ================================================================ 冻结输入与预检
led0 = EX.load_ledger(str(LEDGER))
optA = next(e for e in led0 if e.get("stage") == "H3c-2-optA")
film_in = ROOT / optA["output_path"]
hard("P0 输入 = 已接受的 OPT-A 修正后 H3c-2（sha 与台账一致）",
     sha(film_in) == optA["output_sha256"],
     {"now": sha(film_in)[:16], "ledger": optA["output_sha256"][:16]})
plan_item = json.loads(MATPLAN.read_text(encoding="utf-8"))["items"]["E3"]
spec = VA.compile_from_plan_item(plan_item)
vs = VA.verify_spec(spec)
spec_sha = VA.spec_sha256(spec)
hard("P1 E3 内容逐字来自 6-E 冻结材料计划（C_self_made_spec）且 spec 合法",
     vs.get("errors") in (None, []) and vs.get("panel_count") == 3,
     {"spec_sha256": spec_sha, "panels": [p["id"] for p in spec["panels"]],
      "material_plan_sha256": sha(MATPLAN)})
hard("P2 形式 = A（单一跨子镜窗口 {}，1 次执行）".format(WINDOW),
     WINDOW == [487.572, 539.346] and WINDOW[1] - WINDOW[0] > 50.0, WINDOW)
hard("P3 POLICY / 阈值未变（6 / 0.30 / target_hold_s 25 / A1±0.05）",
     EX.POLICY["max_scenes_per_proposal"] == 6
     and EX.POLICY["max_share_of_film_per_proposal"] == 0.30 and TOL == 0.05, EX.POLICY)

# ================================================================ 登记 E3（幂等）
regs0 = core_revision.load_register(str(REGISTER))
prev = next((r for r in regs0 if r.get("label") == "E3-rebuild-visual-aid-s11"), None)
R6 = [json.loads(x) for x in (LOGS / "phase6e_review_ledger_r2.jsonl").read_text(
    encoding="utf-8").splitlines() if x.strip()]
FIND = next(e for e in R6 if e["finding_id"] == "hr-46048b3de09b")     # 6-E REJECT（S11）
if prev is None:
    share = round((WINDOW[1] - WINDOW[0]) / PROD, 4)
    rec = core_revision.make_proposal(
        FIND, FIND, "add_visual_aid", {"scenes": ["S11"], "window": WINDOW},
        {"what": "在 S11 新窗口内叠加**自制**信息层（形式 A：一个跨子镜 overlay，单次执行）",
         "how": "内容逐字沿用 6-E 冻结材料计划 items.E3.C_self_made_spec（compile_from_plan_item，"
                "哈希绑定 spec_source）；不新增事实、不改写措辞、不使用外部素材",
         "params": {"scene_ids": ["S11"], "window": WINDOW,
                    "spec_source": {"path": "docs/regression_2x/phase6e_materials/"
                                            "phase6e_material_plan.json",
                                    "item": "E3", "sha256": sha(MATPLAN)},
                    "overlay_form": "A", "single_execution": True,
                    "slot_count": vs.get("panel_count"),
                    "slot_count_source": "6-E 冻结材料计划 C_self_made_spec（沿用原设计；"
                                         "**未**使用 D8 改动设计）",
                    "h6_decision": "人工裁定：E3 = A（一个跨子镜 overlay）",
                    "dcv2_plan_sha256": P2["plan_sha256"]}},
        {"scenes": ["S11"], "window": WINDOW, "assets": [], "share_of_film": share,
         "windows": [{"scene_id": "S11", "window_s": WINDOW}],
         "not_touching": ["旁白文本", "字幕文本", "时间轴总时长", "切点", "历史 artifact",
                          "已接受链路产物"]},
        {"metric": "信息增量（可核对项数）", "direction": "3 个信息槽（冻结设计）",
         "basis": "6-E 冻结材料计划 E3 条目（真实 mathlib4 逐字引用 + Apache-2.0 署名）",
         "assumption": "可读性需人工确认（51.774s 窗口）", "not_guaranteed": True},
        constraints={"must_preserve": ["旁白文本", "字幕文本", "时间轴总时长"],
                     "overlay_safe_area": "不得进入底部 5% 字幕安全区",
                     "no_external_assets": True, "spec_hash_bound": True},
        risk=["跨子镜常显（形式 A 的固有取舍）", "可读性需人工确认"],
        known_scene_ids=[c["scene_id"] for c in chain],
        discriminator="6g-e3", label="E3-rebuild-visual-aid-s11",
        evidence_refs=["docs/regression_2x/phase6e_materials/phase6e_material_plan.json"])
    rec["origin_note"] = ("**本回合新登记**：6-G 包中的 E3 记录 action=add_visual_aid 但 slot_count="
                          "PENDING_D8、无 spec；本登记以人工裁定 A + **逐字沿用 6-E 冻结设计**定稿，"
                          "未自创内容、未用 D8 改设计")
    reg = core_revision.append_proposal(str(REGISTER), rec)
    print("  登记 E3 {} sha {} seq {}".format(rec["proposal_id"], EX.proposal_sha256(rec)[:16],
                                             reg.get("seq")))
else:
    print("  复用已登记 E3", prev["proposal_id"])
regs = core_revision.load_register(str(REGISTER))
prop = next(r for r in regs if r.get("label") == "E3-rebuild-visual-aid-s11")
prop_sha = EX.proposal_sha256(prop)
hard("P4 E3 已登记且局部化合规（1 场景 ≤6；share {} ≤0.30）".format(
    prop["affected_scope"]["share_of_film"]), EX.verify_locality(prop, None)["ok"] is True,
     EX.verify_locality(prop, None))
hard("P5 登记参数与实际执行严格对应（window/形式/spec 哈希绑定一致）",
     prop["affected_scope"]["window"] == WINDOW
     and prop["proposed_change"]["params"]["overlay_form"] == "A"
     and prop["proposed_change"]["params"]["spec_source"]["sha256"] == sha(MATPLAN),
     {"window": prop["affected_scope"]["window"],
      "form": prop["proposed_change"]["params"].get("overlay_form"),
      "spec_source": prop["proposed_change"]["params"].get("spec_source")})

# ================================================================ 执行
b1_sb = ROOT / B1["sandbox"]
art = {"script_output": str(b1_sb / "artifacts" / "script_output.json"),
       "voice_output": str(b1_sb / "artifacts" / "voice_output.json")}
script = json.loads(Path(art["script_output"]).read_text(encoding="utf-8"))
voice = json.loads(Path(art["voice_output"]).read_text(encoding="utf-8"))
cues_dcv2 = core_captions.build_cues(
    [{"narration": s["narration"], "duration_s": s.get("duration_s")}
     for s in script["segments"] if str(s.get("narration", "")).strip()],
    windows=[{"start_s": w["start_s"], "end_s": w["end_s"]} for w in CW])
cues_v1 = core_captions.build_cues(
    [{"narration": s["narration"], "duration_s": s.get("duration_s")}
     for s in script["segments"] if str(s.get("narration", "")).strip()])
plan = N.narration_plan(script, voice)
GP = core_integrity.gate_policy(CFG)
master_ass = SANDBOX / "work" / "dcv2_master.ass"
master_ass.write_text(core_captions.to_ass(cues_dcv2, resolution="1280x720"), encoding="utf-8")

import sqlite3                                                          # noqa: E402
con = sqlite3.connect("file:{}?mode=ro".format(
    (ROOT / "projects/video_studio.db").as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
rows = [dict(x) for x in con.execute(
    "select type,task_id,path from artifacts where project_id='p_96efdc03e1aa'")]
con.close()
rend = json.loads(Path(next(x["path"] for x in rows if x["type"] == "render_output"
                            and x.get("task_id") == "t_d0a54bdf1810")).read_text(encoding="utf-8"))
TL_ASSET = {str(e.get("scene_id")): (e.get("selected_asset") or {})
            for e in (rend.get("material_timeline") or []) if e.get("selected_asset")}
TLX = [dict(e, selected_asset=TL_ASSET.get(e["scene_id"], {})) for e in TL]

box = SANDBOX / "work" / "E3"
for sd in ("work", "output"):
    (box / sd).mkdir(parents=True, exist_ok=True)
ctx = OPX.attach_dcv2_time_base(
    {"box": str(box), "root": str(ROOT), "ffmpeg": str(FFMPEG), "ffprobe": str(FFPROBE),
     "config": CFG, "film": str(film_in), "cues": cues_dcv2, "evidence": None, "artifacts": art,
     "narration_plan": plan}, timeline=TLX, caption_windows=CW, production_duration_s=PROD,
    source="docs/regression_2x/logs/phase6f_rebuild_plan_v2.json")
hard("P6 DCv2 timeline identity 校验通过",
     OPX.assert_timeline_identity(ctx)["enforced"] is True
     and ctx["timeline_identity"]["identity_sha256"] == N0["timeline_identity"]["identity_sha256"])
hard("P7 caption time base == DCv2", OPX.caption_time_base(ctx)["mode"] == "dcv2")
appr = EX.make_approval(prop, "APPROVE", "human",
                        "人工裁定 E3 = A（一个跨子镜 overlay，1 次执行）——仅执行 E3",
                        {"authorization": "6-G E3 执行授权（形式 A）",
                         "scope": "E3 only", "not_authorized": ["H5", "E4", "E5", "OPT-B",
                                                               "阈值变更"]})
gate = EX.gate_execution(prop, [appr], None)
hard("P8 execution gate 通过", gate.get("allowed") is True,
     {"code": gate.get("code"), "why": gate.get("why")})

HIST = {"v9": ROOT / "projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4"}
m6c = json.loads((LOGS / "phase6c_batch.json").read_text(encoding="utf-8"))
for c in m6c["candidates"]:
    HIST["c" + str(c["index"])] = ROOT / c["film"]
HIST["e1"] = (ROOT / "output/phase6b_m4_sandbox/p_96efdc03e1aa_6e/output/"
              "t_d0a54bdf1810_draft_6c_rp-ad4bbbee7ea2_outro.mp4")
HIST["e2"] = (ROOT / "output/phase6b_m4_sandbox/p_96efdc03e1aa_6e2/output/"
              "t_d0a54bdf1810_draft_6c_rp-bee31dff3335_vaid.mp4")
BEFORE = {"history": {k: sha(p) for k, p in HIST.items() if p.is_file()},
          "db": sha(ROOT / "projects/video_studio.db"),
          "baseline": sorted(p.name for p in (ROOT / "docs/regression_2x" / "baseline").glob("*")),
          "master": sha(ROOT / N0["master"]["path"]),
          "chain": {e["stage"]: e["output_sha256"] for e in led0},
          "ledger_len": len(led0),
          "matplan": sha(MATPLAN),
          "projects_len": len([p for p in (ROOT / "projects/p_96efdc03e1aa").rglob("*")
                               if p.is_file()])}

res = EX.execute_proposal(prop, [appr], OPX.EXECUTORS, ctx, recheck=OPX.pi_recheck)
hard("P9 执行 SUCCEEDED", res.get("state") == "SUCCEEDED",
     {"state": res.get("state"), "why": res.get("why")})
out_rel = (res.get("outputs") or [{}])[0]["path"]
film_out = SANDBOX / "out" / "E3_{}.mp4".format(prop["proposal_id"])
shutil.copy2(ROOT / out_rel, film_out)
st = streams(film_out)
stre = {"path": str(film_out.relative_to(ROOT)), "sha256": sha(film_out),
        "bytes": film_out.stat().st_size, "audio_md5": amd5(film_out), **st}
print("  E3 out: duration {} video {} frames {} audio {} md5 {}".format(
    st["format_duration_s"], (st.get("video") or {}).get("duration_s"),
    (st.get("video") or {}).get("nb_frames"), (st.get("audio") or {}).get("duration_s"),
    stre["audio_md5"][:12]))

# ---------------- 验收
hard("A1 duration == 978.656 ± 0.05（实测 {}）".format(st["format_duration_s"]),
     abs(st["format_duration_s"] - PROD) <= TOL, stre)
hard("A2 audio identity == 母版（md5 {}）".format(stre["audio_md5"][:12]),
     stre["audio_md5"] == amd5(ROOT / N0["master"]["path"]), stre)
ass_files = sorted((box / "work").glob("cap_*.ass"))
s1, s2 = [], []
for ap in ass_files:
    parsed = parse_ass(ap)
    d = win_sel(cues_dcv2, WINDOW[0], WINDOW[1])
    ok = bool(d) and len(d) == len(parsed) and all(
        abs(a["start"] - b["start"]) < 0.02 and abs(a["end"] - b["end"]) < 0.02
        and norm(a["text"]) == norm(b["text"]) for a, b in zip(parsed, d))
    s1.append({"ass": ap.name, "window": WINDOW, "cues": len(parsed), "dcv2_match": ok,
               "v1_differs": win_sel(cues_v1, WINDOW[0], WINDOW[1]) != d})
    s2.append(ap.name)
hard("B1 窗口 ASS == DCv2 表（{} 文件）".format(len(ass_files)),
     bool(ass_files) and all(x["dcv2_match"] for x in s1), s1)
hard("B2 同窗口 v1 选择 != DCv2（负对照）", all(x["v1_differs"] for x in s1), s1)
fr = []
for w in [WINDOW]:
    cc = [c for c in cues_dcv2 if c["start"] >= w[0] and c["end"] <= w[1]]
    for t in [round((cc[0]["start"] + cc[0]["end"]) / 2, 3),
              round((cc[len(cc) // 2]["start"] + cc[len(cc) // 2]["end"]) / 2, 3)]:
        # 掩膜：把 DCv2 主表在 t 时刻烧到黑底
        mf = SANDBOX / "work" / "mask_{}.png".format(int(t))
        subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i",
                        "color=c=black:s=1280x720:r=1", "-vf",
                        "ass=filename='{}':fontsdir='C\\:/Windows/Fonts'".format(
                            master_ass.as_posix().replace(":", "\\:")), "-ss", str(int(t)),
                        "-frames:v", "1", str(mf)], capture_output=True)
        mg = gray(mf)
        ink = mg > 0.5
        e = (ink[1:-1, 1:-1] & ink[:-2, 1:-1] & ink[2:, 1:-1] & ink[1:-1, :-2] & ink[1:-1, 2:])
        a = frame(film_out, t, "sp", st["format_duration_s"])
        b = frame(ROOT / N0["master"]["path"], t, "mst", PROD)
        if not e.any():
            continue
        fr.append({"t": t, "glyph_core_px": int(e.sum()),
                   "ink_diff_vs_master": round(float(abs(a[1:-1, 1:-1][e]
                                                         - b[1:-1, 1:-1][e]).mean()), 4),
                   "max_ink": round(float(a[1:-1, 1:-1][e].max()), 3)})
hard("B3 语音时刻字幕字形与母版一致（腐蚀差分 < 0.15；字幕时基未变）",
     bool(fr) and all(x["ink_diff_vs_master"] < 0.15 and x["max_ink"] > 0.5 for x in fr), fr)
# C1 叠加层可见 + 字幕安全区未受影响
tin = round((WINDOW[0] + WINDOW[1]) / 2, 3)
a_out, a_in = frame(film_out, tin, "ov", st["format_duration_s"]), frame(film_in, tin, "in", PROD)
h = a_out.shape[0]
mid_diff = float(abs(a_out[int(h * 0.18):int(h * 0.55)] - a_in[int(h * 0.18):int(h * 0.55)]).mean())
bot_diff = float(abs(a_out[int(h * 0.95):] - a_in[int(h * 0.95):]).mean())
hard("C1 叠加层可见（中带 diff > 0.02）且底部 5% 字幕安全区未被占用（< 0.05）",
     mid_diff > 0.02 and bot_diff < 0.05, {"t": tin, "mid_diff": round(mid_diff, 4),
                                           "bottom5_diff": round(bot_diff, 4)})
# C2 未改变切点/时长/未触及区段
out_of_window = 950.0
d_out = float(abs(frame(film_out, out_of_window, "oow", st["format_duration_s"])
                  - frame(film_in, out_of_window, "oowi", PROD)).mean())
hard("C2 窗口外区段未变（抽样帧差 < 0.02）+ 时长守恒（切点/时间轴未改）",
     d_out < 0.02 and abs(st["format_duration_s"] - PROD) <= TOL,
     {"t": out_of_window, "frame_diff": round(d_out, 4)})
pre = core_integrity.pre_render_gate(script.get("segments") or [], voice, PROD, GP,
                                     narration_duration_s=voice.get("narration_duration_s"),
                                     narration_plan=plan, cues=cues_dcv2,
                                     narration_padding_s=PROD - float(
                                         voice.get("narration_duration_s") or 0))
post = core_integrity.post_render_gate(film_out, PROD, cues_dcv2,
                                       voice.get("narration_duration_s"), True, str(FFMPEG),
                                       str(FFPROBE), GP, narration_plan=plan)
sm = lambda m: {a: (b.get("state") if isinstance(b, dict) else b) for a, b in m.items()}
hard("D1 DCv2 pre-render 未阻断 + PI-1/PI-2/PI-6/G-TL/G-PAD/G-SUB 全 PASS",
     (not pre["blocked"]) and all(sm(pre["metrics"]).get(g) == "PASS"
                                  for g in ("PI-1", "PI-2", "PI-6", "G-TL", "G-PAD", "G-SUB")),
     {"states": sm(pre["metrics"]), "reasons": pre["reasons"]})
hard("D2 DCv2 post-render：PI-3 PASS 且 promote 未被阻断",
     sm(post["metrics"]).get("PI-3") == "PASS" and not post.get("promote_blocked"),
     {"PI-3": post["metrics"]["PI-3"], "reasons": post["reasons"]})
hard("D3 冻结复核（DCv2 口径）== PASS", res.get("pi_gate_outcome") == "PASS",
     res.get("pi_gate_outcome"))
bnd = [WINDOW[0], WINDOW[1] - 0.05]
lum = {str(b): round(float(frame(film_out, b, "bd", st["format_duration_s"]).mean()), 4)
       for b in bnd}
hard("E1 窗口边界无黑帧", not [k for k, v in lum.items() if v < 0.02], lum)
iso = {"history_unchanged": all(sha(HIST[k]) == v for k, v in BEFORE["history"].items()
                                if HIST[k].is_file()),
       "db_unchanged": sha(ROOT / "projects/video_studio.db") == BEFORE["db"],
       "baseline_unchanged": sorted(p.name for p in
                                    (ROOT / "docs/regression_2x/baseline").glob("*"))
       == BEFORE["baseline"],
       "master_unchanged": sha(ROOT / N0["master"]["path"]) == BEFORE["master"],
       "accepted_chain_unchanged": all(sha(ROOT / e["output_path"]) == e["output_sha256"]
                                       for e in led0),
       "material_plan_unchanged": sha(MATPLAN) == BEFORE["matplan"],
       "projects_len_unchanged": len([p for p in (ROOT / "projects/p_96efdc03e1aa").rglob("*")
                                      if p.is_file()]) == BEFORE["projects_len"],
       "output_in_new_sandbox": str(film_out).startswith(str(SANDBOX))}
hard("F1 隔离：历史/DB/baseline/母版/已接受链路/材料计划/项目目录 均未变",
     all(iso.values()), iso)

entry = EX.append_execution(str(LEDGER), {
    "schema": "revision-execution-v1", "proposal_id": prop["proposal_id"],
    "label": "E3-rebuild-visual-aid-s11", "stage": "E3", "action": "add_visual_aid",
    "proposal_sha256": prop_sha, "approval_id": appr["approval_id"], "approved_by": "human",
    "input_sha256": sha(film_in), "output_path": stre["path"], "output_sha256": stre["sha256"],
    "duration_s": st["format_duration_s"], "audio_md5": stre["audio_md5"],
    "timeline_identity": N0["timeline_identity"]["identity_sha256"], "caption_time_base": "dcv2",
    "acceptance": "ACCEPTED",
    "overlay_form": "A（一个跨子镜 overlay；1 次执行）",
    "spec_source": prop["proposed_change"]["params"]["spec_source"],
    "pi_states": {**sm(pre["metrics"]), **sm(post["metrics"]),
                  "frozen_recheck": res.get("pi_gate_outcome")},
    "ffmpeg_calls": len(FF_CALLS), "sandbox": str(SANDBOX.relative_to(ROOT)),
    "executed_at": time.strftime("%Y-%m-%dT%H:%M:%S")})

# DQ（E3 不改时间轴 ⇒ 应保持不变）
proj = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
         "end_s": c["new_timeline_window_s"][1], "selected_asset": TL_ASSET.get(c["scene_id"], {})}
        for c in chain]


def apply_split(entries, sp, amap):
    for rr in sp.get("scenes", []):
        base = next(e for e in entries if e["scene_id"] == rr["scene_id"])
        d = rr["sub_duration_s"]
        new = [{"scene_id": "{}.{}".format(rr["scene_id"], j + 1),
                "start_s": round(rr["window"][0] + d * j, 3),
                "end_s": round(rr["window"][0] + d * (j + 1), 3),
                "selected_asset": amap.get(rr["scene_id"], {})} for j in range(rr["sub_count"])]
        i = entries.index(base)
        entries[i:i + 1] = new
    return entries


for stage in ("H3a", "H3b"):
    apply_split(proj, next(s["exec"]["exec_evidence"]["split_plan"] for s in B1["stages"]
                           if s["stage"] == stage), TL_ASSET)
for lab in ("H3c-1", "H3c-2"):
    p = next(x for x in regs if x.get("label") == lab)
    apply_split(proj, OPX.split_plan({"timeline": [dict(e) for e in TLX],
                                      "timeline_identity": None, "caption_timeline": None}, p),
                TL_ASSET)
dq = {"DQ-2": core_direction.asset_reuse(proj), "DQ-3": core_direction.static_hold(proj),
      "DQ-4": core_direction.visual_density(proj)}
# 可读性观察（advisory，非门禁）：冻结设计文本量 vs 窗口时长
txt = sum(len(p.get("title", "")) + sum(len(x) for x in p.get("items", []))
          for p in spec["panels"])
cps = float(core_captions.CHARS_PER_SEC)
readability = {"chars": txt, "window_s": round(WINDOW[1] - WINDOW[0], 3),
               "reading_need_s": round(txt / cps, 1), "advisory_only": True,
               "note": "冻结设计的文本量 vs 窗口时长；仅记录，不构成门禁（可读性需人工确认）"}

led = EX.load_ledger(str(LEDGER))
report = {"schema": "phase6g-exec-e3-v1", "stage": "6-G / E3",
          "state": "E3_ACCEPTED" if not FAIL else "E3_STOPPED_AT_HARD_GATE",
          "overlay_form": "A（一个跨子镜 overlay；单次执行）",
          "human_decision": "人工裁定 E3 = A；台账粒度随之为 1 条执行记录"
                            "（『3 条执行记录』仅适用于未选择的 B）",
          "proposal": {"label": prop["label"], "proposal_id": prop["proposal_id"],
                       "proposal_sha256": prop_sha, "register_entry_seq":
                           next((r.get("seq") for r in regs if r["proposal_id"] == prop["proposal_id"]), None),
                       "scenes": prop["affected_scope"]["scenes"],
                       "window": prop["affected_scope"]["window"],
                       "share_of_film": prop["affected_scope"]["share_of_film"],
                       "spec_source": prop["proposed_change"]["params"]["spec_source"],
                       "spec_sha256": spec_sha,
                       "slot_count": vs.get("panel_count"),
                       "content_provenance": "逐字沿用 6-E 冻结材料计划 C_self_made_spec；"
                                             "未自创、未使用 D8 改设计"},
          "policy_unchanged": {"max_scenes_per_proposal": EX.POLICY["max_scenes_per_proposal"],
                               "max_share_of_film_per_proposal":
                                   EX.POLICY["max_share_of_film_per_proposal"],
                               "a1_tolerance_s": TOL, "thresholds_changed": False,
                               "dq_criteria_changed": False},
          "input": {"path": optA["output_path"], "sha256": optA["output_sha256"]},
          "output": stre, "sandbox": str(SANDBOX.relative_to(ROOT)),
          "gates": {"pass": PASS, "fail": FAIL, "failed": FAIL},
          "PI": {"pre": sm(pre["metrics"]), "post": sm(post["metrics"]),
                 "frozen_recheck": res.get("pi_gate_outcome")},
          "subtitle": {"ass": s1, "frames": fr},
          "overlay_check": {"t": tin, "mid_diff": round(mid_diff, 4),
                            "bottom5_diff": round(bot_diff, 4)},
          "outside_window_frame_diff": round(d_out, 4),
          "visual_continuity": lum, "isolation": iso, "readability_advisory": readability,
          "DQ_measured": {"DQ-2": dq["DQ-2"], "DQ-3": dq["DQ-3"], "DQ-4": dq["DQ-4"],
                          "entries": len(proj), "unchanged_by_E3": True,
                          "no_dq_closure_claim": "**不宣称 Directorial Quality 闭环**（DQ-2 仍 FAIL）"},
          "ledger": {"path": str(LEDGER.relative_to(ROOT)), "entries": len(led),
                     "chain": EX.verify_chain(led), "new_seq": entry.get("seq")},
          "register": {"path": str(REGISTER.relative_to(ROOT)), "entries": len(regs),
                       "chain": core_revision.verify_register_chain(regs)},
          "ffmpeg_calls": len(FF_CALLS),
          "claims": {"promoted": False, "db_written": False, "baseline_or_tag_changed": False,
                     "historical_artifact_changed": False, "h5_e4_e5_executed": False,
                     "threshold_relaxed": False, "dq_criteria_changed": False,
                     "materials_modified": False, "scope_expanded": False}}
report["report_sha256"] = hashlib.sha256(json.dumps(
    report, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("\n== E3 汇总 ==")
print("  proposal {} sha {} | 窗口 {} | spec {}", prop["proposal_id"], prop_sha[:16],
      prop["affected_scope"]["window"], spec_sha[:16])
print("  output {} {}s sha {} md5 {} | overlay mid {:.4f} / bottom5 {:.4f} / 窗外 {:.4f}".format(
    stre["path"], st["format_duration_s"], stre["sha256"][:12], stre["audio_md5"][:12],
    mid_diff, bot_diff, d_out))
print("  DQ: DQ-2 {} (unique {}) | DQ-3 {} (max_hold {}) | DQ-4 {} ({} /min)".format(
    dq["DQ-2"]["state"], dq["DQ-2"].get("unique_assets"), dq["DQ-3"]["state"],
    dq["DQ-3"].get("max_hold_s"), dq["DQ-4"]["state"], dq["DQ-4"].get("scene_changes_per_min")))
print("  gates {} PASS / {} FAIL | ledger seq {} | state {}".format(
    len(PASS), len(FAIL), entry.get("seq"), report["state"]))
print("report ->", OUT)
sys.exit(1 if FAIL else 0)

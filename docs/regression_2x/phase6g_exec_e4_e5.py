# -*- coding: utf-8 -*-
"""6-G / E4 → E5（人工裁定：两者 slot_count=3、形式 A、仅用冻结材料计划 P1/P2/P3）正式执行。

严格遵守：不为凑 4 槽修改工具链（`_PANEL_KIND` 不变）；不新增事实/文案/面板/source；
E4 失败即 STOP（不执行 E5）；不改 POLICY/阈值/DQ 判据；不 promote/写 DB/切 baseline。
E4 内容：冻结材料计划 E4 的 **P1–P3 逐字**（P4 经人工裁定不上屏 ⇒ 过滤后编译，工具链未改）。
E5 内容：冻结材料计划 E5 的 3 面板（`spec_source` 文件哈希绑定，执行时由执行器重新编译）。

产出: docs/regression_2x/logs/phase6g_exec_e4_e5.json
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
MP = ROOT / "docs" / "regression_2x" / "phase6e_materials" / "phase6e_material_plan.json"
P2 = json.loads((LOGS / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
N0 = json.loads((LOGS / "phase6g_n0_dcv2_master.json").read_text(encoding="utf-8"))
B1 = json.loads((LOGS / "phase6g_exec_batch1.json").read_text(encoding="utf-8"))
E3R = json.loads((LOGS / "phase6g_exec_e3.json").read_text(encoding="utf-8"))
PKG = json.loads((LOGS / "phase6g_rebuild_proposals.json").read_text(encoding="utf-8"))
MPJ = json.loads(MP.read_text(encoding="utf-8"))
OUT = LOGS / "phase6g_exec_e4_e5.json"
REGISTER = LOGS / "phase6g_rebuild_proposal_register.jsonl"
LEDGER = LOGS / "phase6g_exec_ledger.jsonl"
FFMPEG, FFPROBE = ROOT / "bin" / "ffmpeg.exe", ROOT / "bin" / "ffprobe.exe"
PROD, TOL = 978.656, 0.05
CFG = {"tools": {"ffmpeg": {"path": str(FFMPEG), "ffprobe": str(FFPROBE)}}}
TS = time.strftime("%Y%m%d_%H%M%S")
SANDBOX = ROOT / "output" / "phase6g_exec_e4_e5" / TS
chain = P2["remapping_21_segments"]
CW = [{"scene_id": c["scene_id"], "start_s": c["new_audio_window_s"][0],
       "end_s": c["new_audio_window_s"][1]} for c in chain]
TL = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
       "end_s": c["new_timeline_window_s"][1]} for c in chain]
AUTH = ("人工裁定 D8：E4 = 3 槽 / E5 = 3 槽（共用）；E4 = A、E5 = A（跨子镜 overlay）；"
        "E4 仅用冻结 P1/P2/P3（P4 不上屏）；E5 仅用冻结 P1/P2/P3（第 4 槽不上屏）；"
        "不扩展 _PANEL_KIND、不新增设计内容")
ITEMS = [("E4", ["S08", "S09", "S10"], "hr-488b41463fb0"),
         ("E5", ["S13", "S14"], "hr-ca922009730c")]
PASS, FAIL, STAGES, FF_CALLS = [], [], [], []
CURRENT = {"stage": None}
_orig_run = OPX._run


def _rec_run(cmd, timeout=3600):
    FF_CALLS.append({"stage": CURRENT["stage"], "argv": [str(c) for c in cmd][:16]})
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
        raise RuntimeError("E4E5_GATE_FAILED: " + name)


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

# ---------------------------------------------------------------- 冻结内容（不自创）
SPECS = {}
for label, _scenes, _fid in ITEMS:
    item = MPJ["items"][label]
    c = item["C_self_made_spec"]
    if label == "E4":
        kept = [p for p in c["panels"] if p["id"] in ("P1", "P2", "P3")]
        excl = [p["id"] for p in c["panels"] if p["id"] not in ("P1", "P2", "P3")]
        spec = VA.compile_from_plan_item(dict(item, C_self_made_spec=dict(c, panels=kept)))
        mode = "inline_filtered（P1–P3；P4 经人工裁定不上屏）"
    else:
        excl = [p["id"] for p in c["panels"] if p["id"] not in ("P1", "P2", "P3")]
        spec = VA.compile_from_plan_item(item)      # 3 面板逐字
        mode = "spec_source（文件哈希绑定，执行时由执行器重新编译）"
    vs = VA.verify_spec(spec)
    SPECS[label] = {"spec": spec, "mode": mode, "excluded": excl,
                    "kept": [p["id"] for p in spec["panels"]],
                    "spec_sha256": VA.spec_sha256(spec),
                    "verify": {k: vs.get(k) for k in ("schema", "panel_count", "errors",
                                                      "warnings")},
                    "kinds": [p["kind"] for p in spec["panels"]],
                    "titles": [p["title"] for p in spec["panels"]],
                    "chars": sum(len(p["title"]) + sum(len(str(x)) for x in p["items"])
                                 for p in spec["panels"])}

hard("P1 冻结材料计划未变（sha 与既有记录一致）",
     sha(MP) == "0cefd8810515138cf3a8e2057ffcf3c695bc16d7b8cfac818bd6fcad74689df8",
     sha(MP))
hard("P2 E4/E5 spec 均合法且面板数 == 3（人工裁定的共用值）",
     all(SPECS[x]["verify"]["panel_count"] == 3 and SPECS[x]["verify"]["errors"] in (None, [])
         for x in ("E4", "E5")), {x: SPECS[x]["verify"] for x in ("E4", "E5")})
hard("P3 未扩展 `_PANEL_KIND`（仍为 P1/P2/P3）且 E4 的 P4 已按裁定排除",
     VA._PANEL_KIND == {"P1": "ladder", "P2": "cards", "P3": "positions"}
     and SPECS["E4"]["excluded"] == ["P4"] and SPECS["E5"]["kept"] == ["P1", "P2", "P3"],
     {"panel_kind": VA._PANEL_KIND, "E4_excluded": SPECS["E4"]["excluded"],
      "E5_kept": SPECS["E5"]["kept"]})
hard("P4 POLICY / 阈值未变（6 / 0.30 / A1±0.05）",
     EX.POLICY["max_scenes_per_proposal"] == 6
     and EX.POLICY["max_share_of_film_per_proposal"] == 0.30 and TOL == 0.05, EX.POLICY)

# ---------------------------------------------------------------- 其余只读输入
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

HIST = {"v9": ROOT / "projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4"}
m6c = json.loads((LOGS / "phase6c_batch.json").read_text(encoding="utf-8"))
for c in m6c["candidates"]:
    HIST["c" + str(c["index"])] = ROOT / c["film"]
HIST["e1"] = (ROOT / "output/phase6b_m4_sandbox/p_96efdc03e1aa_6e/output/"
              "t_d0a54bdf1810_draft_6c_rp-ad4bbbee7ea2_outro.mp4")
HIST["e2"] = (ROOT / "output/phase6b_m4_sandbox/p_96efdc03e1aa_6e2/output/"
              "t_d0a54bdf1810_draft_6c_rp-bee31dff3335_vaid.mp4")
led0 = EX.load_ledger(str(LEDGER))
BEFORE = {"history": {k: sha(p) for k, p in HIST.items() if p.is_file()},
          "db": sha(ROOT / "projects/video_studio.db"),
          "baseline": sorted(p.name for p in (ROOT / "docs/regression_2x/baseline").glob("*")),
          "master": sha(ROOT / N0["master"]["path"]),
          "chain": {e["stage"]: e["output_sha256"] for e in led0},
          "matplan": sha(MP), "ledger_len": len(led0),
          "projects_len": len([p for p in (ROOT / "projects/p_96efdc03e1aa").rglob("*")
                               if p.is_file()])}

# ---------------------------------------------------------------- E4 → E5
film_in = ROOT / E3R["output"]["path"]
hard("P0 输入 = 已接受的 E3 产物（sha 与 E3 报告一致）",
     sha(film_in) == E3R["output"]["sha256"],
     {"now": sha(film_in)[:16], "e3": E3R["output"]["sha256"][:16]})
regs0 = core_revision.load_register(str(REGISTER))
R6 = [json.loads(x) for x in (LOGS / "phase6e_review_ledger_r2.jsonl").read_text(
    encoding="utf-8").splitlines() if x.strip()]

for label, scenes, fid in ITEMS:
    CURRENT["stage"] = label
    spec = SPECS[label]["spec"]
    find = next(e for e in R6 if e["finding_id"] == fid)
    win = [min(next(c["new_timeline_window_s"][0] for c in chain if c["scene_id"] == s)
               for s in scenes),
           max(next(c["new_timeline_window_s"][1] for c in chain if c["scene_id"] == s)
               for s in scenes)]
    share = round(sum(next(c["new_timeline_window_s"][1] - c["new_timeline_window_s"][0]
                           for c in chain if c["scene_id"] == s) for s in scenes) / PROD, 4)
    # ---- 登记（幂等）
    prev = next((r for r in regs0 if r.get("label", "").startswith(label + "-rebuild")), None)
    if prev is None:
        params = {"scene_ids": scenes, "window": win, "overlay_form": "A",
                  "single_execution": True, "slot_count": 3,
                  "slot_count_source": "人工裁定 D8（E4/E5 共用 3；仅取冻结材料计划 P1–P3）",
                  "panels_used": SPECS[label]["kept"],
                  "panels_excluded": SPECS[label]["excluded"],
                  "spec_mode": SPECS[label]["mode"],
                  "spec_sha256": SPECS[label]["spec_sha256"],
                  "material_plan_sha256": sha(MP),
                  "content_provenance": "6-E 冻结材料计划 items.{}.C_self_made_spec（逐字，"
                                        "不含未冻结内容）".format(label),
                  "d8_decision": AUTH, "dcv2_plan_sha256": P2["plan_sha256"]}
        if label == "E4":
            params["visual_aid"] = spec          # 内联（P1–P3 过滤后编译；工具链未改）
        else:
            params["spec_source"] = {"path": str(MP.relative_to(ROOT)), "item": "E5",
                                     "sha256": sha(MP)}
        rec = core_revision.make_proposal(
            find, find, "add_visual_aid", {"scenes": scenes, "window": win},
            {"what": "在 {} 窗口内叠加**自制**信息层（形式 A：一个跨子镜 overlay，单次执行）".format(
                "/".join(scenes)),
             "how": "内容逐字取自 6-E 冻结材料计划；槽数=3（人工裁定 D8）；"
                    "不含未冻结/已排除面板；不使用外部素材",
             "params": params},
            {"scenes": scenes, "window": win, "assets": [], "share_of_film": share,
             "windows": [{"scene_id": s, "window_s": list(next(
                 c["new_timeline_window_s"] for c in chain if c["scene_id"] == s))}
                 for s in scenes],
             "not_touching": ["旁白文本", "字幕文本", "时间轴总时长", "切点", "历史 artifact",
                              "已接受链路产物"]},
            {"metric": "信息增量（可核对项数）", "direction": "3 个信息槽（人工裁定 D8）",
             "basis": "6-E 冻结材料计划 items.{}".format(label),
             "assumption": "可读性需人工确认", "not_guaranteed": True},
            constraints={"must_preserve": ["旁白文本", "字幕文本", "时间轴总时长"],
                         "overlay_safe_area": "不得进入底部 5% 字幕安全区",
                         "no_external_assets": True, "slot_count_fixed_by_human": 3},
            risk=["跨子镜常显（形式 A 固有取舍）", "可读性需人工确认"],
            known_scene_ids=[c["scene_id"] for c in chain],
            discriminator="6g-" + label.lower(), label="{}-rebuild-visual-aid".format(label),
            evidence_refs=[str(MP.relative_to(ROOT))])
        rec["origin_note"] = ("**本回合新登记**：6-G 包原记录 slot_count=PENDING_D8；本次按人工裁定"
                              "（3 槽 / 形式 A / 仅 P1–P3）定稿，未自创内容、未扩展工具链")
        rg = core_revision.append_proposal(str(REGISTER), rec)
        print("  登记 {} {} seq {}".format(label, rec["proposal_id"], rg.get("seq")))
    regs = core_revision.load_register(str(REGISTER))
    prop = next(r for r in regs if r.get("label") == "{}-rebuild-visual-aid".format(label))
    prop_sha = EX.proposal_sha256(prop)
    st = {"stage": label, "proposal_id": prop["proposal_id"], "proposal_sha256": prop_sha,
          "register_seq": next((r.get("seq") for r in regs
                                if r["proposal_id"] == prop["proposal_id"]), None),
          "scenes": scenes, "window": win, "share_of_film": share,
          "slot_count": 3, "overlay_form": "A",
          "panels_used": SPECS[label]["kept"], "panels_excluded": SPECS[label]["excluded"],
          "spec_sha256": SPECS[label]["spec_sha256"], "spec_mode": SPECS[label]["mode"],
          "spec_titles": SPECS[label]["titles"], "spec_chars": SPECS[label]["chars"],
          "input": {"path": str(film_in.relative_to(ROOT)), "sha256": sha(film_in)}}
    hard("{} 登记与裁定严格对应（3 槽 / 形式 A / 面板 {} / 排除 {}）".format(
        label, SPECS[label]["kept"], SPECS[label]["excluded"]),
        prop["proposed_change"]["params"]["slot_count"] == 3
        and prop["proposed_change"]["params"]["overlay_form"] == "A"
        and prop["proposed_change"]["params"]["panels_used"] == SPECS[label]["kept"]
        and prop["proposed_change"]["params"]["panels_excluded"] == SPECS[label]["excluded"]
        and core_revision.verify_proposal(prop) == [], st)
    hard("{} 局部化合规（{} 场景 ≤6；share {} ≤0.30）".format(label, len(scenes), share),
         EX.verify_locality(prop, None)["ok"] is True, EX.verify_locality(prop, None))
    box = SANDBOX / "work" / label
    for sd in ("work", "output"):
        (box / sd).mkdir(parents=True, exist_ok=True)
    ctx = OPX.attach_dcv2_time_base(
        {"box": str(box), "root": str(ROOT), "ffmpeg": str(FFMPEG), "ffprobe": str(FFPROBE),
         "config": CFG, "film": str(film_in), "cues": cues_dcv2, "evidence": None, "artifacts": art,
         "narration_plan": plan}, timeline=TLX, caption_windows=CW, production_duration_s=PROD,
        source="docs/regression_2x/logs/phase6f_rebuild_plan_v2.json")
    hard("{} DCv2 timeline identity 校验通过".format(label),
         OPX.assert_timeline_identity(ctx)["enforced"] is True
         and ctx["timeline_identity"]["identity_sha256"]
         == N0["timeline_identity"]["identity_sha256"])
    hard("{} caption time base == DCv2".format(label),
         OPX.caption_time_base(ctx)["mode"] == "dcv2")
    appr = EX.make_approval(prop, "APPROVE", "human", AUTH,
                            {"authorization": "D8 裁定后执行 {}（形式 A / 3 槽）".format(label),
                             "scope": label, "not_authorized": ["H5", "4 槽", "_PANEL_KIND 扩展",
                                                                "阈值变更"]})
    gate = EX.gate_execution(prop, [appr], None)
    hard("{} execution gate 通过".format(label), gate.get("allowed") is True,
         {"code": gate.get("code"), "why": gate.get("why")})
    res = EX.execute_proposal(prop, [appr], OPX.EXECUTORS, ctx, recheck=OPX.pi_recheck)
    hard("{} 执行 SUCCEEDED".format(label), res.get("state") == "SUCCEEDED",
         {"state": res.get("state"), "why": res.get("why")})
    out_rel = (res.get("outputs") or [{}])[0]["path"]
    film_out = SANDBOX / "out" / "{}_{}.mp4".format(label, prop["proposal_id"])
    shutil.copy2(ROOT / out_rel, film_out)
    stx = streams(film_out)
    stre = {"path": str(film_out.relative_to(ROOT)), "sha256": sha(film_out),
            "bytes": film_out.stat().st_size, "audio_md5": amd5(film_out), **stx}
    st["output"] = stre
    st["exec"] = {"state": res["state"], "steps": res.get("steps"),
                  "exec_evidence": res.get("exec_evidence"),
                  "pi_gate_outcome": res.get("pi_gate_outcome")}
    print("  {} out: duration {} video {} frames {} audio {} md5 {}".format(
        label, stx["format_duration_s"], (stx.get("video") or {}).get("duration_s"),
        (stx.get("video") or {}).get("nb_frames"), (stx.get("audio") or {}).get("duration_s"),
        stre["audio_md5"][:12]))
    # ---- 22 门
    hard("{} A1 duration == 978.656 ± 0.05（实测 {}）".format(label, stx["format_duration_s"]),
         abs(stx["format_duration_s"] - PROD) <= TOL, stre)
    hard("{} A2 audio identity == 母版（md5 {}）".format(label, stre["audio_md5"][:12]),
         stre["audio_md5"] == amd5(ROOT / N0["master"]["path"]), stre)
    ass_files = sorted((box / "work").glob("cap_*.ass"))
    s1 = []
    for ap in ass_files:
        parsed = parse_ass(ap)
        d = win_sel(cues_dcv2, win[0], win[1])
        s1.append({"ass": ap.name, "window": win, "cues": len(parsed),
                   "dcv2_match": bool(d) and len(d) == len(parsed) and all(
                       abs(a["start"] - b["start"]) < 0.02 and abs(a["end"] - b["end"]) < 0.02
                       and norm(a["text"]) == norm(b["text"]) for a, b in zip(parsed, d)),
                   "v1_differs": win_sel(cues_v1, win[0], win[1]) != d})
    hard("{} B1 窗口 ASS == DCv2 表（{} 文件）".format(label, len(ass_files)),
         bool(ass_files) and all(x["dcv2_match"] for x in s1), s1)
    hard("{} B2 同窗口 v1 选择 != DCv2（负对照）".format(label),
         all(x["v1_differs"] for x in s1), s1)
    fr = []
    cc = [c for c in cues_dcv2 if c["start"] >= win[0] and c["end"] <= win[1]]
    for t in [round((cc[0]["start"] + cc[0]["end"]) / 2, 3),
              round((cc[len(cc) // 2]["start"] + cc[len(cc) // 2]["end"]) / 2, 3)]:
        mf = SANDBOX / "work" / "mask_{}_{}.png".format(label, int(t))
        subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i",
                        "color=c=black:s=1280x720:r=1", "-vf",
                        "ass=filename='{}':fontsdir='C\\:/Windows/Fonts'".format(
                            master_ass.as_posix().replace(":", "\\:")), "-ss", str(int(t)),
                        "-frames:v", "1", str(mf)], capture_output=True)
        mg = gray(mf)
        ink = mg > 0.5
        e = (ink[1:-1, 1:-1] & ink[:-2, 1:-1] & ink[2:, 1:-1] & ink[1:-1, :-2] & ink[1:-1, 2:])
        if not e.any():
            continue
        a2 = frame(film_out, t, label + "sp", stx["format_duration_s"])
        b2 = frame(ROOT / N0["master"]["path"], t, label + "mst", PROD)
        fr.append({"t": t, "glyph_core_px": int(e.sum()),
                   "ink_diff_vs_master": round(float(abs(a2[1:-1, 1:-1][e]
                                                         - b2[1:-1, 1:-1][e]).mean()), 4),
                   "max_ink": round(float(a2[1:-1, 1:-1][e].max()), 3)})
    hard("{} B3 语音时刻字形与母版一致（腐蚀差分 < 0.15）".format(label),
         bool(fr) and all(x["ink_diff_vs_master"] < 0.15 and x["max_ink"] > 0.5 for x in fr), fr)
    tin = round((win[0] + win[1]) / 2, 3)
    a_out, a_in = (frame(film_out, tin, label + "ov", stx["format_duration_s"]),
                   frame(film_in, tin, label + "in", PROD))
    h = a_out.shape[0]
    mid_diff = float(abs(a_out[int(h * 0.18):int(h * 0.55)]
                         - a_in[int(h * 0.18):int(h * 0.55)]).mean())
    bot_diff = float(abs(a_out[int(h * 0.95):] - a_in[int(h * 0.95):]).mean())
    hard("{} C1 叠加层可见（中带 diff > 0.02）且底部 5% 安全区未被占用（< 0.05）".format(label),
         mid_diff > 0.02 and bot_diff < 0.05,
         {"t": tin, "mid_diff": round(mid_diff, 4), "bottom5_diff": round(bot_diff, 4)})
    oow = 950.0 if not (win[0] <= 950.0 <= win[1]) else 300.0
    d_out = float(abs(frame(film_out, oow, label + "oow", stx["format_duration_s"])
                      - frame(film_in, oow, label + "oowi", PROD)).mean())
    hard("{} C2 窗口外区段未变（抽样帧差 < 0.02）+ 时长守恒（切点/时间轴未改）".format(label),
         d_out < 0.02 and abs(stx["format_duration_s"] - PROD) <= TOL,
         {"t": oow, "frame_diff": round(d_out, 4)})
    pre = core_integrity.pre_render_gate(script.get("segments") or [], voice, PROD, GP,
                                         narration_duration_s=voice.get("narration_duration_s"),
                                         narration_plan=plan, cues=cues_dcv2,
                                         narration_padding_s=PROD - float(
                                             voice.get("narration_duration_s") or 0))
    post = core_integrity.post_render_gate(film_out, PROD, cues_dcv2,
                                           voice.get("narration_duration_s"), True, str(FFMPEG),
                                           str(FFPROBE), GP, narration_plan=plan)
    sm = lambda m: {a: (b.get("state") if isinstance(b, dict) else b) for a, b in m.items()}
    st["PI"] = {"pre": sm(pre["metrics"]), "post": sm(post["metrics"]),
                "frozen_recheck": res.get("pi_gate_outcome")}
    hard("{} D1 DCv2 pre-render 未阻断 + PI-1/PI-2/PI-6/G-TL/G-PAD/G-SUB 全 PASS".format(label),
         (not pre["blocked"]) and all(sm(pre["metrics"]).get(g) == "PASS"
                                      for g in ("PI-1", "PI-2", "PI-6", "G-TL", "G-PAD", "G-SUB")),
         {"states": sm(pre["metrics"]), "reasons": pre["reasons"]})
    hard("{} D2 DCv2 post-render：PI-3 PASS 且 promote 未被阻断".format(label),
         sm(post["metrics"]).get("PI-3") == "PASS" and not post.get("promote_blocked"),
         {"PI-3": post["metrics"]["PI-3"], "reasons": post["reasons"]})
    hard("{} D3 冻结复核（DCv2 口径）== PASS".format(label), res.get("pi_gate_outcome") == "PASS",
         res.get("pi_gate_outcome"))
    lum = {str(b): round(float(frame(film_out, b, label + "bd",
                                     stx["format_duration_s"]).mean()), 4)
           for b in (win[0], win[1] - 0.05)}
    hard("{} E1 窗口边界无黑帧".format(label), not [k for k, v in lum.items() if v < 0.02], lum)
    iso = {"history_unchanged": all(sha(HIST[k]) == v for k, v in BEFORE["history"].items()
                                    if HIST[k].is_file()),
           "db_unchanged": sha(ROOT / "projects/video_studio.db") == BEFORE["db"],
           "baseline_unchanged": sorted(p.name for p in
                                        (ROOT / "docs/regression_2x/baseline").glob("*"))
           == BEFORE["baseline"],
           "master_unchanged": sha(ROOT / N0["master"]["path"]) == BEFORE["master"],
           "accepted_chain_unchanged": all(sha(ROOT / e["output_path"]) == e["output_sha256"]
                                           for e in led0),
           "material_plan_unchanged": sha(MP) == BEFORE["matplan"],
           "projects_len_unchanged": len([p for p in (ROOT / "projects/p_96efdc03e1aa").rglob("*")
                                          if p.is_file()]) == BEFORE["projects_len"],
           "output_in_new_sandbox": str(film_out).startswith(str(SANDBOX))}
    hard("{} F1 隔离：历史/DB/baseline/母版/已接受链路/材料计划/项目目录 均未变".format(label),
         all(iso.values()), iso)
    st["isolation"] = iso
    st["subtitle"] = {"ass": s1, "frames": fr}
    st["overlay_check"] = {"t": tin, "mid_diff": round(mid_diff, 4),
                           "bottom5_diff": round(bot_diff, 4)}
    st["outside_window_frame_diff"] = round(d_out, 4)
    st["visual_continuity"] = lum
    st["ffmpeg_calls"] = len([c for c in FF_CALLS if c["stage"] == label])
    st["ffmpeg_argv_head"] = [c["argv"] for c in FF_CALLS if c["stage"] == label][:3]
    entry = EX.append_execution(str(LEDGER), {
        "schema": "revision-execution-v1", "proposal_id": prop["proposal_id"], "label": prop["label"],
        "stage": label, "action": "add_visual_aid", "proposal_sha256": prop_sha,
        "approval_id": appr["approval_id"], "approved_by": "human",
        "input_sha256": sha(film_in), "output_path": stre["path"], "output_sha256": stre["sha256"],
        "duration_s": stx["format_duration_s"], "audio_md5": stre["audio_md5"],
        "timeline_identity": N0["timeline_identity"]["identity_sha256"],
        "caption_time_base": "dcv2", "acceptance": "ACCEPTED",
        "slot_count": 3, "overlay_form": "A", "panels_used": SPECS[label]["kept"],
        "panels_excluded": SPECS[label]["excluded"], "spec_sha256": SPECS[label]["spec_sha256"],
        "pi_states": {**st["PI"]["pre"], **st["PI"]["post"],
                      "frozen_recheck": st["PI"]["frozen_recheck"]},
        "ffmpeg_calls": st["ffmpeg_calls"], "sandbox": str(SANDBOX.relative_to(ROOT)),
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    st["ledger_entry"] = {"seq": entry.get("seq"), "entry_sha256": entry.get("entry_sha256")}
    STAGES.append(st)
    film_in = film_out
    print("   -> {} ({}s, sha {}) ledger seq {}".format(stre["path"], stx["format_duration_s"],
                                                        stre["sha256"][:12], entry.get("seq")))

# DQ（E4/E5 不改时间轴 ⇒ 应不变）
regs = core_revision.load_register(str(REGISTER))
E3SP = None
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
    apply_split(proj, OPX.split_plan({"timeline": [dict(e) for e in TLX], "timeline_identity": None,
                                      "caption_timeline": None}, p), TL_ASSET)
dq = {"DQ-2": core_direction.asset_reuse(proj), "DQ-3": core_direction.static_hold(proj),
      "DQ-4": core_direction.visual_density(proj)}
led = EX.load_ledger(str(LEDGER))
report = {"schema": "phase6g-exec-e4-e5-v1", "stage": "6-G / E4 → E5",
          "state": "E4_E5_ACCEPTED" if not FAIL else "E4_E5_STOPPED_AT_HARD_GATE",
          "human_decision": AUTH,
          "policy_unchanged": {"max_scenes_per_proposal": EX.POLICY["max_scenes_per_proposal"],
                               "max_share_of_film_per_proposal":
                                   EX.POLICY["max_share_of_film_per_proposal"],
                               "a1_tolerance_s": TOL, "panel_kind_unchanged": VA._PANEL_KIND,
                               "thresholds_changed": False, "dq_criteria_changed": False},
          "content_provenance": {k: {"mode": SPECS[k]["mode"], "kept": SPECS[k]["kept"],
                                     "excluded": SPECS[k]["excluded"],
                                     "spec_sha256": SPECS[k]["spec_sha256"],
                                     "titles": SPECS[k]["titles"], "chars": SPECS[k]["chars"],
                                     "material_plan_sha256": sha(MP)} for k in ("E4", "E5")},
          "sandbox": str(SANDBOX.relative_to(ROOT)),
          "stages": STAGES,
          "gates": {"pass": PASS, "fail": FAIL, "failed": FAIL},
          "DQ_measured": {"DQ-2": dq["DQ-2"], "DQ-3": dq["DQ-3"], "DQ-4": dq["DQ-4"],
                          "entries": len(proj), "unchanged_by_E4_E5": True,
                          "no_dq_closure_claim": "**不宣称 Directorial Quality 闭环**"
                                                 "（DQ-2 仍 FAIL）"},
          "ledger": {"path": str(LEDGER.relative_to(ROOT)), "entries": len(led),
                     "chain": EX.verify_chain(led)},
          "register": {"path": str(REGISTER.relative_to(ROOT)), "entries": len(regs),
                       "chain": core_revision.verify_register_chain(regs)},
          "ffmpeg_calls_total": len(FF_CALLS),
          "claims": {"promoted": False, "db_written": False, "baseline_or_tag_changed": False,
                     "historical_artifact_changed": False, "h5_executed": False,
                     "fourth_slot_reintroduced": False, "panel_kind_extended": False,
                     "new_content_added": False, "scope_expanded": False,
                     "threshold_relaxed": False}}
report["report_sha256"] = hashlib.sha256(json.dumps(
    report, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("\n== E4 → E5 汇总 ==")
for s in STAGES:
    print("  {} {} {}s sha {} md5 {} | PI pre {} post {} recheck {} | overlay {}/{} | 窗外 {}".format(
        s["stage"], s["output"]["path"].split("\\")[-1], s["output"]["format_duration_s"],
        s["output"]["sha256"][:12], s["output"]["audio_md5"][:12],
        all(v == "PASS" for v in s["PI"]["pre"].values()),
        all(v == "PASS" for v in s["PI"]["post"].values()), s["PI"]["frozen_recheck"],
        s["overlay_check"]["mid_diff"], s["overlay_check"]["bottom5_diff"],
        s["outside_window_frame_diff"]))
print("  DQ: DQ-2 {} (unique {}) | DQ-3 {} (max_hold {}) | DQ-4 {} ({} /min) | entries {}".format(
    dq["DQ-2"]["state"], dq["DQ-2"].get("unique_assets"), dq["DQ-3"]["state"],
    dq["DQ-3"].get("max_hold_s"), dq["DQ-4"]["state"], dq["DQ-4"].get("scene_changes_per_min"),
    len(proj)))
print("  gates {} PASS / {} FAIL | ledger {} chain_ok {} | register {} | state {}".format(
    len(PASS), len(FAIL), len(led), EX.verify_chain(led).get("ok"), len(regs), report["state"]))
print("report ->", OUT)
sys.exit(1 if FAIL else 0)

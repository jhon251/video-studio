# -*- coding: utf-8 -*-
"""6-G / Batch 2 —— H3c-1 → H3c-2（人工 OPT-1 授权；严格顺序 + 完整验收，任一 HARD 失败即 STOP）。

治理要点（对应人工要求）：
  ① **先正式生成并登记** H3c-1 / H3c-2（新登记链 `phase6g_rebuild_proposal_register.jsonl`），
     记录 proposal_id / sha256；**不**把不存在的"整体 H3c"伪装成冻结对象（provenance 明确标注
     由本回合 OPT-1 授权 + 只读 precheck 的范围生成）；
  ② POLICY 不变（max_scenes=6 / max_share=0.30 / target_hold_s=25.0）；不改任何阈值/门禁/治理策略；
  ③ 输入 = Batch 1 最终链路（E2 输出）；DCv2 timeline + DCv2 caption time base，禁止 v1；
  ④ 不新增 H3c 之外的切点、不扩大范围、不追加第三批；不执行 H5/E3/E4/E5；不 promote。

产出: docs/regression_2x/logs/phase6g_exec_batch2.json
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
from video_studio.ops import execution as OPX                        # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
P2 = json.loads((LOGS / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
N0 = json.loads((LOGS / "phase6g_n0_dcv2_master.json").read_text(encoding="utf-8"))
B1 = json.loads((LOGS / "phase6g_exec_batch1.json").read_text(encoding="utf-8"))
PRE = json.loads((LOGS / "phase6g_h3c_precheck.json").read_text(encoding="utf-8"))
OUT = LOGS / "phase6g_exec_batch2.json"
REGISTER = LOGS / "phase6g_rebuild_proposal_register.jsonl"
LEDGER = LOGS / "phase6g_exec_ledger.jsonl"
FFMPEG, FFPROBE = ROOT / "bin" / "ffmpeg.exe", ROOT / "bin" / "ffprobe.exe"
PROD = 978.656
TS = time.strftime("%Y%m%d_%H%M%S")
SANDBOX = ROOT / "output" / "phase6g_exec_batch2" / TS
CFG = {"tools": {"ffmpeg": {"path": str(FFMPEG), "ffprobe": str(FFPROBE)}}}
MASTER = ROOT / N0["master"]["path"]
chain = P2["remapping_21_segments"]
CW = [{"scene_id": c["scene_id"], "start_s": c["new_audio_window_s"][0],
       "end_s": c["new_audio_window_s"][1]} for c in chain]
TL = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
       "end_s": c["new_timeline_window_s"][1]} for c in chain]
# 场景 → 在用素材（只读 v9 时间轴；切分执行器需要真实素材路径，**不得虚构**）
TL_ASSET = {}
_tmp_con = __import__("sqlite3").connect(
    "file:{}?mode=ro".format((ROOT / "projects" / "video_studio.db").as_posix()), uri=True)
_tmp_con.row_factory = __import__("sqlite3").Row
_tmp_con.execute("PRAGMA query_only=ON")
_tmp_rows = [dict(r) for r in _tmp_con.execute(
    "select type,task_id,path from artifacts where project_id='p_96efdc03e1aa'")]
_tmp_con.close()
_rend0 = json.loads(Path(next(r["path"] for r in _tmp_rows if r["type"] == "render_output"
                              and r.get("task_id") == "t_d0a54bdf1810")).read_text(encoding="utf-8"))
for _e in (_rend0.get("material_timeline") or []):
    if _e.get("selected_asset"):
        TL_ASSET[str(_e.get("scene_id"))] = _e["selected_asset"]
for _e in TL:
    _e["selected_asset"] = TL_ASSET.get(_e["scene_id"], {})
GROUPS = [("H3c-1", ["S04", "S09", "S08", "S14", "S10", "S01"]),
          ("H3c-2", ["S21", "S13", "S19", "S02", "S05", "S20"])]
AUTH = ("人工裁定 OPT-1（本回合）：授权把 H3c 拆为两个合规 proposal 并执行 —— "
        "H3c-1: S04,S09,S08,S14,S10,S01（share 0.2607）；H3c-2: S21,S13,S19,S02,S05,S20"
        "（share 0.2555）；未选择 OPT-2，未修改全局局部化策略")
PASS, FAIL, STAGES = [], [], []
CURRENT, FF_CALLS = {"stage": None}, []
_orig_run = OPX._run


def _rec_run(cmd, timeout=3600):
    FF_CALLS.append({"stage": CURRENT["stage"], "argv": [str(c) for c in cmd][:16]})
    return _orig_run(cmd, timeout=timeout)


OPX._run = _rec_run


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def probe(p: Path) -> dict:
    r = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type", "-of", "json", str(p)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    j = json.loads(r.stdout or "{}")
    return {"duration_s": round(float((j.get("format") or {}).get("duration") or 0), 3),
            "has_video": any(s.get("codec_type") == "video" for s in (j.get("streams") or [])),
            "has_audio": any(s.get("codec_type") == "audio" for s in (j.get("streams") or []))}


def amd5(p: Path) -> str:
    r = subprocess.run([str(FFMPEG), "-v", "error", "-i", str(p), "-map", "0:a", "-c", "copy",
                        "-f", "md5", "-"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return (r.stdout or "").strip().split("=")[-1]


def hard(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:240]))
    if not ok:
        raise RuntimeError("BATCH2_GATE_FAILED: " + name)


def gray(p: Path):
    from PIL import Image                                                   # noqa: E402
    import numpy as np                                                      # noqa: E402
    return np.asarray(Image.open(p).convert("L"), dtype=np.float32) / 255.0


def frame(film: Path, t: float, name: str, dur=None):
    import numpy as np                                                      # noqa: E402
    for i, tt in enumerate([t] + ([max(0.0, min(t, dur - 0.25))] if dur else []) + [max(0.0, t - 0.2)]):
        f = SANDBOX / "work" / "acc_{}_{}_{}.png".format(name, str(t).replace(".", "_"), i)
        subprocess.run([str(FFMPEG), "-y", "-v", "error", "-ss", "{:.3f}".format(tt), "-i",
                        str(film), "-frames:v", "1", str(f)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
        if f.is_file():
            return gray(f)
    return np.zeros((720, 1280), dtype=np.float32)


def mask_at(t: int, ass: Path):
    f = SANDBOX / "work" / "mask_{}.png".format(t)
    subprocess.run([str(FFMPEG), "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=black:s=1280x720:r=1", "-vf",
                    "ass=filename='{}':fontsdir='C\\:/Windows/Fonts'".format(
                        ass.as_posix().replace(":", "\\:")), "-ss", str(int(t)), "-frames:v", "1",
                    str(f)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return gray(f)


def erode(b):
    return (b[1:-1, 1:-1] & b[:-2, 1:-1] & b[2:, 1:-1] & b[1:-1, :-2] & b[1:-1, 2:])


def norm(x):
    return re.sub(r"\s+", "", str(x or "").replace("\\N", "").replace("\\n", ""))


def parse_ass(p: Path):
    out, fmt, sec = [], None, None
    for line in p.read_text(encoding="utf-8").splitlines():
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


# ---------------------------------------------------------------- 输入：Batch 1 最终链路
for d in (SANDBOX / "work", SANDBOX / "out", SANDBOX / "artifacts"):
    d.mkdir(parents=True, exist_ok=True)
b1_last = B1["stages"][-1]["output"]
film_in = ROOT / b1_last["path"]
hard("B0 输入 == Batch 1 最终产物（sha 与记录一致）", sha(film_in) == b1_last["sha256"],
     {"now": sha(film_in)[:16], "recorded": b1_last["sha256"][:16]})
# 读取 script/voice（Batch 1 沙箱内的只读副本）
b1_sb = ROOT / B1["sandbox"]
art = {"script_output": str(b1_sb / "artifacts" / "script_output.json"),
       "voice_output": str(b1_sb / "artifacts" / "voice_output.json")}
script = json.loads(Path(art["script_output"]).read_text(encoding="utf-8"))
voice = json.loads(Path(art["voice_output"]).read_text(encoding="utf-8"))
payload = [{"narration": s["narration"], "duration_s": s.get("duration_s")}
           for s in script["segments"] if str(s.get("narration", "")).strip()]
cues_dcv2 = core_captions.build_cues(payload, windows=[{"start_s": w["start_s"], "end_s": w["end_s"]}
                                                       for w in CW])
cues_v1 = core_captions.build_cues(payload)
plan = N.narration_plan(script, voice)
GP = core_integrity.gate_policy(CFG)
master_ass = SANDBOX / "work" / "dcv2_master.ass"
master_ass.write_text(core_captions.to_ass(cues_dcv2, resolution="1280x720"), encoding="utf-8")

HIST = {"v9": ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"}
m6c = json.loads((LOGS / "phase6c_batch.json").read_text(encoding="utf-8"))
for c in m6c["candidates"]:
    HIST["c" + str(c["index"])] = ROOT / c["film"]
HIST["e1"] = (ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e" / "output" /
              "t_d0a54bdf1810_draft_6c_rp-ad4bbbee7ea2_outro.mp4")
HIST["e2"] = (ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e2" / "output" /
              "t_d0a54bdf1810_draft_6c_rp-bee31dff3335_vaid.mp4")
BEFORE = {"history": {k: sha(p) for k, p in HIST.items() if p.is_file()},
          "db": sha(ROOT / "projects" / "video_studio.db"),
          "baseline": sorted(p.name for p in (ROOT / "docs" / "regression_2x" / "baseline").glob("*")),
          "master": sha(MASTER), "b1": {s["stage"]: s["output"]["sha256"] for s in B1["stages"]},
          "projects_len": len([p for p in (ROOT / "projects" / "p_96efdc03e1aa").rglob("*")
                               if p.is_file()])}


def mk_ctx(film: Path, box: Path) -> dict:
    return OPX.attach_dcv2_time_base(
        {"box": str(box), "root": str(ROOT), "ffmpeg": str(FFMPEG), "ffprobe": str(FFPROBE),
         "config": CFG, "film": str(film), "cues": cues_dcv2, "evidence": None,
         "artifacts": art, "narration_plan": plan}, timeline=TL, caption_windows=CW,
        production_duration_s=PROD, source="docs/regression_2x/logs/phase6f_rebuild_plan_v2.json")


# ---------------------------------------------------------------- ① 生成并登记 H3c-1 / H3c-2
M2 = [json.loads(x) for x in (LOGS / "phase6b_m2_review_ledger_v9.jsonl").read_text(
    encoding="utf-8").splitlines() if x.strip()]
H3_REJ = next(e for e in M2 if e["finding_id"] == "hr-3be9759ba28b" and e["decision"] == "REJECT")
created = []
_existing = core_revision.load_register(str(REGISTER)) if REGISTER.exists() else []
for label, scenes in GROUPS:
    share = round(sum(next(c["new_timeline_window_s"][1] - c["new_timeline_window_s"][0]
                           for c in chain if c["scene_id"] == s) for s in scenes) / PROD, 4)
    prev = next((r for r in _existing if r.get("label") == label), None)
    if prev is not None:
        # 登记链是权威：已登记则**复用**（避免重复登记；make_proposal 含时间戳故不可重算）
        sp = (prev.get("proposed_change") or {}).get("params", {}).get("new_split_plan") or {}
        vy = EX.verify_locality(prev, None)
        hard("{} 复用已登记 proposal（避免重复登记）且局部化合规".format(label), vy["ok"] is True, vy)
        created.append({"label": label, "proposal_id": prev["proposal_id"],
                        "proposal_sha256": EX.proposal_sha256(prev),
                        "register_seq": prev.get("seq"),
                        "register_entry_sha256": prev.get("entry_sha256"),
                        "scenes": scenes, "share_of_film": share, "verify_locality": vy,
                        "verify_proposal_errors": core_revision.verify_proposal(prev),
                        "sub_scenes": sum(r["sub_count"] for r in sp.get("scenes", [])),
                        "new_cuts": [round(x, 3) for r in sp.get("scenes", []) for x in r["cuts"]],
                        "reused_registration": True})
        print("  复用 {} {} sha {} seq {}".format(label, prev["proposal_id"],
                                                 created[-1]["proposal_sha256"][:16],
                                                 prev.get("seq")))
        continue
    dry = {"proposal_id": "DRY", "action": "split_scene",
           "affected_scope": {"scenes": scenes}, "proposed_change": {"params": {"target_hold_s": 25.0}}}
    sp = OPX.split_plan(mk_ctx(film_in, SANDBOX / "work" / "dry"), dry)
    rec = core_revision.make_proposal(
        H3_REJ, H3_REJ, "split_scene", {"scenes": scenes, "window": None},
        {"what": "对 H3c 指定场景按冻结规则切分（OPT-1 拆分后的一个合规批次）",
         "how": "target_hold_s=25.0 在新窗口内均分；保留旁白/字幕/总时长/音轨；旧切点全部 INVALID",
         "params": {"scene_ids": scenes, "target_hold_s": 25.0, "keep_audio": True,
                    "keep_total_duration": True, "new_split_plan": sp,
                    "old_cuts_invalidated": True, "dcv2_plan_sha256": P2["plan_sha256"],
                    "origin": "6-G OPT-1 人工裁定（H3c 拆分）；范围来自只读 precheck "
                              "phase6g_h3c_precheck.json"}},
        {"scenes": scenes, "window": None, "assets": [], "share_of_film": share,
         "windows": [{"scene_id": s, "window_s": next(c["new_timeline_window_s"] for c in chain
                                                      if c["scene_id"] == s)} for s in scenes],
         "not_touching": ["旁白文本", "字幕文本", "时间轴总时长", "未列入本批的场景",
                          "历史 artifact（v9/C1–C4/E1/E2）", "Batch 1 产物"]},
        {"metric": "DQ-3 静态保持", "direction": "子镜 ≤ 25s",
         "basis": "H3c 剩余 >25s 场景（{} 个）中的 6 个".format(PRE["long_hold_count"]),
         "assumption": "切分不改变旁白/字幕/总时长", "not_guaranteed": True},
        constraints={"must_preserve": ["旁白文本", "字幕文本", "时间轴总时长"],
                     "target_hold_s": 25.0, "policy_unchanged": True},
        risk=["子镜碎片化", "与 E1/E2 窗口不重叠（已核）"],
        known_scene_ids=[c["scene_id"] for c in chain],
        discriminator="6g-h3c1" if label == "H3c-1" else "6g-h3c2", label=label,
        evidence_refs=["docs/regression_2x/logs/phase6g_h3c_precheck.json"])
    rec["origin_note"] = ("**本回合新登记**：此前不存在『整体 H3c proposal』（仅是 authorized=false 的"
                          "建议记录）；本 proposal 由人工 OPT-1 裁定授权生成，范围取自只读 precheck，"
                          "参数沿用 H3a/H3b 的冻结规则（target_hold_s=25.0）")
    reg = core_revision.append_proposal(str(REGISTER), rec)
    vy = EX.verify_locality(rec, None)
    hard("{} 提案已登记且局部化合规（share {} ≤ 0.30，scenes {} ≤ 6）".format(
        label, share, len(scenes)), vy["ok"] is True, vy)
    created.append({"label": label, "proposal_id": rec["proposal_id"],
                    "proposal_sha256": EX.proposal_sha256(rec),
                    "register_seq": reg.get("seq"), "register_entry_sha256": reg.get("entry_sha256"),
                    "scenes": scenes, "share_of_film": share,
                    "verify_locality": vy, "verify_proposal_errors": core_revision.verify_proposal(rec),
                    "sub_scenes": sum(r["sub_count"] for r in sp["scenes"]),
                    "new_cuts": [round(x, 3) for r in sp["scenes"] for x in r["cuts"]]})
    print("  登记 {} {} sha {} seq {} | 子镜 {} 切点 {}".format(
        label, rec["proposal_id"], created[-1]["proposal_sha256"][:16],
        reg.get("seq"), created[-1]["sub_scenes"], len(created[-1]["new_cuts"])))

# ---------------------------------------------------------------- ② 严格顺序执行 + 完整验收
proj_tl = [dict(e) for e in TL]
for stage in ("H3a", "H3b"):                      # Batch 1 已完成的切分进入投影
    spx = next(s["exec"]["exec_evidence"]["split_plan"] for s in B1["stages"] if s["stage"] == stage)
    for r in spx["scenes"]:
        base = next(e for e in proj_tl if e["scene_id"] == r["scene_id"])
        dd = r["sub_duration_s"]
        new = [{"scene_id": "{}.{}".format(r["scene_id"], j + 1),
                "start_s": round(r["window"][0] + dd * j, 3),
                "end_s": round(r["window"][0] + dd * (j + 1), 3),
                "selected_asset": None} for j in range(r["sub_count"])]
        i = proj_tl.index(base)
        proj_tl[i:i + 1] = new
asset_of = {}
import sqlite3                                                          # noqa: E402
_con = sqlite3.connect("file:{}?mode=ro".format(
    (ROOT / "projects" / "video_studio.db").as_posix()), uri=True)
_con.row_factory = sqlite3.Row
_con.execute("PRAGMA query_only=ON")
_ro = next(dict(r) for r in _con.execute(
    "select type,task_id,path from artifacts where project_id='p_96efdc03e1aa'"))
_rows = [dict(r) for r in _con.execute(
    "select type,task_id,path from artifacts where project_id='p_96efdc03e1aa'")]
_con.close()
_rend = json.loads(Path(next(r["path"] for r in _rows if r["type"] == "render_output"
                             and r.get("task_id") == "t_d0a54bdf1810")).read_text(encoding="utf-8"))
for e in (_rend.get("material_timeline") or []):
    if e.get("selected_asset"):
        asset_of[str(e.get("scene_id"))] = e["selected_asset"]

for label, scenes in GROUPS:
    CURRENT["stage"] = label
    cinfo = next(c for c in created if c["label"] == label)
    # 从登记链取回该 proposal（append-only 登记链为权威记录）
    regs = core_revision.load_register(str(REGISTER))
    prop = next(r for r in regs if r.get("label") == label)
    box = SANDBOX / "work" / label
    for sd in ("work", "output"):
        (box / sd).mkdir(parents=True, exist_ok=True)
    print("\n===== {} {} =====".format(label, prop["proposal_id"]))
    st = {"stage": label, "proposal_id": prop["proposal_id"],
          "proposal_sha256": EX.proposal_sha256(prop),
          "register_seq": cinfo["register_seq"], "scenes": scenes,
          "share_of_film": cinfo["share_of_film"], "sub_scenes": cinfo["sub_scenes"],
          "input": {"path": str(film_in.relative_to(ROOT)), "sha256": sha(film_in),
                    "duration_s": probe(film_in)["duration_s"]}}
    hard("{} 提案身份（verify_proposal 空 + sha 与登记一致）".format(label),
         core_revision.verify_proposal(prop) == []
         and st["proposal_sha256"] == cinfo["proposal_sha256"], st)
    appr = EX.make_approval(prop, "APPROVE", "human", AUTH,
                            {"authorization": "OPT-1（H3c 拆分执行授权）",
                             "scope": "H3c-1 → H3c-2", "not_authorized": ["H5", "E3", "E4", "E5",
                                                                         "OPT-2"]})
    ctx = mk_ctx(film_in, box)
    ident = OPX.assert_timeline_identity(ctx)
    base_cap = OPX.caption_time_base(ctx)
    hard("{} 前置：DCv2 timeline identity（{}）".format(label, ident.get("identity_sha256", "")[:16]),
         ident.get("enforced") is True
         and ident["identity_sha256"] == N0["timeline_identity"]["identity_sha256"], ident)
    hard("{} 前置：caption time base == DCv2".format(label), base_cap["mode"] == "dcv2", base_cap)
    gate = EX.gate_execution(prop, [appr], None)
    hard("{} execution gate 通过".format(label), gate.get("allowed") is True,
         {"code": gate.get("code"), "why": gate.get("why")})
    res = EX.execute_proposal(prop, [appr], OPX.EXECUTORS, ctx, recheck=OPX.pi_recheck)
    hard("{} 执行 SUCCEEDED".format(label), res.get("state") == "SUCCEEDED",
         {"state": res.get("state"), "why": res.get("why")})
    out_rel = (res.get("outputs") or [{}])[0]["path"]
    film_out = SANDBOX / "out" / "{}_{}.mp4".format(label, prop["proposal_id"])
    shutil.copy2(ROOT / out_rel, film_out)
    pr, md5 = probe(film_out), amd5(film_out)
    st["output"] = {"path": str(film_out.relative_to(ROOT)), "sha256": sha(film_out),
                    "duration_s": pr["duration_s"], "audio_md5": md5, "probe": pr}
    st["exec"] = {"state": res["state"], "steps": len(res.get("steps") or []),
                  "recheck": res.get("recheck"), "pi_gate_outcome": res.get("pi_gate_outcome"),
                  "exec_evidence": res.get("exec_evidence")}
    hard("{} A1 duration == 978.656±0.05（实测 {}）".format(label, pr["duration_s"]),
         abs(pr["duration_s"] - PROD) <= 0.05, pr)
    hard("{} A2 audio identity == 母版（{}）".format(label, md5[:12]), md5 == amd5(MASTER),
         {"out": md5, "master": amd5(MASTER)})
    spx = (res.get("exec_evidence") or {}).get("split_plan") or {}
    aff = []
    for r in spx.get("scenes", []):
        dd = r["sub_duration_s"]
        aff.extend([[round(r["window"][0] + dd * j, 3), round(r["window"][0] + dd * (j + 1), 3)]
                    for j in range(r["sub_count"])])
    ass_files = sorted((box / "work").glob("cap_*.ass"))
    s1 = []
    for ap in ass_files:
        parsed = parse_ass(ap)
        got = False
        for w in aff:
            d = win_sel(cues_dcv2, w[0], w[1])
            if d and len(d) == len(parsed) and all(
                    abs(a["start"] - b["start"]) < 0.02 and abs(a["end"] - b["end"]) < 0.02
                    and norm(a["text"]) == norm(b["text"]) for a, b in zip(parsed, d)):
                s1.append({"ass": ap.name, "window": w, "cues": len(parsed), "dcv2_match": True,
                           "v1_differs": win_sel(cues_v1, w[0], w[1]) != d})
                got = True
                break
        if not got:
            s1.append({"ass": ap.name, "dcv2_match": False, "cues": len(parsed)})
    hard("{} B1 本阶段窗口 ASS == DCv2 表（{} 个窗口）".format(label, len(ass_files)),
         bool(ass_files) and all(m.get("dcv2_match") for m in s1), s1)
    hard("{} B2 同窗口 v1 选择 != DCv2（负对照）".format(label),
         all(m.get("v1_differs") for m in s1), s1)
    fr = []
    for w in aff[:3]:
        cc = [c for c in cues_dcv2 if c["start"] >= w[0] and c["end"] <= w[1]]
        if not cc:
            continue
        t = round((cc[0]["start"] + cc[0]["end"]) / 2, 3)
        m = mask_at(int(t), master_ass)
        ink = m > 0.5
        e = erode(ink)
        a, b = frame(film_out, t, label + "sp", pr["duration_s"]), frame(MASTER, t, label + "mst", PROD)
        if not e.any():
            continue
        fr.append({"t": t, "glyph_core_px": int(e.sum()),
                   "ink_diff_vs_master": round(float(abs(a[1:-1, 1:-1][e]
                                                         - b[1:-1, 1:-1][e]).mean()), 4),
                   "max_ink": round(float(a[1:-1, 1:-1][e].max()), 3)})
    hard("{} B3 语音时刻字形与母版一致（腐蚀差分 < 0.15）".format(label),
         bool(fr) and all(r["ink_diff_vs_master"] < 0.15 and r["max_ink"] > 0.5 for r in fr), fr)
    ce = (res.get("exec_evidence") or {}).get("cut_evidence") or []
    hard("{} C1 切点证据 all_distinct（{} 切点）".format(label, len(ce)),
         bool(ce) and all(c["distinct"] for c in ce), ce)
    hard("{} C2 子镜均 <= 25s（target_hold_s 未改）".format(label),
         all(r["sub_duration_s"] <= 25.0 + 1e-6 for r in spx.get("scenes", [])),
         [(r["scene_id"], round(r["sub_duration_s"], 3)) for r in spx.get("scenes", [])])
    pre = core_integrity.pre_render_gate(script.get("segments") or [], voice, PROD, GP,
                                         narration_duration_s=voice.get("narration_duration_s"),
                                         narration_plan=plan, cues=cues_dcv2,
                                         narration_padding_s=PROD - float(
                                             voice.get("narration_duration_s") or 0))
    post = core_integrity.post_render_gate(film_out, PROD, cues_dcv2,
                                           voice.get("narration_duration_s"), True, str(FFMPEG),
                                           str(FFPROBE), GP, narration_plan=plan)
    stx = lambda m: {a: (b.get("state") if isinstance(b, dict) else b) for a, b in m.items()}
    st["PI"] = {"pre_states": stx(pre["metrics"]), "post_states": stx(post["metrics"]),
                "pre_blocked": pre["blocked"], "post_blocked": post["blocked"],
                "promote_blocked": post.get("promote_blocked"),
                "frozen_recheck": res.get("pi_gate_outcome")}
    hard("{} D1 DCv2 pre-render 未阻断 + 全 PASS".format(label),
         (not pre["blocked"]) and all(stx(pre["metrics"]).get(g) == "PASS" for g in
                                      ("PI-1", "PI-2", "PI-6", "G-TL", "G-PAD", "G-SUB")),
         {"states": stx(pre["metrics"]), "reasons": pre["reasons"]})
    hard("{} D2 DCv2 post-render：PI-3 PASS 且 promote 未被阻断".format(label),
         stx(post["metrics"]).get("PI-3") == "PASS" and not post.get("promote_blocked"),
         {"PI-3": post["metrics"]["PI-3"], "reasons": post["reasons"]})
    hard("{} D3 冻结复核（口径已对齐）为 PASS".format(label), res.get("pi_gate_outcome") == "PASS",
         res.get("pi_gate_outcome"))
    bnd = sorted({round(w[0], 3) for w in aff} | {round(w[1] - 0.05, 3) for w in aff})
    lum = {str(b): round(float(frame(film_out, b, label + "bd", pr["duration_s"]).mean()), 4)
           for b in bnd[:8]}
    st["visual_continuity"] = {"boundary_luma": lum,
                               "black_frames": [k for k, v in lum.items() if v < 0.02]}
    hard("{} E1 边界无黑帧".format(label), not st["visual_continuity"]["black_frames"],
         st["visual_continuity"])
    for r in spx.get("scenes", []):
        base = next(e for e in proj_tl if e["scene_id"] == r["scene_id"])
        dd = r["sub_duration_s"]
        new = [{"scene_id": "{}.{}".format(r["scene_id"], j + 1),
                "start_s": round(r["window"][0] + dd * j, 3),
                "end_s": round(r["window"][0] + dd * (j + 1), 3),
                "selected_asset": asset_of.get(r["scene_id"])} for j in range(r["sub_count"])]
        i = proj_tl.index(base)
        proj_tl[i:i + 1] = new
    dq = {"DQ-2": core_direction.asset_reuse(proj_tl),
          "DQ-3": core_direction.static_hold(proj_tl),
          "DQ-4": core_direction.visual_density(proj_tl)}
    st["DQ_measured"] = {k: v for k, v in dq.items()}
    st["timeline_entries_after"] = len(proj_tl)
    print("   DQ 实测: DQ-2 {} (unique {}) | DQ-3 {} (max_hold {}) | DQ-4 {} ({} /min) | entries {}".format(
        dq["DQ-2"]["state"], dq["DQ-2"].get("unique_assets"),
        dq["DQ-3"]["state"], dq["DQ-3"].get("max_hold_s"),
        dq["DQ-4"]["state"], dq["DQ-4"].get("scene_changes_per_min"), len(proj_tl)))
    iso = {"history_unchanged": all(sha(HIST[k]) == v for k, v in BEFORE["history"].items()
                                    if HIST[k].is_file()),
           "db_unchanged": sha(ROOT / "projects" / "video_studio.db") == BEFORE["db"],
           "baseline_unchanged": sorted(p.name for p in
                                        (ROOT / "docs" / "regression_2x" / "baseline").glob("*"))
           == BEFORE["baseline"],
           "master_unchanged": sha(MASTER) == BEFORE["master"],
           "batch1_unchanged": all(sha(ROOT / B1["stages"][i]["output"]["path"])
                                   == BEFORE["b1"][B1["stages"][i]["stage"]] for i in range(4)),
           "projects_len": len([p for p in (ROOT / "projects" / "p_96efdc03e1aa").rglob("*")
                                if p.is_file()]) == BEFORE["projects_len"],
           "output_in_sandbox": str(film_out).startswith(str(SANDBOX))}
    hard("{} F1 隔离：历史/DB/baseline/母版/**Batch1 产物**/项目目录 均未变".format(label),
         all(iso.values()), iso)
    st["isolation"] = iso
    st["ffmpeg_calls"] = len([c for c in FF_CALLS if c["stage"] == label])
    entry = EX.append_execution(str(LEDGER), {
        "schema": "revision-execution-v1", "proposal_id": prop["proposal_id"], "label": label,
        "action": "split_scene", "proposal_sha256": st["proposal_sha256"],
        "approval_id": appr["approval_id"], "approved_by": "human", "stage": label,
        "input_sha256": st["input"]["sha256"], "output_path": st["output"]["path"],
        "output_sha256": st["output"]["sha256"], "duration_s": pr["duration_s"], "audio_md5": md5,
        "timeline_identity": N0["timeline_identity"]["identity_sha256"], "caption_time_base": "dcv2",
        "pi_states": {**st["PI"]["pre_states"], **st["PI"]["post_states"],
                      "frozen_recheck": st["PI"]["frozen_recheck"]},
        "dq_measured": {k: st["DQ_measured"][k]["state"] for k in ("DQ-2", "DQ-3", "DQ-4")},
        "ffmpeg_calls": st["ffmpeg_calls"], "sandbox": str(SANDBOX.relative_to(ROOT)),
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    st["ledger_entry"] = {"seq": entry.get("seq"), "entry_sha256": entry.get("entry_sha256")}
    STAGES.append(st)
    film_in = film_out

led = EX.load_ledger(str(LEDGER))
led_chain = EX.verify_chain(led)
regs = core_revision.load_register(str(REGISTER))
reg_chain = core_revision.verify_register_chain(regs)
remaining = [{"scene_id": e["scene_id"],
              "duration_s": round(e["end_s"] - e["start_s"], 3)}
             for e in proj_tl if (e["end_s"] - e["start_s"]) > 25.0]
report = {"schema": "phase6g-exec-batch2-v1", "stage": "6-G / Batch 2",
          "state": "BATCH2_SUCCEEDED_AWAITING_HUMAN_AUTHORIZATION" if not FAIL
          else "BATCH2_STOPPED_AT_HARD_GATE",
          "authorized": "OPT-1（H3c → H3c-1 + H3c-2；未选择 OPT-2，未改局部化策略）",
          "policy_unchanged": {"max_scenes_per_proposal": EX.POLICY["max_scenes_per_proposal"],
                               "max_share_of_film_per_proposal":
                                   EX.POLICY["max_share_of_film_per_proposal"],
                               "target_hold_s": 25.0},
          "proposals_created": created,
          "proposal_register": {"path": str(REGISTER.relative_to(ROOT)), "entries": len(regs),
                                "chain": reg_chain},
          "input_chain": {"batch1_final": b1_last["path"], "sha256": b1_last["sha256"]},
          "sandbox": str(SANDBOX.relative_to(ROOT)),
          "stages": STAGES,
          "gates": {"pass": len(PASS), "fail": len(FAIL), "failed": FAIL},
          "ledger": {"path": str(LEDGER.relative_to(ROOT)), "entries": len(led), "chain": led_chain},
          "ffmpeg_calls_total": len(FF_CALLS),
          "ffmpeg_argv_by_stage": {l: [c["argv"] for c in FF_CALLS if c["stage"] == l][:3]
                                   for l, _ in GROUPS},
          "timeline_after_batch2": {"entries": len(proj_tl),
                                    "entries_over_25s": remaining,
                                    "over_25s_count": len(remaining)},
          "DQ_measured_after": {"DQ-2": STAGES[-1]["DQ_measured"]["DQ-2"],
                                "DQ-3": STAGES[-1]["DQ_measured"]["DQ-3"],
                                "DQ-4": STAGES[-1]["DQ_measured"]["DQ-4"],
                                "note": "**实测记录**；H3c 完成后以实测为准，不再追加切分"},
          "batch1_unchanged": all(sha(ROOT / B1["stages"][i]["output"]["path"])
                                  == BEFORE["b1"][B1["stages"][i]["stage"]] for i in range(4)),
          "claims": {"promoted": False, "db_written": False, "baseline_or_tag_changed": False,
                     "historical_artifact_changed": False, "historical_candidates_used": False,
                     "third_batch_authorized": False, "h5_e3_e4_e5_executed": False,
                     "no_self_authorization": True}}
report["report_sha256"] = hashlib.sha256(json.dumps(
    report, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

print("\n== Batch 2 汇总 ==")
for s in STAGES:
    print("  {} {} {}s sha {} md5 {} | pre {} post {} recheck {} | DQ3 {} max_hold {}".format(
        s["stage"], s["output"]["path"].split("\\")[-1], s["output"]["duration_s"],
        s["output"]["sha256"][:12], s["output"]["audio_md5"][:12],
        all(v == "PASS" for v in s["PI"]["pre_states"].values()),
        all(v == "PASS" for v in s["PI"]["post_states"].values()), s["PI"]["frozen_recheck"],
        s["DQ_measured"]["DQ-3"]["state"], s["DQ_measured"]["DQ-3"].get("max_hold_s")))
print("  提案登记 {} 条 chain_ok={} | 执行台账 {} 条 chain_ok={}".format(
    len(regs), reg_chain.get("ok"), len(led), led_chain.get("ok")))
print("  >25s 剩余条目 {} | ffmpeg {} | gates {} PASS / {} FAIL | state {}".format(
    len(remaining), len(FF_CALLS), len(PASS), len(FAIL), report["state"]))
print("report ->", OUT)
sys.exit(1 if FAIL else 0)

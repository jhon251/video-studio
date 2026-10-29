# -*- coding: utf-8 -*-
"""Phase 13-E / P13E-1 结论固化 + 底片谱系守卫（P13E-4 守卫，离线自检）。

结论 (A)：权威底片 = **978.7s DCv2/H5 谱系**；13-D 的 ctx 误绑 **v9 1532s 母片** ⇒ PI 五门 FAIL 系
**底片选择错误的度量伪影**（指纹逐值吻合 v9 历史缺陷）；6-C 的 4/4 BLOCKED 同源（**只登记、不改写历史**）。
本脚本**只写结论文件**（不渲染、不改产物）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

# ---- 权威谱系常量（守卫基准；变更须走新授权）----
AUTHORITATIVE_LINEAGE = {
    "id": "DCv2_H5_978s",
    "film": "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4",
    "sha256": "3b61dafda11c1b9d22381833a00645670ec8b4f25b8fccca813bb7ac63cee0be",
    "duration_s": 978.7,
    "timeline_source": "logs/phase6f_rebuild_plan_v2.json#new_production_timeline",
    "scenes": 21,
    "s05_window": [181.776, 221.862],
    "pi_history": "phase6g_exec_h5.json: PI-1/2/3/4/5/6=PASS, G-TL/G-PAD/G-SUB=PASS, frozen_recheck=PASS",
}
LEGACY_LINEAGE = {
    "id": "v9_1532s",
    "film": "projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4",
    "sha256": "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651",
    "duration_s": 1532.0,
    "s05_window": [245.0, 300.0],
    "known_defects": "#65 PI-1 0.6277(=961.7/1532)；#67 570.344/570.874s 缺口与尾静音；PI-5 73 条 orphan(33.8%)",
    "role": "历史谱系（**不得**作为修订候选底片）",
}
PROXIMITY_S = 1.0


def _duration(p: pathlib.Path) -> float:
    out = subprocess.run([str(R / "bin" / "ffprobe.exe"), "-v", "error", "-show_entries",
                          "format=duration", "-of", "json", str(p)],
                         capture_output=True, text=True).stdout
    return round(float(json.loads(out)["format"]["duration"]), 1) if out else -1.0


def assert_lineage(film: pathlib.Path, *, expected: dict = AUTHORITATIVE_LINEAGE) -> dict:
    """**底片谱系守卫**：给定底片必须与权威谱系（sha256 + 时长）一致，否则抛错（防止再次绑错底片）。"""
    if not film.is_file():
        raise ValueError("底片不存在: {}".format(film))
    sha = hashlib.sha256(film.read_bytes()).hexdigest()
    dur = _duration(film)
    ok_sha = sha == expected["sha256"]
    ok_dur = abs(dur - expected["duration_s"]) <= PROXIMITY_S
    rec = {"film": str(film), "sha256": sha, "duration_s": dur,
           "expected_id": expected["id"], "sha_match": ok_sha, "duration_match": ok_dur,
           "verdict": "LINEAGE_OK" if (ok_sha and ok_dur) else "LINEAGE_MISMATCH"}
    if not (ok_sha and ok_dur):
        raise ValueError("底片谱系不符（禁止据此构建 ctx）: {}".format(json.dumps(rec, ensure_ascii=False)))
    return rec


# ---- 证据重采（只读）----
auth_film = R / AUTHORITATIVE_LINEAGE["film"]
leg_film = R / LEGACY_LINEAGE["film"]
auth_sha = hashlib.sha256(auth_film.read_bytes()).hexdigest()
leg_sha = hashlib.sha256(leg_film.read_bytes()).hexdigest()
plan = json.loads((L / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
tl = plan.get("new_production_timeline") or []
s05_dcv2 = next(({"start_s": e.get("start_s"), "end_s": e.get("end_s")}
                 for e in tl if str(e.get("scene_id")) == "S05"), None)
h5j = json.loads((L / "phase6g_exec_h5.json").read_text(encoding="utf-8"))
pi = h5j.get("PI") or {}
leg_tl_path = None
import sqlite3
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
r = con.execute("select path from artifacts where type='render_output' and task_id='t_d0a54bdf1810' "
                "limit 1").fetchone()
con.close()
leg_tl = json.loads(pathlib.Path(r["path"]).read_text(encoding="utf-8")) if r else {}
s05_v9 = next(({"start_s": e.get("start_s"), "end_s": e.get("end_s")}
               for e in (leg_tl.get("material_timeline") or [])
               if str(e.get("scene_id")) == "S05"), None)

# ---- 守卫自检：正确底片通过、错误底片必须被拒 ----
guard_ok = guard_bad = None
try:
    guard_ok = assert_lineage(auth_film)
except ValueError as exc:
    guard_ok = {"error": str(exc)[:120]}
try:
    assert_lineage(leg_film)
    guard_bad = "MISSED（守卫未拦住 v9 底片 —— 不合格）"
except ValueError:
    guard_bad = "REJECTED（守卫正确拦截 v9 底片）"

conclusion = {
    "schema": "phase13e-p13e1-conclusion-v1",
    "conclusion": "A",
    "conclusion_text": "权威底片 = 978.7s DCv2/H5 谱系（PI 全 PASS）；13-D 的 ctx 误绑 v9 1532s 母片 ⇒ "
                       "PI-1/2/3/5/6 FAIL 系**底片选择错误的度量伪影**，非 S05 替换所致。",
    "authoritative_lineage": AUTHORITATIVE_LINEAGE,
    "legacy_lineage": LEGACY_LINEAGE,
    "evidence": {
        "authoritative_film_sha256_now": auth_sha,
        "legacy_film_sha256_now": leg_sha,
        "authoritative_duration_s": _duration(auth_film),
        "legacy_duration_s": _duration(leg_film),
        "s05_window_dcv2": s05_dcv2,
        "s05_window_v9": s05_v9,
        "s05_window_used_by_13d": [245.0, 300.0],
        "window_match": {"dcv2": s05_dcv2 == {"start_s": 181.776, "end_s": 221.862},
                         "v9": s05_v9 == {"start_s": 245.0, "end_s": 300.0},
                         "13d_used": [245.0, 300.0] == [s05_v9.get("start_s"), s05_v9.get("end_s")]
                         if s05_v9 else False},
        "h5_pi_history": {"pre": pi.get("pre"), "post": pi.get("post"),
                          "frozen_recheck": pi.get("frozen_recheck")},
        "fingerprints": {
            "pi1_0.6277": "= 961.7 / 1532.0（v9 历史值 #65）",
            "pi2_pi3_570": "570.344 / 570.874 s = v9 历史缺陷（#67）",
            "pi5_73_orphans": "73 条 / 33.8% = v9 历史缺陷",
            "pi6_552.16": "≈ 1532.0 − 978.7 = 553.3 s（两谱系时长差）",
        },
        "falsified_hypothesis": "Phase 13-D 的「ctx 时基/字幕基未附着」假设**被证伪**；"
                               "真实根因 = **底片谱系绑定错误**（ctx 以 v9 1532s draft 为 FILM）。",
        "six_c_reattribution": "6-C 的 4/4 BLOCKED **同源**（同样以 v9 1532s draft 为 FILM）"
                               "⇒ 重新定调其**成因**；**不改写其历史记录**（只登记重定调）。",
    },
    "lineage_guard": {"AUTHORITATIVE_LINEAGE": AUTHORITATIVE_LINEAGE,
                      "assert_lineage_ok": guard_ok, "assert_lineage_on_legacy": guard_bad},
    "operational_rule": "任何修订候选（REPLACE/ADD 类）的 ctx **必须以 DCv2/H5 978.7s 谱系为底片**；"
                        "构建前调用 `assert_lineage()`（sha256 + 时长双校验）——不符即拒绝构建。",
    "not_done": ["P13E-2 ctx 修正 + P13-4 幂等重跑（未执行）",
                 "P13E-3 P13-5 运动臂全片候选（未执行）",
                 "tests/ 下的守卫套件（未加入；本阶段仅 stage 层守卫自检）"],
    "zero_render": True, "zero_llm": True, "zero_network": True,
}
out = L / "phase13e_p13e1_conclusion.json"
out.write_text(json.dumps(conclusion, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("结论:", conclusion["conclusion"], "|", conclusion["conclusion_text"][:60])
print("权威底片 sha:", auth_sha[:16], "| 时长:", conclusion["evidence"]["authoritative_duration_s"], "s")
print("v9 底片 sha:", leg_sha[:16], "| 时长:", conclusion["evidence"]["legacy_duration_s"], "s")
print("S05 窗口：DCv2", s05_dcv2, "| v9", s05_v9, "| 13-D 实用", [245.0, 300.0])
print("窗口归属判定:", json.dumps(conclusion["evidence"]["window_match"], ensure_ascii=False))
print("H5 PI 历史:", json.dumps(conclusion["evidence"]["h5_pi_history"], ensure_ascii=False)[:150])
print("守卫：正确底片 ->", str(guard_ok)[:60], "| v9 底片 ->", guard_bad)
print("产物:", out.name)

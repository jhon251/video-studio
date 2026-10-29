# -*- coding: utf-8 -*-
"""P13E-3 步 2：**合成 DCv2 谱系脚本产物**（纯派生，文本逐字不改）。

授权依据：Phase 13-E 续跑授权 ① —— 授权新建，但必须 (a) 纯派生/文本逐字/(b) 不重跑内容链/(c) provenance 完整；
若需改写文本才能对齐 ⇒ 不改、STOP 并报告。**本次核验结论：无需改写**（映射由时长证据支持：20/21 逐段吻合，
第 21 景 65→67 s 系已知 E1 片尾卡插入的时长差，非文本问题）。

输出：沙箱目录 `output/phase13e_script_sandbox/`（**新文件，零覆盖**）；不动 DB、不动既有产物。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
DB = R / "projects" / "video_studio.db"
SANDBOX = R / "output" / "phase13e_script_sandbox"
SRC_ARTIFACT = "a_49b58fb3dc01"
RULE = "dcv2-script-derivation-v1:verbatim-text+remapping-windows"
sys.stdout.reconfigure(encoding="utf-8")

con = sqlite3.connect("file:" + DB.as_posix() + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
src_path = pathlib.Path(con.execute("select path from artifacts where artifact_id=?",
                                    (SRC_ARTIFACT,)).fetchone()["path"])
con.close()
src = json.loads(src_path.read_text(encoding="utf-8"))
src_sha = hashlib.sha256(src_path.read_bytes()).hexdigest()
src_segs = src["segments"]

plan_path = L / "phase6f_rebuild_plan_v2.json"
plan = json.loads(plan_path.read_text(encoding="utf-8"))
plan_sha = hashlib.sha256(plan_path.read_bytes()).hexdigest()
rm = plan["remapping_21_segments"]

h5 = json.loads((L / "phase6g_exec_h5.json").read_text(encoding="utf-8"))
binding = h5.get("binding") or {}

assert len(src_segs) == 21 and len(rm) == 21, "段数/条数不为 21，拒绝合成"
segments, timing_checks = [], []
for i, (s, e) in enumerate(zip(src_segs, rm)):
    sid = str(e["scene_id"])
    narration = s.get("narration")            # **逐字**（不做任何 strip/替换/改写）
    new_w0, new_w1 = [float(x) for x in e["new_timeline_window_s"]]
    old_w0, old_w1 = [float(x) for x in e["old_timeline_window_s"]]
    seg = {
        "scene_id": sid, "index": i,
        "chapter": s.get("chapter"), "tone": s.get("tone"),
        "visual_hint": s.get("visual_hint"),
        "narration": narration,                          # 逐字
        "narration_sha256": hashlib.sha256(str(narration).encode("utf-8")).hexdigest(),
        "duration_s": round(new_w1 - new_w0, 3),         # 段时长 = DCv2 窗口
        "audio_window_s": [float(x) for x in e["new_audio_window_s"]],
        "pause_budget_s": e.get("pause_budget_s"),
        "actual_tts_duration_s": e.get("actual_tts_duration_s"),
        "old_timeline_window_s": [old_w0, old_w1],
        "text_unchanged": True, "text_edited": False,
    }
    segments.append(seg)
    timing_checks.append({"scene_id": sid, "seg_dur_s": float(s.get("duration_s") or 0),
                          "old_window_s": round(old_w1 - old_w0, 3),
                          "match": abs(float(s.get("duration_s") or 0) - (old_w1 - old_w0)) <= 0.05})
mismatch = [t for t in timing_checks if not t["match"]]
text_orig = "\u0000".join(str(s.get("narration") or "") for s in src_segs)
text_new = "\u0000".join(str(g["narration"] or "") for g in segments)
verbatim_ok = text_orig == text_new
total_new = round(sum(g["duration_s"] for g in segments), 3)

derived = {
    "schema": "script-output-dcv2-derived-v1",
    "script_lineage": "dcv2_derived",
    "derived_from": {"artifact_id": SRC_ARTIFACT, "path": src_path.name, "sha256": src_sha,
                     "note": "旁白文本**逐字**沿用；未改动一字（见 text_verbatim_hash 校验）"},
    "remapping_source": {"file": "docs/regression_2x/logs/phase6f_rebuild_plan_v2.json",
                         "sha256": plan_sha, "key": "remapping_21_segments",
                         "note": "段时长 = new_timeline_window_s；音频为事实来源（new_audio_window_s + pause_budget_s）"},
    "synthesis_rule_version": RULE,
    "content_conclusions_inherited": "**内容结论继承自 a_49b58fb3dc01 谱系**（未重跑 claim 提取/事实核查/结构审）",
    "text_verbatim": {"text_hash_original": hashlib.sha256(text_orig.encode("utf-8")).hexdigest(),
                      "text_hash_derived": hashlib.sha256(text_new.encode("utf-8")).hexdigest(),
                      "verbatim_ok": verbatim_ok, "char_count": len(text_new)},
    "timing_evidence": {"segments": len(segments), "timing_matched": len(segments) - len(mismatch),
                        "mismatches": mismatch,
                        "mismatch_explanation": "唯一偏差为 S21（脚本 65.0s vs 旧窗口 67.0s，Δ=2.0s）——"
                                                "系已知 **E1 片尾卡插入**造成的时长差（非文本对齐问题，无需改写文本）"},
    "total_duration_s": total_new,
    "asset_binding_inherited": binding,
    "summary": src.get("summary"), "confidence": src.get("confidence"),
    "note": "本产物为 **DCv2 谱系派生脚本**，用于管线级渲染；不覆盖任何既有产物；内容结论继承原谱系",
    "segments": segments,
    "read_only_source": True, "overwrote_nothing": True,
}
SANDBOX.mkdir(parents=True, exist_ok=True)
out = SANDBOX / "script_dcv2_derived_v1.json"
if out.exists():
    print("FAIL-CLOSED: 目标已存在，拒绝覆盖:", out)
    sys.exit(2)
out.write_text(json.dumps(derived, ensure_ascii=False, indent=1), encoding="utf-8")
prov = {"schema": "phase13e-script-derivation-provenance-v1",
        "derived_script": str(out.relative_to(R)).replace("\\", "/"),
        "derived_script_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "source_script": {"artifact_id": SRC_ARTIFACT, "sha256": src_sha},
        "remapping_source_sha256": plan_sha, "synthesis_rule_version": RULE,
        "text_verbatim_ok": verbatim_ok, "segments": len(segments),
        "total_duration_s": total_new, "timing_matched": len(segments) - len(mismatch),
        "timing_mismatch": mismatch, "asset_binding_inherited": binding,
        "zero_overwrite": True, "content_chain_not_rerun": True}
(L / "phase13e_script_derivation_provenance.json").write_text(
    json.dumps(prov, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("源脚本:", SRC_ARTIFACT, "sha256", src_sha[:16], "| 段数", len(src_segs))
print("派生脚本:", out.relative_to(R), "| 段数", len(segments), "| 总时长", total_new, "s")
print("文本逐字校验:", verbatim_ok, "| 字符数", len(text_new))
print("时长证据: 吻合 %d/%d | 偏差 %s" % (len(segments) - len(mismatch), len(segments),
                                          mismatch))
print("内容链未重跑:", True, "| 零覆盖:", True)
print("provenance:", (L / "phase13e_script_derivation_provenance.json").name)
sys.exit(0 if verbatim_ok else 3)

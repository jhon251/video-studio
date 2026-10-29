# -*- coding: utf-8 -*-
"""`add_visual_aid` —— **集成 / 契约回归**（合成 fixture，**不执行 E2**、不改 v9/C1–C4/DB）。

做法：用 ffmpeg 生成一段**合成小片**（6 s / 640×360 / 静音音轨，位于测试沙箱），
把 `add_visual_aid` 提案指向该合成片，走完整 `core.execution` + `ops.execution` 契约：
  I1 spec_source（**哈希绑定 E2 冻结计划**）⇒ 真实渲染 + 叠加 + 组装 ⇒ SUCCEEDED，证据齐备；
  I2 叠加层**只出现在窗口内**（窗口外帧与源片几乎一致；窗口内差异显著）；
  I3 时长守恒、音轨为合成母版整条流复制（逐字节一致）；
  I4 内联 spec 路径同样可执行；
  I5 fail-closed：非法 spec（含 asset_id）/ spec sha 不符 / 缺 spec ⇒ FAILED、无产物；
  I6 无副作用：v9 母版未变、C1–C4 未变、E1 的 `_6e` 沙箱产物未增加（**E2 未被执行**）。

用法: python tests/visual_aid_integration_test.py
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import execution as EX                          # noqa: E402
from video_studio.core import visual_aid as VA                        # noqa: E402
from video_studio.ops import execution as ops_exec                    # noqa: E402

CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FFMPEG = CFG["tools"]["ffmpeg"]["path"]
LOGS = ROOT / "docs" / "regression_2x" / "logs"
REPORT = LOGS / "phase6e_visual_aid_integration.json"
PLAN = ROOT / "docs" / "regression_2x" / "phase6e_materials" / "phase6e_material_plan.json"
BOX = ROOT / "output" / "phase6b_m4_sandbox" / "vaid_test"
CLIP = BOX / "synthetic_master.mp4"
V9 = ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"
V9_SHA = "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651"
M6C = LOGS / "phase6c_batch.json"
E1_OUT = ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e" / "output"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name, "" if ok else "| " + str(detail)[:320]))


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def inventory(d: Path) -> dict:
    return {str(p.relative_to(d)): (p.stat().st_size, round(p.stat().st_mtime, 3))
            for p in d.rglob("*") if p.is_file()} if d.is_dir() else {}


# ---- 合成 fixture（测试沙箱内；与 v9 / E2 无关）----
if BOX.exists():
    shutil.rmtree(BOX)
(BOX / "work").mkdir(parents=True)
(BOX / "output").mkdir(parents=True)
subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i",
                "color=c=0x303840:s=640x360:d=6:r=25", "-f", "lavfi", "-i",
                "sine=frequency=440:duration=6", "-shortest", "-c:v", "libx264", "-pix_fmt",
                "yuv420p", "-c:a", "aac", "-b:a", "96k", str(CLIP)],
               capture_output=True, text=True, encoding="utf-8", errors="replace")
check("I0 合成 fixture 生成成功（6 s / 640×360 / 含音轨）",
      CLIP.is_file() and ops_exec.probe_media(FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"),
                                              CLIP)["duration_s"] > 5.0)

facts = ops_exec.probe_media(FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"), CLIP)
ctx = {"root": ROOT, "box": str(BOX), "film": CLIP, "artifacts": {}, "files": {},
       "ffmpeg": FFMPEG, "ffprobe": CFG["tools"]["ffmpeg"]["ffprobe"], "config": CFG,
       "timeline": [], "timeline_duration_s": 6.0, "evidence": {}, "cues": [],
       "asset_index": {}, "asset_bindings": {},
       "visual_aid_font": VA.DEFAULT_FONT, "visual_aid_font_sha256": VA._file_sha(
           Path(VA.DEFAULT_FONT))}

def stub_recheck(ctx, proposal, res):
    """合成 fixture 专用 PI/DQ 桩：真实执行才跑 ops_exec.pi_recheck（此处不冒充实测）。"""
    outs = res.get("outputs") or [{}]
    return {"pi_gate_outcome": "PASS", "synthetic_fixture": True, "stub": True,
            "film": outs[0].get("path"), "film_sha256": outs[0].get("sha256"),
            "note": "测试桩：非真实 PI-1..PI-6 实测"}

POLICY = {"require_pi_recheck": False}          # 合成 fixture：跳过真实 PI/DQ（真实执行才跑）
APPROVALS = BOX / "approvals.jsonl"
LEDGER = BOX / "ledger.jsonl"

v9_before, e1_inv_before = sha(V9), inventory(E1_OUT)
m6c = json.loads(M6C.read_text(encoding="utf-8"))
cand_before = {c["index"]: sha(ROOT / c["film"]) for c in m6c["candidates"]}
plan_sha = sha(PLAN)
spec_ref = VA.compile_from_plan_item(json.loads(PLAN.read_text(encoding="utf-8"))["items"]["E2"])
spec_ref_sha = VA.spec_sha256(spec_ref)


def mk_proposal(pid, params, window=(1.0, 3.0), label="VAID-test"):
    return {"schema": "revision-proposal-v1", "proposal_id": pid, "label": label,
            "finding_id": "hr-test", "decision_ref": {"finding_id": "hr-test",
                                                      "decision": "REJECT"},
            "action": "add_visual_aid", "status": "PROPOSED_AWAITING_HUMAN_APPROVAL",
            "approved": False, "executed": False,
            "affected_scope": {"scenes": ["S01"], "window": list(window), "assets": [],
                               "share_of_film": 0.3},
            "proposed_change": {"what": "w", "how": "h", "params": params},
            "expected_effect": {"metric": "x", "direction": "y", "basis": "z",
                                "assumption": "a"},
            "constraints": {}, "risk": [], "provenance": "test"}


# ---- I1 spec_source（哈希绑定 E2 冻结计划）⇒ 真实执行 ----
p1 = mk_proposal("rp-vaid-spec-source",
                 {"spec_source": {"path": str(PLAN.relative_to(ROOT)), "item": "E2",
                                  "sha256": plan_sha}})
ap1 = EX.append_approval(APPROVALS, EX.make_approval(p1, "APPROVE", "human:test",
                                                      "集成测试：合成 fixture", "test-6e"))
b1 = EX.execute_batch([p1], [ap1], ops_exec.EXECUTORS, ctx, policy=POLICY, ledger=LEDGER, recheck=stub_recheck)
r1 = b1["records"][0]
check("I1a 契约执行 SUCCEEDED（executor_invoked=True，未 promote；PI/DQ 为桩）",
      r1["state"] == "SUCCEEDED" and r1.get("executor_invoked") and r1.get("promoted") is False,
      {"state": r1["state"], "why": r1.get("why")})
ev = (r1.get("exec_evidence") or {}).get("visual_aid_evidence") or {}
check("I1b exec_evidence 含 visual_aid_evidence（spec sha / overlay sha / panels）",
      ev.get("spec_sha256") == spec_ref_sha and bool(ev.get("sha256"))
      and [p["id"] for p in ev.get("panels", [])] == ["P1", "P2", "P3"],
      {"spec_sha": ev.get("spec_sha256"), "panels": [p.get("id") for p in ev.get("panels", [])]})
check("I1c 渲染证据齐备：安全区通过 + quote-free + 字体 sha + 渲染文本",
      ev.get("safe_bottom_ok") is True and ev.get("quote_free_verified") is True
      and bool(ev.get("font", {}).get("sha256")) and bool(ev.get("rendered_text")))
check("I1d 渲染文本 = E2 冻结计划文本（阶梯 4 级 + 两篇文献 + 两立场）",
      ev["rendered_text"]["P1"]["lines"] == spec_ref["panels"][0]["items"]
      and "10.2307/2025976" in " ".join(ev["rendered_text"]["P2"]["lines"])
      and len(ev["rendered_text"]["P3"]["lines"]) == 2)
outs = r1.get("outputs") or []
cand = ROOT / outs[0]["path"] if outs else None
check("I1e 候选成片落盘且 sha256 与记录一致",
      cand and cand.is_file() and sha(cand) == outs[0]["sha256"])
check("I1f spec_source 记录（mode/path/sha256/item，可审计）",
      ((r1.get("exec_evidence") or {}).get("visual_aid_spec_source") or {}).get("mode")
      == "spec_source"
      and ((r1.get("exec_evidence") or {}).get("visual_aid_spec_source") or {}).get("sha256")
      == plan_sha)

# ---- I3 时长守恒 + 音轨整条流复制 ----
dc = (r1.get("exec_evidence") or {}).get("duration_check")
ac = (r1.get("exec_evidence") or {}).get("audio_check")
check("I3a 时长守恒（|Δ| ≤ 0.2 s）", abs((dc or {}).get("delta_s", 9)) <= 0.2, dc)
check("I3b 音轨 = 母版整条音轨流复制（逐字节 sha 一致）", (ac or {}).get("identical_stream") is True, ac)

# ---- I2 叠加层只在窗口内（窗口外不受影响）----
def frame(film: Path, t: float, name: str) -> Path:
    out = BOX / "work" / name
    subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", "{:.3f}".format(t), "-i", str(film),
                    "-frames:v", "1", str(out)], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
    return out


d_in = ops_exec._gray_diff(frame(CLIP, 2.0, "src_in.png"), frame(cand, 2.0, "cand_in.png"))
d_out = ops_exec._gray_diff(frame(CLIP, 4.5, "src_out.png"), frame(cand, 4.5, "cand_out.png"))
check("I2a 窗口内帧差异显著（叠加层真实生效）", d_in > 3.0, {"gray_diff_in": d_in})
check("I2b 窗口外帧几乎不变（只改窗口）", d_out < 1.0, {"gray_diff_out": d_out})

# ---- I4 内联 spec 路径 ----
p2 = mk_proposal("rp-vaid-inline", {"visual_aid": spec_ref}, window=(4.0, 5.0))
ap2 = EX.append_approval(APPROVALS, EX.make_approval(p2, "APPROVE", "human:test", "内联", "t"))
b2 = EX.execute_batch([p2], [ap2], ops_exec.EXECUTORS, ctx, policy=POLICY, ledger=LEDGER, recheck=stub_recheck)
r2 = b2["records"][0]
check("I4a 内联 spec 亦可执行（SUCCEEDED，证据齐备）",
      r2["state"] == "SUCCEEDED"
      and ((r2.get("exec_evidence") or {}).get("visual_aid_spec_source") or {}).get("mode")
      == "inline",
      {"state": r2["state"], "why": r2.get("why")})

# ---- I5 fail-closed 三例（都必须 FAILED、无产物）----
bad_spec = dict(spec_ref)
bad_spec["panels"] = [dict(spec_ref["panels"][0])]
bad_spec["panels"][0]["items"] = ["见 asset_432cd85be6f1"]                  # 被否决素材
cases = [
    ("I5a 非法 spec（含被否决 asset_id）⇒ FAILED 且含 VISUAL_AID_FORBIDDEN_ASSET",
     mk_proposal("rp-vaid-bad", {"visual_aid": bad_spec}, window=(1.0, 2.0)),
     "VISUAL_AID_FORBIDDEN_ASSET"),
    ("I5b spec sha 不符 ⇒ FAILED 且含 VISUAL_AID_SPEC_SHA_MISMATCH",
     mk_proposal("rp-vaid-sha", {"spec_source": {"path": str(PLAN.relative_to(ROOT)),
                                                 "item": "E2", "sha256": "0" * 64}},
                 window=(1.0, 2.0)), "VISUAL_AID_SPEC_SHA_MISMATCH"),
    ("I5c 缺 spec（既无 visual_aid 也无 spec_source）⇒ FAILED 且含 VISUAL_AID_SPEC_REQUIRED",
     mk_proposal("rp-vaid-none", {}, window=(1.0, 2.0)), "VISUAL_AID_SPEC_REQUIRED"),
]
for name, prop, code in cases:
    ap = EX.append_approval(APPROVALS, EX.make_approval(prop, "APPROVE", "human:test", "negative",
                                                        "t"))
    b = EX.execute_batch([prop], [ap], ops_exec.EXECUTORS, ctx, policy=POLICY, ledger=LEDGER, recheck=stub_recheck)
    r = b["records"][0]
    check(name, r["state"] == "FAILED" and code in (r.get("why") or "")
          and not (r.get("outputs") or []),
          {"state": r["state"], "why": (r.get("why") or "")[:160]})

# ---- I6 无副作用（E2 未被执行；v9/C1–C4 未变）----
m6c_after = json.loads(M6C.read_text(encoding="utf-8"))
check("I6a v9 母版未被改动", sha(V9) == V9_SHA)
check("I6b C1–C4 未被改动",
      all(sha(ROOT / c["film"]) == cand_before[c["index"]] for c in m6c_after["candidates"]))
check("I6c E1 的 _6e 沙箱产物未增加（E2 未被执行）", inventory(E1_OUT) == e1_inv_before,
      sorted(inventory(E1_OUT).keys()))
check("I6d 测试产物全部位于测试沙箱 vaid_test/ 内",
      all(str(p).startswith(str(BOX)) for p in (cand,)
          if p) and str(BOX).endswith("vaid_test"))

report = {"schema": "visual-aid-integration-v1", "stage": "6-E",
          "synthetic_fixture": {"clip": str(CLIP.relative_to(ROOT)), "duration_s":
                                facts.get("duration_s"), "note": "合成片，与 v9 / E2 无关"},
          "checks": [{"check": n} for n in PASS],
          "failures": FAIL, "pass": len(PASS), "failed": len(FAIL),
          "e2_executed": False, "v9_sha256": sha(V9),
          "i1_candidate": (outs[0] if outs else None),
          "gray_diff_in": d_in, "gray_diff_out": d_out}
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
print("report ->", REPORT)
sys.exit(1 if FAIL else 0)

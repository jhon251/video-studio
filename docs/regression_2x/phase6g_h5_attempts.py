# -*- coding: utf-8 -*-
"""固化 H5 尝试历史（4 次；前 3 次均为**验收 harness 缺陷**，执行器每次产出同一字节输出）。"""
import hashlib
import json
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
FF, FP = str(R / "bin/ffmpeg.exe"), str(R / "bin/ffprobe.exe")
OUT = R / "docs/regression_2x/logs/phase6g_h5_attempts.json"
DQ = json.loads((R / "docs/regression_2x/logs/phase6g_h5_dq_recompute.json").read_text(
    encoding="utf-8"))


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def amd5(p):
    r = subprocess.run([FF, "-v", "error", "-i", str(p), "-map", "0:a", "-c", "copy", "-f", "md5",
                        "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip().split("=")[-1]


def dur(p):
    r = subprocess.run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                        str(p)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return round(float((r.stdout or "0").strip() or 0), 4)


rows = []
for sb in sorted((R / "output/phase6g_exec_h5").glob("*")):
    f = sb / "out/H5_rp-0ebebb71f99c.mp4"
    rows.append({"sandbox": str(sb.relative_to(R)), "has_output": f.is_file(),
                 "output_sha256": sha(f) if f.is_file() else None,
                 "bytes": f.stat().st_size if f.is_file() else None,
                 "duration_s": dur(f) if f.is_file() else None,
                 "audio_md5": amd5(f) if f.is_file() else None})
attempts = {
    "schema": "phase6g-h5-attempts-v1", "stage": "6-G / H5",
    "proposal_id": "rp-0ebebb71f99c", "proposal_sha256":
        "91ad8ffb905756b23f5507de8a1c3118c2a3bed86aadd3a3656242dcf45c5cfd",
    "binding": {"S05": "asset_h5_S05_65377b888b778226",
                "S11": "asset_h5_S11_1e9d2ab4e64ef982"},
    "attempts": [
        {"n": 1, "sandbox": "output/phase6g_exec_h5/20260929_150733",
         "exec_state": "SUCCEEDED（时长/音频/帧数全部达标）",
         "harness_defect": "验收从 res['asset_evidence'] 读取，实际在 "
                           "res['exec_evidence']['asset_evidence'] ⇒ C1 误判为空",
         "ledger_written": False,
         "evidence": "docs/regression_2x/logs/phase6g_h5_attempt1_harness_issue.json"},
        {"n": 2, "sandbox": "output/phase6g_exec_h5/20260929_150838",
         "exec_state": "SUCCEEDED",
         "harness_defect": "C2 采用自设 512×288 拉伸 Pearson（0.2529），偏离项目**冻结指标**"
                           "（48×48 灰度 Pearson，min_corr 0.30）⇒ 指标口径错误",
         "ledger_written": False},
        {"n": 3, "sandbox": "output/phase6g_exec_h5/20260929_150954",
         "exec_state": "SUCCEEDED",
         "harness_defect": "B1/B2 用**并集窗口**比对逐镜 ASS（应各按自身场景窗口）⇒ 误判不匹配",
         "ledger_written": False},
        {"n": 4, "sandbox": "output/phase6g_exec_h5/20260929_151026",
         "exec_state": "SUCCEEDED", "harness_defect": None,
         "acceptance": "ACCEPTED（26/26 gates）", "ledger_written": True, "ledger_seq": 11,
         "notes": "其余验收项一次通过（A1/A3/C1/C2/B1/B2/B3/D1/D2/D3/E1/F1/G1）；"
                  "另修正 DQ 投影缺陷（见 phase6g_h5_dq_recompute.json）"}],
    "determinism": {"all_outputs_byte_identical":
                    len({r["output_sha256"] for r in rows if r["output_sha256"]}) == 1,
                    "output_sha256": sorted({r["output_sha256"] for r in rows
                                             if r["output_sha256"]}),
                    "note": "四次运行参数完全相同（同一 proposal / 同一素材 / 同一绑定）"},
    "sandboxes": rows,
    "disclosure": "前三次的失败**全部发生在验收脚本**（证据键、指标口径、比对窗口），"
                  "执行器每次均产出**同一 sha256** 的成片且不变量全部保持；"
                  "三次未写台账（依设计：先验收后记录）。台账仅 1 条（seq 11，ACCEPTED）。",
    "dq_corrected": {"source": "docs/regression_2x/logs/phase6g_h5_dq_recompute.json",
                     "state_changes": DQ["state_changes"], "unique_count": DQ["unique_count"],
                     "DQ2_detail": DQ["DQ"]["after_H5"]["DQ-2"],
                     "DQ3_detail": DQ["DQ"]["after_H5"]["DQ-3"],
                     "DQ4_detail": DQ["DQ"]["after_H5"]["DQ-4"]},
}
attempts["record_sha256"] = hashlib.sha256(json.dumps(
    attempts, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
).hexdigest()
OUT.write_text(json.dumps(attempts, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("outputs byte-identical across attempts:", attempts["determinism"]["all_outputs_byte_identical"])
for r in rows:
    print("  {} sha {} dur {} md5 {}".format(r["sandbox"], str(r["output_sha256"])[:16],
                                             r["duration_s"], str(r["audio_md5"])[:12]))
d3 = DQ["DQ"]["after_H5"]["DQ-3"]
print("\nDQ-3 after:", json.dumps({k: v for k, v in d3.items() if k != "findings"},
                                  ensure_ascii=False))
print("DQ-3 findings:", json.dumps(d3.get("findings"), ensure_ascii=False)[:400])
d4 = DQ["DQ"]["after_H5"]["DQ-4"]
print("DQ-4 after:", json.dumps({k: v for k, v in d4.items() if k != "findings"}, ensure_ascii=False))
print("attempts ->", OUT)

# -*- coding: utf-8 -*-
"""6-G §4 伴随：对 batch1 已执行结果做**只读复核**（确认 62/62 PASS 事实未被改写）。

只读：不重跑执行、不写 DB、不改任何历史/沙箱产物；仅新增本复核 JSON。
"""
import hashlib
import json
import pathlib
import subprocess
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
FF, FP = str(R / "bin" / "ffmpeg.exe"), str(R / "bin" / "ffprobe.exe")
L = R / "docs" / "regression_2x" / "logs"
OUT = L / "phase6g_batch1_reverify.json"
B1 = json.loads((L / "phase6g_exec_batch1.json").read_text(encoding="utf-8"))
PASS, FAIL = [], []


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def dur(p):
    r = subprocess.run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(p)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return round(float((json.loads(r.stdout or "{}").get("format") or {}).get("duration") or 0), 3)


def amd5(p):
    r = subprocess.run([FF, "-v", "error", "-i", str(p), "-map", "0:a", "-c", "copy", "-f", "md5", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "").strip().split("=")[-1]


def ck(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False)[:200]))


# A. 报告自身未被改写
body = {k: v for k, v in B1.items() if k != "report_sha256"}
recomputed = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                       separators=(",", ":"), default=str).encode()
                            ).hexdigest()
ck("A1 batch1 报告 sha256 自洽（文件未被改写）", recomputed == B1["report_sha256"],
   {"recomputed": recomputed[:16], "recorded": B1["report_sha256"][:16]})
ck("A2 报告门禁计数仍为 62 PASS / 0 FAIL（报告仅存计数与失败项，逐项名称见执行 stdout）",
   B1["gates"]["pass"] == 62 and B1["gates"]["fail"] == 0 and B1["gates"]["failed"] == [],
   {"pass": B1["gates"]["pass"], "fail": B1["gates"]["fail"], "failed": B1["gates"]["failed"]})
ck("A3 4 个阶段状态均为 SUCCEEDED", all(s["exec"]["state"] == "SUCCEEDED" for s in B1["stages"]))

# B. 输出产物字节未变（duration / sha256 / audio md5）
rows = []
for s in B1["stages"]:
    p = R / s["output"]["path"]
    rows.append({"stage": s["stage"], "exists": p.is_file(), "sha256_now": sha(p)[:16],
                 "sha256_recorded": s["output"]["sha256"][:16],
                 "sha_ok": sha(p) == s["output"]["sha256"],
                 "duration_now": dur(p), "duration_recorded": s["output"]["duration_s"],
                 "audio_md5_now": amd5(p)[:14], "audio_md5_recorded": s["output"]["audio_md5"][:14]})
ck("B1 4 个输出文件 sha256 与记录一致（未被改写）", all(r["sha_ok"] for r in rows), rows)
ck("B2 duration 仍为 978.656（±0.05）", all(abs(r["duration_now"] - 978.656) <= 0.05 for r in rows))
ck("B3 audio md5 仍与记录一致", all(r["audio_md5_now"] == r["audio_md5_recorded"] for r in rows))

# C. 执行台账链 + 历史不可变
led = [json.loads(x) for x in (L / "phase6g_exec_ledger.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
sys.path.insert(0, str(R / "src"))
from video_studio.core import execution as EX                        # noqa: E402
chain = EX.verify_chain(led)
ck("C1 执行台账 4 条且链校验 ok", len(led) == 4 and chain.get("ok") is True, chain)
HIST = {"v9": ("projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4", "22705c7d7ea20b40"),
        "e1": ("output/phase6b_m4_sandbox/p_96efdc03e1aa_6e/output/"
               "t_d0a54bdf1810_draft_6c_rp-ad4bbbee7ea2_outro.mp4", "e45d79976856090e"),
        "e2": ("output/phase6b_m4_sandbox/p_96efdc03e1aa_6e2/output/"
               "t_d0a54bdf1810_draft_6c_rp-bee31dff3335_vaid.mp4", "659bd0d7c288cd7b")}
now = {k: sha(R / v[0])[:16] for k, v in HIST.items()}
ck("C2 历史 artifact 前缀未变", all(now[k].startswith(v[1][:16]) for k, v in HIST.items()), now)
m6c = json.loads((L / "phase6c_batch.json").read_text(encoding="utf-8"))
c1 = sha(R / m6c["candidates"][0]["film"])[:16]
ck("C3 C1–C4 候选未变（抽样 C1）", c1.startswith("fcaa4e78"), c1)
ck("C4 母版未变", sha(R / B1["master"]["path"])[:16].startswith("9a534e94b4c70914"))
ck("C5 DB 未变（与 batch1 记录一致）", B1["isolation_final"]["db_unchanged"] is True)
ck("C6 baseline/tag 未变", B1["isolation_final"]["baseline_unchanged"] is True)

res = {"schema": "phase6g-batch1-reverify-v1", "stage": "6-G §4",
       "report_sha256_self_consistent": recomputed == B1["report_sha256"],
       "gates_recorded": {"pass": B1["gates"]["pass"], "fail": B1["gates"]["fail"]},
       "fact_62_62_unchanged": B1["gates"]["pass"] == 62 and B1["gates"]["fail"] == 0
       and all(r["sha_ok"] for r in rows) and all(r["audio_md5_now"] == r["audio_md5_recorded"]
                                                 for r in rows),
       "outputs": rows, "ledger": {"entries": len(led), "chain": chain},
       "history_prefixes": now,
       "checks": {"pass": PASS, "fail": FAIL}, "read_only": True,
       "note": "只读复核：未重跑执行、未改任何产物/DB/台账；结论=batch1 的 62/62 PASS 事实未被改写"}
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
print("reverify ->", OUT)
sys.exit(1 if FAIL else 0)

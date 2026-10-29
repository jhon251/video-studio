"""3.x Phase 3-A：非网络回归批次（逐项 rc + 末尾摘要，落 logs/phase3a_regression_batch.json）。

用法: python docs/regression_2x/phase3a_regression_batch.py [--only NAME,NAME]
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
PY = sys.executable

# (name, argv, 期望, 是否依赖外网, 期望 rc, 说明)
ITEMS = [
    ("provider_unit", [r"tests\material_provider_test.py"], "46/46", False, 0, ""),
    ("taxonomy_unit", [r"tests\material_taxonomy_test.py"], "40/40", False, 0, ""),
    ("attribution_unit", [r"tests\attribution_compliance_test.py"], "24/24", False, 0, ""),
    ("audio_loudness_unit", [r"tests\audio_loudness_test.py"], "32/32", False, 0,
     "3-B：真实音频/真实渲染的响度契约与 fail-closed"),
    ("phase3b_failure_paths", [r"docs\regression_2x\phase3b_failure_paths.py"], "12/12", False, 0,
     "3-B：真实渲染故障注入（关母带链/不可能 TP/无声旁白）"),
    ("report_command", [r"tests\report_command_test.py"], "18/18", False, 0,
     "3-C：run.py report 五类场景 + 只读性验证"),
    ("semantic_check", [r"tests\semantic_check_test.py"], "28/28", False, 0,
     "4-B：离线三态语义验证器（3-A 真值表 S04/S06=MISMATCH、零误报、UNKNOWN 语义、确定性/离线/只读）"),
    ("metrics_readonly", [r"tests\metrics_test.py"], "18/18", False, 0,
     "4-A：只读质量/成本指标（两次输出逐字节一致、provider=none 回归证据、口径分离）"),
    ("human_selection", [r"tests\human_selection_test.py"], "18/18", False, 0,
     "4-C：人审候选替换（人工选定生效 / 池外与不可用一律 fail-closed / 池空 BLOCKED / 只动 decisions+changelog）"),
    ("cost_boundary", [r"docs\regression_2x\phase3c_cost_boundary.py", "--poll-seconds", "0"],
     "成本/素材/残余三口径", False, 0, "3-C：成本边界与 ¥3.24 残余（只读；--poll-seconds 0 跳过余额轮询）"),
    ("narration_contract", [r"tests\narration_contract_test.py"], "PASS", False, 0, ""),
    ("phase2e_failure_paths", [r"docs\regression_2x\phase2e_failure_paths.py"], "29/29", True, 0,
     "6 项（2/5/6/7/8）需要**真实搜索**；Wikimedia 不可达时会失败（环境，非代码）"),
    ("phase2d_boundary_matrix", [r"docs\regression_2x\phase2d_boundary_matrix.py"], "40/40", False, 0, ""),
    ("phase2d_provider_e2e", [r"docs\regression_2x\phase2d_provider_e2e.py"], "PASS", False, 0, ""),
    ("phase2c_trace", [r"docs\regression_2x\phase2c_trace.py"], "38/38", False, 0, ""),
    ("phase2c_fault_matrix", [r"docs\regression_2x\phase2c_fault_matrix.py"], "A/C 出片, B/D BLOCKED",
     False, 0, ""),
    ("run_ingest_test", [r"docs\regression_2x\run_ingest_test.py"], "PASS", False, 0, ""),
    ("e2e_mechanical", [r"docs\regression_2x\run_all_tests.py", "--fresh"], "3 组 SETTLED", False, 0, ""),
    ("suite_all", [r"docs\regression_2x\run_all_suites.py"], "32/32 rc=0", False, 0, ""),
    ("real_small_test", [r"docs\regression_2x\real_small_test.py"], "PASS MockLLM=0", False, 0, ""),
    ("check_binaries", [r"scripts\check_binaries.py"], "PASS", False, 0, ""),
    ("phase2ab_accept_verify", [r"docs\regression_2x\phase2_accept.py", "--verify", "p_ab2b352e06b8"],
     "PASS", False, 0, ""),
    ("phase3a_run1_verify", [r"docs\regression_2x\phase2_accept.py", "--verify", "p_f4b466a4a024"],
     "真实链路项目复核：已补齐外部素材 → 应当 PASS", True, 0,
     "需要真实网络/外部素材；若 Wikimedia 不可达则该复核会失败（按环境记录，不是回归）"),
    ("phase2e_real_provider", [r"docs\regression_2x\phase2e_real_provider.py"], "13/13（需真实网络）",
     True, 0, "真实搜索/下载/上屏；Wikimedia 不可达时会失败（环境）"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    want = [x.strip() for x in args.only.split(",") if x.strip()]
    rows = []
    for name, argv, expect, needs_net, expect_rc, note in ITEMS:
        if want and name not in want:
            continue
        t0 = time.time()
        try:
            r = subprocess.run([PY] + argv, cwd=str(ROOT), capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=3600)
            rc, out = r.returncode, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            rc, out = 124, "TIMEOUT after 3600s"
        (LOGS / "phase3a_{}.log".format(name)).write_text(out, encoding="utf-8")
        tail = [ln.strip() for ln in out.strip().splitlines() if ln.strip()][-2:]
        ratios = re.findall(r"(\d+)\s*/\s*(\d+)\s*(?:passed|通过|pass|ok)", out)
        rows.append({"name": name, "argv": argv, "expect": expect, "needs_network": needs_net,
                     "expect_rc": expect_rc, "as_expected": rc == expect_rc, "note": note,
                     "rc": rc, "seconds": round(time.time() - t0, 1),
                     "ratios": ["{}/{}".format(a, b) for a, b in ratios][-3:],
                     "tail": tail[:2]})
        print("[{:24s}] rc={} (期望 {}) {:>6.1f}s  {}".format(
            name, rc, expect_rc, time.time() - t0, " | ".join(tail)[:110]), flush=True)
    (LOGS / "phase3a_regression_batch.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    unexpected = [r["name"] for r in rows if not r["as_expected"]]
    env = [r["name"] for r in rows if r["needs_network"]]
    print("\n非预期结果（必须为 0）: {}".format(unexpected or "无"))
    print("依赖真实网络的项: {}".format(env or "无"))
    print("json ->", LOGS / "phase3a_regression_batch.json")
    return 0 if not unexpected else 1


if __name__ == "__main__":
    sys.exit(main())

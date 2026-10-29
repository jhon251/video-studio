"""把 phase3a_regression_batch.json 按**修正后的分类**重新判读（不重跑测试）。

原始批次运行时，脚本里 2 项的"是否依赖外网/期望 rc"标注有误；本脚本用修正后的
ITEMS 重新判读同一批原始结果，产出 phase3a_regression_batch_classified.json。
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(ROOT / "docs" / "regression_2x"))
from phase3a_regression_batch import ITEMS  # noqa: E402

raw = json.loads((LOGS / "phase3a_regression_batch.json").read_text(encoding="utf-8"))
meta = {n: {"expect_rc": e, "needs_network": nn, "expect": ex, "note": nt}
        for n, _a, ex, nn, e, nt in ITEMS}

rows, unexpected = [], []
for r in raw:
    m = meta.get(r["name"])
    if not m:
        continue
    ok = r["rc"] == m["expect_rc"]
    rec = {**r, **m, "as_expected": ok}
    rows.append(rec)
    if not ok:
        unexpected.append(r["name"])
    print("[{:24s}] rc={} 期望={} 网络={} {}".format(
        r["name"], r["rc"], m["expect_rc"], "是" if m["needs_network"] else "否",
        "OK" if ok else "**非预期**"))

env_items = [r["name"] for r in rows if r["needs_network"]]
print("\n非预期结果（必须为 0）: {}".format(unexpected or "无"))
print("依赖真实网络（当前环境不可达）: {}".format(env_items or "无"))
for r in rows:
    if r["needs_network"] and r["rc"] != 0:
        print("  - {}: rc={} —— {}".format(r["name"], r["rc"], r.get("note", "")))
out = {"rows": rows, "unexpected": unexpected, "env_dependent": env_items}
(LOGS / "phase3a_regression_batch_classified.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("\njson ->", LOGS / "phase3a_regression_batch_classified.json")
sys.exit(0 if not unexpected else 1)

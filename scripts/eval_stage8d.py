"""V2.1 Stage 8D 一次性验收：证据正文可用性专项（fetch 解码修复 + extract_body 打捞）。

- 不重跑冻结 197；不接生产；不修改 EvidenceSignal 语义 / 聚合四结构 / fact_check / semantic_judge。
- 基线：Stage 8C 已存 fetch 文本（projects/_drafts/s5_dev_v2_collection.json 的 evidence.text）。
- 后测：用修复后的 BingSearchProvider().fetch 重抓 72 个信号 dev URL，经 extract_body 提取正文。
- 产出：正文有效率提升 / JS shell 解决率 / 空正文解决率 / 编码错误解决率 / valid 比例。
- 回放：原始 HTML 与最终正文落盘 projects/_drafts/r1_stage8d_recollect.json。
"""
import json
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.tools.evidence_text_quality import extract_body, quality, plain_text  # noqa: E402
from video_studio.tools.search_provider import BingSearchProvider  # noqa: E402

col = json.loads((ROOT / "projects" / "_drafts" / "s5_dev_v2_collection.json").read_text(encoding="utf-8"))
samples = col["samples"]

_tls = threading.local()


def get_provider() -> BingSearchProvider:
    if not hasattr(_tls, "provider"):
        _tls.provider = BingSearchProvider()
    return _tls.provider


def usable(res: dict) -> bool:
    """extract_body 结果是否算「可用正文」。"""
    return res["status"] == "valid" or res.get("salvaged") is True


def final_status(res: dict) -> str:
    if res.get("salvaged"):
        return "valid"  # js_shell 打捞成功 → 视作可用正文
    return res["status"]


# ---------- 基线（Stage 8C 已存 fetch 文本，用同一新链重判） ----------
base_status = {}
base_rows = []
for s in samples:
    stored = s["evidence"].get("text", "") or ""
    r = extract_body(stored)
    base_status[s["id"]] = final_status(r)
    base_rows.append({"id": s["id"], "stored_len": len(stored),
                      "base_status": final_status(r), "base_salvaged": r.get("salvaged")})

# ---------- 后测（修复后 fetch + extract_body） ----------
def refetch(s):
    url = s["evidence"].get("url", "")
    try:
        page = get_provider().fetch(url)
    except Exception as e:  # noqa: BLE001
        return s["id"], "", False, f"ERR:{type(e).__name__}"
    raw = page.text or ""
    res = extract_body(raw)
    return s["id"], raw, usable(res), final_status(res), res.get("salvaged")


after_rows = {}
with ThreadPoolExecutor(max_workers=6) as ex:
    futs = {ex.submit(refetch, s): s["id"] for s in samples}
    for i, fut in enumerate(as_completed(futs), 1):
        sid, raw, ok, status, salvaged = fut.result()
        after_rows[sid] = {"raw_html_len": len(raw), "body_len": len(plain_text(raw)),
                           "status": status, "usable": ok, "salvaged": salvaged}
        if i % 12 == 0 or i == len(samples):
            print(f"  re-fetch {i}/{len(samples)} ...", flush=True)

# ---------- 汇总 ----------
N = len(samples)
base_dist = Counter(r["base_status"] for r in base_rows)
after_dist = Counter(a["status"] for a in after_rows.values())
print("\n==== Stage 8D 正文可用性（信号 dev 72） ====")
print(f"基线（Stage 8C 已存 fetch）: {dict(base_dist)}")
print(f"后测（修复 fetch + extract_body）: {dict(after_dist)}")

base_usable = sum(1 for r in base_rows if r["base_status"] == "valid" or r["base_salvaged"])
after_usable = sum(1 for a in after_rows.values() if a["usable"])
print(f"\n[1] 正文有效率: {base_usable}/{N}={base_usable/N:.3f} -> {after_usable}/{N}="
      f"{after_usable/N:.3f}  (Δ {after_usable - base_usable:+d})")

# [2] JS shell 解决率（基线 js_shell 子集，后测 salvage 成功或 valid 的占比）
shell_ids = [r["id"] for r in base_rows if r["base_status"] == "js_shell"]
shell_resolved = sum(1 for i in shell_ids if after_rows[i]["usable"])
print(f"[2] JS shell 解决率: {shell_resolved}/{len(shell_ids)} = "
      f"{shell_resolved/len(shell_ids) if shell_ids else 0:.3f}  (基线 js_shell={len(shell_ids)})")

# [3] 空正文解决率（基线 empty 子集，后测可用占比）
empty_ids = [r["id"] for r in base_rows if r["base_status"] == "empty"]
empty_resolved = sum(1 for i in empty_ids if after_rows[i]["usable"])
print(f"[3] 空正文解决率: {empty_resolved}/{len(empty_ids)} = "
      f"{empty_resolved/len(empty_ids) if empty_ids else 0:.3f}  (基线 empty={len(empty_ids)})")

# [4] 编码错误解决率（基线 encoding_error 子集，后测可用占比）
enc_ids = [r["id"] for r in base_rows if r["base_status"] == "encoding_error"]
enc_resolved = sum(1 for i in enc_ids if after_rows[i]["usable"])
print(f"[4] 编码错误解决率: {enc_resolved}/{len(enc_ids)} = "
      f"{enc_resolved/len(enc_ids) if enc_ids else 0:.3f}  (基线 encoding_error={len(enc_ids)})")

# [5] valid 比例（后测最终正文按 status 细分）
print(f"[5] valid 比例（后测）: {after_dist['valid']}/{N}={after_dist['valid']/N:.3f}"
      f" | low_content={after_dist['low_content']}")

# 迁移矩阵（基线 -> 后测）
trans = Counter((base_rows[i]["base_status"], after_rows[samples[i]["id"]]["status"])
                for i in range(N))
print("\n迁移矩阵（基线 -> 后测）:")
for (a, b), v in sorted(trans.items()):
    print(f"  {a:15s} -> {b:15s} : {v}")

# ---------- 落盘回放 ----------
out = {
    "_meta": {"name": "r1_stage8d_recollect",
              "note": "Stage 8D 信号 dev 72 重抓：原始 HTML 与最终正文均已保留，可回放。"},
    "base_dist": dict(base_dist), "after_dist": dict(after_dist),
    "metrics": {"valid_rate_base": base_usable / N, "valid_rate_after": after_usable / N,
                "js_shell_resolved": f"{shell_resolved}/{len(shell_ids)}",
                "empty_resolved": f"{empty_resolved}/{len(empty_ids)}",
                "encoding_resolved": f"{enc_resolved}/{len(enc_ids)}"},
    "per_id": {s["id"]: {"url": s["evidence"].get("url", ""),
                          "base_status": base_rows[i]["base_status"],
                          "after": after_rows[s["id"]]} for i, s in enumerate(samples)},
}
(ROOT / "projects" / "_drafts" / "r1_stage8d_recollect.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nwritten: projects/_drafts/r1_stage8d_recollect.json")

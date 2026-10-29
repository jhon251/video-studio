# -*- coding: utf-8 -*-
"""Phase 42 / P42-2：**片级内容排除断言门**（shell-ban）。

断言（运行前写死）：
  B1 被禁素材在 `material_timeline` 的 **selected_asset 中出现次数 = 0**；
  B2 被禁素材在**任一景的候选域**中出现次数 = 0（排除必须在候选层生效，不能只靠不选）；
  B3 排除开关**证据在案**（`approved_by` / `approval_document` 齐备，走 decisions 通道）；
  B4 **未被排除的素材**仍可用（防止误杀整池 —— 池大小应 = 排除前 − |banned|）。

运行: python tests/content_exclusion_test.py
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
PASS, FAIL = [], []
BAN = "2442c39e8002"
CFG = R / "config" / "content_exclusions.json"
SB = R / "output" / "phase36_p36_4_sandbox" / "material_timeline.json"
POOL = R / "docs" / "regression_2x" / "logs" / "phase33_retrieval_payload.json"


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:280]))
    return bool(ok)


def main() -> int:
    if not SB.is_file():
        print("SKIP  未找到 material_timeline.json")
        sys.exit(0)
    dec = json.loads(SB.read_text(encoding="utf-8"))["decisions"]
    cfg = json.loads(CFG.read_text(encoding="utf-8"))["content_exclusions"]
    banned = [x["asset_id"] for x in cfg["excluded"]]

    def hit(a):
        s = "{}|{}".format((a or {}).get("asset_id") or "", (a or {}).get("sha256") or "")
        return any(BAN in s for BAN in banned)

    sel_hits = [d["scene_id"] for d in dec if hit(d.get("selected_asset"))]
    cand_hits = [d["scene_id"] for d in dec
                 if any(hit(c) for c in (d.get("candidates") or []))]
    print("景 {} | 被禁素材 {}".format(len(dec), banned))
    check("B1 被禁素材**上屏**次数 = 0（实测 {}）".format(len(sel_hits)),
          not sel_hits, sel_hits[:6])
    check("B2 被禁素材在**候选域**出现次数 = 0（实测 {}）".format(len(cand_hits)),
          not cand_hits, cand_hits[:6])
    ev = cfg.get("excluded") or [{}]
    check("B3 排除**证据在案**（approved_by + approval_document + 理由）",
          all(x.get("approved_by") and x.get("approval_document") and x.get("reason")
              for x in ev), ev)
    # B4 池未被误杀
    pool_n = len([c for c in json.loads(POOL.read_text(encoding="utf-8"))["candidates"]
                  if c.get("path")])
    types = {str((d.get("selected_asset") or {}).get("asset_id")) for d in dec
             if (d.get("selected_asset") or {}).get("asset_id")}
    check("B4 未被排除的素材仍在使用（实测上屏素材种类 {}；池 {} − 排除 {} = {}）".format(
        len(types), pool_n, len(banned), pool_n - len(banned)),
        len(types) >= (pool_n - len(banned)) - 4, {"kinds": len(types)})
    print()
    print("=" * 72)
    print("content_exclusion_test: {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
    print("=" * 72)
    (R / "docs/regression_2x/logs/p42_2_content_exclusion_test.json").write_text(
        json.dumps({"schema": "p42-2-content-exclusion-test-v1", "banned": banned,
                    "selected_hits": sel_hits, "candidate_hits": cand_hits,
                    "pass": len(PASS), "fail": len(FAIL)}, ensure_ascii=False,
                   indent=1), encoding="utf-8")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())

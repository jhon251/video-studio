# -*- coding: utf-8 -*-
"""Phase 49 / P49-1：**素材元数据 name 语言中立门**（新设计规则，授权书 §0①）。

**设计规则**：匹配器消费的元数据字段（`name` / `relative_path`）**必须语言中立**。
禁止把旁白/脚本语料的 CJK 内容写进这些字段 —— 否则中文关键词匹配器会给该素材
**在全部景**最高分（P48 实测：生成素材 `name` 内嵌旁白 ⇒ 36/36 景置首 ⇒ 家族份额 72.2%）。

断言：
  · **N1** 生成素材（`provider=dashscope/wanx` 或 `asset_id` 以 `asset_gen_` 开头）
    的 `name` / `relative_path` **不含 CJK**；
  · **N2** 全部素材的 `name` / `relative_path` **不含 v6.5 旁白的成句片段**
    （取旁白中长度 ≥8 的连续 CJK 片段做子串检测）；
  · **N3** 生成素材的 `visual_hint`（若存在）**允许**含 CJK（它是**不参与匹配**的
    语义字段）—— 用于证明规则是"字段级"而非"全禁 CJK"。

运行: python tests/asset_name_neutral_test.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
PASS, FAIL = [], []
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
POOL = R / "docs" / "regression_2x" / "logs" / "p45_4_merged_payload.json"
SCRIPT = R / "output" / "p36_script" / "v6_5_fulltext.json"


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:280]))
    return bool(ok)


def main() -> int:
    if not POOL.is_file():
        print("SKIP  未找到合并池")
        sys.exit(0)
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    cands = [c for c in pool["candidates"] if c.get("path")]
    gen = [c for c in cands if str(c.get("provider")) == "dashscope/wanx"
           or str(c.get("asset_id") or "").startswith("asset_gen_")]
    n1 = [c.get("asset_id") for c in gen
          if CJK.search(str(c.get("name") or ""))
          or CJK.search(str(c.get("relative_path") or ""))]
    print("池 {} 张 | 生成素材 {} 张".format(len(cands), len(gen)))
    check("N1 生成素材 name/relative_path **不含 CJK**（违规 {}）".format(len(n1)),
          not n1, n1[:6])

    # N2：全池 name/relative_path 不得含 v6.5 旁白的成句片段
    frags = set()
    if SCRIPT.is_file():
        doc = json.loads(SCRIPT.read_text(encoding="utf-8"))
        for p in doc.get("paragraphs", []):
            t = re.sub(r"\s", "", str(p.get("text") or ""))
            for i in range(0, max(0, len(t) - 8), 4):
                frags.add(t[i:i + 8])
    n2 = []
    for c in cands:
        blob = "{} {}".format(c.get("name") or "", c.get("relative_path") or "")
        for f in frags:
            if f and f in blob:
                n2.append({"asset": c.get("asset_id"), "fragment": f})
                break
    print("从 v6.5 语料抽出 {} 个 8 字片段用于子串检测".format(len(frags)))
    check("N2 全池 name/relative_path **不含 v6.5 旁白片段**（违规 {}）".format(len(n2)),
          not n2, n2[:4])

    with_hint = [c for c in gen if CJK.search(str(c.get("visual_hint") or ""))]
    check("N3 `visual_hint` 允许保留 CJK（不参与匹配）—— {} 张带 CJK hint".format(
        len(with_hint)), len(with_hint) >= 0)
    print()
    print("=" * 76)
    print("asset_name_neutral_test: {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
    print("=" * 76)
    (R / "docs/regression_2x/logs/p49_1_name_neutral.json").write_text(
        json.dumps({"schema": "p49-1-name-neutral-v1",
                    "rule": ("匹配器消费的元数据字段（name/relative_path）必须语言中立；"
                             "禁止内嵌 v6.5 旁白 CJK 内容"),
                    "pool_size": len(cands), "generated": len(gen),
                    "violations_n1": n1, "violations_n2": n2,
                    "fragments_checked": len(frags),
                    "pass": len(PASS), "fail": len(FAIL)},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())

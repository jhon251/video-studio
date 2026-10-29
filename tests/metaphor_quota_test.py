# -*- coding: utf-8 -*-
"""**比喻配额门**（Phase 38 裁定重发后重定义；机械，防未来回潮）。

裁定 ②（**错在配额定义，不在白名单**）：
  · **原创物件比喻 ≤ 5**　——　当前 3：`封条` / `公共标准件` / `橘子摊`
  · **家常习语不计入配额**　——　`请机器挑刺` / `割肉级别` / `手指头酸`（= 口语资产）
  · **白名单 6 个名目全保留**（不删项）
  · **黑名单词条** = 墙上挂 / 等着还 / 看不到终点 / 沙漠筛沙
    + **文艺收尾拍检测**（段末句含「方向/终点/尽头」且非白名单）

运行: python tests/metaphor_quota_test.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
PASS, FAIL = [], []
CANDIDATES = [ROOT / "output/p36_script/v6_5_fulltext.json",
              ROOT / "output/p36_script/v6_4_fulltext.json"]

# ---- 白名单 6 名目，按裁定 ② 分为两类 ----
OBJECT_METAPHORS = [              # **原创物件比喻**（计入配额 ≤5）
    ("封条", ["封条"], "段9，论点承重"),
    ("公共标准件", ["公共标准件"], "段7"),
    ("橘子摊", ["水果摊", "橘子"], "段5"),
]
COLLOQUIAL_IDIOMS = [             # **家常习语**（不计入配额）
    ("请机器挑刺", ["请机器挑刺", "请机器来挑刺"], "段7"),
    ("割肉级别", ["割肉级别"], "段3"),
    ("手指头酸（虚拟语气）", ["手指头", "酸得抬不起来"], "段1"),
]
WHITELIST_ALL = OBJECT_METAPHORS + COLLOQUIAL_IDIOMS          # 6 名目
QUOTA_MAX = 5

BLACKLIST = ["墙上挂", "等着还", "看不到终点", "沙漠筛沙"]
BLACKLIST_NEAR = ["沙漠", "筛成几堆", "在墙上挂着"]
ARTY_TAIL = ["方向", "终点", "尽头"]
SIMILE = ["像把", "像是", "像一", "如同", "好比", "仿佛", "像一套", "像一份"]


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:280]))
    return bool(ok)


def sents(t):
    return [s.strip() for s in re.split(r"(?<=[。！？])", t) if s.strip()]


def main() -> int:
    p = next((c for c in CANDIDATES if c.is_file()), None)
    if p is None:
        print("SKIP  未找到 v6.4/v6.5 脚本")
        sys.exit(0)
    d = json.loads(p.read_text(encoding="utf-8"))
    ps = d["paragraphs"]
    text = "\n".join(x["text"] for x in ps)
    print("脚本: {}（{} 段）｜配额口径: 原创物件比喻 ≤{}，家常习语不计".format(
        p.name, len(ps), QUOTA_MAX))
    print()

    # ---- Q1 黑名单词条 = 0 ----
    bad = {w: [x["id"] for x in ps if w in x["text"]] for w in BLACKLIST}
    bad = {w: v for w, v in bad.items() if v}
    check("Q1 黑名单词条 = 0（{}）".format("、".join(BLACKLIST)), not bad, bad)

    # ---- Q1b 黑名单近义变体 = 0 ----
    near = {w: [x["id"] for x in ps if w in x["text"]] for w in BLACKLIST_NEAR}
    near = {w: v for w, v in near.items() if v}
    check("Q1b 黑名单近义变体 = 0（{}）".format("、".join(BLACKLIST_NEAR)),
          not near, near)

    # ---- Q2 原创物件比喻 ≤5 ----
    obj = [n for n, needles, _ in OBJECT_METAPHORS if any(nd in text for nd in needles)]
    check("Q2 原创物件比喻 ≤{}（实测 {}：{}）".format(
        QUOTA_MAX, len(obj), "、".join(obj)), len(obj) <= QUOTA_MAX, {"kinds": obj})

    # ---- Q3 家常习语：记录但不计入配额 ----
    idio = [n for n, needles, _ in COLLOQUIAL_IDIOMS if any(nd in text for nd in needles)]
    check("Q3 家常习语如实记录（不计入配额）：{}".format("、".join(idio) or "无"),
          True, {"idioms": idio})

    # ---- Q4 白名单 6 名目全保留（不删项）----
    kept = [n for n, needles, _ in WHITELIST_ALL if any(nd in text for nd in needles)]
    check("Q4 白名单名目全保留（{}/{}）".format(len(kept), len(WHITELIST_ALL)),
          len(kept) == len(WHITELIST_ALL),
          {"missing": [n for n, _, _ in WHITELIST_ALL if n not in kept]})

    # ---- Q5 文艺收尾拍 = 0 ----
    arty = []
    for x in ps:
        ss = sents(x["text"])
        if not ss:
            continue
        last = ss[-1]
        if any(w in last for w in ARTY_TAIL) and not any(
                nd in last for _, needles, _ in WHITELIST_ALL for nd in needles):
            arty.append({"id": x["id"], "last": last[-46:]})
    check("Q5 文艺收尾拍 = 0（段末句含 方向/终点/尽头 且非白名单）", not arty, arty)

    # ---- Q6 非白名单明喻 = 0 ----
    susp = []
    for x in ps:
        for s in sents(x["text"]):
            if any(m in s for m in SIMILE):
                if not any(nd in s for _, needles, _ in WHITELIST_ALL for nd in needles):
                    susp.append({"id": x["id"], "sent": s[:56]})
    check("Q6 非白名单明喻 = 0（可疑 {} 处）".format(len(susp)), not susp, susp)

    print()
    print("=" * 74)
    print("metaphor_quota_test: {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
    if FAIL:
        print("FAILED:", json.dumps(FAIL, ensure_ascii=False))
    print("=" * 74)
    (ROOT / "docs/regression_2x/logs/p38_metaphor_quota.json").write_text(
        json.dumps({"schema": "p38-metaphor-quota-v2", "script": p.name,
                    "quota_definition": "原创物件比喻 ≤5；家常习语不计入配额（裁定 ②）",
                    "object_metaphors": obj, "object_count": len(obj),
                    "quota_max": QUOTA_MAX, "colloquial_idioms": idio,
                    "whitelist_kept": kept, "whitelist_total": len(WHITELIST_ALL),
                    "blacklist_hits": bad, "blacklist_near_hits": near,
                    "arty_tail": arty, "suspicious_similes": susp,
                    "pass": len(PASS), "fail": len(FAIL)},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())

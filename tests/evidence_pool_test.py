"""V2.1 Stage 8A.1 独立工程测试：内容去重（转载链）+ source-tier 分类 gold set。

- 无 LLM；不修改任何冻结集/规则；纯确定性。
- A. 复制/转载：Original→转载A/B/C 应归 1 簇（dup_count=4、独立=1）；不同内容不得误并。
- B. source-tier gold set（tests/data/source_tier_gold.json）。
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.tools.evidence_pool import Pool, normalize_text, source_tier  # noqa: E402

ORIG = ("2024年10月，科学家完成了成年果蝇完整大脑神经图谱的绘制，共识别出约十四万个神经元"
        "与五千万个突触连接。这项研究发表于《自然》期刊，标志着连接组学的重要里程碑，"
        "为理解神经系统的工作原理提供了前所未有的分辨率。")

REPRINT_A = ("【转发】" + ORIG + " 来源：某科技媒体")
REPRINT_B = ("<html><body><p>" + ORIG + "</p><p>免责声明：本文图文来源于网络，版权归原作者所有。</p></body></html>")
REPRINT_C = ORIG + " （原标题：果蝇大脑图谱完成绘制） 转自网络，侵删。"
DIFFERENT = ("苹果公司发布新款手机，采用新一代处理器，影像系统全面升级，续航提升明显，"
             "起售价与上一代保持一致。")


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    # ---------- A. 复制/转载 ----------
    pool = Pool("t_copy", [
        {"url": "https://orig.example.com/a", "title": "果蝇大脑图谱", "text": ORIG},
        {"url": "https://reprint-a.example.com/a", "title": "转发：果蝇大脑图谱", "text": REPRINT_A},
        {"url": "https://reprint-b.example.com/a", "title": "果蝇大脑图谱", "text": REPRINT_B},
        {"url": "https://reprint-c.example.com/a", "title": "果蝇大脑图谱", "text": REPRINT_C},
    ])
    check("转载链归并为 1 个簇", len(pool.clusters) == 1, f"({len(pool.clusters)})")
    check("dup_count=4（同一证据，非 4 个独立来源）",
          pool.clusters[0]["dup_count"] == 4, f"({pool.clusters[0]['dup_count']})")
    check("独立簇数 = 1", pool.stats()["independent_clusters"] == 1)
    check("跨域转载标记 syndicated", pool.clusters[0]["syndicated"] is True)

    pool2 = Pool("t_diff", [
        {"url": "https://a.example.com/1", "title": "果蝇大脑图谱", "text": ORIG},
        {"url": "https://b.example.com/1", "title": "苹果发布新手机", "text": DIFFERENT},
    ])
    check("不同内容不误并（2 簇）", len(pool2.clusters) == 2, f"({len(pool2.clusters)})")

    # ---------- B. source-tier gold set ----------
    gold = json.loads((ROOT / "tests" / "data" / "source_tier_gold.json").read_text(encoding="utf-8"))
    entries = gold["entries"]
    ok = 0
    errors = []
    for e in entries:
        got = source_tier(e["url"], e.get("title", ""), e.get("text", ""))["tier"]
        if got == e["expected"]:
            ok += 1
        else:
            errors.append((e["expected"], got, e["url"][:50]))
    check(f"source-tier gold 准确率 ≥0.8", ok / len(entries) >= 0.8,
          f"({ok}/{len(entries)}={ok/len(entries):.2f})")
    print(f"  错误分类案例: {errors}")
    unknown_n = sum(1 for e in entries if e["expected"] == "unknown")
    check("gold set 含 unknown 样例", unknown_n >= 3, f"({unknown_n})")

    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

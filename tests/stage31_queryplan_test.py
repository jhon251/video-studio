"""Stage 3.1.4 query_plan 测试：open-vocabulary 短语提取 + 无测试主题硬编码。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.stage31.query_plan import extract_phrases, plan_queries  # noqa: E402
from video_studio.stage31 import intent_extract  # noqa: E402


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    # 1) 短语提取：三个失败主题的叙述必须提取出核心内容词（无词库参与）
    cases = [
        ("咖啡", "烘焙炉里，豆子在高温下爆裂，颜色从青绿变成深棕。",
         ["烘焙", "豆子", "爆裂"]),
        ("水稻", "风吹过稻田，稻穗沉甸甸地弯下来。",
         ["稻田", "稻穗"]),
        ("自由", "自由不是没有边界，是边界由你自己画。",
         ["自由", "边界"]),
        ("实体", "袁隆平在试验田里弯着腰。", ["袁隆平", "试验田"]),
    ]
    for name, text, expect in cases:
        phrases = [p["text"] for p in extract_phrases(text)]
        joined = "".join(phrases)
        check(f"{name}: 提取出核心词 {expect}", all(e in joined for e in expect),
              str(phrases))

    # 2) 系统无主题硬编码：词库不得包含水稻/咖啡/自由等测试主题词
    keys = " ".join(intent_extract.FAMILY_KEYS.keys()) + " ".join(
        " ".join(v["lit"] + v["con"] + v["met"]) for v in intent_extract.FAMILIES.values())
    for word in ("水稻", "稻田", "咖啡", "烘焙", "自由", "袁隆平", "郑和"):
        check(f"词库无硬编码 [{word}]", word not in keys)

    # 3) plan_queries 路由结构（离线部分：不依赖网络的字段）
    class _I:
        narration = "袁隆平在试验田里弯着腰，一株一株地找水稻。"
        subject = "test"
        match_type = "DIRECT"
        query_ladder = [("literal", ["office worker desk"])]
    plan = plan_queries(_I())
    check("plan 含 5 条路由键", all(k in plan["routes"] for k in
                                  ("R1_entity", "R2_category", "R3_fulltext",
                                   "R4_legacy", "R5_emotion")))
    check("R3 全文本含叙述短语", any("袁隆平" in q["query"]
                                   for q in plan["routes"]["R3_fulltext"]) or
          any("试验田" in q["query"] for q in plan["routes"]["R3_fulltext"]),
          str([q["query"] for q in plan["routes"]["R3_fulltext"]]))

    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

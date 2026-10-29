"""Stage 3.1.2 VISUAL_INTENT 测试（主题无关版）。

验证：
- 无主题硬编码（SECTION_SHOTS / TOPIC_INTENTS 不存在）；
- 意图由逐镜 narration 动态推导（不同主题不同概念族）；
- 四类关系齐全；字段完整；查询阶梯三级。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import video_studio.stage31.visual_intent as vi  # noqa: E402
from video_studio.stage31.visual_intent import build_intents, intent_to_dict  # noqa: E402

REQUIRED_FIELDS = ["shot_id", "match_type", "material_kind", "subject", "action",
                   "object", "environment", "concept", "mood", "temporal_context",
                   "abstraction_level", "preferred_media_type", "camera_style",
                   "preferred_duration", "avoid_list", "queries_en", "query_ladder",
                   "concepts_pos", "concepts_neg", "rationale", "narration"]


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    # C. 无主题硬编码
    check("无 SECTION_SHOTS", not hasattr(vi, "SECTION_SHOTS"))
    check("无 TOPIC_INTENTS", not hasattr(vi, "TOPIC_INTENTS"))

    # 主题无关动态推导：三个不同主题包
    for key, expect_subject in (("busy", "time"), ("phone", "smartphone"),
                                ("jarvis", "ai")):
        shotlist = ROOT / "output" / "stage31_testpkgs" / key / "shotlist.json"
        intents = build_intents(shotlist, None)
        check(f"{key}: 意图生成", len(intents) >= 8, f"({len(intents)})")
        s01 = intents[0]
        check(f"{key}: S01 口播驱动（subject 含 {expect_subject}）",
              expect_subject in s01.subject.lower(), s01.subject)
        check(f"{key}: 每镜保留原口播", all(v.narration for v in intents))
        check(f"{key}: 查询阶梯三级", all(len(v.query_ladder) == 3 for v in intents))
        check(f"{key}: rationale 非空", all(v.rationale for v in intents))

    # 字段完整性 + 四类关系（用 busy 全量）
    intents = build_intents(ROOT / "output" / "stage31_testpkgs" / "busy" / "shotlist.json", None)
    types = {}
    for v in intents:
        types[v.match_type] = types.get(v.match_type, 0) + 1
        d = intent_to_dict(v)
        missing = [k for k in REQUIRED_FIELDS if k not in d]
        check(f"{v.shot_id} 字段完整", not missing, str(missing))
        check(f"{v.shot_id} subject/concept/rationale 非空",
              all(d.get(k) for k in ("subject", "concept", "rationale")))
    check("四类关系齐全", all(t in types for t in ("DIRECT", "CONCEPTUAL",
                                                  "EMOTIONAL", "RHYTHM")), str(types))

    # 抽象/隐喻检测
    s05 = next(v for v in intents if v.shot_id == "S05")  # 效率变网
    check("S05 抽象概念识别（abstraction_level 非 literal）",
          s05.abstraction_level in ("conceptual", "metaphorical"), s05.abstraction_level)

    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

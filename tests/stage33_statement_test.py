"""stage33 statement/validator 测试（v3：反模板/注意力/安全/完整性）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.stage33.sanitizer import build_context  # noqa: E402
from video_studio.stage33.validator import Validator  # noqa: E402
from video_studio.stage33 import realizer  # noqa: E402


def ctx_for_coral() -> dict:
    pkg = ROOT / "output" / "stage31_realworld" / "coral"
    return build_context(pkg / "V2_FINAL_SCRIPT_JARVIS.md", pkg / "shotlist.json",
                         pkg / "material_pkg_real" / "shot_mapping" / "all_shots.json",
                         ROOT / "output" / "stage32b" / "coral" / "manifests" /
                         "alignment_manifest.json")


def good_stmt(text: str, mat: str | None = None) -> dict:
    return {
        "narrative_intent": "让观众先看到焦点再理解全句",
        "attention_target": text[:4],
        "attention_path": f"第一眼看「{text[:4]}」，第二眼与口播对应",
        "visual_evidence": (f"白名单素材 {mat}" if mat else f"口播原文「{text[:4]}」"),
        "evidence_material": mat,
        "visual_metaphor": (None if mat else f"以原文词「{text[:4]}」为焦点做最小构图演绎"),
        "composition": {"layers": [
            {"role": "background", "content": ("素材画面" if mat else "风格色块"),
             "purpose": "提供语境"},
            {"role": "foreground", "content": f"锚点词「{text[:4]}」",
             "purpose": "注意力焦点"}]},
        "shot_language": "固定机位观察",
        "temporal_behavior": {"stages": [
            {"name": "enter", "action": "锚点词淡入", "purpose": "先让焦点出现"},
            {"name": "hold", "action": "停留", "purpose": "与口播同步"}]},
        "relation_to_previous": {"type": "continuation", "explain": "信息顺序承接"},
        "relation_to_next": {"type": "none", "explain": "由下一镜声明"},
        "graphic_layer": {"text": text[:4], "purpose": "焦点词"},
        "motion": {"necessity": "静止即完整表达，删掉运动观众不会损失信息",
                   "intent": "none", "describe": "保持绝对静止"},
        "audio_relationship": "VO 主导",
        "director_note": f"以「{text[:4]}」为唯一焦点，画面不重复字幕。",
    }


def make_plan(ctx, shots=4):
    beats = []
    i = 0
    for s in ctx["shots"][:shots]:
        parts = realizer.split_n(s["narration"], 2, 5.0)
        mat = (s["whitelisted_candidates"][0]["material_id"]
               if s["whitelisted_candidates"] else None)
        for p in parts:
            i += 1
            beats.append({"beat_id": f"B{i:03d}", "shot_id": s["shot_id"],
                          "beat_text": p, "start": 0.0, "end": 2.5, "duration": 2.5,
                          "beat_types": ["INFO"], "intensity": "LOW",
                          "statement": good_stmt(p, mat),
                          "spec": realizer.build_beat_spec(
                              {"beat_id": f"B{i:03d}", "shot_id": s["shot_id"],
                               "beat_text": p, "start": 0.0, "end": 2.5, "duration": 2.5},
                              good_stmt(p, mat), ctx, {"palette": {"bg": "#0E2A33",
                              "surface": "#16404F", "accent": "#4FC3F7", "text": "#F4F8F9",
                              "highlight": "#FFB74D"}, "typography": {"anchor": 128,
                              "small_anchor": 84, "tag": 30}}, 1)})
    return {"schema_version": "3.3-v3-mvp", "beats": beats, "motifs": [],
            "narrative_arc": {"climax_beat": "B001" if beats else None}}


def main() -> int:
    fails = []

    def check(name, cond, detail=""):
        if not cond:
            fails.append(name)
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    ctx = ctx_for_coral()
    # 1) 基线通过
    plan = make_plan(ctx)
    res = Validator(plan, ctx).run()
    check("基线 statement 通过", res["gate"] in ("PASS", "PASS_WITH_REPAIRS"), res["gate"])

    # 2) 模板名 → REJECT
    plan = make_plan(ctx)
    plan["beats"][0]["statement"]["director_note"] = "因为这是数据句，所以使用 DATA_GRAPHIC 模板"
    res = Validator(plan, ctx).run()
    check("模板名 → REJECTED", res["gate"] == "REJECTED", res["gate"])

    # 3) 模板式句式 → REJECT
    plan = make_plan(ctx)
    plan["beats"][0]["statement"]["director_note"] = "因为这是数据句，所以使用图形模板展示"
    res = Validator(plan, ctx).run()
    check("模板式句式 → REJECTED", res["gate"] == "REJECTED", res["gate"])

    # 4) 幻觉计划（抠像）→ REJECT
    plan = make_plan(ctx)
    plan["beats"][0]["statement"]["temporal_behavior"]["stages"][0]["action"] = "先抠像分割主体"
    res = Validator(plan, ctx).run()
    check("幻觉计划（抠像）→ REJECTED", res["gate"] == "REJECTED", res["gate"])

    # 5) graphic 全文复制（整句）→ REJECT
    plan = make_plan(ctx)
    sid = plan["beats"][0]["shot_id"]
    full = next(s["narration"] for s in ctx["shots"] if s["shot_id"] == sid)
    plan["beats"][0]["statement"]["graphic_layer"]["text"] = full
    res = Validator(plan, ctx).run()
    check("graphic 全文复制（整句）→ REJECTED", res["gate"] == "REJECTED", res["gate"])

    # 6) attention_target 非子串 → 修复
    plan = make_plan(ctx)
    plan["beats"][0]["statement"]["attention_target"] = "不存在的词"
    res = Validator(plan, ctx).run()
    at = plan["beats"][0]["statement"]["attention_target"]
    check("attention_target 非子串 → 修复为原文子串",
          at in plan["beats"][0]["beat_text"], at)

    # 7) motion.necessity 过短 → 修复
    plan = make_plan(ctx)
    plan["beats"][0]["statement"]["motion"]["necessity"] = "无"
    res = Validator(plan, ctx).run()
    check("motion.necessity 过短 → 修复",
          len(plan["beats"][0]["statement"]["motion"]["necessity"]) >= 8)

    # 8) 跨镜素材 → 修复 None
    plan = make_plan(ctx)
    s04mat = next(s["whitelisted_candidates"][0]["material_id"] for s in ctx["shots"]
                  if s["shot_id"] == "S04")
    plan["beats"][0]["statement"]["evidence_material"] = s04mat  # B001 属 S01
    res = Validator(plan, ctx).run()
    check("跨镜素材 → 修复为 None + 隐喻补齐",
          plan["beats"][0]["statement"]["evidence_material"] is None and
          bool(plan["beats"][0]["statement"]["visual_metaphor"]))

    # 9) graphic 超长/非子串 → 修复截断
    plan = make_plan(ctx)
    plan["beats"][0]["statement"]["graphic_layer"]["text"] = "这句话的完整文字超过了十二个字"
    res = Validator(plan, ctx).run()
    gl = plan["beats"][0]["statement"]["graphic_layer"]["text"]
    check("graphic 超长 → 修复 ≤12 且为子串",
          len(gl) <= 12 and gl in plan["beats"][0]["beat_text"], gl)

    # 9b) 自造数字（原文不存在）→ 确定性剔除（TRUTH.FACT_INVENTED）
    plan = make_plan(ctx)
    plan["beats"][0]["statement"]["visual_evidence"] = "温度上升 0.457 ±0.068°C 的实测数据"
    res = Validator(plan, ctx).run()
    ev = plan["beats"][0]["statement"]["visual_evidence"]
    check("自造数字 → 剔除且不残留 ±",
          "0.457" not in ev and "0.068" not in ev and "±" not in ev, ev)

    # 9c) placeholder 泄漏 → 修复
    plan = make_plan(ctx)
    plan["beats"][0]["statement"]["attention_path"] = "第一眼看X→第二眼理解Y"
    res = Validator(plan, ctx).run()
    p2 = plan["beats"][0]["statement"]["attention_path"]
    check("placeholder 泄漏 → 修复为具体内容", "X" not in p2 and "Y" not in p2, p2)

    # 9d) path/target 不一致（target 非数字但 path 说"看数字"）→ 修复
    plan = make_plan(ctx)
    plan["beats"][0]["statement"]["attention_path"] = "第一眼看数字，再理解全句"
    res = Validator(plan, ctx).run()
    p3 = plan["beats"][0]["statement"]["attention_path"]
    check("path/target 不一致 → 修复（非数字 target 不提数字）",
          "数字" not in p3, p3)

    # 9e) motion 矛盾（intent≠none 但 necessity 声称静止）→ 修复 intent=none
    plan = make_plan(ctx)
    plan["beats"][0]["statement"]["motion"] = {
        "necessity": "静止即完整表达，删掉运动观众不会损失信息",
        "intent": "attention_shift", "describe": "焦点移动"}
    res = Validator(plan, ctx).run()
    check("motion 矛盾 → 修复为一致静止",
          plan["beats"][0]["statement"]["motion"]["intent"] == "none")

    # 10) junk 超 5% → REJECTED（用 SAFETY 类 junk：全 beat 跨镜素材）
    plan = make_plan(ctx, shots=2)
    s04mat = next(s["whitelisted_candidates"][0]["material_id"] for s in ctx["shots"]
                  if s["shot_id"] == "S04")
    for b in plan["beats"]:
        b["statement"]["evidence_material"] = s04mat
    res = Validator(plan, ctx).run()
    check("junk 超 5% → REJECTED", res["gate"] == "REJECTED", res["gate"])

    print(f"\nstatement/validator test: {'FAIL' if fails else 'ALL PASS'} ({len(fails)} fails)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

"""stage33 realizer 测试（split_n 落地 + 帧规格构建）。"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.stage33 import realizer  # noqa: E402
from video_studio.stage33.sanitizer import build_context  # noqa: E402
from video_studio.stage33.planner_fallback import run_fallback  # noqa: E402


def main() -> int:
    fails = []

    def check(name, cond, detail=""):
        if not cond:
            fails.append(name)
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    pkg = ROOT / "output" / "stage31_realworld" / "coral"
    ctx = build_context(pkg / "V2_FINAL_SCRIPT_JARVIS.md", pkg / "shotlist.json",
                        pkg / "material_pkg_real" / "shot_mapping" / "all_shots.json",
                        ROOT / "output" / "stage32b" / "coral" / "manifests" /
                        "alignment_manifest.json")
    # split_n 逐字覆盖
    cov_ok = True
    for s in ctx["shots"]:
        for n in (1, 2, 3):
            parts = realizer.split_n(s["narration"], n, s["timing"]["duration"])
            if "".join(parts) != s["narration"]:
                cov_ok = False
    check("split_n 任意 n 逐字覆盖原文（无截断）", cov_ok)

    # fallback statement → spec
    out = run_fallback(ctx)
    style = {"palette": {"bg": "#0E2A33", "surface": "#16404F", "accent": "#4FC3F7",
                         "text": "#F4F8F9", "highlight": "#FFB74D"},
             "typography": {"anchor": 128, "small_anchor": 84, "tag": 30}}
    s01 = out["shots"]["S01"]["beats"]
    beat = {"beat_id": "B001", "shot_id": "S01", "beat_text": s01[0]["beat_text"],
            "start": 0.0, "end": 4.4, "duration": 4.4}
    spec = realizer.build_beat_spec(beat, s01[0], ctx, style, 7)
    check("spec 层数 ≤3 且每层有种类", 0 < len(spec["layers"]) <= 3)
    check("锚点词非空且 ≤12", 0 < len(spec["anchor_text"]) <= 12)
    check("锚点词来自原文", spec["anchor_text"] in beat["beat_text"])
    check("alpha 帧长度 == 总帧数", all(len(l["alpha_frames"]) == spec["n_frames"]
                                        for l in spec["layers"] if "alpha_frames" in l))
    check("motion intent 枚举合法", spec["motion_intent"] in
          ("attention_shift", "process_expression", "revelation", "none"))
    # 无素材 S01 → 无 material 层，有 rounded_rect + anchor_text
    kinds = [l["kind"] for l in spec["layers"]]
    check("无素材 beat 用色块+锚点（无 material 层）",
          "material" not in kinds and "anchor_text" in kinds)
    # 有素材 S04 → material 层存在
    s04 = out["shots"]["S04"]["beats"]
    beat4 = {"beat_id": "B002", "shot_id": "S04", "beat_text": s04[0]["beat_text"],
             "start": 0.0, "end": 6.0, "duration": 6.0}
    spec4 = realizer.build_beat_spec(beat4, s04[0], ctx, style, 7)
    check("有素材 beat 含 material 层",
          any(l["kind"] == "material" for l in spec4["layers"]))
    # fallback 字节级确定
    out2 = run_fallback(ctx)
    check("fallback statement 两次字节级一致",
          json.dumps(out, ensure_ascii=False, sort_keys=True) ==
          json.dumps(out2, ensure_ascii=False, sort_keys=True))
    # 反模板：fallback 文本不含模板名
    from video_studio.stage33 import schemas as S
    blob = json.dumps(out, ensure_ascii=False)
    check("fallback 输出无模板名",
          not any(bad in blob for bad in S.TEMPLATE_NAMES_BLACKLIST))

    print(f"\nrealizer test: {'FAIL' if fails else 'ALL PASS'} ({len(fails)} fails)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

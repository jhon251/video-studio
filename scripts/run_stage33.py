"""Stage 3.3 v3-mvp runner。

用法（.venv_tts 运行）：
  python scripts/run_stage33.py plan --pkg output/stage31_realworld/coral \
      --align output/stage32b/coral/manifests/alignment_manifest.json \
      --out output/stage33/coral/v3 [--fallback] [--force]
  python scripts/run_stage33.py execute --out output/stage33/coral/v3 [--force]
  python scripts/run_stage33.py gate --out output/stage33/coral/v3
  python scripts/run_stage33.py compare --out output/stage33/coral/v3
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["plan", "execute", "gate", "compare"])
    ap.add_argument("--pkg", default="", help="项目包目录（plan 用）")
    ap.add_argument("--align", default="", help="alignment_manifest.json（plan 用）")
    ap.add_argument("--out", required=True, help="3.3 v3 输出目录")
    ap.add_argument("--fallback", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    out = ROOT / args.out

    if args.stage == "plan":
        from video_studio.stage33.plan_builder import build_plan
        r = build_plan(ROOT / args.pkg, ROOT / args.align if args.align else None,
                       out, use_fallback=args.fallback, force=args.force)
        if r.get("skipped"):
            return 0
        print(json.dumps({k: r.get(k) for k in ("fingerprint", "plan_sha", "gate")},
                         ensure_ascii=False, indent=2))
        return 0 if r["gate"] in ("PASS", "PASS_WITH_REPAIRS") else 3

    plan_path = out / "visual_plan.json"
    if not plan_path.exists():
        sys.exit(f"缺少 visual_plan：{plan_path}（先跑 plan）")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    if args.stage == "execute":
        from video_studio.stage33.executor import execute_v3
        import shutil
        r = execute_v3(plan, out / "exec", force=args.force)
        print(f"render_gate={r['render_gate']['gate']} qc_gate={r['qc_gate']['gate']}")
        shutil.copy(out / "exec" / "production" / "final_preview.mp4",
                    ROOT / "output" / "stage33" / "coral" / "stage33_p1_v3.mp4")
        shutil.copy(out / "exec" / "production" / "final_preview.mp4",
                    out / "stage33_p1_v3.mp4")
        print("C 版: output/stage33/coral/stage33_p1_v3.mp4（副本于 v3 目录）")
        ok = r["render_gate"]["gate"] == "PASS" and r["qc_gate"]["gate"] == "PASS"
        return 0 if ok else 8

    if args.stage == "gate":
        from video_studio.stage33.visual_qc import run_gates
        g = run_gates(plan, out / "exec")
        print(json.dumps(g["gates"], ensure_ascii=False, indent=2))
        ok = all(v == "PASS" for v in g["gates"].values())
        return 0 if ok else 9

    if args.stage == "compare":
        from video_studio.stage33.visual_qc import make_contact_sheets, \
            statement_frame_consistency
        import shutil
        rev_dir = ROOT / "output" / "stage33" / "coral" / "v3" / "review"
        rev_dir.mkdir(parents=True, exist_ok=True)
        videos = {
            "A_legacy": ROOT / "output" / "stage33" / "coral" / "legacy_3.2b.mp4",
            "B_p1": ROOT / "output" / "stage33" / "coral" / "stage33_p1_m4.mp4",
            "C_v3": ROOT / "output" / "stage33" / "coral" / "stage33_p1_v3.mp4",
        }
        sheets = make_contact_sheets(videos, rev_dir)
        g7 = statement_frame_consistency(plan, out / "exec")
        md = write_compare_md(plan, sheets, g7)
        (ROOT / "docs" / "STAGE33_V3_MVP_VISUAL_REVIEW.md").write_text(md, encoding="utf-8")
        print("对照材料: docs/STAGE33_V3_MVP_VISUAL_REVIEW.md")
        print(f"抽帧: {sheets}")
        return 0
    return 2


def write_compare_md(plan: dict, sheets: dict | None = None, g7: dict | None = None) -> str:
    beats = plan["beats"]
    L = ["# Stage 3.3 V3-MVP 人工观看对照（Coral · A/B/C）", "",
         "> 三版同 VO/字幕/时长/规格/响度链，唯一变量=视觉表达。机器 Gate 只证明完整性；"
         "**好不好看由人工裁决。**", "",
         "## 三个版本", "",
         "| 版 | 路径 | 说明 |", "|---|---|---|",
         "| A = 3.2b legacy | `output/stage33/coral/legacy_3.2b.mp4` | 静态卡+照片 Ken Burns |",
         "| B = P1 | `output/stage33/coral/stage33_p1_m4.mp4` | 模板图形+zoompan 运动（含抖动） |",
         "| C = V3-MVP | `output/stage33/coral/stage33_p1_v3.mp4` | Visual Statement+整数帧运动+静止优先 |",
         ""]
    if sheets:
        L += ["## 抽帧材料（20 镜中帧 5×4）", ""]
        for tag, p in sheets.items():
            L.append(f"- {tag}: `{p}`")
        L += [""]
    L += ["## C 版逐镜 statement → 画面对照（机器证据 G7）", "",
          "| beat | 镜 | 口播 | 焦点(锚点词) | 层数 | 素材层 | enter时序 | 与上镜关系 | G7 |",
          "|---|---|---|---|---|---|---|---|---|"]
    g7map = {r["beat_id"]: r for r in (g7 or {}).get("rows", [])} if g7 else {}
    for b in beats:
        sp = b["spec"]
        st = b["statement"]
        r = g7map.get(b["beat_id"], {})
        L.append(f"| {b['beat_id']} | {b['shot_id']} | {b['beat_text'][:12]}… | "
                 f"{sp['anchor_text'][:8]} | {len(sp['layers'])} | {r.get('has_material', '?')} | "
                 f"{r.get('has_enter', '?')} | {r.get('relation_to_prev', '')} | "
                 f"{'OK' if r.get('ok') else (r.get('problems') or 'NA')} |")
    if g7:
        L += ["", "## Attention handoff（arc.flow 文本侧证据）", "",
              "| 镜 | 焦点提示 | 与上镜关系 |", "|---|---|---|"]
        for h in g7.get("handoff_rows", []):
            L.append(f"| {h['shot_id']} | {h['focus_hint'][:24]} | {h['relation']} |")
    L += ["", "## 12 项失败模式检查（对照 B 的教训）", "",
          "| 模式 | 机器证据（C 版） | 人工裁决 |", "|---|---|---|",
          "| PPT 感 | 图形层锚点化（≤12 字），无全文卡 | 人工 |",
          "| 完整字幕重复到画面 | statement_audit：graphic ⊆ 原文且 ≤12 | 人工 |",
          "| 全屏文字 | 同上 | 人工 |",
          "| 连续同构画面 | 层结构逐 beat 见上表 | 人工 |",
          "| 画面与语言无关系 | attention_target 必须原文子串（gate） | 人工 |",
          "| 运动只为有运动 | motion.necessity 必填 + none=绝对静止 + 降级链 | 人工 |",
          "| 静态图堆积 | 素材层带时序（enter/hold） | 人工 |",
          "| 图形只是换皮文字卡 | 锚点词 ≤12 字 + 层级 + 时序 | 人工 |",
          "| 镜头间无注意力关系 | relation 声明（5 类型）逐 beat 必填 | 人工 |",
          "| 高潮=更多元素 | 高潮=注意力落差（climax_beat） | 人工 |",
          "| 画面无层级 | layers 1-3 层每层有 purpose | 人工 |",
          "| 莫名其妙抖动 | **jitter=0 硬 Gate（25fps 帧差审计）** | 人工复核 |",
          "", "## 8 维人工评分（1–5，只评 C 版）", "",
          "| 维度 | 分数 | 证据 |", "|---|---|---|",
          "| 表达准确性 |  |  |", "| 视觉层级 |  |  |", "| 镜头关系 |  |  |",
          "| 节奏 |  |  |", "| 运动合理性 |  |  |", "| 信息可视化 |  |  |",
          "| 风格一致性 |  |  |", "| 完成度 |  |  |", "| 合计/40 |  |  |",
          "", "## 最终裁决（三选一，必须附证据镜头）", "",
          "**CLEARLY_BETTER** / **BETTER_BUT_NOT_ENOUGH** / **NOT_MEANINGFULLY_BETTER**", "",
          "- 裁决：______________", "- 证据镜头（正/反）：______________",
          "", "## 核心问题（必须回答）", "",
          "**V3 是否终于把“视觉设计”从 JSON 里的理念，变成了屏幕上真正能被人感受到的东西？**", ""]
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())

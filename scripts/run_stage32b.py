"""Stage 3.2b runner（P0 各阶段入口）。

用法（.venv_tts 运行）：
  python scripts/run_stage32b.py vo --pkg output/stage31_realworld/coral --out output/stage32b/coral
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
    ap.add_argument("stage", choices=["vo", "align", "subtitle", "blocked", "assemble", "render", "qc"])
    ap.add_argument("--pkg", required=True, help="项目包目录（含冻结口播稿）")
    ap.add_argument("--out", required=True, help="3.2b 输出目录")
    ap.add_argument("--ref", default="", help="F5-TTS 参考音频（缺省用冒烟参考）")
    ap.add_argument("--ref-text", default="", help="参考音频对应文本")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    pkg = ROOT / args.pkg
    out = ROOT / args.out
    narration = pkg / "V2_FINAL_SCRIPT_JARVIS.md"
    if not narration.exists():
        sys.exit(f"缺少口播稿：{narration}")

    if args.stage == "vo":
        from video_studio.stage32b.vo import build_vo
        m = build_vo(narration, out,
                     ref_file=Path(args.ref) if args.ref else None,
                     ref_text_path=Path(args.ref_text) if args.ref_text else None,
                     force=args.force)
        errs = [s for s in m["segments"] if s["status"] == "ERROR"]
        print(f"P0-1 VO: {len(m['segments'])-len(errs)}/{len(m['segments'])} OK, "
              f"ERROR {len(errs)}, total {m['total_duration']}s")
        sys.exit(0 if not errs else 2)
    elif args.stage == "align":
        from video_studio.stage32b.alignment import build_alignment, gate_alignment
        vo_m = out / "manifests" / "vo_manifest.json"
        shotlist = pkg / "shotlist.json"
        if not vo_m.exists():
            sys.exit("缺少 vo_manifest.json（先跑 P0-1 vo）")
        m = build_alignment(vo_m, shotlist, out, force=args.force)
        g = gate_alignment(m)
        sys.exit(0 if g["gate"] == "PASS" else 3)
    elif args.stage == "subtitle":
        from video_studio.stage32b.subtitle import build_subtitles, gate_subtitles
        al_m = out / "manifests" / "alignment_manifest.json"
        if not al_m.exists():
            sys.exit("缺少 alignment_manifest.json（先跑 P0-2 align）")
        m = build_subtitles(al_m, narration, out, force=args.force)
        al = json.loads(al_m.read_text(encoding="utf-8"))
        g = gate_subtitles(m, al)
        sys.exit(0 if g["gate"] == "PASS" else 4)
    elif args.stage == "blocked":
        from video_studio.stage32b.blocked import build_blocked, gate_blocked
        al_m = out / "manifests" / "alignment_manifest.json"
        pkg_dir = ROOT / "output" / "stage31_realworld" / "coral" / "material_pkg_real"
        if not al_m.exists():
            sys.exit("缺少 alignment_manifest.json（先跑 P0-2 align）")
        if not (pkg_dir / "shot_mapping" / "all_shots.json").exists():
            sys.exit(f"缺少 3.1.4 Material Package：{pkg_dir}")
        m = build_blocked(pkg_dir, al_m, out, force=args.force)
        g = gate_blocked(m)
        sys.exit(0 if g["gate"] == "PASS" else 5)
    elif args.stage == "assemble":
        from video_studio.stage32b.assemble import build_all, gate_assembly
        base = out
        blocked_m = base / "manifests" / "blocked_manifest.json"
        al_m = base / "manifests" / "alignment_manifest.json"
        vo_m = base / "manifests" / "vo_manifest.json"
        meta_m = ROOT / "output" / "stage31_realworld" / "coral" / "material_pkg_real" / "metadata" / "materials.json"
        for f in (blocked_m, al_m, vo_m, meta_m):
            if not f.exists():
                sys.exit(f"缺少输入：{f}")
        m = build_all(blocked_m, al_m, vo_m, meta_m, base, force=args.force)
        blk = json.loads(blocked_m.read_text(encoding="utf-8"))
        g = gate_assembly(m, blk)
        sys.exit(0 if g["gate"] == "PASS" else 6)
    elif args.stage == "render":
        from video_studio.stage32b.render import build_final, gate_render
        m = build_final(out, force=args.force)
        g = gate_render(m, out)
        sys.exit(0 if g["gate"] == "PASS" else 7)
    elif args.stage == "qc":
        from video_studio.stage32b.qc import run_qc, gate_qc
        report = run_qc(out)
        g = gate_qc(report, out)
        md = out / "qc" / "qc_report.md"
        md.write_text(qc_markdown(report, g), encoding="utf-8")
        sys.exit(0 if g["gate"] == "PASS" else 8)


def qc_markdown(report: dict, g: dict) -> str:
    lines = ["# P0-7 QC Report（《珊瑚礁正在消失》）", "", f"- Gate: **{g['gate']}**", ""]
    for k, v in report.items():
        lines.append(f"- **{k}**: `{v}`")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()

"""Stage 3.1 执行入口：读取 2.x Production Package -> Material Package。

用法：
  python scripts/run_stage31.py --pkg output/production_002 --out material_package_31
  python scripts/run_stage31.py --offline   # 不联网（用于测试）
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.stage31.package import build_package            # noqa: E402
from video_studio.stage31.sources import (                         # noqa: E402
    check_source_availability, retrieve_for_intent)
from video_studio.stage31.visual_intent import build_intents       # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg", default="output/production_002")
    ap.add_argument("--out", default="material_package_31")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--max-queries", type=int, default=2)
    ap.add_argument("--per-query", type=int, default=8)
    ap.add_argument("--no-video", action="store_true")
    ap.add_argument("--shots", default="", help="仅处理指定镜号，逗号分隔（如 S01,S02）")
    ap.add_argument("--mode", default="hybrid",
                    help="排序模式: lexical | embedding | hybrid（默认 hybrid）")
    args = ap.parse_args()

    from video_studio.stage31.ranking import set_rank_mode
    set_rank_mode(args.mode)

    pkg = ROOT / args.pkg
    shotlist = pkg / "shotlist.json"
    v2_script = pkg / "V2_FINAL_SCRIPT_JARVIS.md"
    for f in (shotlist, v2_script):
        if not f.exists():
            sys.exit(f"缺少输入：{f}")

    out_dir = pkg / args.out
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    only_shots = {s.strip().upper() for s in args.shots.split(",") if s.strip()}

    print("== Stage 3.1 ==")
    print(f"输入：{shotlist} + {v2_script.name}")
    print(f"输出：{out_dir}")

    intents = build_intents(shotlist, v2_script)
    if only_shots:
        intents = [it for it in intents if it.shot_id in only_shots]
    print(f"VISUAL_INTENT: {len(intents)} 镜生成完毕")
    kinds = {}
    for it in intents:
        kinds[it.match_type] = kinds.get(it.match_type, 0) + 1
    print("match_type 分布:", kinds)

    if args.offline:
        source_status = {"note": "offline 模式：未进行真实检索"}
        outcomes_by_shot = {}
    else:
        source_status = check_source_availability()
        print("来源状态:", source_status)
        from video_studio.stage31.query_plan import plan_queries
        from video_studio.stage31.sources import retrieve_multi
        outcomes_by_shot = {}
        broll = [it for it in intents if it.material_kind == "broll"]
        print(f"需检索 B-roll 镜：{len(broll)} 个")
        for i, it in enumerate(broll, 1):
            plan = plan_queries(it)
            outcomes = retrieve_multi(it, plan, per_query=args.per_query,
                                      include_video=not args.no_video)
            outcomes_by_shot[it.shot_id] = outcomes
            n = sum(len(o.candidates) for o in outcomes)
            print(f"[{i}/{len(broll)}] {it.shot_id} {it.concept[:20]}: "
                  f"{len(outcomes)} 路查询 -> {n} 候选")
        # 无素材需求的镜（evidence/gap）也写入空列表
        for it in intents:
            outcomes_by_shot.setdefault(it.shot_id, [])

    shotlist_data = json.loads(shotlist.read_text(encoding="utf-8"))
    result = build_package(
        intents, outcomes_by_shot, shotlist_data, out_dir, source_status,
        {"input": f"{args.pkg}/shotlist.json + V2_FINAL_SCRIPT_JARVIS.md",
         "generated_at": generated_at, "stage31_version": "3.1.4",
         "offline": args.offline})

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("完成。")


if __name__ == "__main__":
    main()

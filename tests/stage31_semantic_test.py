"""Stage 3.1.3 语义层对抗测试（用户点名的四个假匹配场景）。

断言：embedding 层必须把"错误候选"判低、把"正确候选"判高。
- 手机自动替你安排 vs 打字机 → 低
- Agent 执行任务 vs astronaut/spacewalk → 低
- 长期学习/书越堆越高 vs 古籍手稿 → 相对低（手稿低于现代书堆）
- 凌晨三点蓝光像不肯闭上的眼睛 vs 数据中心 → 低
注：本测试需要本地语义模型，须用 .venv_tts 运行。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.stage31.semantic import semantic_similarity  # noqa: E402

CASES = [
    ("手机自动替你安排 vs 打字机",
     "手机不断弹出新的任务，然后自动替你安排接下来的一整天",
     "Facit Tamil Typing Mechane typewriter machine", None),
    ("手机自动替你安排 vs 手机通知",
     "手机不断弹出新的任务，然后自动替你安排接下来的一整天",
     "smartphone screen showing app notifications", None),
    ("Agent 执行任务 vs 宇航员",
     "现在的 AI Agent 能调用工具执行多步任务",
     "Michael Gernhardt spacewalk astronaut in space", None),
    ("Agent 执行任务 vs 自动化流水线",
     "现在的 AI Agent 能调用工具执行多步任务",
     "automation workflow robot arm assembly factory", None),
    ("书越堆越高 vs 古籍手稿",
     "书越堆越高，翻开的永远是第一页",
     "Iskendername manuscript 1475 ancient book illustration", None),
    ("书越堆越高 vs 现代书堆",
     "书越堆越高，翻开的永远是第一页",
     "stack of modern books on desk", None),
    ("蓝光眼睛隐喻 vs 数据中心",
     "凌晨三点，手机屏幕的蓝光，像一只不肯闭上的眼睛",
     "roof of a data center with cooling towers", None),
    ("蓝光眼睛隐喻 vs 夜光屏幕",
     "凌晨三点，手机屏幕的蓝光，像一只不肯闭上的眼睛",
     "phone screen glowing in dark room at night", None),
]


def main() -> int:
    checks = []

    def check(name, cond, detail=""):
        checks.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    scores = {}
    for name, a, b, _ in CASES:
        s = semantic_similarity(a, b)
        scores[name] = s
        print(f"  {round(s, 3)}  {name}")

    check("打字机 < 手机通知", scores["手机自动替你安排 vs 打字机"] < scores["手机自动替你安排 vs 手机通知"],
          f"({scores['手机自动替你安排 vs 打字机']:.3f} vs {scores['手机自动替你安排 vs 手机通知']:.3f})")
    check("宇航员 < 自动化流水线", scores["Agent 执行任务 vs 宇航员"] < scores["Agent 执行任务 vs 自动化流水线"],
          f"({scores['Agent 执行任务 vs 宇航员']:.3f} vs {scores['Agent 执行任务 vs 自动化流水线']:.3f})")
    check("古籍手稿 < 现代书堆", scores["书越堆越高 vs 古籍手稿"] < scores["书越堆越高 vs 现代书堆"],
          f"({scores['书越堆越高 vs 古籍手稿']:.3f} vs {scores['书越堆越高 vs 现代书堆']:.3f})")
    check("数据中心 < 夜光屏幕", scores["蓝光眼睛隐喻 vs 数据中心"] < scores["蓝光眼睛隐喻 vs 夜光屏幕"],
          f"({scores['蓝光眼睛隐喻 vs 数据中心']:.3f} vs {scores['蓝光眼睛隐喻 vs 夜光屏幕']:.3f})")
    check("打字机绝对分 < 0.35", scores["手机自动替你安排 vs 打字机"] < 0.35)
    check("宇航员绝对分 < 0.35", scores["Agent 执行任务 vs 宇航员"] < 0.35)

    failed = [c for c in checks if not c[1]]
    print(f"\n结果: {len(checks) - len(failed)}/{len(checks)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

"""stage33 motion 整数帧轨迹测试（jitter=0 的算法级保证）。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from video_studio.stage33 import motion as M  # noqa: E402


def _deltas(rects, axis=0):
    return [abs(rects[i][axis] - rects[i - 1][axis]) for i in range(1, len(rects))]


def main() -> int:
    fails = []

    def check(name, cond, detail=""):
        if not cond:
            fails.append(name)
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    n = 125
    # 1) HOLD：帧差恒 0
    hold = M.plan_hold(n, 100, 100, 1920, 1080)
    check("HOLD 全部帧相同（帧差恒 0）",
          len(set(hold)) == 1 and _deltas(hold) == [0] * (n - 1))

    # 2) 平移：恒定步长、单调、无 0/1 交替、头尾静止
    pan = M.plan_pan(n, 2600, 1600, 1920, 1080, "RIGHT", 0.20)
    check("平移可行（幅度/速度达标）", pan is not None)
    if pan:
        dx = _deltas(pan, 0)
        check("平移头尾静止（≥7 帧 0 位移）", dx[:7] == [0] * 7 and dx[-7:] == [0] * 7)
        core = [d for d in dx if d > 0]
        check("平移运动段无 0 间隔（无 0/1 交替）",
              not any(dx[i] == 0 and dx[i + 1] > 0 and dx[i + 2] == 0
                      for i in range(len(dx) - 2)))
        check("平移步长恒定（std≤0.5）", core and
              (max(core) - min(core)) <= 1)
        check("平移方向单调（x 只增不减）",
              all(pan[i][0] <= pan[i + 1][0] for i in range(len(pan) - 1)))
    # 3) 不可行平移 → None（幅度太小）
    check("小幅平移不可行 → None（→HOLD）",
          M.plan_pan(n, 2600, 1600, 1920, 1080, "RIGHT", 0.005) is None)
    # 4) 缩放：偶数步长、单调、头尾静止（n=75 保证 10% 幅度可行）
    z = M.plan_zoom(75, 2400, 1350, 1920, 1080, True, 0.10)
    check("缩放可行", z is not None)
    if z:
        dw = _deltas(z, 2)
        check("缩放头尾静止（≥7 帧 0 位移）", dw[:7] == [0] * 7 and dw[-7:] == [0] * 7)
        core = [d for d in dw if d > 0]
        check("缩放步长偶数且接近恒定（2 或 4px）", core and all(d % 2 == 0 for d in core) and
              (max(core) - min(core)) <= 2)
        check("缩放尺寸单调", all(z[i][2] >= z[i + 1][2] for i in range(len(z) - 1)))
    check("小幅缩放不可行 → None（→HOLD）",
          M.plan_zoom(n, 2400, 1350, 1920, 1080, True, 0.01) is None)
    # 5) alpha_ramp：单调、端点正确
    a = M.alpha_ramp(40, 0, 255)
    check("alpha 渐变端点正确", a[0] == 0 and a[-1] == 255)
    check("alpha 渐变单调不减", all(a[i] <= a[i + 1] for i in range(len(a) - 1)))
    b = M.alpha_ramp(30, 255, 0)
    check("alpha 淡出单调不增", all(b[i] >= b[i + 1] for i in range(len(b) - 1)))

    # 6) frame_range：绝对时间边界→帧数（时长漂移修复回归）
    check("frame_range(0, 102.199) = 2555 帧",
          M.frame_range(0.0, 102.199) == 2555)
    check("frame_range 连续段无截断（0→4.395）",
          M.frame_range(0.0, 4.395) + M.frame_range(4.395, 10.411) ==
          M.frame_range(0.0, 10.411))
    # 7) Coral 33-beat 案例：帧区间连续、无 gap/overlap、无 0.6s 累积损失
    import json as _json
    plan = _json.loads((ROOT / "output" / "stage33" / "coral" / "v3" /
                        "visual_plan.json").read_text(encoding="utf-8"))
    beats = sorted(plan["beats"], key=lambda b: b["start"])
    ok_cont, total_frames = True, 0
    for i, b in enumerate(beats):
        sf, ef = round(b["start"] * 25), round(b["end"] * 25)
        total_frames += (ef - sf)
        if i > 0:
            prev_e = round(beats[i - 1]["end"] * 25)
            if sf != prev_e:
                ok_cont = False
    check("Coral 33 beats 帧区间连续（无 gap/overlap）", ok_cont)
    check("首帧=0 且末帧覆盖时间轴", round(beats[0]["start"] * 25) == 0 and
          round(beats[-1]["end"] * 25) == 2555)
    loss = sum(b["duration"] for b in beats) - total_frames / 25
    check("无 0.6s 累积损失（|Σdur - Σframes/25| < 0.05s）", abs(loss) < 0.05, f"loss={loss:.4f}")
    # 8) 压力测试：随机小数时长的时间轴无漂移
    import random as _r
    _r.seed(7)
    times, t = [], 0.0
    for _ in range(500):
        d = round(_r.uniform(1.2, 6.0), 3)
        times.append((t, round(t + d, 3)))
        t = round(t + d, 3)
    total_expected = round(t * 25)
    got = sum(M.frame_range(s, e) for s, e in times)
    check("500 段随机时间轴：Σframes == round(total*25)（无漂移）",
          got == total_expected, f"{got} vs {total_expected}")
    # 9) 确定性：重复执行完全一致
    g1 = sum(M.frame_range(s, e) for s, e in times)
    check("frame allocation 字节级确定（重复一致）", g1 == got)
    # 10) 冻结 plan 未被本轮改动（文件 SHA 与 plan_sha 字段双锚点）
    import hashlib as _h
    plan_file_sha = _h.sha256((ROOT / "output" / "stage33" / "coral" / "v3" /
                               "visual_plan.json").read_bytes()).hexdigest()
    check("冻结 plan 文件 SHA 不变",
          plan_file_sha == "e08e298a3be4b4747bd9baf86cf84426d6b330267a3e580c10a45fc9c3bf012d",
          plan_file_sha[:16])
    check("plan_sha 字段仍为 8262bb40…", plan["plan_sha"].startswith("8262bb40"))

    print(f"\nmotion test: {'FAIL' if fails else 'ALL PASS'} ({len(fails)} fails)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

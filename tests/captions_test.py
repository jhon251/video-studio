# -*- coding: utf-8 -*-
"""5-M 针对性回归：字幕切分/折行/排布与 SRT/ASS 输出（`core.captions` 纯函数契约）。

覆盖：
  C1 切句与细分：≤max_cue_chars、过短片段合并、空文本无 cue
  C2 折行：≤2 行、每行 ≤max_line（视觉宽度）、行首不放标点、优先在停顿标点处断
  C3 排布：单调、不重叠、不越镜头窗口、单条 ≤max_cue_s、镜头内留白不滞留
  C4 SRT：序号/时间箭头格式、条数一致、**每条单行**（不插入换行，保持文本可检索）
  C5 ASS：PlayRes=分辨率、Style 底部居中(Alignment=2)+描边、字号随高度缩放、两行用 \\N、无 `{}` 覆盖块
  C6 规整化：去换行/空白、`{}` → 全角括号
  C7 确定性：同输入两次输出逐字节一致
  C8 真实脚本 smoke：对 21 段真实脚本全量校验不变量
  C9 规模：200+ 条无重叠、末条不越时间轴总长
  C10 边界：空旁白/缺 duration 不崩

用法: python tests/captions_test.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core.captions import (MAX_CUE_S, build_cues, normalize,  # noqa: E402
                                        split_into_cues, text_width, to_ass, to_srt,
                                        wrap_lines)

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name, "" if ok else "| " + str(detail)[:300]))


SAMPLE = ("假设有一天，一个 AI 交出一份三千页的证明。它通过了所有机器检查，能人工核对的部分也都没问题。"
          "但没有人真的读完了它——不是不愿意，是把它读完需要的时间超过了一个人的一生。")

# ---------------- C1 切句/细分 ----------------
cues = split_into_cues(SAMPLE)
check("C1a 切句：按句末标点切成多条（≥3）且每条 ≤36 字",
      len(cues) >= 3 and all(len(c) <= 36 for c in cues), cues)
merged = split_into_cues("好。这是一句正常长度的话，用来验证过短片段会被合并。")
check("C1b 过短片段合并（不以孤立短句起条）", all(len(c) >= 6 for c in merged), merged)
check("C1c 空文本 → 无 cue；纯空白 → 无 cue",
      split_into_cues("") == [] and split_into_cues("   \n  ") == [])

# ---------------- C2 折行 ----------------
lines = wrap_lines("它通过了所有机器检查，能人工核对的部分也都没问题。")
check("C2a 折行 ≤2 行且每行 ≤22 视觉宽度",
      len(lines) <= 2 and all(text_width(x) <= 22 for x in lines), lines)
check("C2b 优先在停顿标点处断（第一行以『，』结尾）", lines[0].endswith("，"), lines)
lines2 = wrap_lines("如果数学的成果人类已经无法完整地参与理解，那数学家还有意义吗？")
check("C2c 长句同样在标点处断且两行都不超宽",
      len(lines2) == 2 and lines2[0].endswith("，") and all(text_width(x) <= 22 for x in lines2),
      lines2)
short = wrap_lines("短句。")
check("C2d 短文本单行不折", short == ["短句。"], short)

# ---------------- C3 排布 ----------------
segs = [{"narration": SAMPLE, "duration_s": 40.0},
        {"narration": "第二段旁白，用于验证跨镜头不重叠。", "duration_s": 12.0},
        {"narration": "", "duration_s": 8.0}]
cc = build_cues(segs)
ok_mono = all(cc[i]["end"] <= cc[i + 1]["start"] + 1e-6 for i in range(len(cc) - 1))
ok_pos = all(c["dur"] > 0 for c in cc)
ok_dur = all(c["dur"] <= MAX_CUE_S + 1e-6 for c in cc)
seg0 = [c for c in cc if c["segment_index"] == 0]
seg1 = [c for c in cc if c["segment_index"] == 1]
check("C3a 单调、时长为正、单条 ≤max_cue_s", ok_mono and ok_pos and ok_dur,
      {"mono": ok_mono, "pos": ok_pos, "dur": ok_dur, "max": max(c["dur"] for c in cc)})
check("C3b 不越镜头窗口（段 0 全部落在 [0,40]，段 1 落在 [40,52]）",
      all(0 <= c["start"] and c["end"] <= 40.0 + 1e-6 for c in seg0)
      and all(40.0 - 1e-6 <= c["start"] and c["end"] <= 52.0 + 1e-6 for c in seg1),
      {"seg0": (seg0[0]["start"], seg0[-1]["end"]), "seg1": (seg1[0]["start"], seg1[-1]["end"])})
check("C3c 镜头窗口内**均匀铺开**：首条起于窗口起点、末条结束 ≥ 窗口 60%、单条 ≤max_cue_s",
      abs(seg0[0]["start"] - 0.0) < 1e-6 and seg0[-1]["end"] >= 0.6 * 40.0
      and all(c["dur"] <= MAX_CUE_S + 1e-6 for c in seg0),
      {"first": seg0[0]["start"], "last_end": seg0[-1]["end"]})
check("C3d 空旁白段不产生 cue（段 2）", not [c for c in cc if c["segment_index"] == 2])

# ---------------- C4 SRT ----------------
srt = to_srt(cc)
blocks = [b for b in srt.strip().split("\n\n") if b.strip()]
first = blocks[0].splitlines()
check("C4a SRT 结构与条数（序号 + --> 时间行 + 单行文本）",
      len(blocks) == len(cc) and "-->" in first[1] and first[0] == "1"
      and len(first) == 3, {"blocks": len(blocks), "cues": len(cc), "first": first[:2]})
check("C4b SRT 每条为单行文本（无内部换行 → 关键词可检索）",
      all(len(b.splitlines()) == 3 for b in blocks))

# ---------------- C5 ASS ----------------
ass = to_ass(cc, resolution="1920x1080")
head = ass.split("[Events]")[0]
events = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
check("C5a ASS PlayRes == 分辨率 + Style 底部居中/描边 + 字号随高度缩放",
      "PlayResX: 1920" in head and "PlayResY: 1080" in head
      and "Cap,Microsoft YaHei,45," in head and ",1,3,0,2," in head, head.splitlines()[6][:80])
check("C5b Dialogue 条数 == cue 数，两行 cue 用 \\N，文本无 `{}` 覆盖块",
      len(events) == len(cc) and any("\\N" in e for e in events)
      and not any(("{" in e.split(",,", 1)[-1] or "}" in e.split(",,", 1)[-1]) for e in events),
      {"events": len(events), "cues": len(cc)})
ass720 = to_ass(cc, resolution="1280x720")
check("C5c 720p 字号更小（随高度缩放，确定性）",
      "PlayResY: 720" in ass720 and "Cap,Microsoft YaHei,30," in ass720, None)

# ---------------- C6 规整化 ----------------
check("C6 normalize：去换行/多空白、`{}` → 全角括号",
      normalize("  甲\n乙  {丙}  ") == "甲 乙 （丙）", normalize("  甲\n乙  {丙}  "))

# ---------------- C7 确定性 ----------------
check("C7 同输入两次输出逐字节一致（SRT 与 ASS）",
      to_srt(cc) == to_srt(build_cues(segs)) and to_ass(cc) == to_ass(build_cues(segs)))

# ---------------- C8 真实脚本 smoke ----------------
script_art = None
for p in sorted((ROOT / "projects" / "p_96efdc03e1aa" / "artifacts").glob("*.json")):
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                       # noqa: BLE001
        continue
    s = d.get("segments")
    if isinstance(s, list) and s and isinstance(s[0], dict) and "narration" in s[0] \
            and "duration_s" in s[0]:
        script_art = (p.name, s)
        break
if script_art:
    real = build_cues([{"narration": x["narration"], "duration_s": x.get("duration_s")}
                       for x in script_art[1]])
    total = sum(max(float(x.get("duration_s") or 0), 3.0) for x in script_art[1])
    ok = (all(real[i]["end"] <= real[i + 1]["start"] + 1e-6 for i in range(len(real) - 1))
          and all(c["dur"] <= MAX_CUE_S + 1e-6 and c["dur"] > 0 for c in real)
          and all(text_width(l) <= 22.01 for c in real for l in c["lines"])
          and all(len(c["lines"]) <= 2 for c in real)
          and real[-1]["end"] <= total + 1e-6)
    check("C8 真实脚本（{}，{} 段）全量不变量：{} 条 cue 单调/不超宽/≤2 行/不越总长".format(
        script_art[0], len(script_art[1]), len(real)), ok,
        {"last_end": real[-1]["end"], "total": total})
    check("C9 规模：≥150 条（每段约 10 条）且无重叠", len(real) >= 150, len(real))
else:
    check("C8 真实脚本 smoke（无脚本产物则跳过）", True, "skipped")

# ---------------- C10 边界 ----------------
try:
    edge = build_cues([{"narration": "只有一句话。", "duration_s": None},
                       {"narration": None, "duration_s": "bad"}])
    check("C10 缺失/非法 duration 与 None 文本不崩溃，且时间仍单调",
          all(edge[i]["end"] <= edge[i + 1]["start"] + 1e-6 for i in range(len(edge) - 1)), edge)
except Exception as exc:                                     # noqa: BLE001
    check("C10 缺失/非法 duration 与 None 文本不崩溃，且时间仍单调", False, repr(exc))

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(0 if not FAIL else 1)

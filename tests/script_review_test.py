# -*- coding: utf-8 -*-
"""script_review_test：人工审稿导出/回填的契约测试（无网络、无 LLM、确定性）。

覆盖
  1. 解析：只认 `@@Sxx` 行，批注/表格/空行一律忽略
  2. 折算：字数 → 预估秒（5 字/秒）
  3. 校验：缺段/多段/全片漂移/单段漂移/节拍名泄漏/AI 味词
  4. 台账：checklist 解析（1/0 串 与 key=val）、落盘/读取 roundtrip
  5. 选产物：有脚本字段（titles/cta_plan…）的 artifact 优先于"只有 segments"的
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import script_review as SR  # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + (" | " + str(detail)[:200] if detail else ""))


BASE = {
    "topic_understanding": "测试",
    "titles": ["标题一"],
    "segments": [
        {"chapter": "开场", "narration": "这是第一段的旁白，大约二十来个字左右。", "emotion_beat": "curiosity"},
        {"chapter": "机制", "narration": "第二段讲机制，同样是一句不长的话，用于校验漂移计算。", "emotion_beat": "tension"},
        {"chapter": "收束", "narration": "第三段收尾，回扣开头那个人。", "emotion_beat": "payoff"},
    ],
}

# ---------------- 1. 解析 ----------------
print("== 1. 解析 ==")
MD = """# 标题
把这一行改掉：@@S99 不该被识别（在前面有文字）
| 表格 | 行 |
@@S01 这是第一段的旁白，大约二十来个字左右。
@@S02 第二段讲机制，同样是一句不长的话，用于校验漂移计算。
<!-- 批注 @@S03 注释里的不该被识别 -->
   @@S03   第三段收尾，回扣开头那个人。
"""
m = SR.parse_markdown(MD)
check("1a 只解析行首 @@Sxx（行内/注释里的不认）", set(m) == {0, 1, 2}, sorted(m))
check("1b 行尾空白被裁剪", m.get(2) == "第三段收尾，回扣开头那个人。", m.get(2))
check("1c 空文本不产生条目", SR.parse_markdown("@@S01   \n") == {}, SR.parse_markdown("@@S01   \n"))

# ---------------- 2. 折算 ----------------
print("== 2. 折算 ==")
check("2a 5 字/秒折算（10 字 → 2.0s）",
      SR.est_seconds("十个字十个字十个字十") == 2.0, SR.est_seconds("十个字十个字十个字十"))
check("2b 15 字 → 3.0s", SR.est_seconds("一二三四五六七八九十甲乙丙丁戊") == 3.0,
      SR.est_seconds("一二三四五六七八九十甲乙丙丁戊"))
check("2b 空白不计入字数", SR.CHARS_PER_SEC == 5.0 and SR.est_seconds("一 二 三 四 五") == 1.0,
      SR.est_seconds("一 二 三 四 五"))

# ---------------- 3. 校验 ----------------
print("== 3. 校验 ==")
same = {i: s["narration"] for i, s in enumerate(BASE["segments"])}
r = SR.apply_review(BASE, same)
check("3a 未改动 → 通过、零漂移、无告警",
      r["ok"] and not r["warnings"] and abs(r["stats"]["delta_ratio"]) < 1e-9,
      {"errors": r["errors"], "warnings": r["warnings"], "stats": r["stats"]})

r = SR.apply_review(BASE, {0: BASE["segments"][0]["narration"]})
check("3b 缺段 → 报错（段数不可增删）",
      (not r["ok"]) and any("缺少段" in e for e in r["errors"]), r["errors"])

extra = dict(same)
extra[5] = "多出来的一段"
r = SR.apply_review(BASE, extra)
check("3c 多段 → 报错", (not r["ok"]) and any("多出段" in e for e in r["errors"]), r["errors"])

long_map = dict(same)
long_map[0] = "很长" * 60
r = SR.apply_review(BASE, long_map)
check("3d 全片漂移 >5% → 默认报错（时长/素材/字幕会变）",
      (not r["ok"]) and any("全片字数漂移" in e for e in r["errors"]), r["errors"])
r2 = SR.apply_review(BASE, long_map, allow_drift=True)
check("3e --allow-drift → 放行（仍给逐段告警）",
      r2["ok"] and any("字数漂移" in w for w in r2["warnings"]), r2["warnings"][:2])

leak = dict(same)
leak[1] = "这一段不小心写了 curiosity 和 emotion_beat"
r = SR.apply_review(BASE, leak)
check("3f 节拍名/字段名泄漏 → 告警",
      any("泄漏" in w for w in r["warnings"]), r["warnings"][:3])

flavor = dict(same)
flavor[1] = "值得注意的是，第二段讲机制，同样是一句不长的话。"
r = SR.apply_review(BASE, flavor)
check("3g AI 味/公文腔 → 告警", any("AI 味" in w for w in r["warnings"]), r["warnings"][:3])

# ---------------- 4. 台账 ----------------
print("== 4. 台账 ==")
c1 = SR.parse_checklist("11110")
check("4a 1/0 串解析（按 5 问顺序）",
      c1 == {"concrete_person": True, "screenshot_line": True, "counterintuitive": True,
             "analogy": True, "callback": False}, c1)
c2 = SR.parse_checklist("concrete_person=1,analogy=0")
check("4b key=val 解析", c2 == {"concrete_person": True, "analogy": False}, c2)
check("4c 空串 → 空字典", SR.parse_checklist("") == {})

with tempfile.TemporaryDirectory(prefix="vs_sr_") as td:
    pdir = pathlib.Path(td)
    payload = r["payload"] if False else SR.apply_review(BASE, same)["payload"]
    p = SR.save_review(pdir, payload)
    back = SR.load_review(pdir)
    check("4d 落盘/读取 roundtrip（media/script_review.json）",
          p.is_file() and back and len(back["segments"]) == 3
          and back["source"] == "human_review", str(p))
    rebuilt = SR.build_payload_from_review(back)
    check("4e 形状可被 ScriptAgent 消费（segments + summary + source）",
          rebuilt["segments"] and rebuilt.get("source") == "human_review", list(rebuilt)[:6])
check("4f 无文件时 load_review 返回 None",
      SR.load_review(pathlib.Path(tempfile.mkdtemp(prefix="vs_sr_none_"))) is None)

# ---------------- 5. 选产物 ----------------
print("== 5. 选产物 ==")
with tempfile.TemporaryDirectory(prefix="vs_sr_art_") as td:
    pdir = pathlib.Path(td)
    (pdir / "artifacts").mkdir(parents=True)
    plain = {"segments": [{"narration": "只有段落的产物", "duration_s": 3}]}
    full = dict(BASE)
    (pdir / "artifacts" / "a_new.json").write_text(json.dumps(plain, ensure_ascii=False), encoding="utf-8")
    (pdir / "artifacts" / "a_old.json").write_text(json.dumps(full, ensure_ascii=False), encoding="utf-8")
    import os
    import time
    now = time.time()
    os.utime(pdir / "artifacts" / "a_old.json", (now - 100, now - 100))
    os.utime(pdir / "artifacts" / "a_new.json", (now, now))
    path, payload2 = SR.find_script_artifact(pdir)
    check("5a 有脚本字段（titles）的产物优先于更新的'只有 segments'产物",
          path is not None and path.name == "a_old.json", path.name if path else None)
    rev = SR.build_review(pdir)
    check("5b 导出结构完整（段数/字数/预估/5 问）",
          rev["found"] and len(rev["segments"]) == 3 and rev["total_chars"] > 0
          and all(k in SR.render_markdown(rev) for k, _ in SR.CHECKLIST),
          rev.get("total_chars"))
    md = SR.render_markdown(rev)
    check("5c 导出 md 里 @@Sxx 行数与段数一致",
          len(SR.MARK_RE.findall(md)) == 3, len(SR.MARK_RE.findall(md)))

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)

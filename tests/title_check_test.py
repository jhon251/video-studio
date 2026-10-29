# -*- coding: utf-8 -*-
"""Phase 11 测试：标题/封面候选机械校验器（逐违规码 + 中文数字归一化 + 多样性/回声 + 确定性 + legacy）。

覆盖授权书 §5：
 · a) 长度上限（主标 40 / 封面 12）· b) 震惊体黑名单 · c) technique 枚举
 · d) evidence_refs 越界/重复 · e) **数字可溯性**（含中文数字归一化「三千」vs「3000」）
 · f) 5 候选 technique 多样性 ≥3 · g) 与脚本首句回声
 · legacy 结构码 OLD_FORMAT（能力增量对照，且新字段门记为不可评而非 FAIL）
 · 确定性与 `--json --no-timestamp` 逐字节一致

运行: python tests/title_check_test.py
"""
from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import title_check as TC                                    # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:240]))
    return bool(ok)


SEGS = [
    {"narration": "假设明天有一份数学证明被公布出来，它有三千页，没有任何人读完。",
     "duration_s": 60},
    {"narration": "1976 年四色定理的机器证明已经让同行无法逐行检验。", "duration_s": 60},
    {"narration": "开普勒猜想的验证用了 20 年，才被认为是可信的。", "duration_s": 60},
]
SCRIPT = {"segments": SEGS, "summary": "t"}


def cand(text, tech="specificity", ev=(0,), nums=(0,), **kw):
    d = {"text": text, "technique": tech, "evidence_refs": list(ev),
         "number_sources": list(nums), "why_win": "w", "disappointment_risk": "r"}
    d.update(kw)
    return d


def meta(cands, covers=(), ab=None):
    m = {"title_candidates": list(cands)}
    if covers:
        m["cover_text_candidates"] = list(covers)
    if ab is not None:
        m["ab_plan"] = ab
    return m


def codes_of(rep):
    return [v["code"] for c in rep["candidates"] for v in c["codes"]]


# ---------------- 0. schema/校验与哈希 ----------------
GOOD_CANDS = [
    cand("三千页的证明，没人读完", "specificity", (0,), (0,)),
    cand("如果证明没人读懂，数学还属于人类吗", "curiosity_gap", (0, 1), ()),
    cand("数学家的活儿正在被重新分配", "stakes", (2,), ()),
    cand("机器证明最难的，不是算得快，而是让人相信", "expectation_break", (1,), ()),
    cand("给还在手写证明的数学系学生", "identity_callout", (1, 2), ()),
]
GOOD = meta(GOOD_CANDS,
            covers=[{"text": "没人读完的三千页", "cover_title_pairing": "递进",
                     "pairing_note": "n"}],
            ab={"platform": "bilibili", "variants": ["a", "b"], "metric": "ctr",
                "execution": "manual", "note": "人工发布执行"})
rep = TC.check_metadata(SCRIPT, GOOD, source={"case": "good"})
check("0 合法候选集 ⇒ 全部 PASS、validate 通过、哈希可复算",
      rep["all_pass"] and rep["counts"]["fail"] == 0 and TC.validate(rep) == []
      and rep["artifact_hash"] == TC.report_hash(rep), TC.validate(rep)[:3])
check("0b ab_plan 判定：execution=manual 且 variants ≥2（guide §三）",
      rep["ab_plan"]["present"] and rep["ab_plan"]["execution_is_manual"]
      and rep["ab_plan"]["variants_ok"])
check("0c 阈值常量**全部注明 basis**（不得发明新数）",
      all(v.get("basis") for v in TC.THRESHOLDS.values())
      and all(v.get("basis") for v in TC.THRESHOLDS.values()))

# ---------------- a. 长度 ----------------
long_title = copy.deepcopy(GOOD_CANDS)
long_title[0] = cand("三" * 41, "specificity", (0,), ())
r = TC.check_metadata(SCRIPT, meta(long_title))
check("a 主标 >40 字 ⇒ TITLE_TOO_LONG（阈值 40，出处 guide §三）",
      "TITLE_TOO_LONG" in codes_of(r) and TC.THRESHOLDS["title_max_chars"]["value"] == 40)
cover_long = TC.check_metadata(SCRIPT, meta(GOOD_CANDS, covers=[
    {"text": "十" * 13, "cover_title_pairing": "互补"}]))
check("a2 封面大字 >12 字 ⇒ TITLE_COVER_TOO_LONG（阈值 12）",
      "TITLE_COVER_TOO_LONG" in [v["code"] for c in cover_long["cover_texts"]
                                 for v in c["codes"]])

# ---------------- b. 震惊体黑名单（变体） ----------------
for i, w in enumerate(("震惊！三千页证明", "99%的人不知道的数学", "细思极恐的证明",
                       "万万没想到，他证明了", "全网最难的数学题", "删前速看")):
    rr = TC.check_metadata(SCRIPT, meta([cand(w, "curiosity_gap", (0,), (0,))]))
    check("b 震惊体变体 #{} ⇒ TITLE_SENSATIONALISM".format(i + 1),
          "TITLE_SENSATIONALISM" in codes_of(rr), {"text": w, "codes": codes_of(rr)})

# ---------------- c. technique 枚举 ----------------
bad_tech = TC.check_metadata(SCRIPT, meta([cand("合法长度标题", "shocking", (0,), ())]))
check("c 非法 technique ⇒ TITLE_TECHNIQUE_INVALID（白名单 6 种）",
      "TITLE_TECHNIQUE_INVALID" in codes_of(bad_tech) and len(TC.TECHNIQUES) == 6)

# ---------------- d. 引用越界/重复 ----------------
oob = TC.check_metadata(SCRIPT, meta([cand("引用了不存在的段落", "stakes", (9,), ())]))
dup = TC.check_metadata(SCRIPT, meta([cand("重复引用", "stakes", (0, 0), ())]))
check("d evidence_refs 越界 ⇒ TITLE_EVIDENCE_REF_OUT_OF_RANGE",
      "TITLE_EVIDENCE_REF_OUT_OF_RANGE" in codes_of(oob))
check("d2 evidence_refs 重复 ⇒ TITLE_EVIDENCE_REF_DUPLICATE",
      "TITLE_EVIDENCE_REF_DUPLICATE" in codes_of(dup))

# ---------------- e. 数字可溯性（核心门 + 中文数字归一化） ----------------
check("e 中文数字归一化：三千 → 3000，段落含「三千页」⇒ 可溯",
      TC.cn_to_int("三千") == 3000 and TC.cn_to_int("二十") == 20
      and TC.cn_to_int("一百五十") == 150 and TC.cn_to_int("十二") == 12
      and ("num", 3000) in TC.extract_numbers("三千页的证明")
      and ("num", 3000) in TC.extract_numbers("3000 页的证明"))
ok_num = TC.check_metadata(SCRIPT, meta([cand("三千页的证明没人读完", "specificity", (0,), (0,))]))
check("e2 「三千页」（数字来源=段 0，原文即「三千页」）⇒ PASS（无 UNTRACEABLE）",
      "TITLE_NUMBER_UNTRACEABLE" not in codes_of(ok_num))
bad_num = TC.check_metadata(SCRIPT, meta([cand("十万页的证明没人读完", "specificity", (0,), (0,))]))
check("e3 标题数字「十万」在段 0 中找不到 ⇒ TITLE_NUMBER_UNTRACEABLE（反标题诈骗核心门）",
      "TITLE_NUMBER_UNTRACEABLE" in codes_of(bad_num), codes_of(bad_num))
no_src = TC.check_metadata(SCRIPT, meta([cand("三千页的证明", "specificity", (0,), ())]))
check("e4 标题含数字但未给 number_sources ⇒ TITLE_NO_NUMBER_SOURCES",
      "TITLE_NO_NUMBER_SOURCES" in codes_of(no_src))
cross = TC.check_metadata(SCRIPT, meta([cand("1976 年那件事", "specificity", (1,), (0,))]))
check("e5 数字出处指向**不含该数字**的段落 ⇒ TITLE_NUMBER_UNTRACEABLE（出处须真能支撑）",
      "TITLE_NUMBER_UNTRACEABLE" in codes_of(cross))
approx = TC.check_metadata(SCRIPT, meta([cand("几千页的证明没人读完", "specificity", (0,), (0,))]))
check("e6 近似写法「几千」⇒ 与同量级数字（3000）匹配（guide §二.1 明确含近似写法）",
      "TITLE_NUMBER_UNTRACEABLE" not in codes_of(approx), codes_of(approx))

# ---------------- f. 多样性 ----------------
mono = TC.check_metadata(SCRIPT, meta([
    cand("标题一", "stakes", (0,), ()), cand("标题二", "stakes", (1,), ()),
    cand("标题三", "stakes", (2,), ()), cand("标题四", "stakes", (0,), ()),
    cand("标题五", "stakes", (1,), ())]))
check("f 5 候选全同 technique ⇒ TITLE_TECHNIQUE_DIVERSITY_LOW（要求 ≥3 种）",
      "TITLE_TECHNIQUE_DIVERSITY_LOW" in codes_of(mono)
      and TC.THRESHOLDS["min_technique_diversity"]["value"] == 3)
check("f2 合法集覆盖 5 种 technique ⇒ 无多样性违规",
      "TITLE_TECHNIQUE_DIVERSITY_LOW" not in codes_of(rep)
      and len(rep["techniques_used"]) >= 3)

# ---------------- g. 首句回声 ----------------
verbatim = TC.check_metadata(SCRIPT, meta([
    cand("假设明天有一份数学证明被公布出来", "curiosity_gap", (0,), ())]))
near = TC.check_metadata(SCRIPT, meta([
    cand("AI 与数学证明：从开普勒猜想到 Lean 形式化", "specificity", (1,), ())]))
check("g 逐字复用首句（LCS≥12）⇒ TITLE_ECHOES_OPENING",
      "TITLE_ECHOES_OPENING" in codes_of(verbatim),
      [c["codes"] for c in verbatim["candidates"]])
check("g2 同主题但非回声的标题（旧稿样式）⇒ **不**误报回声（P11-3 实测标定：3-gram 阈值）",
      "TITLE_ECHOES_OPENING" not in codes_of(near), codes_of(near))
legacy_titles = [p["title"] for p in json.loads(
    (ROOT / "projects/p_96efdc03e1aa/artifacts/a_e0ec01d11b5a.json").read_text(
        encoding="utf-8"))["platforms"]]
legacy_rep = TC.check_metadata(
    json.loads((ROOT / "docs/regression_2x/logs/phase8_ab_v3.json").read_text(
        encoding="utf-8"))["script"],
    json.loads((ROOT / "projects/p_96efdc03e1aa/artifacts/a_e0ec01d11b5a.json").read_text(
        encoding="utf-8")))
legacy_echo = [c["text"] for c in legacy_rep["candidates"]
               if "TITLE_ECHOES_OPENING" in [v["code"] for v in c["codes"]]]
check("g3 真实旧基线 6 条标题：仅按长度真实违规、**无回声误报**（实测标定依据）",
      legacy_rep["structural_codes"] == ["OLD_FORMAT", "NO_TITLE_CANDIDATES"]
      and legacy_echo == [] and legacy_rep["counts"]["candidates"] == 6,
      {"echo": legacy_echo, "counts": legacy_rep["counts"]})
check("g4 legacy：technique/引用/数字出处/多样性记入 not_assessable_gates（**不判 FAIL**）",
      all(set(c.get("not_assessable_gates") or []) >= {"technique", "evidence_refs",
                                                       "number_sources"}
          for c in legacy_rep["candidates"])
      and legacy_rep["counts"]["fail"] == 1)          # 仅 44 字超限那条真实 FAIL

# ---------------- h. 封面候选 ----------------
cover_dup = TC.check_metadata(SCRIPT, meta(GOOD_CANDS, covers=[
    {"text": GOOD_CANDS[0]["text"][:12], "cover_title_pairing": "互补"}]))
bad_pair = TC.check_metadata(SCRIPT, meta(GOOD_CANDS, covers=[
    {"text": "完全不同的字样", "cover_title_pairing": "重复"}]))
check("h 封面与主标重复 ⇒ COVER_DUPLICATES_TITLE；pairing 非法 ⇒ COVER_PAIRING_INVALID",
      "COVER_DUPLICATES_TITLE" in [v["code"] for c in cover_dup["cover_texts"]
                                   for v in c["codes"]]
      and "COVER_PAIRING_INVALID" in [v["code"] for c in bad_pair["cover_texts"]
                                      for v in c["codes"]])
check("h2 合法封面（互补/递进/反差）⇒ PASS",
      all(c["status"] == "PASS" for c in rep["cover_texts"])
      and rep["counts"]["cover_pass"] == 1)

# ---------------- i. 确定性 ----------------
a = TC.check_metadata(SCRIPT, GOOD, source={"x": 1})
b = TC.check_metadata(SCRIPT, GOOD, source={"x": 2})
proj = lambda r: TC.canonical({k: v for k, v in r.items() if k != "source"})   # noqa: E731
check("i 确定性：同输入两次 ⇒ 判定内容逐字节一致，且 source 标签不参与哈希",
      proj(a) == proj(b) and a["artifact_hash"] == b["artifact_hash"])
env = {"PYTHONPATH": str(ROOT / "src"), **{k: v for k, v in __import__("os").environ.items()}}
out1 = subprocess.run([sys.executable, "run.py", "title-check", "--script",
                       "projects/p_96efdc03e1aa/artifacts/a_e0ec01d11b5a.json", "--metadata",
                       "docs/regression_2x/logs/phase8_ab_v3.json", "--json", "--no-timestamp"],
                      cwd=str(ROOT), capture_output=True, env=env).stdout
out2 = subprocess.run([sys.executable, "run.py", "title-check", "--script",
                       "projects/p_96efdc03e1aa/artifacts/a_e0ec01d11b5a.json", "--metadata",
                       "docs/regression_2x/logs/phase8_ab_v3.json", "--json", "--no-timestamp"],
                      cwd=str(ROOT), capture_output=True, env=env).stdout
check("i2 CLI `--json --no-timestamp` 两次运行逐字节一致（只读、键排序）",
      bool(out1) and out1 == out2)

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)

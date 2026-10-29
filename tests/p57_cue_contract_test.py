# -*- coding: utf-8 -*-
"""Phase 57 / P57-1：**生产 cue 契约回归**（before 夹具留档 + 封存检查 + 门拦截）。

授权书 §3：F10.1 的 105-cue-178s 签名**留档 tests**——作为「生产门必须拦下」的
before 夹具，永不过期。四部分：

  B1  F10.1 烧录 ASS 签名 = 留档值（105 条 / 跨度 178.26s / median 1.0s / max 58.63s）
      ——历史证据不可改写（append-only）；
  B2  **门拦截**：`production_cue_violations` 对 B1 签名**必须报违规**
      （count / median 两项即足以拦下）——否则门形同虚设；
  B3  **封存检查**：`EditingAgent._narration_args` 源码**不再调用**旧词级路径
      `build_cues_from_words(`（不保留双路径）；
  B4  门单元语义：空 cue / 1s 钳制 median / 重叠 / 条数越界 各自报对应违规。

运行: python tests/p57_cue_contract_test.py
"""
from __future__ import annotations

import inspect
import json
import pathlib
import re
import statistics
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
PASS, FAIL = [], []

# ---- before 夹具（F10.1 烧录 ASS 实测签名，2026-10 监理帧检 + ASS 转储）----
BEFORE_SIGNATURE = {
    "label": "F10.1 (t_158db818a8b3)",
    "cues": 105, "span_s": 178.26, "first_start": 0.1, "max_end": 178.36,
    "median_dur": 1.0, "max_dur": 58.63, "d_1s_clamped": 102,
}
F101_ASS = R / "projects" / "p_3e9292101f10" / "artifacts" / "_captions_t_158db818a8b3.ass"


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:300]))
    return bool(ok)


def parse_ass(p: pathlib.Path):
    rows = []
    for m in re.finditer(r"Dialogue: 0,([0-9:.]+),([0-9:.]+),", p.read_text(encoding="utf-8")):
        def sec(ts):
            h, mm, rest = ts.split(":")
            return int(h) * 3600 + int(mm) * 60 + float(rest)
        rows.append((sec(m.group(1)), sec(m.group(2))))
    return rows


def main() -> int:
    from video_studio.core.captions import (production_cue_violations, to_ass)
    from video_studio.agents.editing.agent import EditingAgent

    # ---- B1 before 夹具签名留档 ----
    if not F101_ASS.is_file():
        check("B1 F10.1 烧录 ASS 在档", False, str(F101_ASS))
        return finish()
    rows = parse_ass(F101_ASS)
    durs = [round(e - s, 3) for s, e in rows]
    sig = {"cues": len(rows),
           "span_s": round(max(e for _, e in rows) - min(s for s, _ in rows), 2),
           "first_start": round(min(s for s, _ in rows), 1),
           "max_end": round(max(e for _, e in rows), 2),
           "median_dur": round(statistics.median(durs), 1),
           "max_dur": round(max(durs), 2),
           "d_1s_clamped": sum(1 for d in durs if abs(d - 1.0) <= 0.1)}
    check("B1 F10.1 签名 == 留档值（append-only 证据）",
          all(abs(sig[k] - BEFORE_SIGNATURE[k]) < 0.11 for k in
              ("cues", "span_s", "first_start", "max_end", "median_dur", "max_dur",
               "d_1s_clamped")),
          {"measured": sig, "fixture": BEFORE_SIGNATURE})

    # ---- B2 门必须拦下 before 签名 ----
    cues_before = [{"start": s, "end": e, "dur": round(e - s, 3)} for s, e in rows]
    viol = production_cue_violations(cues_before, audio_dur_s=693.528)
    kinds = " ".join(viol)
    check("B2 生产门对 F10.1 签名报违规（count/median 至少其一）",
          bool(viol) and ("count_out_of_range" in kinds or "median_below_min" in kinds),
          {"violations": viol})

    # ---- B3 旧词级路径封存 ----
    src = inspect.getsource(EditingAgent._narration_args)
    check("B3 _narration_args 不再调用 build_cues_from_words(",
          "build_cues_from_words(" not in src)
    check("B3b _narration_args 仍调用 word_exact（生产路径在位）",
          "build_cues_from_words_exact(" in src and "production_cue_violations(" in src)

    # ---- B4 门单元语义 ----
    check("B4a 空 cue 报 cues_empty",
          production_cue_violations([]) == ["cues_empty"])
    one_s = [{"start": float(i), "end": float(i) + 1.0, "dur": 1.0} for i in range(120)]
    check("B4b 102×1.0s 钳制 ⇒ median_below_min",
          any(v.startswith("median_below_min")
              for v in production_cue_violations(one_s, count_range=(101, 111))))
    ovl = [{"start": 0.0, "end": 5.0, "dur": 5.0},
           {"start": 4.0, "end": 9.0, "dur": 5.0}]
    check("B4c 重叠 ⇒ overlap",
          any(v.startswith("overlap") for v in production_cue_violations(
              ovl, count_range=(2, 111))))
    good = [{"start": 0.1, "end": 6.1, "dur": 6.0},
            {"start": 6.1, "end": 12.1, "dur": 6.0}]
    check("B4d 契约内 cue ⇒ 无违规（除条数外）",
          [v for v in production_cue_violations(good, audio_dur_s=12.0,
                                                count_range=(2, 4))] == [])
    return finish()


def finish() -> int:
    print()
    print("=" * 74)
    print("p57_cue_contract_test: {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
    print("=" * 74)
    (R / "docs/regression_2x/logs/p57_cue_contract.json").write_text(
        json.dumps({"schema": "p57-1-cue-contract-test-v1",
                    "before_fixture": BEFORE_SIGNATURE,
                    "before_ass": str(F101_ASS.relative_to(R)),
                    "pass": len(PASS), "fail": len(FAIL)},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())

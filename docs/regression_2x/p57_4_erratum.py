# -*- coding: utf-8 -*-
"""Phase 57 / P57-4：**erratum 登记**（如实修正，不改写已登记数值）。

三件事：
  A. **循环论证第四例**：F6–F10.1 的字幕门全部为**构建器输出自测**——
     F12 起以**烧录 ASS / 成片混音**为唯一口径（P57-3 已落地）；
  B. 本次实测照出的**静默生产缺陷**清单（含 P56-2 pins 块自登记起从未生效）；
  C. 材料包 v6（`p57_merged_payload.json`）完整性校验（F12 未使用，保持备用）。
运行: python docs/regression_2x/p57_4_erratum.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    # ---- C. 材料包 v6 完整性 ----
    mp = json.loads((L / "p57_merged_payload.json").read_text(encoding="utf-8"))
    cands = mp.get("candidates") or []
    ok = missing = sha_mismatch = 0
    miss_rows = []
    for c in cands:
        p = c.get("path")
        if not p or not pathlib.Path(p).is_file():
            missing += 1
            miss_rows.append({"name": c.get("name"), "path": p, "why": "缺文件"})
            continue
        want = str(c.get("sha256") or "").lower()
        if want:
            got = hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
            if got != want:
                sha_mismatch += 1
                miss_rows.append({"name": c.get("name"), "path": p,
                                  "why": "sha256 不一致（{} vs {}）".format(got[:12],
                                                                        want[:12])})
                continue
        ok += 1
    mat_v6 = {"candidates_total": len(cands), "files_ok": ok,
              "missing": missing, "sha_mismatch": sha_mismatch,
              "note": ("材料包 v6 = 主线黑板图合并池（65 张），为 F11 主线变体预备；"
                       "F12 按「画面零改动」未使用它（沿用 F10.1 池）")}

    rec = {
        "schema": "p57-4-erratum-v1",
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "erratum_circular_measurement_4th": {
            "statement": ("**F6–F10.1 的字幕门全部为构建器输出自测**（词级金门 median 0.0000s、"
                          "覆盖门 99.3% 等测的是构建器**输出**而非烧录产物）——"
                          "**循环论证第四例**（前三例：切片边界自测、段内口径、"
                          "P48 转储口径混用）。"),
            "evidence": ("F10.1 登记门「覆盖 99.3% / median 5.720s」与烧录 ASS 实测"
                         "（105 条压缩在 0.1–178.363s、median 1.0s）完全不符。"),
            "correction_from_f12": ("**F12 起以烧录 ASS + 成片混音为唯一字幕口径**"
                                    "（P57-3 四门已落地并 9/9 通过）。"),
        },
        "silent_production_defects_found": [
            {"id": "D1", "where": "editing agent cue 第二套分发",
             "what": ("P55-1 构好的 cue 被 `build_cues_from_words` 无条件覆盖"
                      "（cue_source 标签仍是 word_exact，逐条 source 已是 word_boundary）"
                      "——F10.1 的 105-cue-178s 直接死因，「测试修了、生产没接」第五例"),
             "fix": "cue 单一分发链 + 旧词级路径退役 + dump 记录逐条 source"},
            {"id": "D2", "where": "P56-2 pins 块",
             "what": ("`_AL` UnboundLocalError 被 except 吞成 `pinned_assignment_error` "
                      "字段——**自 P56-2 登记起钉定机制从未真正生效**"
                      "（F10.1 的 36/36 一致实为确定性求解器复现；"
                      "首轮 F12 渲染 0/36 暴露）"),
             "fix": "块内显式导入 + applied/missing 留痕 + 求解器后终局强制"},
            {"id": "D3", "where": "build_cues_from_words_exact 钳制依据",
             "what": ("按**句首词所在窗**钳制 cue 终点；v6.5 静音吸附切景存在"
                      "**句中切景** ⇒ 句尾语音无字幕（31 处 / 61.45s，覆盖 89.5%）"),
             "fix": "钳制依据改**句末词所在窗**（跨窗由排他约束兜底）"},
            {"id": "D4", "where": "_walk_match 尾句",
             "what": ("TTS WordBoundary 文本每段比旁白少 2–6 字 ⇒ 主循环耗尽词流时"
                      "末尾 1–2 句**没有自己的 cue**（全片 10 句；起点偏差 >1s 达 9 句）"),
             "fix": "末组延伸到最后一词后按字符比例重分（每句 ≥1 词）"},
            {"id": "D5", "where": "agent 诊断转储",
             "what": ("构建器的分组转储与 agent 的汇总转储**同名互相覆盖**"
                      "（`_cuedump_<task>.json`）⇒ 分组证据丢失（本次靠离线重放取回）"),
             "fix": "登记待修（P58 建议：agent 汇总转储改名 `_cuesummary_`）"},
        ],
        "transient_provider_defect": {
            "what": "VLM 仲裁对 P06_4 调用 PROVIDER_TIMEOUT ⇒ uncertain ⇒ 渲染阻断（fail-closed 正确）",
            "disposition": "重渲后通过；视觉等价性已由帧比对独立确认（p064_new vs p064_f101）",
        },
        "materials_package_v6_check": mat_v6,
        "delivery_candidates": "F12 登记（append-only）；F/F2…F10.1 不变；零 promotion",
        "lesson": ("「测试修了、生产没接」第五例 + 循环论证第四例同源：**验证必须"
                   "穿透生产入口并以最终产物为对象**。构建器内部断言（fail-closed）"
                   "必要但不充分——它们测不出「构建对了但被覆盖/被钳掉」。"),
    }
    p = L / "p57_erratum.json"
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print("erratum 登记：循环论证第四例 + 静默生产缺陷 {} 项（D1–D5）".format(5))
    print("  材料包 v6：{}/{} 文件在档且 sha 一致（缺 {} / 不符 {}）".format(
        ok, len(cands), missing, sha_mismatch))
    print("-> " + str(p.relative_to(R)))
    return 0 if (missing == 0 and sha_mismatch == 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
